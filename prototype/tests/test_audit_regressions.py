"""Regression coverage for failures found during the September 2026 audit."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dt_prototype.cli import main
from dt_prototype.common.output_paths import output_component
from dt_prototype.common.project import ProjectInputs
from dt_prototype.common.preprocessing.weather import process_epw, read_epw_text
from dt_prototype.common.preprocessing.schedules import expand_day_type_profiles
from dt_prototype.common.preprocessing.tabular_geometry import _text

ROOT = Path(__file__).resolve().parents[1]
EPW = ROOT / 'data/examples/ITA_Venezia-Tessera.161050_IGDG.epw'


@pytest.mark.parametrize('section,key,value', [
    ('inputs', 'calendar_year', 2024), ('inputs', 'calendar_year', True),
    ('inputs', 'time_steps_per_hour', 7), ('inputs', 'time_steps_per_hour', 1.5),
    ('inputs', 'time_steps_per_hour', True), ('inputs', 'azimuth_subdivisions', 0),
    ('operating', 'heating_season', [1, 366]), ('operating', 'heating_season', [1.5, 120]),
    ('operating', 'initial_temperature', float('nan')),
    ('operating', 'initial_specific_humidity', -0.1),
    ('dynamic', 'plants', 'false'), ('dynamic', 'sizing', 'typo'),
    ('dynamic', 'cooling_max_power', 100), ('simplified', 'zone_mode', 'typo'),
    ('simplified', 'comparison_mode', 'typo'),
])
def test_invalid_configuration_fails_before_reading_sources(tmp_path, section, key, value):
    config = json.loads((ROOT / 'configs/example.json').read_text())
    config[section][key] = value
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        ProjectInputs.load(path)


def test_leap_year_rejected_by_direct_readers():
    with pytest.raises(ValueError, match='non-leap'):
        read_epw_text(EPW.read_text(encoding='latin-1'), year=2024)
    with pytest.raises(ValueError, match='non-leap'):
        expand_day_type_profiles([1] * 24, [1] * 24, [1] * 24, year=2024)


@pytest.mark.parametrize('column,value,match', [(6, '99.9', 'temp_air'),
    (9, '999999', 'pressure'), (13, '9999', 'ghi'), (8, 'nan', 'relative_humidity'),
    (3, '2', 'month/day/hour')])
def test_bad_epw_records_are_not_silently_simulated(column, value, match):
    lines = EPW.read_text(encoding='latin-1').splitlines()
    row = lines[8].split(',')
    row[column] = value
    lines[8] = ','.join(row)
    with pytest.raises(ValueError, match=match):
        read_epw_text('\n'.join(lines))


def test_nondivisor_azimuth_bins_and_subhourly_clock_are_consistent():
    weather = process_epw(EPW, time_steps_per_hour=3, azimuth_subdivisions=7)
    for azimuth in range(360):
        for column in weather.irradiance_columns(azimuth, 90):
            assert column in weather.df.columns
    assert len(weather.df) == 8760 * 3
    assert weather.df.index[-1] == pd.Timestamp('2023-12-31 23:40')
    assert ((weather.df.index[1:] - weather.df.index[:-1]).total_seconds()
            == weather.timestep_seconds).all()


def test_missing_csv_cell_is_not_the_literal_string_none():
    with pytest.raises(ValueError, match='must not be empty'):
        _text({'zone_name': None}, 'zone_name', Path('zones.csv'), 2)


def test_portable_output_names_do_not_collapse_different_identities():
    values = ['../outside', r'C:\outside', 'A/B', 'A?B', 'CASE', 'case', 'CON', 'é' * 300]
    names = [output_component(value) for value in values]
    assert len(set(name.lower() for name in names)) == len(values)
    assert all(len(name) <= 49 and not any(c in name for c in '/\\:') for name in names)


@pytest.mark.parametrize('engine,flag,value', [('monthly', '--model', '5R1C'),
    ('dynamic', '--zone-mode', 'sum')])
def test_cli_rejects_ignored_engine_options(tmp_path, engine, flag, value):
    with pytest.raises(SystemExit) as error:
        main([engine, '--config', str(ROOT / 'configs/example.json'),
              '--output', str(tmp_path / 'unused'), flag, value])
    assert error.value.code == 2
    assert not (tmp_path / 'unused').exists()


def test_cli_safe_paths_hash_identity_and_failed_building_isolation(tmp_path, monkeypatch):
    import dt_prototype.monthly.run as monthly
    project = ProjectInputs.load(ROOT / 'configs/example.json')
    district = project.preprocess()
    district.buildings[0].geometry.name = '../outside'
    monkeypatch.setattr(ProjectInputs, 'preprocess', lambda self: district)
    original = monthly.run_building

    def run(building, *args, **kwargs):
        if building is district.buildings[1]:
            raise ValueError('injected solver failure')
        return original(building, *args, **kwargs)

    monkeypatch.setattr(monthly, 'run_building', run)
    output = tmp_path / 'run'
    with pytest.raises(SystemExit) as error:
        main(['monthly', '--config', str(ROOT / 'configs/example.json'), '--output', str(output)])
    assert error.value.code == 1
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['status'] == 'failed'
    assert len(manifest['failed_buildings']) == 1
    assert len(pd.read_csv(output / 'monthly.csv')) == 48
    assert not (tmp_path / 'outside_details.csv').exists()
    assert len(list(output.glob('*_details.csv'))) == 4
