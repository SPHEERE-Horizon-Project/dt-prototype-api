"""Reproducible Monthly_SS_VBDD runner consuming shared or monthly inputs."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import pandas as pd
from dt_prototype.common.project import ProjectInputs
from dt_prototype.monthly_ss.simulation.config import SimulationConfig
from . import __version__
from .model import MonthlyInput, VBOptions, simulate
from .preprocessing import prepare_building
from .weather import monthly_weather, orientation_multipliers, temperature_linear_solar


def main(argv=None):
    parser = argparse.ArgumentParser(description='Monthly_SS_VBDD monthly sensible demand')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--config', type=Path)
    source.add_argument('--monthly-inputs', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--energy-config', type=Path, help='Apply shared systems/carriers; requires --config')
    parser.add_argument('--utilisation', choices=['monthly_balance','fixed'], default='monthly_balance')
    parser.add_argument('--solar', choices=['direct','temperature_linear'], default='direct')
    parser.add_argument('--eta-heating', type=float, default=1.0)
    parser.add_argument('--eta-cooling', type=float, default=1.0)
    parser.add_argument('--attenuation-heating', type=float, default=0.0)
    parser.add_argument('--attenuation-cooling', type=float, default=0.0)
    args = parser.parse_args(argv)
    options = VBOptions(args.utilisation, args.eta_heating, args.eta_cooling,
                        args.attenuation_heating, args.attenuation_cooling)
    if args.energy_config:
        if not args.config:
            parser.error('--energy-config requires --config for common DHW, electrical and renewable inputs')
        from dt_prototype.energy_carriers.workflow import run_project
        run_project(args.config,args.energy_config,args.output,engine='Monthly_SS_VBDD',vb_solar=args.solar,vb_options=options)
        return
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite {out}')
    if args.config:
        project = ProjectInputs.load(args.config)
        district = project.preprocess()
        config = SimulationConfig(**{k:tuple(v) if k.endswith('_season') else v for k,v in project.configuration['operating'].items()})
        rows = [r for b in district.buildings for r in prepare_building(b,district.weather,config)]
        hashes = project.hashes()
        weather = monthly_weather(district.weather)
    else:
        rows = [MonthlyInput(**row) for row in json.loads(args.monthly_inputs.read_text(encoding='utf-8'))]
        hashes = {'monthly_inputs':hashlib.sha256(args.monthly_inputs.read_bytes()).hexdigest()}
        weather = None
    fit = None
    if args.solar == 'temperature_linear':
        rows, fit = temperature_linear_solar(rows)
    result = simulate(rows, options)
    out.mkdir(parents=True)
    (out/'monthly_inputs.json').write_text(json.dumps([asdict(r) for r in rows],indent=2), encoding='utf-8')
    result.to_csv(out/'monthly.csv',index=False)
    result.groupby(['case_id','building_name','representation'])[['zone_heating_kWh','zone_cooling_kWh','ahu_heating_kWh','ahu_cooling_kWh','heating_kWh','cooling_kWh']].sum().to_csv(out/'annual.csv')
    individual = result[result.representation.isin(['individual_zone','native_single_zone'])]
    sums = individual.groupby(['building_id','building_name','period_id'])[['zone_heating_kWh','zone_cooling_kWh','ahu_heating_kWh','ahu_cooling_kWh','heating_kWh','cooling_kWh']].sum().reset_index()
    sums.to_csv(out/'independent_zone_sum_monthly.csv',index=False)
    if weather is not None:
        weather.to_csv(out/'monthly_weather.csv',index=False)
        orientation_multipliers(weather).to_csv(out/'orientation_multipliers.csv',index=False)
    if fit is not None:
        fit.to_csv(out/'solar_fit.csv',index=False)
    manifest = dict(status='complete', engine='Monthly_SS_VBDD',
                    version=__version__,timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    input_hashes=hashes,options=asdict(options),solar=args.solar,
                    python=sys.version,
                    dependencies={name:importlib.metadata.version(name) for name in ('numpy','pandas')},
                    configuration=project.configuration if args.config else None,
                    boundary='useful_sensible_zone_plus_separate_ahu',
                    code_hashes={str(p.relative_to(Path(__file__).parents[1])):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parents[1].rglob('*.py')})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Monthly_SS_VBDD: {result.case_id.nunique()} cases, {len(result)} case-months; {out}')


if __name__ == '__main__':
    main()
