from __future__ import annotations

import pytest

from dt_prototype.integration.weather import (
    audit_raw_epw_ingestion,
    process_epw_to_monthly,
)


def test_reference_epw_monthly_contract_and_independent_audit(project_root) -> None:
    epw = project_root / "data" / "examples" / "ITA_Venezia-Tessera.161050_IGDG.epw"
    prepared = process_epw_to_monthly(epw, "venezia_161050")
    assert len(prepared.monthly_records) == 12
    january = prepared.monthly_records[0]
    assert january.days == 31
    assert january.hours_valid == 744.0
    assert january.outdoor_temp_C == pytest.approx(2.638440860215, abs=1e-12)
    assert january.source_hash == (
        "5e413257f09151e800fb5b9b84dc2af4aa18409aa6fce89b87337831faeba3d6"
    )
    assert all(record.data_quality_flag == "good" for record in prepared.monthly_records)
    assert all(record.solar_HOR_kWh_m2 >= 0.0 for record in prepared.monthly_records)

    audit = audit_raw_epw_ingestion(epw, prepared.reference_hourly_weather)
    assert audit.passed
    assert audit.raw_row_count == 8760
