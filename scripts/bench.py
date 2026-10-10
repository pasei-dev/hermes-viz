#!/usr/bin/env python3
"""The four cost axes of hermes-viz, measured.

    python3 scripts/bench.py

The plugin is a prompt on every request plus two shipped bundles, so its cost is
four numbers, not one:

  1. the **format guide's** prompt cost per request — chars, an estimated token
     count and the headroom under ``FORMAT_GUIDE_MAX_CHARS`` — for the groups a
     fresh install ships and for every group on.  Composed through the plugin's
     own ``format_guide_section``, never a second copy of the text.
  2. the **transform hook's** wall time per answer over the corpus ``tests/``
     already uses, run through the plugin's own hook entry point.
  3. the **desktop half's** size (bytes) and the milliseconds ``node`` takes to
     import the drawing core — a proxy for the mount's parse cost, not the app's
     load.
  4. the **dashboard bundle's** size (bytes).

Stdlib only — no third-party import, no network — and it must run on the agent
half's floor interpreter (3.10) as well as the newest release.  Every number
carries its unit and the command that produced it; an axis that cannot be
measured honestly prints as ``not measured: <why>``.
"""

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

#: The divisor the plugin itself uses for its live token read, `dashboard/plugin_api.py`: `round(len/4.05)`.
#: A second divisor here would make README's figures disagree with the settings chip on the same text.
TOKEN_DIVISOR = 4.05

#: The hook is timed over N iterations per corpus item.
HOOK_ITERATIONS = 100
#: The core is imported this many times; the fastest run is reported (node startup is noise otherwise).
IMPORT_ITERATIONS = 3


def _load_agent():
    """Load the plugin's root module the way the tests do (``tests/_agent.py``)."""
    spec = importlib.util.spec_from_file_location("hermes_viz_bench", ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


agent = _load_agent()


def _tokens(text):
    """The guide's estimated tokens, by the plugin's own divisor."""
    return round(len(text) / TOKEN_DIVISOR)


def axis1_guide():
    """The format guide's prompt cost per request, through the plugin's own composer."""
    rules = agent.load_rules(agent.RULES_PATH)
    every_on = agent.DEFAULT_RULE_GROUPS + "," + ",".join(agent.DEFAULT_RULE_GROUPS_OFF)
    cases = (
        ("shipped groups (every group on except %s)" % ",".join(agent.DEFAULT_RULE_GROUPS_OFF),
         agent.DEFAULT_RULE_GROUPS),
        ("every group on", every_on),
    )
    print("1. format guide — prompt cost per request")
    print("   method: __init__.format_guide_section(True, groups, rules) — the plugin's own composer")
    print("   tokens: chars / %.2f — the divisor dashboard/plugin_api.py uses for its live read"
          % TOKEN_DIVISOR)
    for label, groups in cases:
        text = agent.format_guide_section(True, groups, rules)
        chars = len(text)
        print("   %-46s %5d chars  ~%4d tokens  %5d chars headroom of %d"
              % (label, chars, _tokens(text), agent.FORMAT_GUIDE_MAX_CHARS - chars,
                 agent.FORMAT_GUIDE_MAX_CHARS))
    print("   command: python3 scripts/bench.py   (FORMAT_GUIDE_MAX_CHARS = %d at __init__.py)"
          % agent.FORMAT_GUIDE_MAX_CHARS)
    print()


def axis2_hook():
    """The transform hook's wall time per answer, over the corpus the tests already use."""
    import answers  # tests/answers.py — the fixtures the hook tests derive against

    rules = agent.load_rules(agent.RULES_PATH)
    hook = agent.make_hook(
        rules,
        groups=agent.DEFAULT_RULE_GROUPS,
        max_widgets=agent.DEFAULT_MAX_WIDGETS,
        palette=agent.DEFAULT_PALETTE,
    )
    corpus = (
        ("table + run (widgets)", answers.ANSWER_WITH_TABLE_AND_RUN),
        ("prose only", answers.PROSE_ONLY),
        ("code fence", answers.FENCED_CODE_ONLY),
    )
    print("2. transform hook — wall time per answer (N=%d iterations each)" % HOOK_ITERATIONS)
    print("   method: __init__.make_hook(rules, DEFAULT_RULE_GROUPS, DEFAULT_MAX_WIDGETS,"
          " DEFAULT_PALETTE)(text, platform=\"desktop\")")
    total_ms = 0.0
    for label, text in corpus:
        hook(text, platform="desktop")  # warm the caches before timing
        start = time.perf_counter()
        for _ in range(HOOK_ITERATIONS):
            hook(text, platform="desktop")
        ms_each = (time.perf_counter() - start) * 1000
        per_answer = ms_each / HOOK_ITERATIONS
        total_ms += ms_each
        print("   %-22s %7.3f ms/answer   %8.2f ms per %d" % (label, per_answer, ms_each, HOOK_ITERATIONS))
    print("   total: %.2f ms per %d answers (all three items)"
          % (total_ms, HOOK_ITERATIONS * len(corpus)))
    print("   command: python3 scripts/bench.py")
    print()


def axis3_desktop():
    """The desktop half's size, and the core's node import time as a parse proxy."""
    plugin = ROOT / "desktop" / "plugin.js"
    core = ROOT / "desktop" / "render" / "core.mjs"
    print("3. desktop half — size and core parse cost")
    for path in (plugin, core):
        print("   %-26s %8d bytes" % (path.relative_to(ROOT), path.stat().st_size))
    uri = core.as_uri()
    cmd = ["node", "--input-type=module", "-e", "await import(%r)" % uri]
    print("   command: %s" % " ".join(cmd))
    node = subprocess.run(["/usr/bin/env", "node", "--version"], capture_output=True, text=True)
    if node.returncode != 0:
        print("   core import: not measured: node not runnable on PATH (%s)"
              % (node.stderr.strip() or "exit %d" % node.returncode))
    else:
        times = []
        for _ in range(IMPORT_ITERATIONS):
            start = time.perf_counter()
            proc = subprocess.run(cmd, capture_output=True, text=True)
            times.append((time.perf_counter() - start) * 1000)
            if proc.returncode != 0:
                print("   core import: not measured: node exited %d: %s"
                      % (proc.returncode, proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""))
                break
        else:
            print("   core import: %.1f ms (fastest of %d, %s) — node startup included"
                  % (min(times), IMPORT_ITERATIONS, node.stdout.strip()))
    print("   note: the import time is a PROXY for the mount's parse cost, not the app's load —")
    print("   it times a bare process importing core.mjs, not the desktop app mounting the plugin.")
    print()


def axis4_dashboard():
    """The shipped dashboard bundle's size."""
    bundle = ROOT / "dashboard" / "dist" / "index.js"
    print("4. dashboard bundle — size")
    if not bundle.exists():
        print("   not measured: %s does not exist" % bundle.relative_to(ROOT))
    else:
        print("   %-26s %8d bytes" % (bundle.relative_to(ROOT), bundle.stat().st_size))
    print("   command: python3 scripts/bench.py")
    print()


def main():
    print("hermes-viz cost axes — python %s, %s\n" % (sys.version.split()[0], "stdlib only, offline"))
    axis1_guide()
    axis2_hook()
    axis3_desktop()
    axis4_dashboard()
    return 0


if __name__ == "__main__":
    sys.exit(main())
