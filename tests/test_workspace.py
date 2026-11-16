import subprocess

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
    (root / "linked").symlink_to(outside, target_is_directory=True)
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
