"""Record the active runtime and lock only the installed dependency closure.

This captures an environment after testing. It does not install or upgrade it.
The main lock is specific to the recorded Python/platform, not universal.
"""
import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOTS = ["numpy", "pandas", "matplotlib", "pytest", "openpyxl", "jsonschema"]


def closure(roots):
    pending, found = list(roots), {}
    while pending:
        name = canonicalize_name(pending.pop())
        if name in found:
            continue
        package = metadata.distribution(name)
        found[name] = package.version
        for value in package.requires or []:
            dependency = Requirement(value)
            if dependency.marker is None or dependency.marker.evaluate({"extra": ""}):
                pending.append(dependency.name)
    return dict(sorted(found.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    versions = closure(["opendsm", "multimethod"] if args.worker else ROOTS)
    result = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                  architecture=platform.machine(), dependencies=versions)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    if args.lock:
        args.lock.write_text("# Verified dependency closure; Windows x64 / Python 3.12.10.\n"+
                             "\n".join(f"{k}=={v}" for k, v in versions.items())+"\n", encoding="utf-8")
    print(f"Captured {len(versions)} packages: {args.report}")
