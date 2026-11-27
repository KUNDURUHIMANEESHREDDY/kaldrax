"""Bounded, read-only cross-repository Python consumer discovery.

This is navigation evidence, not Python type inference or proof of a regression.
The caller is responsible for pinning and verifying trusted Git snapshots.
Files are parsed with the standard-library AST and are never imported or run.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_MAX_FILES = 400
_MAX_BYTES = 80_000
_MAX_MATCHES = 60


@dataclass(frozen=True)
class ExternalCall:
    consumer_path: str
    line: int
    column: int
    member: str
    receiver: str
    positional_args: int
    keyword_args: tuple[str, ...]
    evidence_level: str
    source_excerpt: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExternalUsageReport:
    provider_package: str
    inspected_files: int = 0
    omitted_files: int = 0
    matches: list[ExternalCall] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_package": self.provider_package,
            "inspected_files": self.inspected_files,
            "omitted_files": self.omitted_files,
            "matches": [m.as_dict() for m in self.matches],
            "warnings": self.warnings,
            "interpretation": (
                "Possible external callers only. Imported-package provenance and "
                "AST syntax are observed; dynamic receiver types are not proven. "
                "No runtime behavior was tested."
            ),
        }


def _safe_read(root: Path, file: Path) -> str | None:
    current = root
    try:
        for part in file.relative_to(root).parts:
            current = current / part
            if current.is_symlink():
                return None
        if (
            not file.resolve(strict=True).is_relative_to(root)
            or not file.is_file()
            or file.stat().st_size > _MAX_BYTES
        ):
            return None
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return None


def _import_aliases(tree: ast.Module, package: str) -> tuple[set[str], set[str]]:
    modules: set[str] = set()
    classes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == package or alias.name.startswith(package + "."):
                    modules.add(alias.asname or package)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module == package or (node.module or "").startswith(package + "."):
                for alias in node.names:
                    if alias.name != "*":
                        classes.add(alias.asname or alias.name)
    return modules, classes


def _qualifier(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _qualifier(node.value) + "." + node.attr
    if isinstance(node, ast.Call):
        return _qualifier(node.func) + "()"
    return "unresolved"


def _lexically_typed_loops(tree: ast.Module, package: str) -> set[str]:
    """Find for-loop targets over annotated collections mentioning the provider.

    This evidence is still heuristic: annotations don't guarantee runtime types.
    """
    typed: set[str] = set()
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        annotations = {
            arg.arg
            for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs
            if arg.annotation is not None and package in ast.unparse(arg.annotation)
        }
        if not annotations:
            continue
        for node in ast.walk(function):
            if isinstance(node, (ast.For, ast.AsyncFor)):
                if isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Name):
                    if node.iter.id in annotations:
                        typed.add(node.target.id)
    return typed


def discover_external_calls(
    consumer_root: Path | str,
    *,
    provider_package: str,
    members: set[str],
    limit: int = _MAX_MATCHES,
) -> ExternalUsageReport:
    """Search trusted consumer source for package-linked method call candidates.

    A match is NOT a verified dependency break; receiver provenance may be
    unknown, even when the file imports the provider package.
    """
    root = Path(consumer_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("consumer root must be a directory")
    if (
        not provider_package or not all(part.isidentifier() for part in provider_package.split("."))
        or not members or not all(member.isidentifier() for member in members)
        or not 1 <= limit <= _MAX_MATCHES
    ):
        raise ValueError("invalid provider package, method set or limit")

    report = ExternalUsageReport(provider_package)
    files = sorted(
        root.rglob("*.py"),
        key=lambda file: (
            any(part.lower() in {"tests", "test", "docs", "docs_src", "examples"}
                for part in file.relative_to(root).parts),
            file.relative_to(root).as_posix(),
        ),
    )
    if len(files) > _MAX_FILES:
        report.warnings.append("consumer file limit reached; coverage incomplete")
        report.omitted_files += len(files) - _MAX_FILES
    for file in files[:_MAX_FILES]:
        source = _safe_read(root, file)
        if source is None:
            report.omitted_files += 1
            continue
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            report.omitted_files += 1
            continue
        report.inspected_files += 1
        modules, classes = _import_aliases(tree, provider_package)
        if not (modules or classes):
            continue
        typed_vars = _lexically_typed_loops(tree, provider_package)
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in members:
                continue
            receiver = _qualifier(node.func.value)
            top = receiver.split(".", 1)[0]
            if receiver.startswith(tuple(alias + "." for alias in modules)):
                level = "import-linked-module-expression"
            elif top in classes:
                level = "import-linked-class-expression"
            elif isinstance(node.func.value, ast.Name) and node.func.value.id in typed_vars:
                level = "annotated-collection-receiver-candidate"
            else:
                level = "package-file-method-name-only"
            if not 1 <= node.lineno <= len(lines):
                continue
            report.matches.append(ExternalCall(
                consumer_path=file.relative_to(root).as_posix(),
                line=node.lineno,
                column=node.col_offset,
                member=node.func.attr,
                receiver=receiver,
                positional_args=len(node.args),
                keyword_args=tuple(
                    kw.arg for kw in node.keywords if kw.arg is not None
                ),
                evidence_level=level,
                source_excerpt=lines[node.lineno - 1].strip()[:250],
            ))
            if len(report.matches) >= limit:
                report.warnings.append("external call-site limit reached; coverage incomplete")
                return report
    return report
