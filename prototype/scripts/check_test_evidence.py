"""Fail CI/release validation on empty, skipped, failing or errored JUnit runs."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def check(path):
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    counts = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ["tests", "failures", "errors", "skipped"]}
    if counts["tests"] < 1 or any(counts[k] for k in ["failures", "errors", "skipped"]):
        raise ValueError(f"full evidence requires nonempty tests and zero failures/errors/skips: {counts}")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junit", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.junit), indent=2))
