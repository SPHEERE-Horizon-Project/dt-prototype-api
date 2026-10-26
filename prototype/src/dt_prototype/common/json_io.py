"""Strict UTF-8 JSON input, including files saved with a UTF-8 BOM.

Duplicate settings and nonfinite numbers must fail before defaults or numerical
calculation can hide an input error. This reader does not change valid values.
"""
import json
import math
from pathlib import Path


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"non-finite JSON number: {value}")
        return number

    def invalid(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique, parse_float=finite,
                      parse_constant=invalid)
