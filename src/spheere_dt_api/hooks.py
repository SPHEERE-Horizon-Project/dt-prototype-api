"""Hooks that every endpoint runs around a DT Prototype command.

Before hooks get the request parts before staging. After hooks get the result payload.
Each hook returns its input, changed or not, and decides for itself whether it applies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import RequestValues, Tool

type Before = Callable[[Tool, RequestValues], RequestValues]
type After = Callable[[Tool, dict[str, Any]], dict[str, Any]]

EPW_HEADER_LINES = 8
EPW_AIR_TEMPERATURE = 6
EPW_DEW_POINT = 7
EPW_WIND_SPEED = 21


def _within(field: str, lower: float, upper: float) -> bool:
    try:
        return lower <= float(field) <= upper
    except ValueError:
        return False


def repair_epw(tool: Tool, values: RequestValues) -> RequestValues:
    """Replace missing or out-of-range wind speed and dew point in the weather file.

    DT Prototype rejects them but never uses them. Wind speed becomes 0 and dew point
    becomes the air temperature; every other byte is kept. PVGIS files often have small
    negative wind speeds.
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
    return {**values, "weather_epw": "".join(lines).encode("latin-1")}


BEFORE: tuple[Before, ...] = (repair_epw,)
AFTER: tuple[After, ...] = ()
