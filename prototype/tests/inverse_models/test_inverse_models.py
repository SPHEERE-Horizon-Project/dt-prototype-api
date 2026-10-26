"""Contract, preservation and real isolated-backend tests."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dt_prototype.inverse_models.adapters import _resample_subhourly, load_dataset
from dt_prototype.inverse_models.backends import fivep
from dt_prototype.inverse_models.data import load_json, monthly, timestamps, validate, validate_clock
from dt_prototype.inverse_models.workflow import model_settings, run_inverse
from dt_prototype.inverse_models.reporting import aggregate_monthly
from dt_prototype.monthly_ss_simplified.five_parameter import fit_five_parameter
from dt_prototype import pipeline

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(os.environ.get("DT_OPENDSM_PYTHON", ROOT / ".venv-opendsm/Scripts/python.exe"))
CLOCK = {"convention":"standard", "timezone":"Etc/GMT-1"}


def settings(name="inverse_billing_example.json"):
    data = load_json(ROOT / "configs" / name)
    for key in ["observations", "weather"]:
        data["source"][key] = str((ROOT / "configs" / data["source"][key]).resolve())
    data["opendsm_python"] = str(WORKER)
    return data


def run(tmp_path, config, name):
    path = tmp_path / (name + ".json")
    path.write_text(json.dumps(config))
    return run_inverse(path, tmp_path / name)


@pytest.fixture
def dataset():
    config = settings()
    return load_dataset(config, ROOT / "configs")


def test_5p_facade_reproduces_original_fitter_exactly(dataset):
    sid = next(iter(dataset.series))
    data, payload = fivep(dataset, sid, {})
    train = data[data.split == "train"]
    fit = fit_five_parameter(train.temperature_C, train.energy_kWh/train.days)
    assert payload["parameters"]["beta_heating_kWh_day_K"] == fit.beta_heating_kWh_day_K
    np.testing.assert_array_equal(data.predicted_energy_kWh, fit.predict_daily_energy(data.temperature_C)*data.days)


def test_5p_does_not_train_on_validation_targets(dataset):
    sid = next(iter(dataset.series))
    _, original = fivep(dataset, sid, {})
    dataset.observations.loc[dataset.observations.split == "validation", "energy_kWh"] *= 100
    _, altered = fivep(dataset, sid, {})
    assert original == altered


def test_prediction_needs_no_targets_and_never_refits(dataset, tmp_path, monkeypatch):
    config = settings()
    config["models"] = ["5p_monthly"]
    trained = run(tmp_path, config, "fit")
    input_frame = dataset.observations.copy()
    input_frame["energy_kWh"] = np.nan
    input_frame["split"] = "predict"
    observations = tmp_path / "features_only.csv"
    input_frame.to_csv(observations,index=False)
    config.update(operation="predict",model_dir=str(trained))
    config["source"]["observations"] = str(observations)
    monkeypatch.setattr("dt_prototype.monthly_ss_simplified.five_parameter.fit_five_parameter", lambda *a,**kw: (_ for _ in ()).throw(AssertionError("refit")))
    predicted = run(tmp_path, config, "predict")
    result = pd.read_csv(predicted / "predictions.csv")
    assert result.observed_energy_kWh.isna().all()
    assert result.predicted_energy_kWh.notna().all()
    np.testing.assert_allclose(result.predicted_energy_kWh, pd.read_csv(trained / "predictions.csv").predicted_energy_kWh, rtol=0,atol=0)


def test_measured_data_and_multiple_leading_zero_building_ids_need_no_geometry(dataset,tmp_path):
    config = settings()
    config["models"] = ["5p_monthly"]
    obs = dataset.observations.copy()
    sid = next(iter(dataset.series))
    second = obs.copy()
    second["series_id"] = "second"
    path = tmp_path / "two.csv"
    pd.concat([obs,second]).to_csv(path,index=False)
    metadata = dict(dataset.series[sid], source_type="measured", building_id="001", source_id="synthetic_measured_format_test_only")
    config["source"].update(observations=str(path),series={sid:metadata,"second":dict(metadata,building_id="002")})
    out = run(tmp_path,config,"measured")
    result = pd.read_csv(out/"predictions.csv",dtype={"building_id":str})
    assert set(result.building_id) == {"001","002"}
    assert set(result.source_type) == {"measured"}


def test_mixed_split_month_cannot_leak_into_monthly_training():
    config = settings("inverse_synthetic_example.json")
    data = load_dataset(config,ROOT/"configs")
    data.observations.loc[0,"split"] = "validation"
    with pytest.raises(ValueError,match="single split"):
        monthly(data,next(iter(data.series)))


def test_subhourly_resampling_preserves_energy_and_missing_hours():
    time = pd.date_range("2023-01-01",periods=8,freq="15min",tz="UTC")
    data = pd.DataFrame(dict(series_id="x", interval_start=time, interval_end=time+pd.Timedelta(minutes=15),
                             energy_kWh=[1.0]*8,split="train",quality="valid"))
    result = _resample_subhourly(data)
    assert result.energy_kWh.tolist() == [4.0,4.0]
    incomplete = _resample_subhourly(data.drop(index=5))
    assert np.isnan(incomplete.energy_kWh.iloc[1]) and incomplete.quality.iloc[1] == "missing"
    data.loc[1,"split"] = "test"
    with pytest.raises(ValueError,match="cut an hour"):
        _resample_subhourly(data)


def test_monthly_report_aggregates_energy_temperature_residuals_without_inventing_uncertainty():
    time=pd.date_range("2023-01-01","2023-02-01",freq="h",inclusive="left",tz="UTC")
    data=pd.DataFrame(dict(interval_start=time,interval_end=time+pd.Timedelta(hours=1),
        period_id="2023-01",month_complete=True,split="train",quality="valid",duration_h=1.0,
        observed_energy_kWh=2.0,predicted_energy_kWh=1.0,residual_energy_kWh=1.0,
        temperature_C=np.arange(len(time)),native_uncertainty=0.5,prediction_reason="ok"))
    result=aggregate_monthly(data).iloc[0]
    assert result.observed_energy_kWh==1488 and result.predicted_energy_kWh==744
    assert result.residual_energy_kWh==744 and result.temperature_C==371.5
    assert np.isnan(result.native_uncertainty)


def test_civil_clock_requires_disambiguation_and_preserves_real_repeated_hour():
    clock = {"convention":"civil","timezone":"Europe/Rome"}
    with pytest.raises(Exception):
        timestamps(["2023-10-29 02:00"],clock)
    with pytest.raises(Exception):
        timestamps(["2023-03-26 02:00"],clock)
    index = timestamps(["2023-10-29T02:00:00+02:00","2023-10-29T02:00:00+01:00"],clock)
    assert index[1]-index[0] == pd.Timedelta(hours=1)
    with pytest.raises(ValueError,match="fixed-offset"):
        validate_clock({"convention":"standard","timezone":"Europe/Rome"})


@pytest.mark.parametrize("defect",["negative","infinity","overlap","weather_gap","bad_quality","metadata"])
def test_invalid_data_rejected(dataset,defect):
    obs,weather,metadata = dataset.observations.copy(),dataset.weather.copy(),dict(dataset.series)
    if defect == "negative": obs.loc[0,"energy_kWh"]=-1
    elif defect == "infinity": obs.loc[0,"energy_kWh"]=np.inf
    elif defect == "overlap": obs=pd.concat([obs,obs.iloc[[0]]])
    elif defect == "weather_gap": weather=weather.drop(index=1)
    elif defect == "bad_quality": obs.loc[0,"quality"]="guess"
    else: metadata={}
    with pytest.raises(ValueError): validate(obs,weather,metadata,CLOCK)


def test_split_boundary_cannot_cut_a_bill(dataset):
    config=settings()
    config["source"]["train_end"]="2022-01-15"
    with pytest.raises(ValueError,match="must not cut"):
        load_dataset(config,ROOT/"configs")


@pytest.mark.parametrize("models",[[],["unknown"],["5p_monthly","5p_monthly"],
    [{"backend":"opendsm_billing","options":{"variant":"solar"}}],
    [{"backend":"opendsm_hourly","options":{"allow_disqualified":"true"}}]])
def test_invalid_model_settings_rejected(models):
    with pytest.raises(ValueError): model_settings(models)


def test_missing_worker_isolated_and_5p_outputs_are_retained(tmp_path):
    config=settings()
    config["opendsm_python"]=str(tmp_path/"absent.exe")
    out=run(tmp_path,config,"missing_worker")
    manifest=load_json(out/"manifest.json")
    assert manifest["status"]=="partial"
    assert manifest["successful_models"]==1 and manifest["failed_models"]==1
    assert (out/"predictions.csv").exists()


def test_artifact_corruption_and_physical_identity_mismatch_are_rejected(tmp_path):
    config=settings()
    config["models"]=["5p_monthly"]
    trained=run(tmp_path,config,"trained")
    config.update(operation="evaluate",model_dir=str(trained))
    sid=next(iter(config["source"]["series"]))
    config["source"]["series"][sid]["meter_boundary_id"]="another-meter"
    result=run(tmp_path,config,"wrong_boundary")
    assert load_json(result/"manifest.json")["status"]=="failed"
    artifact=next((trained/"models").rglob("artifact.json"))
    artifact.write_text("{}")
    with pytest.raises(ValueError,match="hash mismatch"):
        run(tmp_path,config,"corrupt")


def test_forward_and_inverse_pipeline_dispatch_preserves_old_defaults(tmp_path,monkeypatch):
    assert pipeline.load_configuration(ROOT/"configs/pipeline_example.json")["mode"]=="forward"
    config={"schema_version":"1.0","mode":"inverse","inverse_config":str(ROOT/"configs/inverse_5p_example.json")}
    source=tmp_path/"inverse.json"
    source.write_text(json.dumps(config))
    monkeypatch.setattr("dt_prototype.common.project.ProjectInputs.load",lambda *a: (_ for _ in ()).throw(AssertionError("geometry required")))
    out=pipeline.run_pipeline(source,tmp_path/"pipeline")
    manifest=load_json(out/"manifest.json")
    assert manifest["status"]=="complete"
    assert manifest["stages"]["energy"]["status"]=="skipped"


def test_simulation_adapter_covers_all_solver_cases_without_changing_outputs():
    config=load_json(ROOT/"configs/inverse_simulation_example.json")
    data=load_dataset(config,ROOT/"configs")
    assert len(data.series)==51 and len(data.observations)==612
    assert {v["building_id"] for v in data.series.values()}=={"1","18","19","20","21"}
    assert len({v["representation"] for v in data.series.values()}) >= 2


@pytest.fixture(scope="module")
def real_backends(tmp_path_factory):
    if not WORKER.exists():
        pytest.skip("optional OpenDSM worker environment not installed; see requirements-opendsm.txt")
    tmp=tmp_path_factory.mktemp("inverse_backends")
    config=settings("inverse_synthetic_example.json")
    out=run(tmp,config,"fit")
    return tmp,config,out


@pytest.mark.opendsm
def test_real_all_backends_fit_and_preserve_billing_energy(real_backends):
    _,_,out=real_backends
    manifest=load_json(out/"manifest.json")
    assert manifest["status"]=="complete"
    assert manifest["successful_models"]==4 and manifest["failed_models"]==0
    index=load_json(out/"model_index.json")
    billing=next(r for r in index["models"] if r["model_id"]=="opendsm_billing")
    training=load_json(out/billing["artifact"])["payload"]["training"]
    assert training["bills"]==12
    assert training["input_energy_kWh"]==pytest.approx(training["processed_energy_kWh"],abs=1e-8)
    metrics=pd.read_csv(out/"comparison_metrics.csv")
    assert metrics[metrics.split=="validation"].scored_observations.eq(12).all()


@pytest.mark.opendsm
def test_real_saved_models_reload_without_targets_or_refitting(real_backends):
    tmp,config,out=real_backends
    config=json.loads(json.dumps(config))
    data=pd.read_csv(config["source"]["observations"])
    data["energy_kWh"]=np.nan
    data["split"]="predict"
    path=tmp/"features_only.csv"
    data.to_csv(path,index=False)
    config["source"]["observations"]=str(path)
    config.update(operation="predict",model_dir=str(out))
    predicted=run(tmp,config,"prediction")
    a,b=pd.read_csv(out/"predictions.csv"),pd.read_csv(predicted/"predictions.csv")
    keys=["series_id","model_id","interval_start"]
    a=a.sort_values(keys).reset_index(drop=True)
    b=b.sort_values(keys).reset_index(drop=True)
    np.testing.assert_allclose(a.predicted_energy_kWh,b.predicted_energy_kWh,rtol=1e-12,atol=1e-10)
    assert b.observed_energy_kWh.isna().all()


@pytest.mark.opendsm
def test_real_billing_holdout_targets_never_enter_training(real_backends):
    tmp,_,reference=real_backends
    config=settings()
    config["models"]=[{"backend":"opendsm_billing","options":{"allow_disqualified":True}}]
    bills=pd.read_csv(config["source"]["observations"])
    bills.loc[bills.split=="validation","energy_kWh"]*=10
    path=tmp/"changed_bills.csv"
    bills.to_csv(path,index=False)
    config["source"]["observations"]=str(path)
    out=run(tmp,config,"changed_validation")
    a=pd.read_csv(reference/"predictions.csv")
    a=a[a.model_id=="opendsm_billing"]
    b=pd.read_csv(out/"predictions.csv")
    np.testing.assert_allclose(a.predicted_energy_kWh,b.predicted_energy_kWh,rtol=1e-12,atol=1e-8)
    bills.loc[3,"split"]="validation"
    bills.to_csv(path,index=False)
    rejected=run(tmp,config,"interleaved_bills")
    manifest=load_json(rejected/"manifest.json")
    assert manifest["status"]=="failed" and "contiguous block" in manifest["models"][0]["error"]
