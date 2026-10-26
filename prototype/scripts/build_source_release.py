"""Create a portable source ZIP from a reviewed Git commit, with byte hashes.

Only tracked files enter the archive. Outputs, virtual environments, credentials
and data/private must remain untracked. The destination must be a new file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def git(*arguments):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *arguments], cwd=ROOT)


def build(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("release ZIP already exists")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("commit reviewed tracked changes before packaging")
    names = [v for v in git("ls-files", "-z").decode("utf-8").split("\0") if v]
    forbidden = {"node_modules", "__pycache__", ".git", "outputs", "private"}
    for name in names:
        parts = Path(name).parts
        if any(p in forbidden or p.startswith(".venv") or p.startswith(".env") for p in parts):
            raise ValueError(f"forbidden generated/private path is tracked: {name}")
        if (ROOT / name).is_symlink():
            raise ValueError(f"release refuses symlinks: {name}")
    manifest = {"schema_version": "1.0", "git_commit": git("rev-parse", "HEAD").decode().strip(),
                "files": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(ROOT/name, name)
        archive.writestr("SOURCE_RELEASE_MANIFEST.json", json.dumps(manifest, indent=2)+"\n")
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f"ZIP byte hash mismatch: {name}")
    result = dict(path=str(destination), git_commit=manifest["git_commit"], files=len(names),
                  bytes=destination.stat().st_size, sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    destination.with_suffix(".verification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
