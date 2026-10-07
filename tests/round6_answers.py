"""Round-6 fixtures — one answer holding a genuine bracket, gloss and paradigm, and the same answer
with each shape *absent*, replaced by something that merely resembles it.

Kept apart from the earlier fixture modules so those answers stay exactly as they were.
"""

#: One real instance of each of the three new kinds: a word-aligned interlinear gloss, a labelled
#: conjugation, and a bracket of rounds whose winners advance.
GENUINE_ANSWER = """## Language notes

The German present tense is regular here.

der Hund bellt=the dog barks=PRS.3SG
der Mann geht=the man goes=PRS.3SG

## The verb haben

| person | singular | plural |
| --- | --- | --- |
| 1st | habe | haben |
| 2nd | hast | habt |

## Cup

R16: Arsenal>Chelsea, Brentford>Leeds
QF: Arsenal>Brentford
"""

#: The same answer with the three shapes gone.  Each stand-in *resembles* one — a plain `word: meaning`
#: definition and a sentence with a dash (not a gloss), a two-column list (not a paradigm), and a single
#: pairing (not a bracket) — and must emit nothing.
ABSENT_ANSWER = """## Language notes

The German present tense is regular here.

Hund: dog
Der Hund bellt - the dog barks.

## The verb haben

| Word | Meaning |
| --- | --- |
| haben | to have |
| gehen | to go |

## Cup

R16: Arsenal>Chelsea
Arsenal beat Chelsea and Brentford beat Leeds.
"""

#: A three-round bracket — enough rounds that `facts` would otherwise card the same lines.
BRACKET_THREE = """R16: Arsenal>Chelsea, Brentford>Leeds
QF: Arsenal>Brentford
SF: Arsenal>Liverpool
"""
