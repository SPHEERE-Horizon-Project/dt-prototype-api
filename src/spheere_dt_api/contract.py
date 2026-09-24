"""Load the OpenAPI document and validate project requests."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import jsonschema
import yaml

SPEC_PATH = Path(__file__).resolve().parents[2] / "DT-PROTOTYPE-OPENAPI.yaml"
PROJECT_SCHEMAS = {
    "dynamic": "DynamicProject",
    "monthly": "MonthlyProject",
    "simplified": "SimplifiedProject",
}


@lru_cache(maxsize=1)
def openapi_spec() -> dict:
    """Load and cache the OpenAPI document."""
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=3)
def project_validator(engine: str) -> jsonschema.Draft202012Validator:
    """Build the project schema validator for one engine."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": {"schemas": openapi_spec()["components"]["schemas"]},
        "$ref": f"#/components/schemas/{PROJECT_SCHEMAS[engine]}",
    }
    return jsonschema.Draft202012Validator(schema)


def validate_project(engine: str, project: object) -> tuple[str, str] | None:
    """Return the first project validation error, if any."""
    errors = project_validator(engine).iter_errors(project)
    error = next(errors, None)
    if error is None:
        return None
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "project", error.message
