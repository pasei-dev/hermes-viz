"""Put the repo root on ``sys.path`` so ``python.derive`` and ``python.viz_dsl`` import directly.

Loaded by pytest automatically, and imported by ``run_all.py`` for the pytest-less run.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
