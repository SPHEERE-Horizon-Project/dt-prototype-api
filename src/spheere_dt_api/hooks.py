"""Hooks that every endpoint runs around a DT Prototype command.

Before hooks get the request parts before staging. After hooks get the result payload.
Both get the run, whose inputs folder can carry state from one to the other. Each hook
returns its input, changed or not, and decides for itself whether it applies.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import RequestValues, Run, Tool

type Before = Callable[[Tool, Run, RequestValues], RequestValues]
type After = Callable[[Tool, Run, dict[str, Any]], dict[str, Any]]

WEATHER_REPAIR = "weather_repair.json"
WEATHER_ID_PREFIX = "weather_"
WEATHER_ID_HASH_LENGTH = 16
EPW_HEADER_LINES = 8
EPW_AIR_TEMPERATURE = 6
EPW_DEW_POINT = 7
EPW_WIND_SPEED = 21


def _within(field: str, lower: float, upper: float) -> bool:
    try:
        return lower <= float(field) <= upper
    except ValueError:
        return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _weather_id(sha256: str) -> str:
    return WEATHER_ID_PREFIX + sha256[:WEATHER_ID_HASH_LENGTH]


def _replaced(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replaced(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replaced(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def repair_epw(tool: Tool, run: Run, values: RequestValues) -> RequestValues:
    """Replace missing or out-of-range wind speed and dew point in the weather file.

    DT Prototype rejects them but never uses them. Wind speed becomes 0 and dew point
    becomes the air temperature; every other byte is kept. PVGIS files often have small
    negative wind speeds. A changed file leaves both hashes in the run's inputs folder.
    """
    weather = values.get("weather_epw")
    if weather is None:
        return values
    lines = weather.decode("latin-1").splitlines(keepends=True)
    for index in range(EPW_HEADER_LINES, len(lines)):
        line = lines[index]
        body = line.rstrip("\r\n")
        fields = body.split(",")
        if len(fields) <= EPW_WIND_SPEED:
            continue
        if not _within(fields[EPW_WIND_SPEED], 0, 40):
            fields[EPW_WIND_SPEED] = "0.0"
        if not _within(fields[EPW_DEW_POINT], -70, 70):
            fields[EPW_DEW_POINT] = fields[EPW_AIR_TEMPERATURE]
        lines[index] = ",".join(fields) + line[len(body) :]
    repaired = "".join(lines).encode("latin-1")
    if repaired != weather:
        hashes = {"uploaded": _sha256(weather), "repaired": _sha256(repaired)}
        (run.inputs / WEATHER_REPAIR).write_text(json.dumps(hashes), encoding="utf-8")
    return {**values, "weather_epw": repaired}


def report_uploaded_weather(tool: Tool, run: Run, payload: dict[str, Any]) -> dict[str, Any]:
    """Report the uploaded weather file's hash and weather ID instead of the repaired file's."""
    path = run.inputs / WEATHER_REPAIR
    if not path.is_file():
        return payload
    hashes = json.loads(path.read_text(encoding="utf-8"))
    replacements = {
        hashes["repaired"]: hashes["uploaded"],
        _weather_id(hashes["repaired"]): _weather_id(hashes["uploaded"]),
    }
    return _replaced(payload, replacements)


BEFORE: tuple[Before, ...] = (repair_epw,)
AFTER: tuple[After, ...] = (report_uploaded_weather,)
