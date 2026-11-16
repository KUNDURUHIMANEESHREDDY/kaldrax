import json
import subprocess

from kaldrax.repository_intelligence import RepositoryIntelligenceAnalyzer


def init_repo(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "KALDRAX Tests"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--all"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
    return root


def test_python_ast_imports_exports_cycles_and_transitive_affected_tests(tmp_path):
    root = init_repo(tmp_path / "repo", {
        "pyproject.toml": (
            "[build-system]\nrequires = ['setuptools']\n"
            "build-backend = 'setuptools.build_meta'\n"
            "[project]\nname = 'sample'\ndependencies = ['fastapi>=0.100']\n"
        ),
        "src/pkg/__init__.py": "from .core import public_api\n__all__ = ['public_api']\n",
        "src/pkg/core.py": (
            "from .helper import normalize\n"
            "def public_api(value):\n    return normalize(value)\n"
            "def _private():\n    return None\n"
        ),
        "src/pkg/helper.py": "def normalize(value):\n    return str(value).strip()\n",
        "src/pkg/alpha.py": "from . import beta\n\ndef alpha(): return beta.beta()\n",
        "src/pkg/beta.py": "from . import alpha\n\ndef beta(): return alpha.alpha()\n",
        "src/pkg/__main__.py": "from .core import public_api\nif __name__ == '__main__':\n    print(public_api('x'))\n",
        "tests/test_core.py": "from pkg.core import public_api\n\ndef test_public_api(): assert public_api(' x ') == 'x'\n",
        ".env": "API_KEY=must-not-be-read\n",
        "node_modules/dependency/index.js": "module.exports = 1;\n",
    })
    # Dirty worktrees are intentionally analyzable; no files are changed by analysis.
    (root / "src/pkg/helper.py").write_text(
        "def normalize(value):\n    return str(value).strip().lower()\n",
        encoding="utf-8",
    )

    report = RepositoryIntelligenceAnalyzer(root).analyze(changed_paths=["src/pkg/helper.py"])
    files = {item["path"]: item for item in report.files}
    edges = {(item["source"], item["target"]) for item in report.dependencies}

    assert "FastAPI" in report.frameworks
    assert "setuptools" in report.build_systems
    assert files["src/pkg/core.py"]["imports"][0]["module"] == "src.pkg.helper"
    assert "public_api" in files["src/pkg/core.py"]["exports"]
    assert "_private" not in files["src/pkg/core.py"]["exports"]
    assert ("src/pkg/core.py", "src/pkg/helper.py") in edges
    assert report.affected_components["src/pkg/helper.py"] == [
        "src/pkg/__init__.py", "src/pkg/__main__.py", "src/pkg/core.py",
        "src/pkg/helper.py", "tests/test_core.py",
    ]
    assert report.relevant_tests["src/pkg/helper.py"] == ["tests/test_core.py"]
    assert ["src/pkg/alpha.py", "src/pkg/beta.py"] in report.circular_dependencies
    assert any(item["path"] == "src/pkg/__main__.py" for item in report.entry_points)
    assert ".env" not in files
    assert "node_modules/dependency/index.js" not in files


def test_javascript_typescript_resolution_aliases_exports_and_stack_detection(tmp_path):
    root = init_repo(tmp_path / "frontend", {
        "package.json": json.dumps({
            "name": "web",
            "main": "src/main.tsx",
            "dependencies": {"react": "^19.0.0", "vite": "^6.0.0"},
            "scripts": {"dev": "vite"},
        }),
        "vite.config.ts": "export default {};",
        "tsconfig.json": json.dumps({
            "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}
        }),
        "src/main.tsx": "import { renderApp } from '@/app';\nexport const start = renderApp;\n",
        "src/app.tsx": "import { Button } from './components/Button';\nexport function renderApp() { return Button; }\n",
        "src/components/Button.tsx": "export const Button = () => null;\n",
        "tests/app.test.tsx": "import { renderApp } from '../src/app';\n",
    })
    report = RepositoryIntelligenceAnalyzer(root).analyze(changed_paths=["src/components/Button.tsx"])
    files = {item["path"]: item for item in report.files}
    edges = {(item["source"], item["target"]) for item in report.dependencies}

    assert "React" in report.frameworks
    assert "npm" in report.build_systems
    assert "Vite" in report.build_systems
    assert files["src/main.tsx"]["exports"] == ["start"]
    assert ("src/main.tsx", "src/app.tsx") in edges
    assert ("src/app.tsx", "src/components/Button.tsx") in edges
    assert report.affected_components["src/components/Button.tsx"] == [
        "src/app.tsx", "src/components/Button.tsx", "src/main.tsx", "tests/app.test.tsx",
    ]
    assert report.relevant_tests["src/components/Button.tsx"] == ["tests/app.test.tsx"]
    assert any(item["path"] == "src/main.tsx" for item in report.entry_points)


def test_go_and_rust_imports_and_entry_points_are_discovered(tmp_path):
    root = init_repo(tmp_path / "systems", {
        "go.mod": "module example.com/service\n\ngo 1.22\n",
        "cmd/server/main.go": (
            "package main\nimport \"example.com/service/internal/app\"\n"
            "func main() { app.Run() }\n"
        ),
        "internal/app/app.go": "package app\nfunc Run() {}\n",
        "src/main.rs": "mod engine;\nfn main() { engine::run(); }\n",
        "src/engine.rs": "pub fn run() {}\n",
    })
    report = RepositoryIntelligenceAnalyzer(root).analyze()
    edges = {(item["source"], item["target"]) for item in report.dependencies}

    assert "Go modules" in report.build_systems
    assert ("cmd/server/main.go", "internal/app/app.go") in edges
    assert ("src/main.rs", "src/engine.rs") in edges
    assert any(item["path"] == "cmd/server/main.go" for item in report.entry_points)
    assert any(item["path"] == "src/main.rs" for item in report.entry_points)
    assert "Run" in next(item for item in report.files if item["path"] == "internal/app/app.go")["exports"]


def test_manifest_and_parser_errors_degrade_with_warnings_not_crashes(tmp_path):
    root = init_repo(tmp_path / "mixed", {
        "pyproject.toml": "[project\ninvalid",
        "src/broken.py": "def broken(:\n    pass\n",
        "README.md": "# sample\n",
    })
    report = RepositoryIntelligenceAnalyzer(root).analyze()
    broken = next(item for item in report.files if item["path"] == "src/broken.py")

    assert broken["imports"] == []
    assert broken["exports"] == []
    assert isinstance(report.warnings, list)
    assert report.scanned_files >= 2


def test_csharp_and_java_entry_points_and_framework_detection(tmp_path):
    root = init_repo(tmp_path / "dotnet-java", {
        "app.csproj": "<Project Sdk=\"Microsoft.NET.Sdk.Web\"></Project>",
        "Program.cs": "public class Program { public static void Main(string[] args) {} }",
        "pom.xml": "<project><dependency>spring-boot-starter</dependency></project>",
        "src/main/java/com/example/App.java": (
            "package com.example;\npublic class App {\n"
            " public static void main(String[] args) {}\n}\n"
        ),
    })
    report = RepositoryIntelligenceAnalyzer(root).analyze()

    assert ".NET SDK" in report.build_systems
    assert "ASP.NET Core" in report.frameworks
    assert "Maven" in report.build_systems
    assert "Spring Boot" in report.frameworks
    assert any(item["path"] == "Program.cs" for item in report.entry_points)
    assert any(item["path"].endswith("App.java") for item in report.entry_points)


def test_cpp_include_graph_exports_and_entry_point(tmp_path):
    root = init_repo(tmp_path / "native", {
        "CMakeLists.txt": "cmake_minimum_required(VERSION 3.20)\nproject(native)\n",
        "src/main.cpp": '#include "engine.hpp"\nint main() { return runEngine(); }\n',
        "src/engine.hpp": "int runEngine();\n",
        "src/engine.cpp": '#include "engine.hpp"\nint runEngine() { return 0; }\n',
    })
    report = RepositoryIntelligenceAnalyzer(root).analyze()
    edges = {(item["source"], item["target"]) for item in report.dependencies}
    header = next(item for item in report.files if item["path"] == "src/engine.hpp")

    assert "CMake" in report.build_systems
    assert ("src/main.cpp", "src/engine.hpp") in edges
    assert ("src/engine.cpp", "src/engine.hpp") in edges
    assert "runEngine" in header["exports"]
    assert any(item["path"] == "src/main.cpp" for item in report.entry_points)


def test_changed_paths_are_normalized_and_unsafe_paths_are_ignored(tmp_path):
    root = init_repo(tmp_path / "paths", {
        "src/app.py": "def main(): return 1\n",
    })
    report = RepositoryIntelligenceAnalyzer(root).analyze(
        changed_paths=["./src/app.py", "../outside.py", r"C:\outside.py"],
    )

    assert report.changed_paths == ["src/app.py"]
    assert report.affected_components["src/app.py"] == ["src/app.py"]
    assert any("unsafe changed path" in warning for warning in report.warnings)
