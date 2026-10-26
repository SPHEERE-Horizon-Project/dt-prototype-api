"""Check the lean source distribution's byte manifest and local Markdown links.

Run after download/upload to catch missing files or changed input bytes. Normal
generated environments, outputs and the optional archive are excluded from this
source inventory. This does not run a thermal solver or certify model accuracy.
"""
from pathlib import Path
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]


def source_files():
    for directory, folders, names in os.walk(ROOT):
        folders[:] = [n for n in folders if n not in {
            ".git", "__pycache__", ".pytest_cache", "node_modules", "outputs",
            "build", "dist", "validation_archive"} and not n.startswith(".venv") and not n.endswith(".egg-info")]
        for name in names:
            file = Path(directory)/name
            relative = file.relative_to(ROOT)
            if relative.parts[:2] == ("data", "private") or file.suffix in {".pyc", ".pyo"}:
                continue
            if name.startswith(".env") or name == "DT_Prototype_validation_archive.zip":
                continue
            yield relative.as_posix(), file


def verify():
    manifest = json.loads((ROOT/"PUBLICATION_MANIFEST.json").read_text(encoding="utf-8"))
    expected = manifest["published_hashes"]
    actual = dict(source_files())
    if set(actual) != set(expected) | {"PUBLICATION_MANIFEST.json"}:
        raise ValueError(f"Source inventory differs; missing={sorted(set(expected)-set(actual))}, "
                         f"extra={sorted(set(actual)-set(expected)-{'PUBLICATION_MANIFEST.json'})}")
    for name, digest in expected.items():
        if hashlib.sha256(actual[name].read_bytes()).hexdigest() != digest:
            raise ValueError(f"Published file byte hash differs: {name}")
    checked = 0
    for name, document in actual.items():
        if not name.endswith(".md"):
            continue
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8-sig")):
            target = target.strip("<>").split("#")[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (document.parent/target).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                raise ValueError(f"Missing/outside publication link in {name}: {target}")
            checked += 1
    return dict(status="passed", files=len(actual), bytes=sum(p.stat().st_size for p in actual.values()),
                checked_local_links=checked, source_commit=manifest["source_commit"])


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
