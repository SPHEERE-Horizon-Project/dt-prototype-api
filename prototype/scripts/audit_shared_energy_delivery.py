"""Check final run provenance and links; attach completed pytest evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dt_prototype.common.project import ProjectInputs
from dt_prototype.energy_carriers import EnergyConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/example.json")
    parser.add_argument("--pytest-xml", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "complete":
        raise AssertionError("Energy run is not complete")
    package = ROOT / "src/dt_prototype"
    current = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob("*.py")}
    if current != manifest["code_hashes"]:
        raise AssertionError("Source code differs from the validated run")
    if ProjectInputs.load(args.config).hashes() != manifest["input_hashes"]:
        raise AssertionError("Project inputs differ from the validated run")
    if EnergyConfig.load(out / "energy_config_resolved.json").sha256 != manifest["energy_config_sha256"]:
        raise AssertionError("Resolved energy configuration differs from the validated run")
    links = 0
    for document in out.rglob("*.md"):
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            target = target.strip("<>").split("#")[0]
            if not (document.parent / target).resolve().exists():
                raise AssertionError(f"Broken local link in {document.name}: {target}")
            links += 1
    suites = list(ET.parse(args.pytest_xml).getroot().iter("testsuite"))
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    if counts["tests"] == 0 or counts["failures"] or counts["errors"]:
        raise AssertionError(f"Test suite was not successful: {counts}")
    shutil.copyfile(args.pytest_xml, out / "test_results.xml")
    result = dict(source_hashes_match=True, input_hashes_match=True, energy_config_hash_matches=True,
                  checked_local_links=links, pytest=counts, validation=manifest["validation"])
    (out / "delivery_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = out / "comparison_report.md"
    body = report.read_text(encoding="utf-8").split("\n## Automated test evidence\n")[0]
    body += ("\n## Automated test evidence\n\n"
             f"The completed regression suite contains {counts['tests']} tests, {counts['failures']} failures, "
             f"{counts['errors']} errors and {counts['skipped']} skips. See [machine-readable test results](test_results.xml) "
             "and [delivery audit](delivery_audit.json). The audit also verifies the run's source/input/configuration "
             "hashes against the delivered files and checks all generated report links.\n")
    report.write_text(body, encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
