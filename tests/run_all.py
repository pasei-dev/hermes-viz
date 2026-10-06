"""Run the pytest-style tests without pytest.

The system ``python3`` (3.9.6) has no pytest, so this is the runner that proves the agent half on the
interpreter it has to work on:

    python3 tests/run_all.py

Pytest sees exactly the same functions.
"""

import importlib
import pathlib
import sys
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import conftest  # noqa: E402,F401  — puts the repo root on sys.path, same as under pytest


def main() -> int:
    ran = 0
    failures = []
    for path in sorted(HERE.glob("test_*.py")):
        module = importlib.import_module(path.stem)
        for name in sorted(vars(module)):
            if not name.startswith("test_"):
                continue
            func = getattr(module, name)
            if not callable(func):
                continue
            ran += 1
            try:
                func()
            except Exception:
                failures.append((path.stem, name, traceback.format_exc()))

    for module_name, test_name, detail in failures:
        print("FAIL %s::%s" % (module_name, test_name))
        print(detail)

    passed = ran - len(failures)
    print("%d passed, %d failed (python %s)" % (passed, len(failures), sys.version.split()[0]))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
