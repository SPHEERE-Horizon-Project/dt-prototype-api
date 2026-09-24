"""Independent DT-Prototype dynamic RC launcher."""

import sys

from dt_prototype.cli import main


if __name__ == "__main__":
    main(["dynamic", *sys.argv[1:]])
