"""
settings.py - Benchmark configuration (config.toml) as a typed, read-only object, checked when it is loaded.

Where the data come from is the main choice ([inputs] source):
    "energy_insight"   the cleaned interim datasets of the energy_insight pipeline (default)
    "csv"              one plain CSV file per period: stand-alone use, no other program needed
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BENCHMARK_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = BENCHMARK_ROOT / "config.toml"

SOURCES = ("energy_insight", "csv")
VARIANTS = ("solar", "nonsolar")
CSV_KEYS = ("csv_file", "csv_timestamp", "csv_energy", "csv_temperature", "csv_ghi", "csv_use")


class ConfigError(ValueError):
    """The configuration file is inconsistent; the message lists every problem."""


def standard_time_zone(site_timezone: str, year: int = 2021):
    """Local STANDARD time of a site (its UTC offset without daylight saving time), as a time zone usable
    by pandas: 'Etc/GMT-1' for Europe/Rome (POSIX names have the opposite sign), a fixed offset for zones
    with a fractional offset (India, ...). OpenDSM works on days of 24 hours, which only a clock without
    daylight saving time offers."""
    zone = ZoneInfo(site_timezone)
    offsets = {datetime(year, month, 1, 12, tzinfo=zone).utcoffset() for month in range(1, 13)}
    standard = min(offsets)                                  # daylight saving time only adds to the offset
    hours = standard / timedelta(hours=1)
    if hours == int(hours):
        return "UTC" if hours == 0 else f"Etc/GMT{int(-hours):+d}"
    return timezone(standard)


@dataclass(frozen=True)
class Settings:
    config_path: Path
    root: Path                         # benchmark folder
    input_source: str                  # "energy_insight" | "csv"
    energy_insight_root: Path | None   # source = energy_insight
    inputs: dict[str, str]             # name -> path pattern (energy_insight: relative to energy_insight_root)
    csv: dict[str, str]                # source = csv: file pattern and column names
    periods: tuple[int, ...]
    site_timezone: str                 # clock of the energy data (daylight saving time)
    weather_label_marks: str           # "start" or "end" of the hour
    weather_clock: str                 # "UTC", "local" (= site clock) or a fixed-offset zone name
    model_timezone: object             # local standard time of the site (a time zone name or object)
    ghi_column: str
    temperature_column: str
    max_filled_hours_per_day: int
    seed: int
    is_electricity_data: bool
    ignore_disqualification: bool
    variants: tuple[str, ...]
    n_folds: int
    block_days: int
    results_dir: Path

    def input_path(self, name: str, period: int | None = None) -> Path:
        pattern = self.inputs[name]
        return self.energy_insight_root / (pattern.format(period=period) if period is not None else pattern)

    def csv_path(self, period: int) -> Path:
        return self.root / self.csv["csv_file"].format(period=period)

    def period_dir(self, period: int) -> Path:
        return self.results_dir / f"period_{period}"

    @property
    def summary_dir(self) -> Path:
        return self.results_dir / "summary"


def load_settings(path: str | Path = DEFAULT_CONFIG) -> Settings:
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"configuration file not found: {path}")
    root = path.parent
    with open(path, "rb") as f:
        c = tomllib.load(f)
    try:
        i, t, p, o, cv = c["inputs"], c["time"], c["preprocessing"], c["opendsm"], c["cross_validation"]
        source = i.get("source", "energy_insight")
        problems = _check(source, i, t, p, o, cv)
        if problems:
            raise ConfigError(f"{path}:\n  - " + "\n  - ".join(problems))
        site_tz = t["site_timezone"]
        model_tz = t["model_timezone"]
        if model_tz == "auto":
            model_tz = standard_time_zone(site_tz)
        return Settings(
            config_path=path, root=root, input_source=source,
            energy_insight_root=(root / i["energy_insight_root"]).resolve() if "energy_insight_root" in i else None,
            inputs={k: v for k, v in i.items() if k in ("energy_hourly", "climate_hourly", "model_dataset")},
            csv={k: i.get(k, "") for k in CSV_KEYS},
            periods=tuple(i["periods"]),
            site_timezone=site_tz,
            weather_label_marks=t["weather_label_marks"], weather_clock=t["weather_clock"],
            model_timezone=model_tz,
            ghi_column=p["ghi_column"], temperature_column=p["temperature_column"],
            max_filled_hours_per_day=p["max_filled_hours_per_day"],
            seed=o["seed"], is_electricity_data=o["is_electricity_data"],
            ignore_disqualification=o["ignore_disqualification"], variants=tuple(o["variants"]),
            n_folds=cv["n_folds"], block_days=cv["block_days"],
            results_dir=(root / c["output"]["results_dir"]).resolve(),
        )
    except KeyError as err:
        raise ConfigError(f"{path}: required key {err} is missing (compare with the config.toml of the "
                          "distribution)") from None


def _check(source, i, t, p, o, cv) -> list[str]:
    problems = []
    if source not in SOURCES:
        problems.append(f"[inputs] source must be one of {SOURCES}")
    if source == "energy_insight":
        for key in ("energy_insight_root", "energy_hourly", "climate_hourly", "model_dataset"):
            if key not in i:
                problems.append(f"[inputs] {key} is required when source = \"energy_insight\"")
    if source == "csv":
        for key in ("csv_file", "csv_timestamp", "csv_energy", "csv_temperature"):
            if not i.get(key):
                problems.append(f"[inputs] {key} is required when source = \"csv\"")
        if "{period}" not in i.get("csv_file", "{period}"):
            problems.append("[inputs] csv_file must contain {period} (one file per period)")
    if not i.get("periods"):
        problems.append("[inputs] periods must list at least one period")
    try:
        ZoneInfo(t["site_timezone"])
    except Exception:                                      # noqa: BLE001  unknown name or no tz database
        problems.append(f"[time] site_timezone {t['site_timezone']!r} is not an IANA time zone name "
                        "(e.g. 'Europe/Rome'; on Windows `pip install tzdata`)")
    if t["weather_label_marks"] not in ("start", "end"):
        problems.append('[time] weather_label_marks must be "start" or "end"')
    if t["model_timezone"] != "auto":
        try:
            ZoneInfo(t["model_timezone"])
        except Exception:                                  # noqa: BLE001
            problems.append('[time] model_timezone must be "auto" or a zone name such as "Etc/GMT-1"')
    unknown = [v for v in o["variants"] if v not in VARIANTS]
    if unknown or not o["variants"]:
        problems.append(f"[opendsm] variants must be a non-empty subset of {list(VARIANTS)}")
    if source == "csv" and not i.get("csv_ghi") and "solar" in o["variants"]:
        problems.append('[inputs] csv_ghi is empty (no irradiance): use variants = ["nonsolar"]')
    if cv["n_folds"] < 2 or cv["block_days"] < 1:
        problems.append("[cross_validation] n_folds must be >= 2 and block_days >= 1")
    return problems
