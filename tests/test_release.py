from __future__ import annotations

import importlib.util
import subprocess
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = "openapi: 3.1.0\ninfo:\n  title: Test API\n  version: 0.2.0\n  description: Keep this.\npaths: {}\n"
spec = importlib.util.spec_from_file_location("release", PROJECT_ROOT / "scripts/release.py")
assert spec is not None and spec.loader is not None
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch):
    root = tmp_path / "repository"
    root.mkdir()
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    monkeypatch.setenv("UV_OFFLINE", "1")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "release-fixture"\nversion = "0.2.0"\nrequires-python = ">=3.12,<3.13"\n'
    )
    (root / "DT-PROTOTYPE-OPENAPI.yaml").write_text(SPEC)
    (root / "Taskfile.yml").write_text(
        'version: "3"\ntasks:\n'
        + "".join(
            f'  {name}:\n    cmds: ["true"]\n'
            for name in ("lint", "format:check", "openapi:validate", "test")
        )
    )
    release.run("uv", "lock")
    release.run("git", "init", "-b", "main")
    for key, value in (
        ("user.name", "Release Test"),
        ("user.email", "release@example.invalid"),
        ("commit.gpgsign", "false"),
        ("tag.gpgsign", "false"),
        ("core.hooksPath", "/dev/null"),
    ):
        release.run("git", "config", key, value)
    release.run("git", "add", ".")
    release.run("git", "commit", "-m", "Initial fixture")
    return root


@pytest.mark.parametrize(
    "bump,expected", [("patch", "0.2.1"), ("minor", "0.3.0"), ("major", "1.0.0")]
)
def test_prepare_updates_only_versions_and_creates_annotated_tag(repository, bump, expected):
    release.prepare(bump)
    assert release.version() == expected
    assert (repository / "DT-PROTOTYPE-OPENAPI.yaml").read_text() == SPEC.replace(
        "version: 0.2.0", f"version: {expected}"
    )
    lock = tomllib.loads((repository / "uv.lock").read_text())
    assert next(p for p in lock["package"] if p["name"] == "release-fixture")["version"] == expected
    assert release.run("git", "status", "--porcelain", capture=True) == ""
    assert (
        release.run("git", "log", "-1", "--format=%s", capture=True)
        == f"chore(release): v{expected}"
    )
    assert release.run("git", "cat-file", "-t", f"refs/tags/v{expected}", capture=True) == "tag"
    assert set(
        release.run("git", "diff", "HEAD~", "--name-only", capture=True).splitlines()
    ) == set(release.VERSION_FILES)


@pytest.mark.parametrize("command", [("prepare", "patch"), ("push",)])
@pytest.mark.parametrize("state", ["dirty", "feature", "detached"])
def test_release_rejects_dirty_or_non_main_worktree(repository, command, state):
    if state == "dirty":
        (repository / "untracked.txt").write_text("unrelated work")
    elif state == "feature":
        release.run("git", "switch", "-c", "feature")
    else:
        release.run("git", "checkout", "--detach")
    head = release.run("git", "rev-parse", "HEAD", capture=True)
    with pytest.raises(ValueError, match="clean working tree|from main"):
        getattr(release, command[0])(*command[1:])
    assert release.version() == "0.2.0"
    assert release.run("git", "rev-parse", "HEAD", capture=True) == head


def test_duplicate_tag_is_rejected_before_bumping(repository):
    release.run("git", "tag", "v0.2.1")
    with pytest.raises(ValueError, match="already exists"):
        release.prepare("patch")
    assert release.version() == "0.2.0"
    assert release.run("git", "status", "--porcelain", capture=True) == ""


def test_failed_checks_leave_edits_without_commit_or_tag(repository):
    taskfile = repository / "Taskfile.yml"
    taskfile.write_text(taskfile.read_text().replace('["true"]', '["false"]', 1))
    release.run("git", "add", "Taskfile.yml")
    release.run("git", "commit", "-m", "Fail validation")
    head = release.run("git", "rev-parse", "HEAD", capture=True)
    with pytest.raises(subprocess.CalledProcessError):
        release.prepare("patch")
    assert release.version() == "0.2.1"
    assert release.run("git", "rev-parse", "HEAD", capture=True) == head
    assert release.run("git", "tag", "--list", capture=True) == ""
    assert release.run("git", "status", "--porcelain", capture=True)


def test_push_is_atomic_and_failed_push_can_be_retried(repository, tmp_path):
    remote = tmp_path / "remote.git"
    release.run("git", "init", "--bare", str(remote))
    release.run("git", "remote", "add", "origin", str(remote))
    release.run("git", "push", "origin", "main")
    initial = release.run("git", "rev-parse", "HEAD", capture=True)
    release.run("git", "--git-dir", str(remote), "update-ref", "refs/tags/v0.2.1", initial)
    release.prepare("patch")
    with pytest.raises(subprocess.CalledProcessError):
        release.push()
    assert (
        release.run("git", "--git-dir", str(remote), "rev-parse", "main", capture=True) == initial
    )
    assert release.run("git", "cat-file", "-t", "v0.2.1", capture=True) == "tag"
    release.run("git", "--git-dir", str(remote), "update-ref", "-d", "refs/tags/v0.2.1")
    release.push()
    for ref in ("refs/heads/main", "refs/tags/v0.2.1"):
        assert release.run("git", "--git-dir", str(remote), "rev-parse", ref, capture=True) == (
            release.run("git", "rev-parse", ref, capture=True)
        )


def test_push_requires_release_tag_at_head(repository):
    release.prepare("patch")
    release.run("git", "commit", "--allow-empty", "-m", "Work after release")
    with pytest.raises(ValueError, match="must point at HEAD"):
        release.push()


def test_ci_tag_check_uses_package_version(repository):
    release.check_tag("v0.2.0")
    for tag in ("0.2.0", "v0.2.1", "v0.2.0-rc.1"):
        with pytest.raises(ValueError, match="does not match"):
            release.check_tag(tag)
