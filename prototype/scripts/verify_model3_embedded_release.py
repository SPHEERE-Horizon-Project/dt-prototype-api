"""Final audit for the embedded Model 3 package layout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "20260917_model3_embedded_release"
MODEL3 = ROOT / "src" / "dt_prototype" / "integration" / "model3"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    expected_source_hash = "d0d4add1770f3e21cb9ae178f4ce8d206554a2ec9da1b63c8e50b55373e26f9c"
    assert sha256(MODEL3 / "model3.py") == expected_source_hash
    assert not (ROOT / "third_party").exists()

    golden = sorted((MODEL3 / "reference_outputs").glob("*.csv"))
    standalone = ROOT / "outputs" / "20260917_model3_embedded_standalone"
    assert len(golden) == 5
    assert all((standalone / path.name).read_bytes() == path.read_bytes() for path in golden)

    test_log = (ROOT / "outputs" / "20260917_model3_embedded_tests_002.log").read_text(
        encoding="utf-8"
    )
    assert "169 passed" in test_log
    relocation = json.loads(
        (ROOT / "outputs/20260917_model3_relocation_verification/verification.json").read_text(
            encoding="utf-8"
        )
    )
    assert relocation["status"] == "PASS"
    assert relocation["maximum_absolute_difference"] == 0.0

    wheel = next((ROOT / "outputs/20260917_model3_embedded_wheel").glob("*.whl"))
    required = {
        "dt_prototype/integration/engines/model3.py",
        "dt_prototype/integration/model3/model3.py",
        *{
            "dt_prototype/integration/model3/reference_outputs/" + path.name
            for path in golden
        },
    }
    with ZipFile(wheel) as package:
        packaged = set(package.namelist())
    assert required <= packaged
    assert not any("model3_legacy.py" in name for name in packaged)

    result = {
        "status": "PASS",
        "active_model3_root": "src/dt_prototype/integration/model3",
        "active_adapter": "src/dt_prototype/integration/engines/model3.py",
        "separate_third_party_directory_present": False,
        "model3_source_sha256": expected_source_hash,
        "golden_outputs_reproduced_byte_for_byte": len(golden),
        "five_building_maximum_numeric_difference": relocation[
            "maximum_absolute_difference"
        ],
        "full_test_suite": test_log.strip().splitlines()[-1],
        "wheel": {
            "file": str(wheel.relative_to(ROOT)),
            "sha256": sha256(wheel),
            "contains_complete_model3_pipeline": True,
        },
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
