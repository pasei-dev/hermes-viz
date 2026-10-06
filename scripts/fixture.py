#!/usr/bin/env python3
"""Write the visual-evidence page for the drawing core.

One self-contained HTML file — the app's theme tokens inlined as CSS variables
plus the core's own stylesheet — rendering one of every widget kind. The page
carries no script and no network reference, so it screenshots at 1400 / 900 /
500px without a gateway, a CDP port or the desktop app.

    python3 scripts/fixture.py [out.html]

The markup is not re-implemented here: node imports `desktop/render/core.mjs`
(the same module the plugin vendors and the tests exercise) and prints its CSS
and one `renderWidget` result per sample spec, so the page cannot drift from
what the app draws.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "desktop" / "render" / "core.mjs"
DEFAULT_OUT = ROOT / "desktop" / "fixture.html"

# One directive per kind — the shapes the agent half emits and SPEC.md describes.
SAMPLES = [
    ("kpi", {"k": "kpi", "d": "Builds=128=+12;Fails=3=-1;Queued=7", "t": "CI", "u": ""}),
    ("bars", {"k": "bars", "d": "Firmware=42;Model A=28;Web=18", "t": "Share", "u": "%"}),
    ("line", {"k": "line", "d": "3;7;4;9;11;8;14", "t": "Latency", "u": "ms"}),
    ("donut", {"k": "donut", "d": "Used=62;Free=38", "t": "Disk", "u": "%"}),
    ("steps", {"k": "steps", "d": "Read the archive;Patch the entry;Flash over EC3", "t": "Runbook", "u": ""}),
    ("table", {"k": "table", "d": "h=Board|Runs|Failures;291e|42|0;296|17|2", "t": "Boards", "u": ""}),
    ("progress", {"k": "progress", "d": "Flash=75;Verify=40", "t": "Bring-up", "u": ""}),
    ("sparkline", {"k": "sparkline", "d": "1;1;2;3;5;8;13;21", "t": "Trend", "u": ""}),
    (
        "board",
        {
            "k": "board",
            "d": "kpi:Builds=128=+12;Fails=3=-1;Queued=7"
            "~bars:Firmware=42;Model A=28;Web=18"
            "~table:h=Board|Runs;291e|42;296|17",
            "t": "Build board",
            "u": "",
        },
    ),
    ("fallback", {"k": "figure", "d": "", "source": '::viz{k="figure"}'}),
]

# The app's dark-theme token values, resolved from apps/desktop/src/styles.css
# (--theme-foreground / --theme-midground / the --ui-* ramp over --theme-neutral-*).
# The app's REAL token names and values, read off the live renderer. The widget CSS may only use
# these: `--foreground`, `--color-muted-foreground`, `--dt-primary`, `--dt-border`, `--dt-muted`.
# The shorter names a preview iframe injects (`--accent`, `--border`, `--card`, `--muted-foreground`)
# do NOT exist in the app's own tree, and a var() that resolves to nothing silently drops the
# declaration — which is how a styled widget renders as plain text.
TOKENS = {
    "--background": "#101010",
    "--foreground": "color-mix(in srgb, #ffffff 94%, transparent)",
    "--color-muted-foreground": "color-mix(in srgb, #ffffff 54%, transparent)",
    "--dt-primary": "#fe8f40",
    "--dt-border": "#282828",
    "--dt-muted": "#1e1e1e",
}

NODE_SNIPPET = """
const { pathToFileURL } = require('node:url')
import(pathToFileURL(process.env.VIZ_CORE).href).then(mod => {
  const specs = JSON.parse(process.env.VIZ_SPECS)
  process.stdout.write(JSON.stringify({
    css: mod.CSS,
    widgets: specs.map(attrs => mod.renderWidget(attrs))
  }))
}).catch(err => { console.error(err); process.exit(1) })
"""


def render_with_core():
    """Ask node for the core's CSS and markup — the page never re-implements it."""
    env = dict(os.environ)
    env["VIZ_CORE"] = str(CORE)
    env["VIZ_SPECS"] = json.dumps([attrs for _, attrs in SAMPLES])

    proc = subprocess.run(
        ["node", "-e", NODE_SNIPPET], env=env, capture_output=True, text=True
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or "node failed\n")
        raise SystemExit(1)

    return json.loads(proc.stdout)


def page(css, widgets):
    tokens = "\n".join("    %s: %s;" % (name, value) for name, value in TOKENS.items())
    cases = []

    for (name, attrs), markup in zip(SAMPLES, widgets):
        directive = '::viz{k="%s"%s%s}' % (
            attrs["k"],
            ' d="%s"' % attrs["d"] if attrs.get("d") else "",
            ' t="%s"' % attrs["t"] if attrs.get("t") else "",
        )
        cases.append(
            '  <section class="case">\n'
            '    <span class="label">%s &mdash; %s</span>\n'
            "    %s\n"
            "  </section>" % (name, directive.replace("&", "&amp;").replace("<", "&lt;"), markup)
        )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>hermes-viz — every kind</title>
<style>
  /* The app's token values, resolved from the dark theme. */
  :root {
%s
  }
  html, body { margin: 0; }
  body {
    background: var(--background);
    color: var(--foreground);
    font-family: ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  main { display: flex; flex-direction: column; gap: 1.5rem; padding: 1.25rem; }
  .case { display: flex; flex-direction: column; gap: 0.5rem; }
  .label { color: var(--color-muted-foreground); font-family: ui-monospace, "SF Mono", monospace; font-size: 0.6875rem; }
  /* The core's own stylesheet, verbatim. */
%s
</style>
</head>
<body>
<main>
%s
</main>
</body>
</html>
""" % (
        tokens,
        css.strip(),
        "\n".join(cases),
    )


def main():
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUT

    if not CORE.exists():
        sys.stderr.write("missing %s\n" % CORE)
        raise SystemExit(1)

    data = render_with_core()
    out.write_text(page(data["css"], data["widgets"]), encoding="utf-8")
    print("wrote %s (%d kinds)" % (out, len(SAMPLES)))


if __name__ == "__main__":
    main()
