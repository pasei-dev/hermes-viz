"""The derivation corpus — the shapes real answers are written in, and the widgets they must draw.

The complaint this file answers was measured, not assumed: a realistic answer (a prose line of
numbers, a markdown table, a numbered list, two `- path modified` bullets, `Status: 1 blocked, 2
doing, 5 done.`, `Config: theme=dark, palette=mermaid, widgets=10` and `Session started 2026-10-12
and ended 2026-10-14.`) derived **two** widgets — the table's and the ordered list's — and left
every other shape as prose.  The matchers only fired on a widget's OWN grammar, and the one shape an
agent writes naturally is the markdown table.  So an agent's answers only ever drew tables.

Each answer below is written the way it would be written for real, in one of this deployment's
domains — agent/code work, plugin and theme work, hardware and bench work, audio, and planning — and
each names the kinds its shapes must derive.  Two are deliberately plain prose: a paragraph and a
`Note:` line, because an incidental colon must not become a facts card.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # so the file runs standalone as well as under pytest
    sys.path.insert(0, str(ROOT))

from python.derive import derive  # noqa: E402

from _agent import RULES, agent  # noqa: E402

#: The groups a fresh install has on.  The corpus is judged on the shipped configuration, because
#: that is what a reader actually gets.
SHIPPED_GROUPS = agent.DEFAULT_RULE_GROUPS

#: `(name, answer, the kinds derived)`.  The kind list is the *set* of kinds across every rule that
#: fires on the answer, so it says what the answer's shapes reached, not the order they arrived in.
CORPUS = (
    (
        "refactor-summary",
        """The refactor touched 12 files and left the build green, so the change is safe to land.

Status: 1 blocked, 2 doing, 5 done.

| Module | Before | After |
| --- | --- | --- |
| core | 812 | 540 |
| api | 430 | 431 |
| ui | 210 | 205 |

1. Extract the parser
2. Move the config reader
3. Delete the dead helpers

- apps/x.css modified
- python/derive.py modified

Config: theme=dark, palette=mermaid, widgets=10

Session started 2026-10-12 and ended 2026-10-14.
""",
        ("bars", "checklist", "files", "records", "steps", "timeline"),
    ),
    (
        "failing-test-triage",
        """Two suites fail on the 3.10 interpreter, both on the same locale assumption.

- tests/test_derive.py failed
- tests/test_hook.py failed

3 failed, 117 passed.

Pin LC_ALL in conftest and both go green.
""",
        ("checklist", "files"),
    ),
    (
        "pr-summary",
        """PR #12 is open and ready for review.

- python/derive.py modified
- tests/test_derive.py modified
- README.md modified

Checks: 2 green, 1 red.
""",
        ("checklist", "files"),
    ),
    (
        "plugin-theme-change",
        """The box now takes the app's own muted token, so a light sheet deepens and a dark one lightens.

Config: palette=dark, widgets=6, body_style=on

Everything above is user-changeable in the settings page.
""",
        ("records",),
    ),
    (
        "flashing-session",
        """The ESP32 flashed cleanly and came up on the first attempt.

- Flash 18s
- Verify 3s
- Boot 42s

Started 2026-10-12, finished 2026-10-14.
""",
        ("metrics", "timeline"),
    ),
    (
        "bench-run",
        """The bench held the target across every run.

| Run | Latency | Jitter |
| --- | --- | --- |
| 1 | 41.2 | 0.8 |
| 2 | 43.6 | 1.1 |
| 3 | 40.9 | 0.6 |

Worst case 43.6 ms, best case 40.9 ms.
""",
        ("bars", "metrics"),
    ),
    (
        "synth-voice",
        """The patch is a four-operator FM voice with a deliberately slow attack.

| Operator | Ratio | Level |
| --- | --- | --- |
| Car | 1 | 90 |
| Mod A | 2 | 62 |
| Mod B | 3 | 40 |

Voice cost 3 operators, headroom 6 dB.
""",
        ("bars", "metrics"),
    ),
    (
        "launch-plan",
        """The launch slips a week and the campaign is unaffected.

- Visited: 1200
- Signed up: 340
- Activated: 180
- Paid: 64

Budget: flight 2 weeks, copy 3 days.
""",
        ("funnel", "metrics"),
    ),
    (
        "work-plan",
        """The plan has two halves and one open question in it.

1. Agent half
1.1 Matchers
1.2 Emitters
2. Desktop half
2.1 Renderers
""",
        ("outline",),
    ),
    (
        "settings-flags",
        """The flags are read from plugin.yaml on register.

Telemetry: on
Autoflash: off
Cloud sync: on
""",
        ("settings",),
    ),
    (
        "disk-share",
        """The disk is nearly full and the cache is the largest thing on it.

62% used, 38% free

Clearing the cache reclaims the room.
""",
        ("pie",),
    ),
    (
        "prose-only",
        """The board flashed cleanly and the DSP came up on the first attempt, so nothing else was
touched.
""",
        (),
    ),
    (
        "prose-with-a-colon",
        """Note: this is prose and it explains one thing about the plan, at some length.
""",
        (),
    ),
)

#: The answers that carry a data shape the table is not — each must draw at least one non-table widget.
DATA_BEARING = frozenset(name for name, _text, kinds in CORPUS if kinds)


#: The kinds that are a table's own drawing — an answer that produces only these has drawn a table.
TABLE_KINDS = frozenset({"table", "grid", "array", "forms", "parts", "recipe"})


def _kinds(answer):
    return {spec["kind"] for spec in derive(answer, RULES, SHIPPED_GROUPS, None)}


def _drawn_kinds(text):
    """Every kind *text* actually draws: a board's entries, a single directive, a Mermaid fence."""
    kinds = set()
    for line in text.splitlines():
        if line.startswith("::viz{k="):
            if 'k="board"' in line:
                payload = line.split('d="', 1)[1]
                for entry in payload.split("~"):
                    head = entry.split(":", 1)[0]
                    if ":" in entry and head:
                        kinds.add("`%s`" % head)
            else:
                kinds.add(line.split('k="', 1)[1].split('"', 1)[0])
        elif line.startswith("```mermaid"):
            kinds.add("mermaid")
    return {kind.strip("`") for kind in kinds}


def test_each_answer_derives_exactly_the_kinds_it_should():
    for name, answer, kinds in CORPUS:
        assert _kinds(answer) == set(kinds), (name, sorted(_kinds(answer)), sorted(kinds))


def test_the_corpus_reaches_at_least_ten_distinct_kinds():
    """Before the prose matchers this was four: `grid`, `bars`, `steps`, `section`."""
    reached = set()
    for _name, answer, _kinds_expected in CORPUS:
        reached |= _kinds(answer)
    assert len(reached) >= 10, sorted(reached)


def test_every_answer_with_a_data_shape_draws_something_that_is_not_a_table():
    """A shape the table is not must reach the reader as something the table is not."""
    for name, answer, kinds in CORPUS:
        if name not in DATA_BEARING:
            continue
        drawn = _kinds(answer) - TABLE_KINDS
        assert drawn, name


def test_a_plain_prose_answer_derives_nothing():
    """The false-positive gate: a paragraph, and a `Note:` line, are not data."""
    for name, answer, kinds in CORPUS:
        if kinds:
            continue
        assert derive(answer, RULES, SHIPPED_GROUPS, None) == [], name
        assert agent.transform(answer, RULES, SHIPPED_GROUPS, 6, "mermaid") is None, name


#: Sentences that look like the shapes above and are not: a colon, an incidental number, a sentence
#: that opens with `First`.  Every prose matcher's boundary is one of these, and a widening that
#: broke one would be caught here rather than by a reader.
PROSE_GATE = (
    "Note: this is prose and it explains one thing about the plan, at some length.",
    "There are 3 reasons: speed, clarity and cost.",
    "The build failed twice before the pin was fixed.",
    "We changed 12 files: 8 in the agent half and 4 in the desktop half.",
    "See rules.yaml:120 for the matcher, and derive.py:421 for the checklist.",
    "Step 1 is the only step left, and it is done.",
    "This sentence mentions 42 and 18 without a unit.",
    "The reader asked for 2 things; both are done.",
    "First impressions matter, then again the plan is long.",
    "The patch has 4 operators, a slow attack and no reverb.",
    "Tests: 117 passed and 3 failed, so the gate is red.",
    "I read the README.md carefully and found nothing wrong.",
    "The archive is 3 MB and the pin file is 2 KB.",
    "Session started, ended, and nothing else happened.",
    "The room was 62% full at the start of the day.",
    "Todo: rewrite the matcher, then re-run the suite.",
    "Config lives in plugin.yaml and is read once.",
    "The build took 12 minutes and the flash 3 minutes.",
    "Version 0.4.15 is the one that landed.",
    "It renders in about 110 ms, which is fine.",
)


def test_no_prose_sentence_is_read_as_data():
    for line in PROSE_GATE:
        assert derive(line + "\n", RULES, SHIPPED_GROUPS, None) == [], line


def test_every_data_answer_survives_the_splice_with_a_non_table_widget():
    """Deriving is not drawing: `_covers` still refuses a widget that drops one of the source's words.

    So the corpus is judged twice — what the matchers reached above, and what the reader is actually
    handed here.  Every data-bearing answer must come back from `transform` carrying a drawing that
    is not a table.
    """
    for name, answer, _kinds_expected in CORPUS:
        if name not in DATA_BEARING:
            continue
        out = agent.transform(answer, RULES, SHIPPED_GROUPS, 10, "mermaid")
        assert out is not None, name
        drawn = _drawn_kinds(out)
        assert drawn, name
        assert drawn - TABLE_KINDS, (name, sorted(drawn))


if __name__ == "__main__":  # so this file is a check in its own right, not only under pytest
    failures = 0
    for _name in sorted(k for k in list(globals()) if k.startswith("test_")):
        try:
            globals()[_name]()
        except AssertionError as error:
            failures += 1
            print("FAIL %s: %s" % (_name, error))
    print("%d corpus checks, %d failed" % (len([k for k in globals() if k.startswith("test_")]), failures))
    sys.exit(1 if failures else 0)
