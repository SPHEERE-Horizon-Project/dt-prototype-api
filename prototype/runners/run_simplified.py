"""Independent DT-Prototype simplified Model 3 launcher."""

import sys

from dt_prototype.cli import main


if __name__ == "__main__":
    main(["simplified", *sys.argv[1:]])
