"""Shared energy-layer command, including an explicit example-config generator."""
import argparse
import json
from pathlib import Path
from dt_prototype.common.project import ProjectInputs
from dt_prototype.monthly_ss_vbdd import VBOptions
from .templates import example_configuration
from .workflow import run_project


def main(argv=None):
    p = argparse.ArgumentParser(description="Energy_carriers conversion, renewables and impacts after the thermal solvers")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--energy-config", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--write-example-energy-config", type=Path)
    p.add_argument("--engine", choices=["all", "Dynamic_RC", "Monthly_SS", "Monthly_SS_simplified", "Monthly_SS_VBDD"], default="all")
    p.add_argument("--model", choices=["5R1C", "7R2C"])
    p.add_argument("--zone-mode", choices=["sum", "collapsed", "both"], default="both")
    p.add_argument("--solar", choices=["direct", "temperature_linear"], default="direct")
    p.add_argument("--utilisation", choices=["monthly_balance", "fixed"], default="monthly_balance")
    p.add_argument("--eta-heating", type=float, default=1.0)
    p.add_argument("--eta-cooling", type=float, default=1.0)
    p.add_argument("--attenuation-heating", type=float, default=0.0)
    p.add_argument("--attenuation-cooling", type=float, default=0.0)
    args = p.parse_args(argv)
    if args.write_example_energy_config:
        path = args.write_example_energy_config
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}")
        energy = example_configuration(ProjectInputs.load(args.config).preprocess())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(energy.data, indent=2), encoding="utf-8")
        print(f"Wrote illustrative configuration: {path}")
        return
    if not args.energy_config or not args.output:
        p.error("--energy-config and --output are required for calculation")
    if args.model and args.engine != "Dynamic_RC":
        p.error("--model applies only to --engine Dynamic_RC; all runs both RC models")
    result = run_project(args.config, args.energy_config, args.output, engine=args.engine, model=args.model,
        zone_mode=args.zone_mode, vb_solar=args.solar,
        vb_options=VBOptions(args.utilisation, args.eta_heating, args.eta_cooling, args.attenuation_heating, args.attenuation_cooling))
    print(f"Shared energy calculation complete: {result}")


if __name__ == "__main__":
    main()
