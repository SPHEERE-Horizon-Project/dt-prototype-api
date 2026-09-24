"""Print an API example response as JSON, previewing long arrays."""

from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

import httpx

from spheere_dt_api.contract import openapi_spec

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "prototype/data/examples/ITA_Venezia-Tessera.161050_IGDG.epw"


def preview(value: object) -> object:
    """Preserve JSON values, replacing arrays of 20+ items with bounded previews."""
    if isinstance(value, dict):
        return {key: preview(item) for key, item in value.items()}

    if isinstance(value, list):
        if len(value) >= 10:
            return {
                "_truncated": True,
                "total_items": len(value),
                "first": [preview(item) for item in value[:2]],
                "last": [preview(item) for item in value[-2:]],
            }
        return [preview(item) for item in value]

    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", choices=("dynamic", "monthly", "simplified"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    example = openapi_spec()["components"]["examples"][f"{args.engine.title()}Request"]["value"]
    project = copy.deepcopy(example["project"])
    project["run_id"] = f"example_{args.engine}_{uuid.uuid4().hex[:12]}"
    try:
        with WEATHER.open("rb") as weather:
            response = httpx.post(
                f"{args.base_url.rstrip('/')}/runs/{args.engine}",
                files={
                    "project": (
                        "project.json",
                        json.dumps(project),
                        "application/json",
                    ),
                    "weather_epw": (WEATHER.name, weather, "text/plain"),
                },
                timeout=None,
            )
    except httpx.HTTPError as exc:
        raise SystemExit(str(exc)) from exc
    if response.status_code != 200:
        raise SystemExit(f"HTTP {response.status_code}: {response.text[:2000]}")
    result = response.json()
    print(json.dumps(preview(result), indent=2, ensure_ascii=False))
    if result["manifest"]["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
