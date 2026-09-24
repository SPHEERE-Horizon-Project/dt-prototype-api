"""Versioned shared input configuration for all DT-Prototype entry points."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from .input_validation import validate_calendar, validate_resolution
from .preprocessing.building_input import preprocess_district, preprocess_tabular_district
from .preprocessing.geometry import load_district_geojson
from .preprocessing.tabular_geometry import TABLE_FILENAMES, load_district_tables


def _path_hash(path: Path) -> str:
    """Hash a file or a directory deterministically, including relative names."""

    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
    return digest.hexdigest()

@dataclass(frozen=True)
class ProjectInputs:
    config_path: Path
    configuration: dict
    paths: dict[str, Path]

    @classmethod
    def load(cls, path):
        path=Path(path).resolve()
        configuration=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(configuration, dict):
            raise ValueError('Configuration must be a JSON object')
        if configuration.get('schema_version')!='1.0':
            raise ValueError('Expected input schema_version 1.0')
        for section in ['inputs', 'operating', 'dynamic', 'simplified']:
            if not isinstance(configuration.get(section), dict):
                raise ValueError(f'Missing configuration object {section}')
        data=configuration['inputs']
        for key in ['calendar_year','time_steps_per_hour','azimuth_subdivisions']:
            if key not in data:raise ValueError(f'Missing explicit input {key}')
        validate_calendar(data['calendar_year'])
        validate_resolution(data['time_steps_per_hour'], data['azimuth_subdivisions'])
        operating=configuration['operating']
        allowed_operating = {'heating_season', 'cooling_season', 'ahu_mode',
                             'initial_temperature', 'initial_specific_humidity'}
        if set(operating) - allowed_operating:
            raise ValueError(f'Unknown operating settings: {sorted(set(operating) - allowed_operating)}')
        for key in ['heating_season','cooling_season','ahu_mode','initial_temperature','initial_specific_humidity']:
            if key not in operating:raise ValueError(f'Missing explicit operating setting {key}')
        for key in ['heating_season','cooling_season']:
            if (not isinstance(operating[key], (list, tuple)) or len(operating[key])!=2
                    or any(type(d) is not int or not 1<=d<=365 for d in operating[key])):
                raise ValueError(f'Invalid {key}')
        if operating['ahu_mode'] not in ('extended', 'basic'):
            raise ValueError("operating.ahu_mode must be 'extended' or 'basic'")
        for key in ['initial_temperature', 'initial_specific_humidity']:
            value = operating[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'operating.{key} must be finite and numeric')
        if operating['initial_specific_humidity'] < 0:
            raise ValueError('initial_specific_humidity must be non-negative')
        dynamic = configuration['dynamic']
        allowed_dynamic = {'model', 'latent', 'plants', 'sizing', 'dhw_tank', 'pv_battery',
                           'heating_max_power', 'cooling_max_power'}
        if set(dynamic) - allowed_dynamic:
            raise ValueError(f'Unknown dynamic settings: {sorted(set(dynamic) - allowed_dynamic)}')
        if dynamic.get('model') not in ('5R1C', '7R2C', '1C', '2C'):
            raise ValueError('dynamic.model must be 5R1C or 7R2C (aliases 1C/2C)')
        if dynamic.get('sizing', 'design_day') not in ('design_day', 'static'):
            raise ValueError('dynamic.sizing must be design_day or static')
        for key in ['latent', 'plants', 'dhw_tank', 'pv_battery']:
            if key in dynamic and type(dynamic[key]) is not bool:
                raise ValueError(f'dynamic.{key} must be a JSON boolean')
        for key, sign in [('heating_max_power', 1), ('cooling_max_power', -1)]:
            value = dynamic.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or sign * value < 0):
                raise ValueError(f'dynamic.{key} must be finite with the correct sign, or null')
        simplified = configuration['simplified']
        if simplified.get('zone_mode') not in ('sum', 'collapsed', 'both'):
            raise ValueError('simplified.zone_mode must be sum, collapsed or both')
        if simplified.get('comparison_mode') not in ('legacy', 'seasonal_ahu'):
            raise ValueError('simplified.comparison_mode must be legacy or seasonal_ahu')
        for key in ['geometry', 'weather_epw', 'envelopes', 'schedules', 'systems']:
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError(f'Missing nonempty input path {key}')
        paths={k:(path.parent/data[k]).resolve() for k in ['geometry','weather_epw','envelopes','schedules','systems']}
        geometry_format=data.get('geometry_format')
        if geometry_format is None:
            geometry_format='tabular' if paths['geometry'].is_dir() else 'geojson'
            data['geometry_format']=geometry_format
        if geometry_format not in {'geojson','tabular'}:
            raise ValueError("inputs.geometry_format must be 'geojson' or 'tabular'")
        for key,file in paths.items():
            expected=file.is_dir() if key=='geometry' and geometry_format=='tabular' else file.is_file()
            if not expected:raise FileNotFoundError(f'{key}: {file}')
        if geometry_format=='tabular':
            for filename in TABLE_FILENAMES:
                if not (paths['geometry']/filename).is_file():
                    raise FileNotFoundError(f"geometry: missing {paths['geometry']/filename}")
            geometries=load_district_tables(paths['geometry'])
        else:
            geometries=load_district_geojson(paths['geometry'])
        ids=[str(geometry.building_id) for geometry in geometries]
        names=[str(geometry.name) for geometry in geometries]
        if not ids or any(not x.strip() for x in ids+names) or len(ids)!=len(set(ids)) or len(names)!=len(set(names)):
            raise ValueError('Building IDs and names must be nonempty and unique')
        return cls(path,configuration,paths)

    def preprocess(self):
        p=self.paths;cfg=self.configuration['inputs']
        preprocess = (
            preprocess_tabular_district
            if cfg['geometry_format']=='tabular'
            else preprocess_district
        )
        return preprocess(p['geometry'],p['weather_epw'],p['envelopes'],p['schedules'],
            systems_path=p['systems'],year=cfg['calendar_year'],
            time_steps_per_hour=cfg['time_steps_per_hour'],azimuth_subdivisions=cfg['azimuth_subdivisions'])

    def hashes(self):
        return {k:_path_hash(p) for k,p in {'configuration':self.config_path,**self.paths}.items()}
