"""Portable output names, keeping user identifiers out of filesystem paths."""
import hashlib
import re


def output_component(value: object) -> str:
    """Return a bounded ASCII filename component with a stable identity suffix.

    The digest prevents collisions from punctuation removal and case folding.
    Original identifiers remain unchanged in result tables and manifests.
    """
    raw = str(value)
    label = re.sub(r'[^A-Za-z0-9_-]+', '-', raw).strip('-_')[:32] or 'item'
    return f"{label}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def validate_run_id(run_id: str) -> None:
    if (not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', run_id)
            or run_id.upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                 *(f'COM{i}' for i in range(1, 10)),
                                 *(f'LPT{i}' for i in range(1, 10))}):
        raise ValueError('run_id must be 1..64 letters/digits/underscores/hyphens, start with a letter or digit, and not be a reserved device name')
