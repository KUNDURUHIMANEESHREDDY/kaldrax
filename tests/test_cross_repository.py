"""External consumer discovery: AST-only, bounded, conservative provenance."""
from __future__ import annotations

from pathlib import Path

import pytest

from kaldrax.cross_repository import discover_external_calls


def test_detects_annotated_click_receiver_without_claiming_type_proof(tmp_path: Path) -> None:
    package = tmp_path / "typer"
    package.mkdir()
    (package / "rich_utils.py").write_text(
        "import click\n"
        "from typing import List, Union\n"
        "def panel(params: Union[List[click.Option], List[click.Argument]]):\n"
        "    for param in params:\n"
        "        output = param.make_metavar()\n",
        encoding="utf-8",
    )
    result = discover_external_calls(
        tmp_path, provider_package="click", members={"make_metavar"}
    )
    assert result.inspected_files == 1
    assert len(result.matches) == 1
    site = result.matches[0]
    assert site.consumer_path == "typer/rich_utils.py"
    assert site.line == 5
    assert site.positional_args == 0
    assert site.evidence_level == "annotated-collection-receiver-candidate"
    assert "not proven" in result.to_dict()["interpretation"]


def test_does_not_claim_no_import_matches_as_external_call(tmp_path: Path) -> None:
    (tmp_path / "script.py").write_text(
        "def run(param):\n    return param.make_metavar()\n", encoding="utf-8"
    )
    result = discover_external_calls(
        tmp_path, provider_package="click", members={"make_metavar"}
    )
    assert result.matches == []


def test_import_alias_and_exact_symbol(tmp_path: Path) -> None:
    (tmp_path / "script.py").write_text(
        "import click as ck\n"
        "def go():\n"
        "    return ck.Option(['--x']).make_metavar()\n",
        encoding="utf-8",
    )
    result = discover_external_calls(
        tmp_path, provider_package="click", members={"make_metavar"}
    )
    assert result.matches[0].evidence_level == "import-linked-module-expression"
    assert result.matches[0].receiver == "ck.Option()"


def test_symlinks_and_oversized_files_are_omitted(tmp_path: Path) -> None:
    (tmp_path / "big.py").write_bytes(b"x=1\n" * 30_000)
    outside = tmp_path.parent / "outside-crossrepo.py"
    outside.write_text(
        "import click\nclick.Option().make_metavar()\n", encoding="utf-8"
    )
    try:
        (tmp_path / "linked.py").symlink_to(outside)
    except (OSError, NotImplementedError):
        pass  # Windows developer mode might disallow symlink creation
    result = discover_external_calls(
        tmp_path, provider_package="click", members={"make_metavar"}
    )
    assert result.matches == []
    assert result.omitted_files >= 1


@pytest.mark.parametrize(("package", "members"), [
    ("../click", {"make_metavar"}),
    ("click;import os", {"make_metavar"}),
    ("click", {"invalid-name!"}),
    ("", {"make_metavar"}),
    ("click", set()),
])
def test_invalid_selector_is_refused(
    tmp_path: Path, package: str, members: set[str]
) -> None:
    with pytest.raises(ValueError):
        discover_external_calls(tmp_path, provider_package=package, members=members)
