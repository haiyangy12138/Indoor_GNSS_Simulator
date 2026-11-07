"""Run without installation: python simulate.py --config configs/default.json --output experiments/demo"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from indoor_gnss.cli import main
if __name__ == "__main__":
    main()
