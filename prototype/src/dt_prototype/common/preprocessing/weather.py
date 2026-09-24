"""EPW weather processing (FR-05, FR-08).

Migrated from ``reference_building.weather`` with the ``pvlib`` dependency
replaced by a built-in solar position algorithm (Spencer/NOAA formulations)
and an isotropic-sky transposition model. EXTENDED: weather can also be
fetched from the PVGIS API for arbitrary coordinates
(:func:`process_pvgis` / :func:`fetch_pvgis_epw`, standard library only).

The output of this module is a :class:`WeatherData` object that can be fully
serialised to CSV (+ JSON metadata sidecar), making the preprocessing →
simulation handoff explicit and inspectable.

All quantities are SI (temperatures in degrees Celsius, irradiance in W/m2,
pressure in Pa, humidity ratio in kg/kg).
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from dt_prototype.common.constants import GROUND_ALBEDO
from dt_prototype.common.input_validation import validate_calendar, validate_resolution

# EPW fixed field positions (EnergyPlus Auxiliary Programs specification)
_EPW_COLUMNS = {
    "temp_air": 6,  # dry bulb temperature [°C]
    "temp_dew": 7,  # dew point temperature [°C]
    "relative_humidity": 8,  # [%]
    "pressure": 9,  # atmospheric station pressure [Pa]
    "ghi": 13,  # global horizontal irradiance [Wh/m2]
    "dni": 14,  # direct normal irradiance [Wh/m2]
    "dhi": 15,  # diffuse horizontal irradiance [Wh/m2]
    "wind_direction": 20,  # [deg]
    "wind_speed": 21,  # [m/s]
    "opaque_sky_cover": 23,  # [tenths]
}


@dataclass
class WeatherData:
    """Container for processed, simulation-ready weather data.

    Attributes
    ----------
    df : pandas.DataFrame
        Time-indexed table. Base columns: ``temp_air``, ``temp_dew``,
        ``relative_humidity`` (0-1), ``pressure``, ``specific_humidity``,
        ``wind_speed``, ``ghi``, ``dni``, ``dhi``, ``sun_elevation``,
        ``sun_azimuth`` (compass, 0 = North, 90 = East). Irradiance-bin
        columns: ``poa_glob_az{az}_t{tilt}`` / ``poa_dir_az{az}_t{tilt}``
        for each azimuth bin at tilt 90 (vertical) plus the horizontal bin
        ``az0_t0``.
    latitude, longitude : float
        Site coordinates [deg].
    timezone : float
        UTC offset [h].
    time_steps_per_hour : int
        Temporal resolution (1 = hourly, 2 = 30 min, ...). FR-12.
    azimuth_subdivisions : int
        Number of vertical-surface azimuth bins.
    average_dt_air_sky : float
        Mean difference between outdoor air and apparent sky temperature [K],
        used by the 5R1C long-wave extra-flow term.
    """

    df: pd.DataFrame
    latitude: float
    longitude: float
    timezone: float
    time_steps_per_hour: int = 1
    azimuth_subdivisions: int = 8
    average_dt_air_sky: float = 11.0
    location_name: str = ""

    # ------------------------------------------------------------------ #
    # Convenience accessors
    # ------------------------------------------------------------------ #
    @property
    def n_steps(self) -> int:
        """Number of simulation time steps in the dataset."""
        return len(self.df)

    @property
    def timestep_seconds(self) -> float:
        """Duration of one simulation time step [s]."""
        return 3600.0 / self.time_steps_per_hour

    def irradiance_columns(self, azimuth: float, tilt: float) -> tuple[str, str]:
        """Return the (global, direct) POA column names of the bin closest to
        a surface with the given compass ``azimuth`` and ``tilt`` [deg]."""
        if tilt < 45.0:  # horizontal-ish surfaces map to the horizontal bin
            return "poa_glob_az0_t0", "poa_dir_az0_t0"
        bins = (np.arange(self.azimuth_subdivisions) * 360 / self.azimuth_subdivisions).astype(int)
        # circular distance to each bin centre
        dist = np.abs((bins - azimuth + 180.0) % 360.0 - 180.0)
        az_bin = int(bins[int(np.argmin(dist))])
        return f"poa_glob_az{az_bin}_t90", f"poa_dir_az{az_bin}_t90"

    # ------------------------------------------------------------------ #
    # Serialisation (FR-08)
    # ------------------------------------------------------------------ #
    def to_csv(self, csv_path: str | Path) -> None:
        """Serialise to ``<path>.csv`` plus a ``<path>.meta.json`` sidecar."""
        csv_path = Path(csv_path)
        self.df.to_csv(csv_path, index_label="time")
        meta = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "time_steps_per_hour": self.time_steps_per_hour,
            "azimuth_subdivisions": self.azimuth_subdivisions,
            "average_dt_air_sky": self.average_dt_air_sky,
            "location_name": self.location_name,
        }
        csv_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> "WeatherData":
        """Load a :class:`WeatherData` previously written by :meth:`to_csv`."""
        csv_path = Path(csv_path)
        df = pd.read_csv(csv_path, index_col="time", parse_dates=True)
        meta = json.loads(csv_path.with_suffix(".meta.json").read_text())
        return cls(df=df, **meta)


# ---------------------------------------------------------------------- #
# Solar geometry (replaces pvlib; Spencer 1971 / Duffie & Beckman)
# ---------------------------------------------------------------------- #
def solar_position(
    times: pd.DatetimeIndex, latitude: float, longitude: float, timezone: float
) -> tuple[np.ndarray, np.ndarray]:
    """Compute sun elevation and compass azimuth for local-standard-time stamps.

    Parameters
    ----------
    times : pandas.DatetimeIndex
        Local standard time stamps (start of interval; solar position is
        evaluated at the interval centre).
    latitude, longitude : float
        Site coordinates [deg] (longitude positive East).
    timezone : float
        UTC offset [h].

    Returns
    -------
    tuple of numpy.ndarray
        ``(elevation, azimuth)`` in degrees; azimuth is compass convention
        (0 = North, 90 = East, 180 = South).
    """
    lat = np.radians(latitude)
    doy = times.dayofyear.to_numpy()
    # interval-centre clock time in hours
    hour = (
        times.hour.to_numpy()
        + times.minute.to_numpy() / 60.0
        + 0.5 / max(1, int(round(3600 / (times[1] - times[0]).total_seconds())))
    )
    gamma = 2.0 * np.pi * (doy - 1) / 365.0
    # Equation of time [min] and solar declination [rad] (Spencer 1971)
    eot = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.04089 * np.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )
    solar_time = hour + eot / 60.0 + (longitude - 15.0 * timezone) / 15.0
    omega = np.radians(15.0 * (solar_time - 12.0))  # hour angle

    sin_el = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(omega)
    elevation = np.degrees(np.arcsin(np.clip(sin_el, -1.0, 1.0)))
    # azimuth measured from South (positive towards West), then to compass
    az_south = np.degrees(
        np.arctan2(np.sin(omega), np.cos(omega) * np.sin(lat) - np.tan(decl) * np.cos(lat))
    )
    azimuth = (az_south + 180.0) % 360.0
    return elevation, azimuth


def tilted_irradiance(
    elevation: np.ndarray,
    sun_azimuth: np.ndarray,
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    tilt: float,
    surface_azimuth: float,
    albedo: float = GROUND_ALBEDO,
) -> tuple[np.ndarray, np.ndarray]:
    """Plane-of-array irradiance with the isotropic-sky model.

    Parameters
    ----------
    elevation, sun_azimuth : numpy.ndarray
        Sun position [deg] (azimuth in compass convention).
    ghi, dni, dhi : numpy.ndarray
        Horizontal global, normal direct, horizontal diffuse irradiance [W/m2].
    tilt : float
        Surface tilt from horizontal [deg] (90 = vertical).
    surface_azimuth : float
        Surface compass azimuth [deg].
    albedo : float
        Ground reflectance [-].

    Returns
    -------
    tuple of numpy.ndarray
        ``(poa_global, poa_direct)`` [W/m2].
    """
    zen = np.radians(90.0 - elevation)
    beta = np.radians(tilt)
    cos_aoi = np.cos(zen) * np.cos(beta) + np.sin(zen) * np.sin(beta) * np.cos(
        np.radians(sun_azimuth - surface_azimuth)
    )
    # beam only when the sun is above the horizon and in front of the surface
    up = elevation > 1.0
    poa_direct = np.where(up, dni * np.clip(cos_aoi, 0.0, None), 0.0)
    poa_diffuse = dhi * (1.0 + np.cos(beta)) / 2.0
    poa_reflected = ghi * albedo * (1.0 - np.cos(beta)) / 2.0
    poa_global = poa_direct + poa_diffuse + poa_reflected
    return poa_global, poa_direct


def _specific_humidity(t_air: np.ndarray, rh: np.ndarray, pressure: np.ndarray) -> np.ndarray:
    """Humidity ratio [kg_vapour/kg_dry_air] from temperature, RH (0-1), pressure.

    Saturation pressure correlations as in the retained reference (``reference_building.weather``).
    """
    p_sat = np.where(
        t_air > 0.0,
        610.5 * np.exp(17.269 * t_air / (237.3 + t_air)),
        610.5 * np.exp(21.875 * t_air / (265.5 + t_air)),
    )
    return 0.622 * rh * p_sat / (pressure - rh * p_sat)


def _sky_temperature(t_air: np.ndarray) -> np.ndarray:
    """Apparent sky temperature [°C] via the VDI 6007 long-wave model
    (migrated from ``reference_building._VDI6007_auxiliary_functions.long_wave_radiation``,
    clear-sky case)."""
    e_atm = 9.9 * 5.671e-14 * (273.15 + t_air) ** 6
    return ((e_atm / (0.93 * 5.67)) ** 0.25) * 100.0 - 273.15


# ---------------------------------------------------------------------- #
# EPW ingestion
# ---------------------------------------------------------------------- #
def read_epw_text(text: str, year: int = 2023) -> tuple[pd.DataFrame, dict]:
    """Parse EPW file content (string) into an hourly DataFrame + metadata.

    Parameters
    ----------
    text : str
        Full EPW file content (as downloaded from PVGIS, for instance).
    year : int
        Calendar year used to build the (non-leap) DatetimeIndex.

    Returns
    -------
    tuple
        ``(df, meta)`` where ``df`` has 8760 hourly rows and ``meta`` holds
        ``location``, ``latitude``, ``longitude``, ``timezone``.
    """
    validate_calendar(year)
    lines = text.splitlines()
    header = lines[0].strip().split(",") if lines else []
    if len(header) < 10 or header[0].upper() != "LOCATION":
        raise ValueError("Not a valid EPW content (missing LOCATION header)")
    meta = {
        "location": header[1],
        "latitude": float(header[6]),
        "longitude": float(header[7]),
        "timezone": float(header[8]),
    }
    raw = pd.read_csv(io.StringIO(text), skiprows=8, header=None)
    if len(raw) != 8760:
        raise ValueError(f"EPW content has {len(raw)} data rows, expected 8760")
    if raw.shape[1] <= max(_EPW_COLUMNS.values()):
        raise ValueError("EPW content is missing required weather columns")
    index = pd.date_range(start=f"{year}-01-01 00:00", periods=8760, freq="h")
    # TMY years may vary, but month/day/hour must describe one ordered year.
    expected = np.column_stack((index.month, index.day, index.hour + 1))
    if not np.array_equal(raw.iloc[:, 1:4].to_numpy(dtype=float), expected):
        raise ValueError("EPW month/day/hour must be an ordered non-leap year with hours 1..24")
    df = pd.DataFrame(
        {name: raw.iloc[:, col].to_numpy(dtype=float) for name, col in _EPW_COLUMNS.items()},
        index=index,
    )
    df["relative_humidity"] = df["relative_humidity"] / 100.0  # [%] -> [0-1]
    # Reject missing sentinels in quantities used by the engines. Unused sky
    # cover fields may legitimately carry a missing code.
    bounds = {"temp_air": (-70, 70), "temp_dew": (-70, 70),
              "relative_humidity": (0, 1), "pressure": (31000, 120000),
              "ghi": (0, 9998), "dni": (0, 9998), "dhi": (0, 9998),
              "wind_speed": (0, 40)}
    for name, (lower, upper) in bounds.items():
        invalid = ~np.isfinite(df[name]) | ~df[name].between(lower, upper)
        if invalid.any():
            row = int(np.flatnonzero(invalid.to_numpy())[0]) + 9
            raise ValueError(f"EPW {name} contains missing or out-of-range data at line {row}")
    for key, bound in (("latitude", 90), ("longitude", 180), ("timezone", 12)):
        if not np.isfinite(meta[key]) or abs(meta[key]) > bound:
            raise ValueError(f"EPW LOCATION has invalid {key}")
    return df, meta


def read_epw(path: str | Path, year: int = 2023) -> tuple[pd.DataFrame, dict]:
    """Read an EnergyPlus EPW file into an hourly DataFrame plus site metadata.

    Parameters
    ----------
    path : str or pathlib.Path
        EPW file path.
    year : int
        Calendar year used to build the (non-leap) DatetimeIndex.

    Returns
    -------
    tuple
        ``(df, meta)`` — see :func:`read_epw_text`.
    """
    return read_epw_text(Path(path).read_text(encoding="latin-1"), year=year)


# PVGIS TMY endpoint (the retained reference ``WeatherFile.from_pvgis``)
PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/tmy?lat={lat:.4f}&lon={lon:.4f}&outputformat=epw"


def fetch_pvgis_epw(
    latitude: float, longitude: float, cache_path: str | Path | None = None
) -> str:
    """Download a typical meteorological year EPW from PVGIS (EXTENDED).

    Migrated from the retained reference ``WeatherFile.from_pvgis``, using the standard
    library instead of ``requests``. When ``cache_path`` exists it is read
    instead of contacting the API; downloads are cached there.

    Parameters
    ----------
    latitude, longitude : float
        Site coordinates [deg] (longitude positive East).
    cache_path : str or pathlib.Path, optional
        File used to cache the downloaded EPW content.

    Returns
    -------
    str
        EPW file content.
    """
    import urllib.request

    if cache_path is not None and Path(cache_path).exists():
        return Path(cache_path).read_text(encoding="latin-1")
    url = PVGIS_URL.format(lat=latitude, lon=longitude)
    with urllib.request.urlopen(url, timeout=60) as response:
        text = response.read().decode()
    if cache_path is not None:
        Path(cache_path).write_text(text, encoding="latin-1")
    return text


def process_epw(
    path: str | Path,
    year: int = 2023,
    time_steps_per_hour: int = 1,
    azimuth_subdivisions: int = 8,
) -> WeatherData:
    """Full weather preprocessing: EPW → simulation-ready :class:`WeatherData`.

    Computes psychrometrics, solar position, and plane-of-array irradiance for
    ``azimuth_subdivisions`` vertical bins plus the horizontal bin; optionally
    interpolates to sub-hourly resolution (FR-12).

    Parameters
    ----------
    path : str or pathlib.Path
        EPW file path.
    year : int
        Reference (non-leap) year for the time index.
    time_steps_per_hour : int
        1 for hourly, n for sub-hourly (linear interpolation).
    azimuth_subdivisions : int
        Number of vertical-surface azimuth bins (the retained reference default: 8).

    Returns
    -------
    WeatherData
    """
    df, meta = read_epw(path, year=year)
    return _process_weather(df, meta, time_steps_per_hour, azimuth_subdivisions)


def process_pvgis(
    latitude: float,
    longitude: float,
    year: int = 2023,
    time_steps_per_hour: int = 1,
    azimuth_subdivisions: int = 8,
    cache_path: str | Path | None = None,
) -> WeatherData:
    """Weather preprocessing from PVGIS TMY data (EXTENDED).

    Same output as :func:`process_epw`, but the EPW content is fetched from
    the PVGIS API for the given coordinates (cached in ``cache_path`` when
    provided) instead of a local file.

    Parameters
    ----------
    latitude, longitude : float
        Site coordinates [deg].
    year : int
        Reference (non-leap) year for the time index.
    time_steps_per_hour : int
        1 for hourly, n for sub-hourly (FR-12).
    azimuth_subdivisions : int
        Number of vertical-surface azimuth bins.
    cache_path : str or pathlib.Path, optional
        Cache file for the downloaded EPW.

    Returns
    -------
    WeatherData
    """
    text = fetch_pvgis_epw(latitude, longitude, cache_path=cache_path)
    df, meta = read_epw_text(text, year=year)
    return _process_weather(df, meta, time_steps_per_hour, azimuth_subdivisions)


def _process_weather(
    df: pd.DataFrame, meta: dict, time_steps_per_hour: int, azimuth_subdivisions: int
) -> WeatherData:
    """Shared weather processing: psychrometrics, solar, irradiance bins."""
    validate_resolution(time_steps_per_hour, azimuth_subdivisions)
    df["specific_humidity"] = _specific_humidity(
        df["temp_air"].to_numpy(), df["relative_humidity"].to_numpy(), df["pressure"].to_numpy()
    )

    elevation, azimuth = solar_position(
        df.index, meta["latitude"], meta["longitude"], meta["timezone"]
    )
    df["sun_elevation"] = elevation
    df["sun_azimuth"] = azimuth

    ghi = df["ghi"].to_numpy()
    dni = df["dni"].to_numpy()
    dhi = df["dhi"].to_numpy()
    # Vertical bins around the compass + one horizontal bin (as in the retained reference)
    for az in (np.arange(azimuth_subdivisions) * 360 / azimuth_subdivisions).astype(int):
        glob, direct = tilted_irradiance(elevation, azimuth, ghi, dni, dhi, 90.0, float(az))
        df[f"poa_glob_az{az}_t90"] = glob
        df[f"poa_dir_az{az}_t90"] = direct
    glob_h, dir_h = tilted_irradiance(elevation, azimuth, ghi, dni, dhi, 0.0, 0.0)
    df["poa_glob_az0_t0"] = glob_h
    df["poa_dir_az0_t0"] = dir_h

    if time_steps_per_hour > 1:
        freq = f"{int(round(60 / time_steps_per_hour))}min"
        # extend by one hour so the last sub-hourly steps exist, then trim
        df = df.reindex(
            pd.date_range(df.index[0], periods=8760 * time_steps_per_hour, freq=freq)
        ).interpolate(method="linear", limit_direction="both")

    dt_sky = float(np.mean(df["temp_air"].to_numpy() - _sky_temperature(df["temp_air"].to_numpy())))
    return WeatherData(
        df=df,
        latitude=meta["latitude"],
        longitude=meta["longitude"],
        timezone=meta["timezone"],
        time_steps_per_hour=time_steps_per_hour,
        azimuth_subdivisions=azimuth_subdivisions,
        average_dt_air_sky=dt_sky,
        location_name=meta["location"],
    )
