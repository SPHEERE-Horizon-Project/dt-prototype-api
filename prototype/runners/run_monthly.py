"""Independent DT-Prototype monthly semi-stationary launcher."""

import sys

from dt_prototype.cli import main


if __name__ == "__main__":
    main(["monthly", *sys.argv[1:]])
