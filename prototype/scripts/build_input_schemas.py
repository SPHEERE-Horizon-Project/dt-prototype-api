"""Generate the shipped JSON Schema 2020-12 contracts, without inspecting inputs.

Run after deliberate contract changes; tests verify the committed schemas match.
Semantic checks (references, calendars, units, model domains) remain in Python.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "src/dt_prototype/schemas/v1"
TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
NUMBER = {"type": "number"}
BOOL = {"type": "boolean"}
NONNEGATIVE = {"type": "number", "minimum": 0}
POSITIVE = {"type": "number", "exclusiveMinimum": 0}
FRACTION = {"type": "number", "minimum": 0, "maximum": 1}
VERSION = {"const": "1.0"}


def obj(properties, required=(), comments=False):
    result = {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}
    if comments:
        result["patternProperties"] = {"^_": {}}
    return result


def enum(*values):
    return {"enum": list(values)}


def array(items, minimum=1, maximum=None, unique=False):
    result = {"type": "array", "items": items, "minItems": minimum}
    if maximum is not None:
        result["maxItems"] = maximum
    if unique:
        result["uniqueItems"] = True
    return result


def mapping(items):
    return {"type": "object", "minProperties": 1, "additionalProperties": items,
            "propertyNames": TEXT}


def monthly(value):
    return {"anyOf": [value, array(value, 12, 12)]}


def library(wrapper, record):
    records = {**mapping(record), "patternProperties": {"^_": {}}}
    return {"oneOf": [obj({wrapper: records}, [wrapper], comments=True),
                       {**records, "not": {"required": [wrapper]}}]}


def contracts():
    project = obj({
        "schema_version": VERSION, "description": TEXT,
        "inputs": obj({**{k: TEXT for k in ["geometry", "weather_epw", "envelopes", "schedules", "systems"]},
            "geometry_format": enum("geojson", "tabular"),
            "calendar_year": {"type": "integer", "minimum": 1, "maximum": 9998},
            "time_steps_per_hour": enum(1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60),
            "azimuth_subdivisions": {"type": "integer", "minimum": 1, "maximum": 360}},
            ["geometry", "weather_epw", "envelopes", "schedules", "systems", "calendar_year", "time_steps_per_hour", "azimuth_subdivisions"]),
        "operating": obj({"heating_season": array({"type": "integer", "minimum": 1, "maximum": 365}, 2, 2),
            "cooling_season": array({"type": "integer", "minimum": 1, "maximum": 365}, 2, 2),
            "ahu_mode": enum("extended", "basic"), "initial_temperature": NUMBER, "initial_specific_humidity": NONNEGATIVE},
            ["heating_season", "cooling_season", "ahu_mode", "initial_temperature", "initial_specific_humidity"]),
        "dynamic": obj({"model": enum("5R1C", "7R2C", "1C", "2C"),
            **{k: BOOL for k in ["latent", "plants", "dhw_tank", "pv_battery"]}, "sizing": enum("static", "design_day"),
            "heating_max_power": {"anyOf": [NONNEGATIVE, {"type": "null"}]},
            "cooling_max_power": {"type": ["number", "null"], "maximum": 0}}, ["model"]),
        "simplified": obj({"zone_mode": enum("sum", "collapsed", "both"), "comparison_mode": enum("legacy", "seasonal_ahu")},
                          ["zone_mode", "comparison_mode"])}, ["schema_version", "inputs", "operating", "dynamic", "simplified"])
    metadata_fields = ["source_type", "source_id", "building_id", "scenario_id", "carrier", "meter_boundary_id", "weather_id"]
    metadata = obj({**{k: TEXT for k in metadata_fields + ["zone_id", "model", "representation", "description"]},
                    "source_type": enum("measured", "simulated")}, metadata_fields)
    cuts = {"train_end": TEXT, "validation_end": TEXT}
    csv_source = obj({"type": {"const": "csv"}, "observations": TEXT, "weather": TEXT, "series": mapping(metadata), **cuts},
                     ["type", "observations", "weather", "series"])
    simulation_source = obj({"type": enum("energy_run", "thermal_monthly"), "results": TEXT, "project_config": TEXT,
        "resolution": enum("monthly", "hourly"), "target": TEXT, "buildings": array(TEXT, unique=True),
        "models": array(TEXT, unique=True), "carrier": TEXT, "meter_boundary_id": TEXT, **cuts},
        ["type", "results", "project_config"])
    fit_fields = ["heating_change_point_min_C", "heating_change_point_max_C", "cooling_change_point_min_C",
                  "cooling_change_point_max_C", "change_point_step_C", "minimum_observations",
                  "minimum_regime_observations", "minimum_temperature_span_C", "coefficient_lower_bound"]
    model_variants = [enum("5p_monthly", "opendsm_billing", "opendsm_hourly")]
    for backend in ["5p_monthly", "opendsm_billing", "opendsm_hourly"]:
        options = {"fit": obj({k: NUMBER for k in fit_fields})} if backend == "5p_monthly" else {
            "seed": {"type": "integer"}, "allow_disqualified": BOOL}
        if backend == "opendsm_hourly":
            options["variant"] = enum("solar", "nonsolar")
        model_variants.append(obj({"backend": {"const": backend}, "options": obj(options)}, ["backend"]))
    inverse = obj({"schema_version": VERSION, "description": TEXT, "operation": enum("fit", "predict", "evaluate"),
        "source": {"oneOf": [csv_source, simulation_source]},
        "clock": obj({"convention": enum("standard", "civil", "utc"), "timezone": TEXT}, ["convention", "timezone"]),
        "models": array({"oneOf": model_variants}), "model_dir": TEXT, "opendsm_python": TEXT,
        "worker_timeout_s": {"type": "integer", "minimum": 1}}, ["schema_version", "source"])
    inverse["allOf"] = [
        {"if": {"properties": {"source": {"properties": {"type": {"const": "csv"}}}}}, "then": {"required": ["clock"]}},
        {"if": {"properties": {"operation": enum("predict", "evaluate")}, "required": ["operation"]},
         "then": {"required": ["model_dir"]}}]
    engine = enum("all", "Dynamic_RC", "Monthly_SS", "Monthly_SS_simplified", "Monthly_SS_VBDD")
    energy_stage = obj({"mode": enum("run", "reuse"), "engine": engine, "model": enum("5R1C", "7R2C"),
        "zone_mode": enum("sum", "collapsed", "both"), "vb_solar": enum("direct", "temperature_linear"), "results": TEXT,
        "vb_options": obj({"utilisation": enum("monthly_balance", "fixed"),
                           **{k: NUMBER for k in ["eta_heating", "eta_cooling", "attenuation_heating", "attenuation_cooling"]}})})
    assessment = obj({"enabled": BOOL, "modules": array(enum("LCC", "LCA", "MCI"), unique=True),
                      **{k: TEXT for k in ["assessment_id", "asset_results", "resolved_quantities", "design_note"]}})
    # Inactive assessment values are intentionally unfinished; match the runner.
    assessment = {"if": {"properties": {"enabled": {"const": True}}, "required": ["enabled"]},
        "then": {**assessment, "required": ["assessment_id", "asset_results"]},
        "else": obj({"enabled": BOOL, **{k: {} for k in assessment["properties"] if k != "enabled"}})}
    pipeline = {"oneOf": [
        obj({"schema_version": VERSION, "description": TEXT, "mode": {"const": "inverse"}, "inverse_config": TEXT},
            ["schema_version", "mode", "inverse_config"]),
        obj({"schema_version": VERSION, "description": TEXT, "mode": {"const": "forward"},
             "project_config": TEXT, "energy_config": TEXT, "energy": energy_stage, "assessment": assessment,
             "analysis": obj({"enabled": BOOL, "config": {} })}, ["schema_version", "project_config", "energy_config"])]}
    curve = obj({"coefficients": array(NUMBER, 1, 6), "temperature_min_C": NUMBER, "temperature_max_C": NUMBER,
                 "out_of_range": enum("clip", "error"), "source": TEXT},
                ["coefficients", "temperature_min_C", "temperature_max_C", "out_of_range", "source"])
    efficiency = {"type": "number", "exclusiveMinimum": 0, "maximum": 1}
    technology = {"carrier": TEXT, "performance": curve, "description": TEXT,
                  **{k: efficiency for k in ["distribution_efficiency", "emission_efficiency", "regulation_efficiency"]},
                  "auxiliary_kWh_per_kWh_generated": NONNEGATIVE}
    factor_names = ["primary_nonrenewable", "primary_renewable", "carbon_kgCO2e_per_kWh", "import_price_per_kWh",
                    "export_primary_nonrenewable", "export_primary_renewable", "export_carbon_kgCO2e_per_kWh", "export_price_per_kWh"]
    factors = {**{k: monthly(NUMBER if "price" in k else NONNEGATIVE) for k in factor_names}, "source": TEXT}
    pv = {"roof_coverage": FRACTION, "module_kWp_per_m2": NONNEGATIVE, "performance_ratio": FRACTION,
          "monthly_factor": monthly(FRACTION), "factor_basis": enum("overlap", "generation"), "source": TEXT}
    st = {"roof_coverage": FRACTION, "eta0": FRACTION, "a1_W_m2K": NONNEGATIVE, "a2_W_m2K2": NONNEGATIVE,
          "mean_fluid_temperature_C": NUMBER, "monthly_utilisation": monthly(FRACTION), "source": TEXT}
    services = {k: TEXT for k in ["zone_heating", "ahu_heating", "zone_cooling", "ahu_cooling", "dhw"]}
    plant = {"services": obj(services, services), "pv": obj(pv, pv), "solar_thermal": obj(st, st),
             "fan_W_per_m3_h": NONNEGATIVE, "base_auxiliary_W": NONNEGATIVE, "source": TEXT}
    energy = {"schema_version": VERSION, "scenario_id": TEXT, "description": TEXT, "currency": TEXT,
              "technologies": mapping(obj(technology, technology)), "carriers": mapping(obj(factors, factors)),
              "buildings": mapping(obj(plant, plant))}
    element = obj({"layers": array(obj({k: POSITIVE for k in ["thickness", "conductivity", "density", "specific_heat"]},
                                      ["thickness", "conductivity", "density", "specific_heat"])),
        "u_value": POSITIVE, "mass_class": enum("Very heavy", "Heavy", "Medium", "Light", "Very light"), "absorptance": FRACTION}, comments=True)
    element["anyOf"] = [{"required": ["layers"]}, {"required": ["u_value"]}]
    envelope = obj({**{k: element for k in ["ext_wall", "roof", "ground_floor", "int_wall", "int_ceiling", "int_floor"]},
        "window": obj({"u_value": POSITIVE, "shgc": FRACTION, "frame_factor": FRACTION, "shading_coef": FRACTION}, ["u_value", "shgc"]),
        "wwr": FRACTION, "infiltration_ach": NONNEGATIVE},
        ["ext_wall", "roof", "ground_floor", "int_wall", "int_ceiling", "window"], comments=True)
    profile = {"anyOf": [NUMBER, obj({**{k: array(NUMBER, 24, 24) for k in ["weekday", "weekend", "saturday", "sunday"]},
                                     "radiant_fraction": FRACTION}, ["weekday"])]}
    schedule = obj({**{k: profile for k in ["people", "appliances", "lighting", "people_latent", "heating_setpoint",
        "cooling_setpoint", "humidity_setpoint_low", "humidity_setpoint_high", "ventilation_ach", "infiltration_ach", "ventilation_flow_per_area"]},
        "dhw": obj({"method": enum("profile", "stochastic"), "profile": array(NONNEGATIVE, 24, 24),
                    "volume_per_m2_day": NONNEGATIVE, "flow_l_per_m2_h": profile}),
        "ahu": {"anyOf": [{"type": "null"}, obj({"sensible_recovery_eff": FRACTION, "latent_recovery_eff": FRACTION,
            "supply_temperature_heating": NUMBER, "supply_temperature_cooling": NUMBER,
            "supply_specific_humidity": NONNEGATIVE, "humidity_control": BOOL, "outdoor_air_ratio": efficiency})]},
        "natural_ventilation": {"anyOf": [{"type": "null"}, obj({"ach_max": NONNEGATIVE,
            "zone_temperature_threshold": NUMBER, "min_outdoor_temperature": NUMBER})]}}, comments=True)
    heating = {**{k: efficiency for k in ["emission_efficiency", "distribution_efficiency", "regulation_efficiency",
        "generation_efficiency", "dhw_emission_efficiency", "dhw_distribution_efficiency", "dhw_regulation_efficiency", "dhw_generation_efficiency"]},
        "convective_fraction": FRACTION, "cop": {"anyOf": [POSITIVE, {"type": "null"}]},
        "dhw_cop": {"anyOf": [POSITIVE, {"type": "null"}]},
        "fuel": enum("gas", "electric", "district_heat", "other_fuel"), "dhw_fuel": enum("gas", "electric", "district_heat", "other_fuel")}
    heating.update(description=TEXT, emitter={"anyOf": [TEXT, {"type": "null"}]}, emission_target_temperature={"type": ["number", "null"]})
    cooling = {k: heating[k] for k in ["convective_fraction", "emission_efficiency", "distribution_efficiency", "regulation_efficiency", "fuel", "description", "emitter"]}
    cooling["eer"] = POSITIVE
    systems = obj({"heating_systems": {**mapping(obj(heating, comments=True)), "patternProperties": {"^_": {}}},
                   "cooling_systems": {**mapping(obj(cooling, comments=True)), "patternProperties": {"^_": {}}}}, comments=True)
    observations = obj({"series_id": TEXT, "interval_start": TEXT, "interval_end": TEXT,
        "energy_kWh": {"anyOf": [NONNEGATIVE, {"type": "null"}]}, "duration_h": POSITIVE,
        "split": enum("train", "validation", "test", "excluded", "predict"), "quality": enum("valid", "missing", "excluded")},
        ["series_id", "interval_start", "interval_end"])
    weather = obj({"weather_id": TEXT, "time": TEXT, "temperature_C": NUMBER,
                   "ghi_Wm2": {"anyOf": [NONNEGATIVE, {"type": "null"}]}}, ["time", "temperature_C"])
    return {"project": project, "inverse": inverse, "pipeline": pipeline, "energy": obj(energy, energy),
            "envelopes": library("envelopes", envelope), "schedules": library("end_uses", schedule), "systems": systems,
            "observations-row": observations, "weather-row": weather}


def rendered():
    return {name: {"$schema": "https://json-schema.org/draft/2020-12/schema",
                   "$id": f"urn:dt-prototype:input:v1:{name}", "title": f"DT Prototype {name} contract v1",
                   **value} for name, value in contracts().items()}


if __name__ == "__main__":
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, value in rendered().items():
        (DESTINATION / f"{name}.schema.json").write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
