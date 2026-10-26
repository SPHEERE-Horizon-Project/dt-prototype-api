"""Forward energy/assessment orchestration or independent inverse analysis.

No standalone valuation calculators or quantity-to-plant feedback are invoked.
The legacy component runners and their contracts remain independent.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path


MODULES = {"LCC", "LCA", "MCI"}
ENGINES = {"all", "Dynamic_RC", "Monthly_SS", "Monthly_SS_simplified", "Monthly_SS_VBDD"}


def _sha(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError(f"non-finite JSON value: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique, parse_constant=nonfinite)


def _keys(data, allowed, context):
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be an object")
    if set(data) - allowed:
        raise ValueError(f"{context}: unknown fields {sorted(set(data) - allowed)}")


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _path(base, value, label):
    path = Path(_text(value, label))
    return (base / path).resolve()


def load_configuration(path):
    """Resolve paths relative to this new configuration, not the working directory.

    Inactive assessment fields are deliberately not validated or opened.
    """
    source = Path(path).resolve()
    data = _json(source)
    if not isinstance(data, dict):
        raise ValueError("pipeline must be an object")
    if data.get("schema_version") != "1.0":
        raise ValueError("pipeline schema_version must be 1.0")
    base = source.parent
    if data.get("mode", "forward") == "inverse":
        _keys(data, {"schema_version", "description", "mode", "inverse_config"}, "inverse pipeline")
        return dict(source=source, mode="inverse", inverse_config=_path(base, data.get("inverse_config"), "inverse_config"))
    if data.get("mode", "forward") != "forward":
        raise ValueError("pipeline mode must be forward or inverse")
    _keys(data, {"schema_version", "description", "mode", "project_config", "energy_config", "energy", "assessment", "analysis"}, "pipeline")
    analysis = data.get("analysis", {})
    _keys(analysis, {"enabled", "config"}, "analysis")
    if type(analysis.get("enabled", False)) is not bool:
        raise ValueError("analysis.enabled must be boolean")
    analysis = dict(enabled=True, config=_path(base, analysis.get("config"), "analysis.config")) if analysis.get("enabled", False) else {"enabled":False}
    if analysis["enabled"]:
        # Fail before running physics if this stage would fit unrelated CSV data.
        inverse_settings = _json(analysis["config"])
        if not isinstance(inverse_settings, dict) or inverse_settings.get("source", {}).get("type") != "energy_run":
            raise ValueError("forward analysis requires source.type=energy_run")
    project = _path(base, data.get("project_config"), "project_config")
    energy_config = _path(base, data.get("energy_config"), "energy_config")
    energy = data.get("energy", {"mode": "run"})
    _keys(energy, {"mode", "results", "engine", "model", "zone_mode", "vb_solar", "vb_options"}, "energy")
    energy = dict(energy)
    mode = energy.get("mode", "run")
    if mode == "reuse":
        _keys(energy, {"mode", "results"}, "reuse energy")
        energy["results"] = _path(base, energy.get("results"), "energy.results")
    elif mode == "run":
        _keys(energy, {"mode", "engine", "model", "zone_mode", "vb_solar", "vb_options"}, "run energy")
        energy.setdefault("engine", "all")
        energy.setdefault("zone_mode", "both")
        energy.setdefault("vb_solar", "direct")
        if not isinstance(energy["engine"], str) or energy["engine"] not in ENGINES:
            raise ValueError("unknown energy.engine")
        if not isinstance(energy["zone_mode"], str) or energy["zone_mode"] not in {"sum", "collapsed", "both"}:
            raise ValueError("energy.zone_mode must be sum, collapsed or both")
        if not isinstance(energy["vb_solar"], str) or energy["vb_solar"] not in {"direct", "temperature_linear"}:
            raise ValueError("energy.vb_solar must be direct or temperature_linear")
        if energy.get("model") is not None and (energy["engine"] != "Dynamic_RC" or energy["model"] not in {"5R1C", "7R2C"}):
            raise ValueError("energy.model applies only to Dynamic_RC and must be 5R1C or 7R2C")
        # Reuse the existing parameter domain checks, before a long simulation.
        if "vb_options" in energy:
            from .monthly_ss_vbdd import VBOptions
            _keys(energy["vb_options"], {"utilisation", "eta_heating", "eta_cooling", "attenuation_heating", "attenuation_cooling"}, "vb_options")
            for key, value in energy["vb_options"].items():
                if key != "utilisation" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                    raise ValueError(f"{key} must be numeric")
            VBOptions(**energy["vb_options"])
    else:
        raise ValueError("energy.mode must be run or reuse")
    energy["mode"] = mode
    assessment = data.get("assessment", {})
    _keys(assessment, {"enabled", "modules", "assessment_id", "asset_results", "resolved_quantities", "design_note"}, "assessment")
    if type(assessment.get("enabled", False)) is not bool:
        raise ValueError("assessment.enabled must be boolean")
    if assessment.get("enabled", False):
        assessment = dict(assessment)
        modules = assessment.get("modules", ["LCC", "LCA", "MCI"])
        if (not isinstance(modules, list) or not modules or
                any(not isinstance(m, str) or m not in MODULES for m in modules) or
                len(modules) != len(set(modules))):
            raise ValueError("assessment.modules must be a non-empty unique list of LCC, LCA, MCI")
        assessment["modules"] = modules
        assessment["assessment_id"] = _text(assessment.get("assessment_id"), "assessment_id")
        assessment["asset_results"] = _path(base, assessment.get("asset_results"), "asset_results")
        if assessment.get("resolved_quantities") is not None:
            assessment["resolved_quantities"] = _path(base, assessment["resolved_quantities"], "resolved_quantities")
        if "design_note" in assessment:
            assessment["design_note"] = _text(assessment["design_note"], "design_note")
    else:
        assessment = {"enabled": False}
    return dict(source=source, mode="forward", project_config=project, energy_config=energy_config,
                energy=energy, assessment=assessment, analysis=analysis)


def _select_assets(settings):
    """Check CSV structure globally and the calculation contract for selected rows.

    Disabled known modules may contain unfinished numeric values. Unknown module
    identifiers are errors to prevent silently skipping a misspelled selection.
    """
    import pandas as pd
    from .assessment.contract import REQUIRED_COLUMNS, validate_asset_results

    raw = settings["asset_results"].read_bytes()
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if len(header) != len(set(header)) or set(header) != set(REQUIRED_COLUMNS):
            raise ValueError("asset CSV must have exactly the Assessment columns, without duplicate headers")
        rows = []
        present = set()
        for line, values in enumerate(reader, start=2):
            if not values:
                continue
            if len(values) != len(header):
                raise ValueError(f"asset CSV row {line} has the wrong field count")
            row = dict(zip(header, values))
            module = row["module"].strip()
            if module not in MODULES:
                raise ValueError(f"unknown asset module at CSV row {line}: {module!r}")
            present.add(module)
            if module in settings["modules"]:
                rows.append(row)
    frame = validate_asset_results(pd.DataFrame(rows, columns=REQUIRED_COLUMNS))
    if set(frame.assessment_id) != {settings["assessment_id"]}:
        raise ValueError("selected rows must all match the configured assessment_id")
    if settings.get("resolved_quantities") is not None:
        from .assessment.quantities import check_assessment_quantities
        check_assessment_quantities(frame, settings["resolved_quantities"])
    return frame, sorted(present - set(settings["modules"])), hashlib.sha256(raw).hexdigest()


def _simulation_code_hashes():
    """Reuse permits assessment/orchestrator development, not solver code drift."""
    root = Path(__file__).parent
    return {p.relative_to(root).as_posix(): _sha(p) for p in sorted(root.rglob("*.py"))
            if p.relative_to(root).parts[0] not in {"Assessment", "Inverse_models"}
            and p.relative_to(root).as_posix() not in {"pipeline.py", "validation.py"}}


def _verify_energy(directory, input_hashes, config_sha):
    """Require completed, compatible simulation provenance and resolved config."""
    from .energy_carriers.config import EnergyConfig

    directory = Path(directory).resolve()
    source = _json(directory / "manifest.json")
    if source.get("status") != "complete":
        raise ValueError("energy manifest must have status=complete")
    if source.get("input_hashes") != input_hashes:
        raise ValueError("energy project/input hashes differ from the pipeline project")
    if source.get("energy_config_sha256") != config_sha or EnergyConfig.load(directory / "energy_config_resolved.json").sha256 != config_sha:
        raise ValueError("energy configuration hashes differ from the pipeline configuration")
    recorded = {k.replace("\\", "/"): v for k, v in source.get("code_hashes", {}).items()}
    if any(recorded.get(k) != v for k, v in _simulation_code_hashes().items()):
        raise ValueError("energy simulation code hashes differ from current code")
    annual = directory / "energy_annual.csv"
    return {"directory": str(directory), "annual_sha256": _sha(annual),
            "manifest_sha256": _sha(directory / "manifest.json"),
            "resolved_config_sha256": _sha(directory / "energy_config_resolved.json"),
            "compatibility": "project_inputs, resolved_energy_configuration, simulation_code",
            "historical_result_authenticity": "annual bytes hashed at connection; legacy energy manifest has no annual output digest"}


def _coverage(aggregate, modules):
    """Completeness is bounded to declared selected buildings and result rows."""
    missing_modules = []
    for building in sorted(set(aggregate.building_id.astype(str))):
        found = set(aggregate.loc[aggregate.building_id.astype(str) == building, "module"])
        missing_modules.extend({"building_id": building, "module": m} for m in sorted(set(modules) - found))
    missing = int(aggregate.status.eq("missing").sum())
    return {"status": "incomplete" if missing or missing_modules else "complete",
            "scope": "declared_selected_rows_only; absent assets/indicators/buildings are not inferred",
            "missing_aggregate_rows": missing, "missing_requested_modules": missing_modules,
            "not_applicable_aggregate_rows": int(aggregate.status.eq("not_applicable").sum())}


def run_pipeline(configuration, output, *, progress=print):
    """Dispatch inverse-only, or run/reuse energy with optional assessment/analysis.

    A valid incomplete assessment is exported and returns an incomplete pipeline
    manifest. Invalid inputs raise with a failed manifest; energy is preserved.
    """
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": "1.0", "status": "running",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "pipeline_code_sha256": _sha(Path(__file__)),
                "stages": {"preflight": {"status": "running"}, "energy": {"status": "pending"},
                           "assessment": {"status": "pending"}}}

    def save():
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    stage = "preflight"
    save()
    try:
        settings = load_configuration(configuration)
        if settings["mode"] == "inverse":
            from .inverse_models.workflow import run_inverse
            manifest.update(mode="inverse", configuration_path=str(settings["source"]),
                            configuration_sha256=_sha(settings["source"]))
            manifest["stages"] = {"preflight":{"status":"complete"},
                "energy":{"status":"skipped", "reason":"inverse_only"},
                "assessment":{"status":"skipped", "reason":"inverse_only"}, "analysis":{"status":"running"}}
            stage = "analysis"
            save()
            result = run_inverse(settings["inverse_config"], out / "inverse")
            status = _json(result / "manifest.json")["status"]
            manifest["stages"][stage] = {"status":status, "directory":str(result)}
            manifest.update(status=status, completed_utc=datetime.now(timezone.utc).isoformat())
            save()
            return out
        from .common.project import ProjectInputs
        from .energy_carriers.config import EnergyConfig

        project = ProjectInputs.load(settings["project_config"])
        energy = EnergyConfig.load(settings["energy_config"])
        hashes = project.hashes()
        manifest.update(configuration_path=str(settings["source"]), configuration_sha256=_sha(settings["source"]),
                        project_config=str(settings["project_config"]), input_hashes=hashes,
                        energy_config=str(settings["energy_config"]), energy_config_sha256=energy.sha256,
                        energy_file_sha256=_sha(settings["energy_config"]),
                        resolved_settings=json.loads(json.dumps(settings, default=str)))
        selected = None
        assessment = settings["assessment"]
        manifest["stages"]["analysis"] = {"status":"pending" if settings["analysis"]["enabled"] else "skipped"}
        if assessment.get("enabled", False):
            quantity_hash = _sha(assessment["resolved_quantities"]) if assessment.get("resolved_quantities") is not None else None
            selected, skipped, asset_hash = _select_assets(assessment)
            (out / "inputs").mkdir()
            # Pin preflighted inputs for the downstream runner; edits during an
            # expensive simulation cannot silently change the assessed design.
            selected.to_csv(out / "inputs/selected_asset_results.csv", index=False)
            manifest["assessment_binding"] = {
                "assessment_id": assessment["assessment_id"], "building_ids": sorted(set(selected.building_id)),
                "modules_requested": assessment["modules"], "modules_present": sorted(set(selected.module)),
                "modules_skipped": skipped, "asset_results_path": str(assessment["asset_results"]),
                "asset_results_sha256": asset_hash,
                "selected_asset_results_sha256": _sha(out / "inputs/selected_asset_results.csv"),
                "design_note": assessment.get("design_note", "External assessment association declared by the user; physical plant quantities are not reconciled automatically"),
                "quantities_applied_to_simulation": False,
            }
            if assessment.get("resolved_quantities") is not None:
                import shutil
                shutil.copyfile(assessment["resolved_quantities"], out / "inputs/resolved_quantities.csv")
                if _sha(out / "inputs/resolved_quantities.csv") != quantity_hash:
                    raise ValueError("resolved quantities changed during preflight; rerun with stable inputs")
                manifest["assessment_binding"]["resolved_quantities_sha256"] = _sha(out / "inputs/resolved_quantities.csv")
        else:
            manifest["stages"]["assessment"] = {"status": "skipped", "reason": "disabled"}
        manifest["stages"]["preflight"]["status"] = "complete"
        stage = "energy"
        manifest["stages"][stage]["status"] = "running"
        save()
        options = settings["energy"]
        if options["mode"] == "run":
            from .energy_carriers.workflow import run_project
            from .monthly_ss_vbdd import VBOptions

            kwargs = {k: v for k, v in options.items() if k != "mode"}
            if "vb_options" in kwargs:
                kwargs["vb_options"] = VBOptions(**kwargs["vb_options"])
            energy_dir = run_project(settings["project_config"], settings["energy_config"], out / "energy", progress=progress, **kwargs)
        else:
            energy_dir = options["results"]
        manifest["energy_source"] = _verify_energy(energy_dir, hashes, energy.sha256)
        manifest["stages"][stage]["status"] = "complete" if options["mode"] == "run" else "reused"
        save()
        if selected is not None:
            from .assessment.workflow import run_assessment
            import pandas as pd

            stage = "assessment"
            manifest["stages"][stage]["status"] = "running"
            save()
            quantities = out / "inputs/resolved_quantities.csv" if assessment.get("resolved_quantities") is not None else None
            assessment_out = run_assessment(out / "inputs/selected_asset_results.csv", out / "assessment", energy_dir, quantities)
            aggregate = pd.read_csv(assessment_out / "building_asset_results.csv", dtype={"building_id": str}, keep_default_na=False)
            manifest["coverage"] = _coverage(aggregate, assessment["modules"])
            manifest["stages"][stage] = {"status": "complete", "directory": str(assessment_out),
                                         "coverage_status": manifest["coverage"]["status"]}
        manifest["status"] = "incomplete" if manifest.get("coverage", {}).get("status") == "incomplete" else "complete"
        if settings["analysis"]["enabled"]:
            from .inverse_models.workflow import run_inverse
            stage = "analysis"
            manifest["stages"][stage]["status"] = "running"
            save()
            result = run_inverse(settings["analysis"]["config"], out / "inverse", simulation_results=energy_dir)
            status = _json(result / "manifest.json")["status"]
            manifest["stages"][stage] = {"status":status, "directory":str(result)}
            if status != "complete":
                manifest["status"] = status
        manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        return out
    except Exception as error:
        manifest["status"] = "failed"
        manifest["stages"][stage] = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
        for record in manifest["stages"].values():
            if record["status"] == "pending":
                record["status"] = "not_run"
        manifest["error"] = f"{type(error).__name__}: {error}"
        save()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forward simulation with optional LCC/LCA/MCI and inverse analysis, or inverse-only fitting/prediction")
    parser.add_argument("--config", type=Path, required=True, help="Pipeline configuration JSON")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)
    try:
        out = run_pipeline(args.config, args.output)
    except Exception as error:
        parser.exit(1, f"Pipeline failed: {error}\n")
    status = _json(out / "manifest.json")["status"]
    print(f"Pipeline {status}: {out}")
    return 0 if status == "complete" else 1 if status == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
