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
PLUGIN = ROOT / "desktop" / "plugin.js"
DEFAULT_OUT = ROOT / "desktop" / "fixture.html"

# One directive per kind — the shapes the agent half emits and SPEC.md describes.
SAMPLES = [
    ("kpi", {"k": "kpi", "d": "Builds=128=+12;Fails=3=-1;Queued=7", "t": "CI", "u": ""}),
    ("bars", {"k": "bars", "d": "Firmware=42;Model A=28;Web=18", "t": "Share", "u": "%"}),
    ("line", {"k": "line", "d": "3;7;4;9;11;8;14", "t": "Latency", "u": "ms"}),
    ("donut", {"k": "donut", "d": "Used=62;Free=38", "t": "Disk", "u": "%"}),
    # Four slices: exercises four palette slots in first-seen order.
    ("donut-ramp", {"k": "donut", "d": "Builds=120;Tests=64;Lint=18;Docs=9", "t": "Work mix", "u": ""}),
    ("steps", {"k": "steps", "d": "Read the archive;Patch the entry;Flash the board", "t": "Runbook", "u": ""}),
    ("table", {"k": "table", "d": "h=Board|Runs|Failures;Alpha|42|0;Beta|17|2", "t": "Boards", "u": ""}),
    ("progress", {"k": "progress", "d": "Flash=75;Verify=40", "t": "Bring-up", "u": ""}),
    ("sparkline", {"k": "sparkline", "d": "1;1;2;3;5;8;13;21", "t": "Trend", "u": ""}),
    # A non-percent unit: the bars scale to the row maximum (812ms), not to 100.
    ("bars-max", {"k": "bars", "d": "Flash=812;Verify=430;Idle=96", "t": "Stage time", "u": "ms"}),
    # The header band: `t` is the heading, `d` the lead line.
    ("section", {"k": "section", "d": "Rolling out to the north cluster this week", "t": "Deployment", "u": "", "l": "1"}),
    # The type scale, three cases in a row so one crop shows L1 next to L2 next to a widget title.
    ("scale-l1", {"k": "section", "d": "The answer's own first division", "t": "Deployment", "u": "", "l": "1"}),
    ("scale-l2", {"k": "section", "d": "A sub-division, one type step down", "t": "Stage times", "u": "", "l": "2"}),
    ("scale-title", {"k": "sparkline", "d": "1;2;3;5;8;13;21", "t": "Widget title", "u": ""}),
    # Two levels mixed in one board.
    (
        "board-sections",
        {"k": "board", "d": "section:Build board;l=1~section:Stage times;l=2~progress:Flash=75;Verify=40", "t": "Mixed levels", "u": ""},
    ),
    # The twelve round-2 kinds, in SPEC table order.
    ("checklist", {"k": "checklist", "d": "Build=done;Flash=doing;Verify=todo;Docs=blocked", "t": "Release", "u": ""}),
    ("changes", {"k": "changes", "d": "desktop/render/core.mjs=+212=-48;desktop/plugin.js=+8=-2;tests/desktop.test.mjs=+96=-30", "t": "Diff", "u": ""}),
    ("outline", {"k": "outline", "d": "1=Palette;1.1=Six hues, first-seen;1.2=Literals live in one block;2=Measure;2.1=42rem cap;3=Axes", "t": "Contents", "u": ""}),
    ("facts", {"k": "facts", "d": "Target=Probe;Part=MCU-1;Toolchain=Vendor IDE;Clock=49MHz", "t": "Board", "u": ""}),
    ("files", {"k": "files", "d": "desktop/render/core.mjs=480 lines;desktop/plugin.js=608 lines;scripts/fixture.py=170 lines", "t": "Files", "u": ""}),
    ("refs", {"k": "table", "d": "h=Where|What;Docs|https://example.com/guide;Repo|/srv/app", "t": "References", "u": ""}),
    ("parts", {"k": "parts", "d": "h=Ref|Part|Qty;U1|MCU-1|1;U2|Radio|2;J3|Probe header|4", "t": "BOM", "u": ""}),
    ("settings", {"k": "settings", "d": "Reduced motion=off;Tabular numerals=on;Palette=on;Live theme=on", "t": "Preferences", "u": ""}),
    ("timeline", {"k": "timeline", "d": "Mon 09:00=Freeze=cut the release branch;Tue 14:00=Flash the board=bench rig;Fri=Sign-off", "t": "Schedule", "u": ""}),
    ("ranges", {"k": "ranges", "d": "Build=2..9;Flash=5..14;Verify=8..11", "t": "Windows", "u": "h"}),
    ("metrics", {"k": "metrics", "d": "Coverage=88=-2;Latency=14=+3;Errors=0=-7", "t": "Health", "u": ""}),
    # Round 4: the `of` form — a value with something to measure it against.
    # The target is the row's own track end and its share is named.
    ("bars-of", {"k": "bars", "d": "Intake=1850 of 2200;Burn=1500 of 2000;Protein=120 of 150", "t": "Energy", "u": "kcal"}),
    ("metrics-of", {"k": "metrics", "d": "Coverage=88 of 100;Latency=14 of 20;Errors=0 of 5", "t": "SLO", "u": ""}),
    # A composed board: several kinds share one board with one vertical rhythm.
    (
        "board-rhythm",
        {
            "k": "board",
            "d": "kpi:Builds=128=+12;Fails=3=-1"
            "~bars:Intake=1850 of 2200;Burn=1500 of 2000"
            "~facts:Port=Probe;Chip=MCU-1"
            "~checklist:Build=done;Flash=doing;Verify=todo",
            "t": "Composed board",
            "u": "",
        },
    ),
    ("array", {"k": "array", "d": "Alpha|Beta|Gamma;a1|a2|a3;12|07|04", "t": "Matrix", "u": ""}),
    ("heatmap", {"k": "heatmap", "d": "Mon=40;Tue=90;Wed=12;Thu=66;Fri=78", "t": "Load", "u": ""}),
    # The two round-3 kinds.
    ("wireframe", {"k": "wireframe", "d": "Toolbar=btn:3,field:1,text:2;Sidebar=card:2,circle:1,item:4;Canvas=chart:2,img:1", "t": "Layout", "u": ""}),
    ("candlestick", {"k": "candlestick", "d": "Mon=12:18:9:16;Tue=16:21:14:20;Wed=20:26:18:14;Thu=14:24:13:22;Fri=22:25:15:15", "t": "Daily close", "u": ""}),
    # Round 5: the five subject kinds.
    ("words", {"k": "words", "d": "Nouns;der Hund=[deːɐ hʊnt]=the dog=Der Hund bellt.;laufen=[ˈlaʊfn̩]=to run;das Haus=[das haʊs]=the house=Das Haus ist alt.", "t": "Vocabulary", "u": ""}),
    ("recipe", {"k": "recipe", "d": "h=Ingredient|Amount|Note;Butter|80 g|brown the butter;Caster sugar|150 g|whisk until pale;Eggs|2|room temperature;!Do not boil|—|the caramel will scorch", "t": "Recipe", "u": ""}),
    ("route", {"k": "route", "d": "09:40=Depot 1=Check in;11:10=Gate B=Board;12:55=Depot 3=Ship the firmware;14:20=Site C=Review session", "t": "Itinerary", "u": ""}),
    ("nutrition", {"k": "nutrition", "d": "Calories=1850 of 2200;Protein=132 g of 150;Carbs=210 g of 250;Fat=60 g of 70", "t": "Macros", "u": ""}),
    ("matches", {"k": "matches", "d": "18:00=Arsenal 2-1 Chelsea=League Cup;20:45=Brentford vs Leeds=League Cup;15:00=Ajax 0-0 PSV=Eredivisie;17:30=Feyenoord vs Utrecht=Eredivisie", "t": "Matches", "u": ""}),
    # Round 6: the last three kinds.
    # A bracket with a DELIBERATE contradiction: Lyon is named in the semi-final
    # though it never won the quarter-final — the payload is shown as written and
    # the contradiction is flagged in place, not quietly redrawn.
    ("bracket", {"k": "bracket", "d": "R16=Arsenal>Chelsea,Brentford>Leeds;QF=Arsenal>Brentford;SF=Arsenal>Lyon", "t": "Cup run", "u": ""}),
    # A consistent bracket beside it, so the flag is visibly the exception.
    ("bracket-clean", {"k": "bracket", "d": "R16=Arsenal>Chelsea,Brentford>Leeds,Ajax>PSV,Lyon>Nice;QF=Arsenal>Brentford,Ajax>Lyon;SF=Arsenal>Ajax", "t": "Cup run — consistent", "u": ""}),
    # Aligned interlinear gloss: three source words, three gloss words.
    ("gloss", {"k": "gloss", "d": "der Hund bellt=the dog barks=PRS.3SG;die Katze schläft=the cat sleeps=PRS.3SG;ich sehe den Hund=I see the dog=PRS.1SG", "t": "Interlinear", "u": ""}),
    # A count mismatch: 3 source words, 4 gloss words -> shown unaligned, never faked.
    ("gloss-unaligned", {"k": "gloss", "d": "der Hund bellt=the dog barks loudly=PRS.3SG;die Katze=the cat", "t": "Interlinear — unaligned", "u": ""}),
    # A paradigm: a grid like `parts`, a header row naming the axes.
    ("forms", {"k": "forms", "d": "h=person|singular|plural;1st|habe|haben;2nd|hast|habt;3rd|hat|haben", "t": "haben — present", "u": ""}),
    # A 4-entry board next to a 5-entry board: neither leaves a lone orphan
    # (4 -> 2 columns of 2; 5 -> 3 columns with a balanced last row of 2).
    (
        "board-4",
        {"k": "board", "d": "kpi:A=1~kpi:B=2~kpi:C=3~kpi:D=4", "t": "Four entries", "u": ""},
    ),
    (
        "board-5",
        {"k": "board", "d": "kpi:A=1~kpi:B=2~kpi:C=3~kpi:D=4~kpi:E=5", "t": "Five entries", "u": ""},
    ),
    (
        "board",
        {
            "k": "board",
            "d": "kpi:Builds=128=+12;Fails=3=-1;Queued=7"
            "~bars:Firmware=42;Model A=28;Web=18"
            "~table:h=Board|Runs;Alpha|42;Beta|17",
            "t": "Build board",
            "u": "",
        },
    ),
    # Round 7: funnel, scatter, waterfall — the last three kinds.
    # A funnel: the stages keep their order and each drop is named in the gap.
    ("funnel", {"k": "funnel", "d": "Visited=1200;Signed up=340;Activated=180;Paid=64", "t": "Signup funnel", "u": ""}),
    # A scatter: both axes carry a range and ticks, each point prints its x · y.
    ("scatter", {"k": "scatter", "d": "1=2.4;2=3.1;3=2.9;4=4.2;5=3.6", "t": "Latency across runs", "u": "ms"}),
    # A waterfall whose bars go DOWN as well as up — the sign is the direction.
    ("waterfall", {"k": "waterfall", "d": "Start=+120;Refunds=-30;Costs=-45;Net=+45", "t": "Cash walk", "u": ""}),
    # A longer walk: several downs, then a recovery — direction, not colour.
    ("waterfall-long", {"k": "waterfall", "d": "Open=+80;Churn=-25;Upsell=+40;Refunds=-18;Outage=-52;Recover=+31", "t": "Quarter walk", "u": ""}),
    # Round 8: the eight shapes as first-class kinds — how data is arranged, not
    # what it is about. A rule emits one when no subject kind claims the data.
    ("shape-records", {"k": "records", "d": "Owner=Platform=on call;SLA=99.9%;Escalation=@pager", "t": "Service", "u": ""}),
    ("shape-pairs", {"k": "pairs", "d": "2=14;4=28;6=41;8=57;10=73", "t": "Throughput", "u": "ms"}),
    ("shape-series", {"k": "series", "d": "12;19;17;24;31;28;37", "t": "Uptime", "u": ""}),
    ("shape-stages", {"k": "stages", "d": "Seen=4800;Signed up=1240;Activated=610;Retained=240", "t": "Stage walk", "u": ""}),
    ("shape-steps", {"k": "steps", "d": "Cut the stencil=done;Etch the board=doing;Populate it=todo", "t": "Fabrication", "u": ""}),
    ("shape-grid", {"k": "grid", "d": "h=Region|Q1|Q2|Q3;North|12|15|19;South|9|11|14;West|6|8|13", "t": "By region", "u": ""}),
    ("shape-groups", {"k": "groups", "d": "Mon=Argon=Physics;Tue=Boron=Physics;Wed=Cobalt=Chemistry;Thu=Radon=Chemistry", "t": "Labs", "u": ""}),
    ("shape-events", {"k": "events", "d": "2026-03-01=Kickoff=crew brief;2026-04-15=Beta;2026-06-01=Launch", "t": "Milestones", "u": ""}),
    # Unfamiliar data: beekeeping has no subject kind, so the SHAPE must carry it
    # — the whole point of rendering by shape instead of by subject.
    ("shape-unfamiliar", {"k": "records", "d": "Hive 1=42 kg=queen marked;Hive 2=38 kg;Hive 3=51 kg=swarm risk", "t": "Apiary log", "u": ""}),
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


def body_css() -> str:
    """The desktop half's body stylesheet, read out of `desktop/plugin.js`.

    It is not in the core (the core draws widgets; the body is the host's DOM), so
    there is nothing for the node call above to hand back. Extracting the constant
    from the source keeps the fixture honest — a second copy here would drift.
    """
    src = PLUGIN.read_text(encoding="utf-8")
    marker = "const BODY_STYLE = `"
    start = src.index(marker) + len(marker)
    return src[start : src.index("\n`", start)]


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
        directive = '::viz{k="%s"%s%s%s}' % (
            attrs["k"],
            ' d="%s"' % attrs["d"] if attrs.get("d") else "",
            ' t="%s"' % attrs["t"] if attrs.get("t") else "",
            ' l="%s"' % attrs["l"] if attrs.get("l") else "",
        )
        cases.append(
            '  <section class="case">\n'
            '    <span class="label">%s &mdash; %s</span>\n'
            "    %s\n"
            "  </section>" % (name, directive.replace("&", "&amp;").replace("<", "&lt;"), markup)
        )

    # The body styling sits on the answer's own DOM, not in a widget, so its case is a
    # miniature answer rather than a sample: the `.aui-md` root the transcript uses, and the
    # app's line-height token read the way the app reads it.
    body_case = (
        '  <section class="case">\n'
        '    <span class="label">body text &mdash; BODY_STYLE from desktop/plugin.js, under .aui-md</span>\n'
        '    <div class="aui-md" style="line-height: var(--dt-line-height); max-width: 52rem">\n'
        "      <h2>Body typography</h2>\n"
        "      <p>A heading takes the accent, so structure reads as more than size. Prose stops at a measure,\n"
        "      so a wide window gives more margin instead of longer lines. Nothing else here is the plugin's:\n"
        "      the line-height, the paragraph rhythm and the heading scale above are the app's own.</p>\n"
        "      <ul>\n"
        "        <li>One idea per line.</li>\n"
        "        <li>A list keeps its own rhythm.</li>\n"
        "      </ul>\n"
        "      <blockquote><p>A callout lines up with the text it belongs to.</p></blockquote>\n"
        "    </div>\n"
        "  </section>"
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
  .label { color: var(--color-muted-foreground); font-family: ui-monospace, "SF Mono", monospace; font-size: 0.6875rem; overflow-wrap: anywhere; }
  /* The host's own reference vocabulary, in the two kinds a widget can emit
     (apps/desktop/src/styles.css, `.ref` / `[data-ref]`). The fixture has no
     --ui-accent-secondary, so both kinds take the primary accent here; in the app
     the url kind resolves to a lighter secondary. */
  [data-ref='url'], [data-ref='file'] { --ref-color: var(--dt-primary); }
  .ref { font-weight: inherit; color: var(--ref-color); text-decoration: none; }
  :where(a, button).ref:hover { text-decoration: underline; text-underline-offset: 0.15em; }
  .ref > :where(svg, i.codicon) { margin-inline-end: 0.25em; opacity: 0.8; }
  .ref > svg { display: inline-block; width: 0.875em; height: 0.875em; vertical-align: -0.1em; }
  /* The desktop half's body styling, extracted from desktop/plugin.js — the app
     scopes it to `.aui-md`, so the demo below carries that class. */
%s
  /* The core's own stylesheet, verbatim. */
%s
</style>
</head>
<body>
<main>
%s
%s
</main>
</body>
</html>
""" % (
        tokens,
        body_css().strip(),
        css.strip(),
        body_case,
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
