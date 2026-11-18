import hashlib
import subprocess
from pathlib import Path

import pytest

from kaldrax.workspace import RepositoryWorkspace, WorkspaceError


def init_repo(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "kaldrax@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "KALDRAX Tests"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--all"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
    return RepositoryWorkspace(root)


PATCH = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def value():
-    return 1
+    # Updated behavior
+    return 2
"""


def test_snapshot_excludes_environment_secrets_and_runtime_state(tmp_path):
    root = tmp_path / "repo"
    workspace = init_repo(root, {
        "app.py": "print('safe')\n",
        ".env": "TOKEN=do-not-send\n",
        ".env.example": "TOKEN=placeholder\n",
    })
    snapshot = workspace.capture()
    paths = {item.path for item in snapshot.files}
    assert "app.py" in paths
    assert ".env.example" in paths
    assert ".env" not in paths
    assert ".env" in snapshot.omitted_paths


def test_snapshot_refuses_dirty_repository(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "print('safe')\n"})
    (workspace.root / "app.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="uncommitted or untracked"):
        workspace.capture()


def test_patch_path_traversal_and_private_paths_are_rejected():
    traversal = PATCH.replace("a/app.py b/app.py", "a/../secret b/../secret")
    with pytest.raises(WorkspaceError, match="unsafe path"):
        RepositoryWorkspace.changed_paths(traversal)
    private = PATCH.replace("a/app.py b/app.py", "a/.env b/.env")
    with pytest.raises(WorkspaceError, match="private"):
        RepositoryWorkspace.changed_paths(private)


def test_patch_is_staged_without_changing_real_repository(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "def value():\n    return 1\n"})
    snapshot = workspace.capture()
    with workspace.staged_patch(snapshot, PATCH) as (staged, changed):
        assert changed == ("app.py",)
        assert "return 2" in (staged / "app.py").read_text(encoding="utf-8")
    assert "return 1" in (workspace.root / "app.py").read_text(encoding="utf-8")


def test_apply_patch_rechecks_base_commit_and_updates_only_after_explicit_call(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "def value():\n    return 1\n"})
    snapshot = workspace.capture()
    changed = workspace.apply_patch(snapshot, PATCH)
    assert changed == ("app.py",)
    assert "return 2" in (workspace.root / "app.py").read_text(encoding="utf-8")


def test_apply_patch_refuses_changed_head(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "def value():\n    return 1\n"})
    snapshot = workspace.capture()
    (workspace.root / "other.py").write_text("pass\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace.root), "add", "other.py"], check=True)
    subprocess.run(["git", "-C", str(workspace.root), "commit", "-qm", "concurrent"], check=True)
    with pytest.raises(WorkspaceError, match="HEAD changed"):
        workspace.apply_patch(snapshot, PATCH)


def test_patch_requires_headers_for_every_file_section():
    malformed = PATCH + "\ndiff --git a/other.py b/other.py\n@@ -0,0 +1 @@\n+print('new')\n"
    with pytest.raises(WorkspaceError, match="each patch section"):
        RepositoryWorkspace.changed_paths(malformed)


def test_patch_accepts_new_file_dev_null_headers():
    patch = """diff --git a/new_file.py b/new_file.py
new file mode 100644
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1 @@
+print('new')
"""
    assert RepositoryWorkspace.changed_paths(patch) == ("new_file.py",)


def test_snapshot_prioritizes_source_and_tests_over_large_documentation(tmp_path):
    root = tmp_path / "repo"
    docs = "d" * 45_000
    workspace = init_repo(root, {
        "README.md": docs,
        "src/app.py": "def run(): return 1\n",
        "tests/test_app.py": "def test_run(): assert True\n",
    })
    snapshot = workspace.capture()
    paths = {item.path for item in snapshot.files}
    assert "src/app.py" in paths
    assert "tests/test_app.py" in paths
    assert "README.md" not in paths


def test_patch_rejects_nested_git_metadata_and_windows_drive_paths():
    nested = PATCH.replace("a/app.py b/app.py", "a/vendor/.git/config b/vendor/.git/config")
    with pytest.raises(WorkspaceError, match="Git metadata"):
        RepositoryWorkspace.changed_paths(nested)
    drive = PATCH.replace("a/app.py b/app.py", "a/C:/Windows/system.ini b/C:/Windows/system.ini")
    with pytest.raises(WorkspaceError, match="unsafe path"):
        RepositoryWorkspace.changed_paths(drive)


def test_apply_patch_rejects_a_symlink_parent_component(tmp_path):
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "app.py").write_text("print('outside')\n", encoding="utf-8")
    workspace = init_repo(root, {"app.py": "print('safe')\n"})
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is not permitted on this Windows host: {exc}")
    subprocess.run(["git", "-C", str(root), "add", "linked"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "track symlink"], check=True)
    snapshot = workspace.capture()
    patch = """diff --git a/linked/app.py b/linked/app.py
--- a/linked/app.py
+++ b/linked/app.py
@@ -1 +1 @@
-print('outside')
+print('changed')
"""
    with pytest.raises(WorkspaceError, match="symlink path component"):
        workspace.apply_patch(snapshot, patch)
    assert (outside / "app.py").read_text(encoding="utf-8") == "print('outside')\n"


def test_patch_rejects_excluded_dependency_directories():
    patch = PATCH.replace("a/app.py b/app.py", "a/.venv/bin/tool b/.venv/bin/tool")
    with pytest.raises(WorkspaceError, match="excluded dependency/build"):
        RepositoryWorkspace.changed_paths(patch)


def test_patch_rejects_nested_cloud_credential_and_terraform_state_paths():
    for path in (".docker/config.json", "infra/terraform.tfstate"):
        patch = PATCH.replace("a/app.py b/app.py", f"a/{path} b/{path}")
        with pytest.raises(WorkspaceError):
            RepositoryWorkspace.changed_paths(patch)

import hashlib


def test_repository_status_lists_branch_head_and_dirty_paths(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "print('safe')\n"})
    clean = workspace.status()
    assert clean["clean"] is True
    assert clean["branch"]
    assert clean["head"]

    (workspace.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
    dirty = workspace.status()
    assert dirty["clean"] is False
    assert any(item["path"] == "app.py" for item in dirty["changes"])


def test_repository_file_listing_and_read_exclude_secrets_and_runtime(tmp_path):
    workspace = init_repo(tmp_path / "repo", {
        "app.py": "print('safe')\n",
        "README.md": "# Project\n",
        ".env": "TOKEN=private\n",
        "secrets/token.txt": "private\n",
        ".kaldrax/state.json": "{\"secret\":true}\n",
        "assets/image.png": "not text",
    })
    files = workspace.list_files()
    paths = {item["path"] for item in files}
    assert paths == {"app.py", "README.md"}
    loaded = workspace.read_file("app.py")
    assert loaded["content"].replace("\r\n", "\n") == "print('safe')\n"
    assert loaded["sha256"] == hashlib.sha256((workspace.root / "app.py").read_bytes()).hexdigest()
    with pytest.raises(WorkspaceError):
        workspace.read_file(".env")
    with pytest.raises(WorkspaceError):
        workspace.read_file("secrets/token.txt")


def test_repository_file_apply_uses_hash_precondition_and_creates_backup(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "print('before')\n"})
    original = workspace.read_file("app.py")
    result = workspace.apply_file(
        "app.py", "print('after')\n", expected_sha256=original["sha256"],
    )
    assert result["created"] is False
    assert result["old_sha256"] == original["sha256"]
    assert result["new_sha256"] == hashlib.sha256(b"print('after')\n").hexdigest()
    backup = workspace.root / Path(result["backup_path"])
    assert backup.read_text(encoding="utf-8") == "print('before')\n"
    assert (workspace.root / "app.py").read_text(encoding="utf-8") == "print('after')\n"


def test_repository_file_apply_refuses_stale_hash_and_blind_overwrite(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "print('before')\n"})
    original = workspace.read_file("app.py")
    (workspace.root / "app.py").write_text("print('concurrent')\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="changed since it was read"):
        workspace.apply_file("app.py", "print('after')\n", expected_sha256=original["sha256"])
    with pytest.raises(WorkspaceError, match="expected SHA-256"):
        workspace.apply_file("app.py", "print('after')\n", expected_sha256=None)


def test_repository_file_apply_can_create_a_new_text_file(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "print('safe')\n"})
    result = workspace.apply_file("docs/notes.md", "# Added\n", expected_sha256=None)
    assert result["created"] is True
    assert result["backup_path"] is None
    assert (workspace.root / "docs" / "notes.md").read_text(encoding="utf-8") == "# Added\n"


def test_repository_file_apply_rejects_private_traversal_and_symlink_paths(tmp_path):
    workspace = init_repo(tmp_path / "repo", {"app.py": "print('safe')\n"})
    with pytest.raises(WorkspaceError):
        workspace.apply_file("../outside.py", "pass\n", expected_sha256=None)
    with pytest.raises(WorkspaceError):
        workspace.apply_file(".env", "TOKEN=x\n", expected_sha256=None)

def test_repository_file_apply_refuses_a_symlinked_runtime_backup_directory(tmp_path):
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = init_repo(root, {"app.py": "print('safe')\n"})
    original = workspace.read_file("app.py")
    try:
        (root / ".kaldrax").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is not permitted on this Windows host: {exc}")
    with pytest.raises(WorkspaceError, match="unsafe .kaldrax runtime path"):
        workspace.apply_file("app.py", "print('changed')\n", expected_sha256=original["sha256"])
    assert (root / "app.py").read_text(encoding="utf-8") == "print('safe')\n"
    assert list(outside.iterdir()) == []

def test_repository_file_apply_refuses_a_symlinked_backup_subdirectory(tmp_path):
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = init_repo(root, {"app.py": "print('safe')\n"})
    original = workspace.read_file("app.py")
    runtime = root / ".kaldrax"
    runtime.mkdir()
    try:
        (runtime / "desktop-backups").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is not permitted on this Windows host: {exc}")
    with pytest.raises(WorkspaceError, match="unsafe desktop-backups path"):
        workspace.apply_file("app.py", "print('changed')\n", expected_sha256=original["sha256"])
    assert (root / "app.py").read_text(encoding="utf-8") == "print('safe')\n"
    assert list(outside.iterdir()) == []

def test_checkpoint_binding_uses_full_head_and_refuses_dirty_worktree(tmp_path):
    root = tmp_path / "repo"
    workspace = init_repo(root, {"app.py": "print('safe')\n"})

    binding = workspace.checkpoint_binding()
    expected_head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert binding == {"root": str(root.resolve()), "head": expected_head}
    assert len(binding["head"]) in {40, 64}

    (root / "app.py").write_text("print('changed')\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="uncommitted or untracked"):
        workspace.checkpoint_binding()
