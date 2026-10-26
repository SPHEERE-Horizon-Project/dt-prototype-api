"""Read-only, consolidated preflight: schemas plus existing semantic readers.

Preprocessing expands weather/schedules and checks references; it never runs a
thermal solver, fits a regression, refreshes a workbook or writes simulation data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .common.json_io import load_json

SCHEMAS = Path(__file__).parent / "schemas/v1"


def schema_errors(value, kind):
    schema = load_json(SCHEMAS / f"{kind}.schema.json")
    errors = []
    for error in Draft202012Validator(schema).iter_errors(value):
        error = best_match([error])
        errors.append({"field": "/" + "/".join(str(p) for p in error.absolute_path),
                       "message": error.message[:500]})
    return errors


class Preflight:
    def __init__(self):
        self.checks = []

    def record(self, label, status, message, **details):
        self.checks.append(dict(check=label, status=status, message=message, **details))

    def attempt(self, label, operation):
        try:
            result = operation()
            self.record(label, "passed", "Validated")
            return result
        except Exception as error:
            self.record(label, "failed", f"{type(error).__name__}: {error}")
            return None

    def document(self, path, kind):
        path = Path(path).resolve()
        data = self.attempt(f"{path}: JSON", lambda: load_json(path))
        if data is None:
            self.record(f"{path}: document", "failed", "A readable JSON object is required; null is not a configuration")
            return None
        errors = schema_errors(data, kind)
        if errors:
            for error in errors:
                self.record(f"{path}: schema", "failed", error["message"], field=error["field"])
        else:
            self.record(f"{path}: schema", "passed", f"{kind} v1")
        return data

    def project(self, path):
        from .common.project import ProjectInputs
        data = self.document(path, "project")
        if isinstance(data, dict) and isinstance(data.get("inputs"), dict):
            for kind in ["envelopes", "schedules", "systems"]:
                value = data["inputs"].get(kind)
                if isinstance(value, str) and value:
                    self.document(Path(path).resolve().parent / value, kind)
        project = self.attempt(f"{path}: project references", lambda: ProjectInputs.load(path))
        if project:
            district = self.attempt(f"{path}: physical preprocessing", project.preprocess)
            if district:
                self.record("building coverage", "passed", "Prepared without a thermal solve",
                            buildings=[str(b.geometry.building_id) for b in district.buildings])
            return project, district
        return None, None

    def energy(self, path):
        from .energy_carriers.config import EnergyConfig
        self.document(path, "energy")
        return self.attempt(f"{path}: technology/carrier domains", lambda: EnergyConfig.load(path))

    def inverse(self, path, defer_simulation=False, simulation_results=None):
        from .inverse_models.adapters import load_dataset
        from .inverse_models.workflow import model_settings
        from .inverse_models.data import monthly, sha
        from .monthly_ss_simplified.five_parameter import FiveParameterConfig

        path = Path(path).resolve()
        data = self.document(path, "inverse")
        if not isinstance(data, dict):
            return
        models = self.attempt("inverse model options", lambda: model_settings(data.get("models", ["5p_monthly"])))
        if models:
            for model in models:
                if model["backend"] == "5p_monthly":
                    self.attempt("5P fit domains", lambda m=model: FiveParameterConfig(**m["options"].get("fit", {})).validate())
        dataset = None
        if defer_simulation:
            self.record("inverse simulation data", "deferred", "Will validate the new completed energy output after simulation")
        else:
            dataset = self.attempt("inverse intervals/weather/identity", lambda: load_dataset(data, path.parent, simulation_results))
        operation = data.get("operation", "fit")
        saved = {}
        if operation != "fit":
            def artifacts():
                directory = (path.parent / data["model_dir"]).resolve()
                index = load_json(directory / "model_index.json")
                if index.get("schema_version") != "1.0":
                    raise ValueError("unsupported model index")
                for entry in index["models"]:
                    file = (directory / entry["artifact"]).resolve()
                    if not file.is_relative_to(directory) or sha(file) != entry["sha256"]:
                        raise ValueError("model artifact path/hash mismatch")
                    artifact = load_json(file)
                    saved[(artifact["series_id"], artifact["model_id"])] = artifact
                if not saved:
                    raise ValueError("no saved models")
                if dataset:
                    for sid, metadata in dataset.series.items():
                        requested = models if "models" in data else [a for (s, _), a in saved.items() if s == sid]
                        if not requested:
                            raise ValueError(f"no saved models for {sid}")
                        for model in requested:
                            a = saved.get((sid, model["model_id"]))
                            if not a or a.get("schema_version") != "1.0" or a["clock"] != dataset.clock:
                                raise ValueError(f"saved model missing/schema/clock mismatch: {sid}")
                            for key in ["building_id", "zone_id", "carrier", "meter_boundary_id", "scenario_id", "representation"]:
                                if a["series"].get(key) != metadata.get(key):
                                    raise ValueError(f"saved model identity mismatch: {sid}/{key}")
                return True
            self.attempt("saved model integrity and identity", artifacts)
            if "models" not in data and saved:
                models = list({a["model_id"]: a for a in saved.values()}.values())
        if models and any(m["backend"].startswith("opendsm") for m in models):
            def worker():
                executable = (path.parent / data["opendsm_python"]).resolve()
                probe = subprocess.run([str(executable), "-c",
                    "import importlib.metadata as m; import pandas as p; "
                    "assert m.version('opendsm') == '1.2.7'; assert p.__version__.split('.')[0] == '2'; "
                    "print(m.version('opendsm'), p.__version__)"], capture_output=True, text=True, timeout=45)
                if probe.returncode:
                    raise ValueError(probe.stderr.strip() or "worker version check failed")
                return probe.stdout.strip()
            self.attempt("isolated worker imports/version", worker)
        if dataset and models:
            for sid in dataset.series:
                for model in models:
                    def coverage(m=model, s=sid):
                        frame = dataset.observations[dataset.observations.series_id.eq(s)]
                        backend = m["backend"]
                        if backend == "5p_monthly" or (backend == "opendsm_billing" and frame.duration_h.eq(1).all()):
                            frame = monthly(dataset, s)
                        if backend == "opendsm_hourly":
                            if not frame.duration_h.eq(1).all():
                                raise ValueError("hourly needs genuine one-hour intervals")
                            if m["options"].get("variant", "nonsolar") == "solar" and dataset.weather_for(s).ghi_Wm2.isna().any():
                                raise ValueError("solar hourly needs GHI throughout the requested weather period")
                        if backend == "opendsm_billing" and any(t != t.normalize() for t in list(frame.interval_start)+list(frame.interval_end)):
                            raise ValueError("billing boundaries must be local midnight")
                        eligible = frame.quality.eq("valid") & frame.energy_kWh.notna()
                        if operation == "evaluate" and not (eligible & ~frame.split.isin(["excluded", "predict"])).any():
                            raise ValueError("evaluate requires observed targets")
                        if operation == "fit":
                            train = frame[eligible & frame.split.eq("train")]
                            minimum = FiveParameterConfig(**m["options"].get("fit", {})).minimum_observations if backend == "5p_monthly" else 6 if backend == "opendsm_billing" else 24
                            if len(train) < minimum:
                                raise ValueError(f"needs at least {minimum} eligible training intervals")
                            if backend == "5p_monthly":
                                fit = FiveParameterConfig(**m["options"].get("fit", {}))
                                if train.temperature_C.max()-train.temperature_C.min() < fit.minimum_temperature_span_C:
                                    raise ValueError("training temperature span is below the declared 5P minimum")
                            if backend == "opendsm_billing" and any(a != b for a, b in zip(train.interval_start.iloc[1:], train.interval_end.iloc[:-1])):
                                raise ValueError("billing training must be contiguous")
                        return True
                    self.attempt(f"{sid}/{model['model_id']}: data readiness", coverage)
            self.record("fit qualification", "deferred", "Preflight cannot establish convergence, native qualification or prediction accuracy")

    def pipeline(self, path):
        from .pipeline import load_configuration, _select_assets, _verify_energy
        self.document(path, "pipeline")
        config = self.attempt("pipeline settings", lambda: load_configuration(path))
        if not config:
            return
        if config["mode"] == "inverse":
            self.inverse(config["inverse_config"])
            return
        project, district = self.project(config["project_config"])
        energy = self.energy(config["energy_config"])
        if energy and district:
            self.attempt("plant coverage for buildings", lambda: [energy.building(b.geometry.building_id) for b in district.buildings])
        if config["energy"]["mode"] == "reuse" and project and energy:
            self.attempt("reused energy provenance", lambda: _verify_energy(config["energy"]["results"], project.hashes(), energy.sha256))
        if config["assessment"]["enabled"]:
            self.attempt("external asset assessment", lambda: _select_assets(config["assessment"]))
        if config["analysis"]["enabled"]:
            if project:
                def matching_project():
                    from .common.project import ProjectInputs
                    file = config["analysis"]["config"]
                    settings = load_json(file)
                    inverse_project = ProjectInputs.load(file.parent/settings["source"]["project_config"])
                    if inverse_project.hashes() != project.hashes():
                        raise ValueError("inverse source project must match the forward project")
                self.attempt("forward/inverse project identity", matching_project)
            self.inverse(config["analysis"]["config"], defer_simulation=config["energy"]["mode"] == "run",
                         simulation_results=config["energy"].get("results"))


def preflight(configuration, kind="pipeline"):
    runner = Preflight()
    runner.attempt(f"{kind}: preflight completed", lambda: getattr(runner, kind)(Path(configuration).resolve()))
    failed = sum(c["status"] == "failed" for c in runner.checks)
    return dict(schema_version="1.0", created_utc=datetime.now(timezone.utc).isoformat(),
                configuration=str(Path(configuration).resolve()), kind=kind,
                status="failed" if failed else "passed", failed_checks=failed,
                scope="input readiness only; no simulation, fitting or accuracy certification", checks=runner.checks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--kind", choices=["pipeline", "project", "energy", "inverse"], default="pipeline")
    parser.add_argument("--report", type=Path, help="Optional new JSON file; existing files are not overwritten")
    args = parser.parse_args(argv)
    if args.report and args.report.exists():
        parser.error("report already exists")
    result = preflight(args.config, args.kind)
    text = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(text)
    return 1 if result["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
