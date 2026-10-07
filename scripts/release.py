"""Prepare local releases, publish their Git tags, and validate CI release tags."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILES = ("pyproject.toml", "uv.lock", "DT-PROTOTYPE-OPENAPI.yaml")


def run(*command: str, capture: bool = False) -> str:
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else ""


def version() -> str:
    value = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError(f"Expected a stable major.minor.patch version, got {value!r}")
    return value


def check_tag(tag: str) -> None:
    expected = f"v{version()}"
    if tag != expected:
        raise ValueError(f"Release tag {tag!r} does not match package version {expected!r}")


def check_worktree() -> None:
    if run("git", "branch", "--show-current", capture=True) != "main":
        raise ValueError("Releases must be prepared and pushed from main")
    if run("git", "status", "--porcelain", "--untracked-files=all", capture=True):
        raise ValueError("Release commands require a clean working tree")


def prepare(bump: str) -> None:
    check_worktree()
    next_version = run(
        "uv", "version", "--bump", bump, "--dry-run", "--short", "--no-sync", capture=True
    )
    tag = f"v{next_version}"
    if run("git", "tag", "--list", tag, capture=True):
        raise ValueError(f"Release tag {tag} already exists")

    spec_path = ROOT / VERSION_FILES[2]
    spec, count = re.subn(
        r"(?m)(^info:\n(?:  .*\n)*?  version: )[^\n]+",
        rf"\g<1>{next_version}",
        spec_path.read_text(encoding="utf-8"),
    )
    if count != 1:
        raise ValueError("Expected exactly one OpenAPI info.version field")
    run("uv", "version", "--bump", bump, "--no-sync")
    check_tag(tag)
    spec_path.write_text(spec, encoding="utf-8")

    for task in ("lint", "format:check", "openapi:validate", "test"):
        run("task", task)
    message = f"chore(release): {tag}"
    run("git", "add", "--", *VERSION_FILES)
    run("git", "commit", "-m", message)
    run("git", "tag", "-a", tag, "-m", message)
    print(f"Prepared {tag}. Review with git show; publish with task release:push.")


def push() -> None:
    check_worktree()
    tag = f"v{version()}"
    if run("git", "rev-parse", f"refs/tags/{tag}^{{commit}}", capture=True) != run(
        "git", "rev-parse", "HEAD", capture=True
    ):
        raise ValueError(f"Release tag {tag} must point at HEAD")
    run("git", "push", "--atomic", "origin", "HEAD:refs/heads/main", f"refs/tags/{tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").add_argument("bump", choices=("patch", "minor", "major"))
    commands.add_parser("push")
    commands.add_parser("check-tag").add_argument("tag")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.bump)
        elif args.command == "push":
            push()
        else:
            check_tag(args.tag)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Release failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
