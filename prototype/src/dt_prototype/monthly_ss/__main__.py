"""Run the monthly engine through the shared DT-Prototype configuration."""

import sys

from dt_prototype.cli import main


if __name__ == "__main__":
    main(["monthly", *sys.argv[1:]])
