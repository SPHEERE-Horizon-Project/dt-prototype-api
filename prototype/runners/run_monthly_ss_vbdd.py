"""Run the Monthly_SS_VBDD component from a source checkout."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dt_prototype.monthly_ss_vbdd.cli import main

if __name__ == '__main__':
    main()
