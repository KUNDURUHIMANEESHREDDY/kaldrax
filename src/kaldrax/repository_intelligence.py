"""Read-only repository structure, dependency, entry-point, and test intelligence.

Python files are parsed with the standard-library AST. Other supported languages use
bounded import/export recognizers; their results are useful navigation evidence, not
compiler-grade semantic analysis.
"""
from __future__ import annotations

import ast
import json
import os
import posixpath
import re
import tomllib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .workspace import RepositoryWorkspace


_LANGUAGE_BY_SUFFIX = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".cs": "C#", ".c": "C", ".h": "C/C++", ".cc": "C++", ".cpp": "C++",
    ".hh": "C++", ".hpp": "C++", ".html": "HTML", ".vue": "Vue",
    ".svelte": "Svelte", ".css": "CSS", ".scss": "SCSS",
    ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
}
_MANIFEST_NAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "pipfile",
    "package.json", "pnpm-workspace.yaml", "yarn.lock", "pnpm-lock.yaml", "bun.lock",
    "bun.lockb", "cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "makefile", "cmakelists.txt",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "tsconfig.json",
    "vite.config.js", "vite.config.ts", "webpack.config.js", "next.config.js",
    "next.config.ts", "next.config.mjs", "angular.json", "tauri.conf.json",
    "global.json", "packages.config", "justfile", "meson.build", "build.zig",
}
_EXTRA_EXCLUDED_DIRS = {
    "target", "vendor", "out", "bin", "obj", "pods", "deriveddata",
    ".idea", ".gradle", ".terraform", ".serverless", ".vercel", ".parcel-cache",
    ".svelte-kit", ".nuxt", ".output", ".angular", "storybook-static",
    "playwright-report", "test-results", "htmlcov", ".coverage",
}
_IMPORT_PATTERN = re.compile(
    r"""(?m)^\s*(?:import\s+(?:[^'"\n;]*?\s+from\s+)?|export\s+[^'"\n;]*?\s+from\s+)['"]([^'"]+)['"]"""
)
_REQUIRE_PATTERN = re.compile(r"""(?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_EXPORT_PATTERN = re.compile(
    r"\bexport\s+(?:(?:declare|default|abstract|async)\s+)*(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)"
)
_GO_EXPORT_PATTERN = re.compile(r"(?m)^\s*(?:func|type|var|const)\s+([A-Z][A-Za-z0-9_]*)")
_RUST_EXPORT_PATTERN = re.compile(r"\bpub\s+(?:async\s+)?(?:fn|struct|enum|trait|mod|type|const|static)\s+([A-Za-z_][A-Za-z0-9_]*)")
_JAVA_EXPORT_PATTERN = re.compile(r"\bpublic\s+(?:abstract\s+|final\s+|static\s+)*(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
_JAVA_IMPORT_PATTERN = re.compile(r"(?m)^\s*import\s+(?:static\s+)?([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)(?:\.\*)?\s*;?\s*$")


@dataclass
class RepositoryAnalysis:
    repository_name: str
    scanned_files: int
    omitted_files: int
    languages: list[dict[str, Any]]
    frameworks: list[str]
    build_systems: list[str]
    files: list[dict[str, Any]]
    dependencies: list[dict[str, str]]
    entry_points: list[dict[str, str]]
    test_files: list[str]
    affected_components: dict[str, list[str]] = field(default_factory=dict)
    relevant_tests: dict[str, list[str]] = field(default_factory=dict)
    circular_dependencies: list[list[str]] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt(self) -> dict[str, Any]:
        """Return a compact structural brief suitable for bounded model context."""
        return {
            "repository_name": self.repository_name,
            "scanned_files": self.scanned_files,
            "omitted_files": self.omitted_files,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "build_systems": self.build_systems,
            "entry_points": self.entry_points[:80],
            "test_files": self.test_files[:160],
            "files": [
                {
                    "path": item["path"],
                    "language": item["language"],
                    "imports": item["imports"],
                    "exports": item["exports"],
                    "is_test": item["is_test"],
                    "is_entry_point": item["is_entry_point"],
                }
                for item in self.files[:400]
            ],
            "dependencies": self.dependencies[:1200],
            "circular_dependencies": self.circular_dependencies[:100],
            "affected_components": self.affected_components,
            "relevant_tests": self.relevant_tests,
            "changed_paths": self.changed_paths,
            "warnings": self.warnings,
            "analysis_note": (
                "Python imports are AST-derived. Other language imports/exports use bounded "
                "syntax recognizers; unresolved external imports are not graph edges. Omitted "
                "files are not represented and must not be assumed to have been inspected."
            ),
        }


class RepositoryIntelligenceAnalyzer:
    """Analyze a local Git checkout without requiring a clean working tree."""

    MAX_FILES = 750
    MAX_FILE_BYTES = 300_000
    MAX_TOTAL_BYTES = 14_000_000

    def __init__(self, root: Path | str) -> None:
        self.workspace = RepositoryWorkspace(root)
        self.root = self.workspace.root
        self.warnings: list[str] = []

    @staticmethod
    def _is_test(path: str, content: str, language: str) -> bool:
        parts = {part.casefold() for part in PurePosixPath(path).parts}
        name = PurePosixPath(path).name.casefold()
        if parts.intersection({"test", "tests", "__tests__", "spec", "specs"}):
            return True
        if (
            name.startswith("test_") or name.endswith("_test.py")
            or ".test." in name or ".spec." in name
        ):
            return True
        if language == "Go" and name.endswith("_test.go"):
            return True
        if language == "Rust" and "#[cfg(test)]" in content:
            return True
        return False

    @staticmethod
    def _module_names(path: str) -> set[str]:
        pure = PurePosixPath(path)
        if pure.suffix.casefold() not in {".py", ".pyi"}:
            return set()
        parts = list(pure.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        names = {".".join(parts)} if parts else set()
        for prefix in ("src", "lib", "app", "python"):
            if parts and parts[0] == prefix and len(parts) > 1:
                names.add(".".join(parts[1:]))
        return {name for name in names if name}

    @staticmethod
    def _python_imports(content: str, path: str) -> tuple[list[dict[str, Any]], list[str], bool]:
        try:
            tree = ast.parse(content, filename=path)
        except (SyntaxError, ValueError, TypeError):
            return [], [], False
        imports: list[dict[str, Any]] = []
        exports: list[str] = []
        explicit_exports: list[str] | None = None
        entry = False
        module_parts = list(PurePosixPath(path).with_suffix("").parts)
        if module_parts and module_parts[-1] == "__init__":
            package_parts = module_parts[:-1]
        else:
            package_parts = module_parts[:-1]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend({
                    "module": alias.name, "line": node.lineno, "kind": "import",
                } for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    base = package_parts[: max(0, len(package_parts) - node.level + 1)]
                    module = ".".join([*base, module] if module else base)
                if module:
                    imports.append({
                        "module": module, "line": node.lineno, "kind": "from",
                        "names": [alias.name for alias in node.names],
                    })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_") and node in tree.body:
                    exports.append(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node in tree.body:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        if target.id == "__all__":
                            value = node.value
                            try:
                                parsed = ast.literal_eval(value)
                                if isinstance(parsed, (list, tuple)) and all(isinstance(x, str) for x in parsed):
                                    explicit_exports = list(parsed)
                            except (ValueError, TypeError):
                                pass
                        elif not target.id.startswith("_"):
                            exports.append(target.id)
            elif isinstance(node, ast.If):
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name) and test.left.id == "__name__"
                    and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Eq, ast.Is))
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value == "__main__"
                ):
                    entry = True
        return imports, sorted(set(explicit_exports if explicit_exports is not None else exports)), entry

    @staticmethod
    def _regex_imports(content: str, language: str) -> tuple[list[dict[str, Any]], list[str], bool]:
        imports: list[dict[str, Any]] = []
        exports: set[str] = set()
        entry = False
        if language in {"JavaScript", "TypeScript"}:
            for match in _IMPORT_PATTERN.finditer(content):
                imports.append({"module": match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "es"})
            for match in _REQUIRE_PATTERN.finditer(content):
                imports.append({"module": match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "dynamic"})
            exports.update(_JS_EXPORT_PATTERN.findall(content))
            for group in re.findall(r"\bexport\s*\{([^}]+)\}", content):
                for item in group.split(","):
                    name = item.strip().split(" as ", 1)[0].strip()
                    if name:
                        exports.add(name)
            if re.search(r"\bexport\s+default\b", content):
                exports.add("default")
            if re.search(r"\b(?:function\s+)?main\s*\(", content):
                entry = True
        elif language == "Go":
            block_matches = re.findall(r"(?ms)^\s*import\s*\((.*?)\)", content)
            for block in block_matches:
                for spec in re.findall(r'"([^"]+)"', block):
                    imports.append({"module": spec, "line": content.count("\n", 0, content.find(block)), "kind": "go"})
            for match in re.finditer(r'(?m)^\s*import\s+(?:[A-Za-z_.][\w.]*\s+)?\"([^\"]+)\"', content):
                imports.append({"module": match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "go"})
            exports.update(_GO_EXPORT_PATTERN.findall(content))
            entry = bool(re.search(r"(?m)^\s*package\s+main\b", content) and re.search(r"(?m)^\s*func\s+main\s*\(", content))
        elif language == "Rust":
            for match in re.finditer(r"(?m)^\s*use\s+([^;]+);", content):
                imports.append({"module": match.group(1).strip(), "line": content.count("\n", 0, match.start()) + 1, "kind": "rust"})
            for match in re.finditer(r"(?m)^\s*mod\s+([A-Za-z_][\w]*)\s*;", content):
                imports.append({"module": "mod:" + match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "rust-mod"})
            exports.update(_RUST_EXPORT_PATTERN.findall(content))
            entry = bool(re.search(r"\bfn\s+main\s*\(", content))
        elif language in {"Java", "Kotlin"}:
            for match in _JAVA_IMPORT_PATTERN.finditer(content):
                imports.append({"module": match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "java"})
            exports.update(_JAVA_EXPORT_PATTERN.findall(content))
            entry = bool(re.search(r"\bstatic\s+void\s+main\s*\(", content) or re.search(r"\bfun\s+main\s*\(", content))
        elif language == "C#":
            for match in re.finditer(r"(?m)^\s*using\s+([A-Za-z_][\w.]*)\s*;", content):
                imports.append({"module": match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "using"})
            exports.update(re.findall(r"\bpublic\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*(?:class|interface|record|enum)\s+([A-Za-z_]\w*)", content))
            entry = bool(re.search(r"\bstatic\s+(?:async\s+)?(?:Task(?:<[^>]+>)?|void|int)\s+Main\s*\(", content))
        elif language in {"C", "C/C++", "C++"}:
            for match in re.finditer(r'(?m)^\s*#\s*include\s+"([^"]+)"', content):
                imports.append({"module": match.group(1), "line": content.count("\n", 0, match.start()) + 1, "kind": "include"})
            declarations = re.findall(
                r"(?m)^(?!\s*static\b)\s*(?:extern\s+)?[A-Za-z_][\w\s:*&<>]*?\s+([A-Za-z_]\w*)\s*\(",
                content,
            )
            exports.update(name for name in declarations if name not in {"if", "while", "switch", "for"})
            entry = bool(re.search(r"(?m)^\s*(?:int|void)\s+main\s*\(", content))
        return imports, sorted(exports), entry

    def _scan(self) -> tuple[dict[str, str], dict[str, str], int]:
        contents: dict[str, str] = {}
        languages: dict[str, str] = {}
        omitted = 0
        total = 0
        excluded = RepositoryWorkspace.EXCLUDED_DIRS | _EXTRA_EXCLUDED_DIRS
        for current, dirs, names in os.walk(self.root, followlinks=False):
            current_path = Path(current)
            kept: list[str] = []
            for name in dirs:
                child = current_path / name
                rel = child.relative_to(self.root).as_posix()
                if name.casefold() in excluded or child.is_symlink():
                    omitted += 1
                else:
                    kept.append(name)
            dirs[:] = sorted(kept, key=str.casefold)
            for name in sorted(names, key=str.casefold):
                path = current_path / name
                relative = path.relative_to(self.root).as_posix()
                if path.is_symlink() or not path.is_file() or RepositoryWorkspace._is_private(relative):
                    omitted += 1
                    continue
                suffix = path.suffix.casefold()
                language = _LANGUAGE_BY_SUFFIX.get(suffix)
                is_manifest = (
                    name.casefold() in _MANIFEST_NAMES
                    or name.casefold().startswith("requirements")
                    or suffix in {".csproj", ".sln", ".slnx"}
                )
                if language is None and not is_manifest:
                    continue
                try:
                    size = path.stat().st_size
                    if size > self.MAX_FILE_BYTES or total + size > self.MAX_TOTAL_BYTES:
                        omitted += 1
                        continue
                    raw = path.read_bytes()
                    content = raw.decode("utf-8")
                except (OSError, UnicodeDecodeError):
                    omitted += 1
                    continue
                if len(contents) >= self.MAX_FILES:
                    omitted += 1
                    continue
                contents[relative] = content
                if language:
                    languages[relative] = language
                total += size
        if omitted:
            self.warnings.append(f"{omitted} files or directories were omitted by safety, type, or scan limits.")
        return contents, languages, omitted

    @staticmethod
    def _json_manifest(contents: dict[str, str], name: str) -> dict[str, Any]:
        for path, content in contents.items():
            if PurePosixPath(path).name.casefold() == name.casefold():
                try:
                    payload = json.loads(content)
                    return payload if isinstance(payload, dict) else {}
                except (json.JSONDecodeError, TypeError):
                    return {}
        return {}

    @staticmethod
    def _toml_manifest(contents: dict[str, str], name: str) -> dict[str, Any]:
        for path, content in contents.items():
            if PurePosixPath(path).name.casefold() == name.casefold():
                try:
                    payload = tomllib.loads(content)
                    return payload if isinstance(payload, dict) else {}
                except (tomllib.TOMLDecodeError, TypeError):
                    return {}
        return {}

    def _detect_stack(self, contents: dict[str, str]) -> tuple[list[str], list[str], dict[str, Any]]:
        frameworks: set[str] = set()
        builds: set[str] = set()
        metadata: dict[str, Any] = {}
        names = {PurePosixPath(path).name.casefold() for path in contents}
        pyproject = self._toml_manifest(contents, "pyproject.toml")
        package = self._json_manifest(contents, "package.json")
        cargo = self._toml_manifest(contents, "Cargo.toml")
        go_mod = next((text for path, text in contents.items() if PurePosixPath(path).name.casefold() == "go.mod"), "")
        py_deps: set[str] = set()
        project = pyproject.get("project", {})
        if isinstance(project, dict):
            py_deps.update(str(item).split("[", 1)[0].split(">", 1)[0].split("=", 1)[0].split("<", 1)[0].strip().casefold().replace("_", "-") for item in project.get("dependencies", []) if isinstance(item, str))
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for values in optional.values():
                    if isinstance(values, list):
                        py_deps.update(str(item).split("[", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().casefold().replace("_", "-") for item in values)
        tool = pyproject.get("tool", {})
        if isinstance(tool, dict):
            poetry = tool.get("poetry", {})
            if isinstance(poetry, dict) and isinstance(poetry.get("dependencies"), dict):
                py_deps.update(str(item).casefold().replace("_", "-") for item in poetry["dependencies"])
        for path, content in contents.items():
            leaf = PurePosixPath(path).name.casefold()
            if leaf.startswith("requirements") and leaf.endswith(".txt"):
                for line in content.splitlines():
                    item = re.match(r"\s*([A-Za-z0-9_.-]+)", line)
                    if item and not line.lstrip().startswith(("#", "-")):
                        py_deps.add(item.group(1).casefold().replace("_", "-"))
        for package_name, framework in {
            "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
            "starlette": "Starlette", "streamlit": "Streamlit",
            "pytest": "pytest", "pydantic": "Pydantic", "sqlalchemy": "SQLAlchemy",
            "celery": "Celery", "gradio": "Gradio", "litestar": "Litestar",
        }.items():
            if package_name in py_deps:
                frameworks.add(framework)
        if "pyproject.toml" in names:
            builds.add("Python project (pyproject.toml)")
            build_system = pyproject.get("build-system", {})
            if isinstance(build_system, dict):
                backend = str(build_system.get("build-backend", "")).casefold()
                for marker, label in (("setuptools", "setuptools"), ("hatchling", "Hatch"), ("poetry", "Poetry"), ("flit", "Flit"), ("pdm", "PDM"), ("uv", "uv")):
                    if marker in backend:
                        builds.add(label)
        if "setup.py" in names or "setup.cfg" in names:
            builds.add("setuptools")
        if "pipfile" in names:
            builds.add("Pipenv")
        if "requirements.txt" in names or any(name.startswith("requirements") for name in names):
            builds.add("pip requirements")

        js_deps: set[str] = set()
        for field_name in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            section = package.get(field_name, {})
            if isinstance(section, dict):
                js_deps.update(str(key).casefold() for key in section)
        for package_name, framework in {
            "react": "React", "next": "Next.js", "vue": "Vue", "@angular/core": "Angular",
            "svelte": "Svelte", "express": "Express", "fastify": "Fastify",
            "@nestjs/core": "NestJS", "hono": "Hono", "electron": "Electron",
            "@tauri-apps/api": "Tauri", "astro": "Astro", "nuxt": "Nuxt",
            "remix": "Remix", "prisma": "Prisma", "tailwindcss": "Tailwind CSS",
        }.items():
            if package_name in js_deps:
                frameworks.add(framework)
        if "package.json" in names:
            builds.add("Node.js package")
            if "pnpm-workspace.yaml" in names or "pnpm-lock.yaml" in names:
                builds.add("pnpm")
            elif "yarn.lock" in names:
                builds.add("Yarn")
            elif "bun.lock" in names or "bun.lockb" in names:
                builds.add("Bun")
            else:
                builds.add("npm")
            if any(name.startswith("vite.config.") for name in names):
                builds.add("Vite")
            if any(name.startswith("webpack.config.") for name in names):
                builds.add("Webpack")
            if any(name.startswith("next.config.") for name in names):
                builds.add("Next.js build")
            metadata["package"] = {
                key: package.get(key) for key in ("name", "main", "module", "browser", "bin", "scripts")
                if key in package
            }
        if "angular.json" in names:
            frameworks.add("Angular")
        if any(name.startswith("vite.config.") for name in names):
            builds.add("Vite")
        if "cargo.toml" in names:
            builds.add("Cargo")
            deps = cargo.get("dependencies", {})
            if isinstance(deps, dict):
                for key, framework in {
                    "tauri": "Tauri", "axum": "Axum", "actix-web": "Actix Web",
                    "rocket": "Rocket", "warp": "Warp", "tokio": "Tokio",
                    "bevy": "Bevy",
                }.items():
                    if key in deps:
                        frameworks.add(framework)
        if "go.mod" in names:
            builds.add("Go modules")
            for module, framework in {
                "github.com/gin-gonic/gin": "Gin", "github.com/labstack/echo": "Echo",
                "github.com/gofiber/fiber": "Fiber", "github.com/go-chi/chi": "Chi",
                "github.com/gorilla/mux": "Gorilla Mux",
            }.items():
                if module in go_mod:
                    frameworks.add(framework)
        if "pom.xml" in names:
            builds.add("Maven")
            pom = next((text for path, text in contents.items() if PurePosixPath(path).name.casefold() == "pom.xml"), "")
            if "spring-boot" in pom.casefold():
                frameworks.add("Spring Boot")
        if any(name.startswith("build.gradle") for name in names) or any(name.startswith("settings.gradle") for name in names):
            builds.add("Gradle")
            gradle = "\n".join(text for path, text in contents.items() if PurePosixPath(path).name.casefold().startswith("build.gradle")).casefold()
            if "com.android.application" in gradle or "com.android.library" in gradle:
                frameworks.add("Android")
            if "org.springframework.boot" in gradle:
                frameworks.add("Spring Boot")
        if any(name.endswith(".csproj") for name in names) or any(name.endswith(".sln") for name in names):
            builds.add(".NET SDK")
            if any("Microsoft.NET.Sdk.Web" in text for path, text in contents.items() if path.casefold().endswith(".csproj")):
                frameworks.add("ASP.NET Core")
        if "makefile" in names:
            builds.add("Make")
        if "cmakelists.txt" in names:
            builds.add("CMake")
        if any(name.startswith("dockerfile") for name in names) or "docker-compose.yml" in names or "docker-compose.yaml" in names:
            builds.add("Docker")
        if "justfile" in names:
            builds.add("just")
        if "meson.build" in names:
            builds.add("Meson")
        if "build.zig" in names:
            builds.add("Zig build")
        if {"module.bazel", "workspace", "workspace.bazel", "build", "build.bazel"} & names:
            builds.add("Bazel")
        return sorted(frameworks), sorted(builds), metadata

    @staticmethod
    def _resolve_python(module: str, module_map: dict[str, set[str]], from_names: list[str] | None = None) -> list[str]:
        if from_names:
            submodules = {
                target
                for name in from_names
                for target in module_map.get(f"{module}.{name}", set())
            }
            if submodules:
                return sorted(submodules)
        return sorted(module_map.get(module, set()))

    @staticmethod
    def _resolve_js(specifier: str, source_path: str, known: set[str], aliases: list[tuple[str, str]]) -> list[str]:
        alias_resolved = False
        if specifier.startswith(("@/", "~/")):
            for prefix, target in aliases:
                normalized_prefix = prefix.replace("*", "")
                if specifier.startswith(normalized_prefix):
                    suffix = specifier[len(normalized_prefix):].lstrip("/")
                    specifier = target.rstrip("/") + ("/" + suffix if suffix else "")
                    alias_resolved = True
                    break
            else:
                return []
        elif not specifier.startswith((".", "/")):
            return []
        if specifier.startswith("/") or alias_resolved:
            base = specifier.lstrip("/")
        else:
            base = (PurePosixPath(source_path).parent / specifier).as_posix()
        normalized = posixpath.normpath(base)
        if normalized.startswith("../") or normalized == "..":
            return []
        suffixes = (".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".json", ".css")
        candidates = {normalized + suffix for suffix in suffixes}
        candidates.update(f"{normalized}/index{suffix}" for suffix in suffixes)
        candidates.add(normalized + "/index")
        if PurePosixPath(normalized).suffix:
            candidates.add(normalized)
        return sorted(path for path in candidates if path in known)

    @staticmethod
    def _cycle_components(nodes: set[str], adjacency: dict[str, set[str]]) -> list[list[str]]:
        index = 0
        stack: list[str] = []
        on_stack: set[str] = set()
        indices: dict[str, int] = {}
        low: dict[str, int] = {}
        cycles: list[list[str]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = low[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for target in sorted(adjacency.get(node, set())):
                if target not in indices:
                    visit(target)
                    low[node] = min(low[node], low[target])
                elif target in on_stack:
                    low[node] = min(low[node], indices[target])
            if low[node] == indices[node]:
                component: list[str] = []
                while stack:
                    current = stack.pop()
                    on_stack.remove(current)
                    component.append(current)
                    if current == node:
                        break
                if len(component) > 1 or node in adjacency.get(node, set()):
                    cycles.append(sorted(component))

        for node in sorted(nodes):
            if node not in indices:
                visit(node)
        return sorted(cycles, key=lambda item: (len(item), item))

    def analyze(self, *, changed_paths: tuple[str, ...] | list[str] = ()) -> RepositoryAnalysis:
        self.warnings = []
        contents, language_by_path, omitted = self._scan()
        frameworks, build_systems, metadata = self._detect_stack(contents)
        known_paths = set(contents)
        module_map: dict[str, set[str]] = defaultdict(set)
        java_map: dict[str, set[str]] = defaultdict(set)
        go_dirs: dict[str, set[str]] = defaultdict(set)
        for path, language in language_by_path.items():
            if language == "Python":
                for module in self._module_names(path):
                    module_map[module].add(path)
            elif language in {"Java", "Kotlin"}:
                content = contents[path]
                package = re.search(r"(?m)^\s*package\s+([\w.]+)\s*;?", content)
                classes = re.findall(r"\b(?:class|interface|enum|record|object)\s+([A-Za-z_$][\w$]*)", content)
                prefix = package.group(1) + "." if package else ""
                for name in classes:
                    java_map[prefix + name].add(path)
            elif language == "Go":
                parent = PurePosixPath(path).parent.as_posix()
                go_dirs[parent].add(path)

        tsconfig = self._json_manifest(contents, "tsconfig.json")
        compiler = tsconfig.get("compilerOptions", {}) if isinstance(tsconfig, dict) else {}
        aliases: list[tuple[str, str]] = []
        if isinstance(compiler, dict):
            base_url = str(compiler.get("baseUrl", "")).strip("./")
            paths = compiler.get("paths", {})
            if isinstance(paths, dict):
                for alias, targets in paths.items():
                    if isinstance(targets, list):
                        for target in targets:
                            if isinstance(target, str):
                                prefix = str(alias).replace("*", "")
                                destination = str(target).replace("*", "")
                                aliases.append((prefix, (PurePosixPath(base_url) / destination).as_posix() if base_url else destination))

        go_module = ""
        for path, content in contents.items():
            if PurePosixPath(path).name.casefold() == "go.mod":
                match = re.search(r"(?m)^\s*module\s+(\S+)", content)
                go_module = match.group(1).rstrip("/") if match else ""

        files: list[dict[str, Any]] = []
        raw_imports: dict[str, list[dict[str, Any]]] = {}
        entry_points: list[dict[str, str]] = []
        for path, language in sorted(language_by_path.items()):
            content = contents[path]
            if language == "Python":
                imports, exports, has_main = self._python_imports(content, path)
                is_entry = has_main or PurePosixPath(path).name == "__main__.py"
                for item in imports:
                    item["targets"] = self._resolve_python(
                        item["module"], module_map, item.get("names") if item["kind"] == "from" else None,
                    )
            else:
                imports, exports, has_main = self._regex_imports(content, language)
                is_entry = has_main
                for item in imports:
                    module = item["module"]
                    targets: list[str] = []
                    if language in {"JavaScript", "TypeScript"}:
                        targets = self._resolve_js(module, path, known_paths, aliases)
                    elif language in {"Java", "Kotlin"}:
                        targets = sorted(java_map.get(module, set()))
                    elif language in {"C", "C/C++", "C++"} and item["kind"] == "include":
                        parent = PurePosixPath(path).parent
                        candidates = (
                            (parent / module).as_posix(),
                            PurePosixPath(module).as_posix(),
                        )
                        targets = [candidate for candidate in candidates if candidate in known_paths]
                    elif language == "Go" and go_module and module.startswith(go_module + "/"):
                        directory = module[len(go_module):].strip("/").replace("/", "/")
                        targets = sorted(go_dirs.get(directory, set()))
                    elif language == "Rust":
                        if module.startswith("mod:"):
                            name = module[4:]
                            parent = PurePosixPath(path).parent
                            targets = [
                                candidate for candidate in (
                                    (parent / f"{name}.rs").as_posix(),
                                    (parent / name / "mod.rs").as_posix(),
                                    (parent / name / "lib.rs").as_posix(),
                                ) if candidate in known_paths
                            ]
                        elif module.startswith("crate::"):
                            parts = module.split("::")
                            if len(parts) > 1:
                                name = parts[1]
                                for prefix in ("src",):
                                    for candidate in (f"{prefix}/{name}.rs", f"{prefix}/{name}/mod.rs"):
                                        if candidate in known_paths:
                                            targets.append(candidate)
                    item["targets"] = sorted(set(targets))
            raw_imports[path] = imports
            is_test = self._is_test(path, content, language)
            conventional_entry = (
                PurePosixPath(path).name.casefold() in {"main.py", "app.py", "manage.py", "main.js", "main.ts", "index.js", "index.ts"}
                and not is_test
            )
            is_entry = is_entry or conventional_entry
            if is_entry:
                entry_points.append({"path": path, "kind": language, "reason": "language entry-point syntax or conventional entry filename"})
            files.append({
                "path": path,
                "language": language,
                "imports": imports,
                "exports": exports,
                "is_test": is_test,
                "is_entry_point": is_entry,
            })

        # Package metadata declares executable entry points and Python console scripts.
        package_meta = metadata.get("package", {})
        if isinstance(package_meta, dict):
            for field_name in ("main", "module", "browser"):
                value = package_meta.get(field_name)
                if isinstance(value, str):
                    target = value.lstrip("./")
                    if target in known_paths:
                        entry_points.append({"path": target, "kind": "JavaScript", "reason": f"package.json {field_name}"})
            bin_value = package_meta.get("bin")
            bins = bin_value.values() if isinstance(bin_value, dict) else ([bin_value] if isinstance(bin_value, str) else [])
            for value in bins:
                if isinstance(value, str) and value.lstrip("./") in known_paths:
                    entry_points.append({"path": value.lstrip("./"), "kind": "JavaScript", "reason": "package.json bin"})
        pyproject = self._toml_manifest(contents, "pyproject.toml")
        scripts = pyproject.get("project", {}).get("scripts", {}) if isinstance(pyproject.get("project", {}), dict) else {}
        if isinstance(scripts, dict):
            for command, target in scripts.items():
                if isinstance(target, str):
                    module = target.split(":", 1)[0].strip()
                    resolved = self._resolve_python(module, module_map)
                    entry_points.extend({"path": path, "kind": "Python", "reason": f"console script {command}"} for path in resolved)
        if "index.html" in known_paths:
            entry_points.append({"path": "index.html", "kind": "HTML", "reason": "web document entry"})
        entry_points = sorted(
            { (item["path"], item["kind"], item["reason"]): item for item in entry_points }.values(),
            key=lambda item: item["path"].casefold(),
        )

        dependencies: list[dict[str, str]] = []
        adjacency: dict[str, set[str]] = defaultdict(set)
        reverse: dict[str, set[str]] = defaultdict(set)
        for source, imports in raw_imports.items():
            for item in imports:
                for target in item.get("targets", []):
                    adjacency[source].add(target)
                    reverse[target].add(source)
                    dependencies.append({
                        "source": source, "target": target,
                        "module": str(item["module"]), "kind": str(item["kind"]),
                    })
        dependencies.sort(key=lambda item: (item["source"], item["target"], item["module"]))

        normalized_change_set: set[str] = set()
        for path in changed_paths:
            raw_path = str(path).replace("\\", "/").strip()
            if not raw_path:
                continue
            normalized = posixpath.normpath(raw_path)
            if normalized in {"", ".", ".."} or normalized.startswith(("../", "/")) or ":" in normalized:
                self.warnings.append(f"Ignored unsafe changed path: {raw_path[:160]}")
                continue
            normalized_change_set.add(normalized)
        normalized_changes = sorted(normalized_change_set)
        affected: dict[str, list[str]] = {}
        relevant_tests: dict[str, list[str]] = {}
        test_paths = sorted(item["path"] for item in files if item["is_test"])
        for changed in normalized_changes:
            affected_set = {changed}
            pending = [changed]
            while pending:
                current = pending.pop()
                for dependent in reverse.get(current, set()):
                    if dependent not in affected_set:
                        affected_set.add(dependent)
                        pending.append(dependent)
            affected[changed] = sorted(affected_set)
            tests = {path for path in affected_set if path in test_paths}
            stem = PurePosixPath(changed).stem.casefold()
            for test_path in test_paths:
                test_name = PurePosixPath(test_path).name.casefold()
                if stem and (
                    test_name in {f"test_{stem}.py", f"{stem}_test.py", f"{stem}.test.js",
                                  f"{stem}.test.ts", f"{stem}.spec.js", f"{stem}.spec.ts"}
                    or stem in PurePosixPath(test_path).parts
                ):
                    tests.add(test_path)
            relevant_tests[changed] = sorted(tests)

        language_counts: dict[str, int] = defaultdict(int)
        for language in language_by_path.values():
            language_counts[language] += 1
        total_source_files = max(1, len(language_by_path))
        languages = [
            {"name": language, "files": count, "percentage": round(count * 100 / total_source_files, 1)}
            for language, count in sorted(language_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        tests = sorted(item["path"] for item in files if item["is_test"])
        if not dependencies:
            self.warnings.append("No local source-to-source dependencies were resolved; external imports are intentionally omitted.")
        return RepositoryAnalysis(
            repository_name=self.root.name,
            scanned_files=len(contents),
            omitted_files=omitted,
            languages=languages,
            frameworks=frameworks,
            build_systems=build_systems,
            files=files,
            dependencies=dependencies,
            entry_points=entry_points,
            test_files=tests,
            affected_components=affected,
            relevant_tests=relevant_tests,
            circular_dependencies=self._cycle_components(set(language_by_path), adjacency),
            changed_paths=normalized_changes,
            warnings=sorted(set(self.warnings)),
        )


def analyze_repository(
    root: Path | str,
    *,
    changed_paths: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Convenience API returning a JSON-serializable repository intelligence report."""
    return RepositoryIntelligenceAnalyzer(root).analyze(changed_paths=changed_paths).to_dict()
