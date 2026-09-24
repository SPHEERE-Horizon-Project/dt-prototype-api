from __future__ import annotations

from tempfile import TemporaryDirectory

from dt_prototype.integration.model3 import model3
from dt_prototype.integration.project_paths import model3_pipeline_root


def test_model3_reference_outputs_regenerate_byte_for_byte(project_root) -> None:
    model_root = model3_pipeline_root()
    with TemporaryDirectory() as temporary:
        from pathlib import Path

        generated = Path(temporary)
        model3.run(model_root / "example_data", generated)
        expected = model_root / "reference_outputs"
        names = sorted(path.name for path in expected.glob("*.csv"))
        assert names
        assert all(
            (generated / name).read_bytes() == (expected / name).read_bytes()
            for name in names
        )
