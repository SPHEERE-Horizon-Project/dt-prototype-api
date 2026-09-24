from __future__ import annotations

import pandas as pd
import pytest

from dt_prototype.integration.reporting import build_side_by_side_report
from dt_prototype.integration.workflow import run_supplied_reference_comparison


def test_side_by_side_report_preserves_building_and_zone_cases(project_root, tmp_path) -> None:
    source = run_supplied_reference_comparison(project_root, tmp_path, "comparison")
    report = build_side_by_side_report(source, tmp_path, "report", project_root)

    annual = pd.read_csv(report / "annual_side_by_side_outputs.csv")
    monthly = pd.read_csv(report / "monthly_side_by_side_outputs.csv")
    assert len(annual) == 13
    assert len(monthly) == 156
    assert {"building_aggregate", "individual_zone:upper", "individual_zone:lower"}.issubset(
        set(annual["case_scope"])
    )
    assert annual["building_name"].replace("", pd.NA).notna().all()
    assert monthly["difference_total_gain_kWh"].abs().max() < 1e-8
    assert "cross-model comparison" in (report / "annual_side_by_side_outputs.md").read_text(
        encoding="utf-8"
    )
    with pytest.raises(FileExistsError):
        build_side_by_side_report(source, tmp_path, "report", project_root)
