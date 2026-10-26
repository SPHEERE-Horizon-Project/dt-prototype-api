"""Building tables from map footprints: POST /geometry/from-footprints."""

from __future__ import annotations

from fastapi import FastAPI

from ..core import (
    Context,
    EmptyMetadata,
    Job,
    Part,
    ReadResult,
    RequestValues,
    Run,
    Tool,
    python,
    read_json,
    read_table,
    route,
    write_json,
)
from ..project import read_geometry

TOOL = Tool("footprints")
PARTS = {
    "run_id": Part("text", required=False),
    "footprints": Part("file"),
    "rules": Part("json"),
}
# DT Prototype ships this step as a runner script only, so call its function directly.
CALL = (
    "import sys\n"
    "from dt_prototype.common.preprocessing.cadastre import generate_cadastral_inputs\n"
    "generate_cadastral_inputs(*sys.argv[1:4])\n"
)


def stager(run: Run, values: RequestValues) -> Job[EmptyMetadata]:
    footprints = run.inputs / "footprints.geojson"
    footprints.write_bytes(values["footprints"])
    rules = run.inputs / "rules.json"
    write_json(rules, values["rules"])
    return Job(python("-c", CALL, str(footprints), str(rules), str(run.results)), {})


def reader(run: Run, meta: EmptyMetadata) -> ReadResult:
    manifest = read_json(run.results / "preprocessing_manifest.json", run.root)
    payload = {
        "manifest": manifest,
        "geometry": read_geometry(run.results / "geometry"),
        "report": read_table(run.results / "preprocessing_report.csv"),
    }
    return ReadResult.reported(payload, manifest.get("status"), {"complete": 0})


def register(app: FastAPI, context: Context) -> None:
    route(
        app,
        context,
        TOOL,
        "/geometry/from-footprints",
        "geometryFromFootprints",
        PARTS,
        stager,
        reader,
    )
