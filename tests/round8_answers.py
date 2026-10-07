"""Round-8 fixtures — the shapes, level 2 from a bold sub-division, and two kinds on one run.

Kept apart from the earlier fixture modules so those answers stay exactly as they were.
"""

#: Unfamiliar data — a subject with no kind of its own.  `records` is the shape it has, so the subject
#: needs no rule at all: any run of `label=value` rows is a labelled value list.
UNFAMILIAR_ANSWER = """## Cargo manifest

Pallet=12 crates of tile
Container=40 ft high cube
Customs=cleared for release
"""

#: A recipe is a `grid`: a header row plus equal-width cells.  So is a form.
RECIPE_ANSWER = """## Dough

| Ingredient | Amount | Note |
| --- | --- | --- |
| Flour | 500 g | strong |
| Water | 325 g | warm |
"""

#: A route is `events`: a time or date plus a label.
ROUTE_ANSWER = """## Walk

08:12 - Cathedral - 5 min
08:40 - Market Square - 12 min
"""

#: A league's fixtures are `groups`: a label that repeats down a column.
MATCHES_ANSWER = """## Fixtures

18:00=Arsenal 2-1 Chelsea=League Cup
20:45=Liverpool 0-2 Everton=League Cup
"""

#: A real answer's sub-divisions are all-bold, not `###`.  With a `##` already open, each is a level-2
#: band — the sub-division the text already states.
BOLD_UNDER_H2 = """## Build report

The flash ran on three boards.

**Board runs**

| Board | Runs |
| --- | --- |
| 291e | 42 |

**Timing**

- Build: 42
- Test: 18
"""

#: The same bold lines with no `##` above them: they are siblings, so every one is the answer's own
#: division.  A level 2 here would be invented.
BOLD_SIBLINGS = """**Build report**

The flash ran on three boards.

**Timing**

- Build: 42
- Test: 18
"""

#: Six named stages that narrow — long enough that `heatmap` (>= 6 rows) claims the very same rows.
SIX_STAGE_FUNNEL = """## Acquisition

Visited: 1200
Signed up: 340
Activated: 180
Paid: 64
Renewed: 30
Referred: 12
"""

#: Six rows, no stage vocabulary and not narrowing — a heatmap, not a funnel.
SIX_ROW_RAMP = """## Load

Core 0: 3
Core 1: 7
Core 2: 5
Core 3: 9
Core 4: 2
Core 5: 8
"""
