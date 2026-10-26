"""Independent catalogue/quantity preparation before external assessment."""
import argparse
import json
from pathlib import Path
from .quantities import run_quantities


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs",type=Path,required=True,help="Quantity JSON or Excel input")
    parser.add_argument("--catalogue",type=Path,required=True,help="Asset definitions and quantity units")
    parser.add_argument("--config",type=Path,help="Shared project config for geometry/design estimates")
    parser.add_argument("--output",type=Path,required=True,help="New output directory")
    args = parser.parse_args(argv)
    out = run_quantities(args.inputs,args.catalogue,args.output,args.config)
    manifest = json.loads((out/"manifest.json").read_text())
    print(f"Asset quantities {manifest['status']}: {out}")
    if manifest["status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
