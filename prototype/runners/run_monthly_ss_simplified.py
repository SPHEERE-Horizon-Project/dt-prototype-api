"""Launcher for the Monthly_SS_simplified solver and energy-signature workflow."""

import sys

from dt_prototype.cli import main


if __name__ == "__main__":
    main(["Monthly_SS_simplified", *sys.argv[1:]])
