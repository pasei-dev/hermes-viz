"""Test helper — the answer fixtures, and the rule table they are derived against.

Kept out of the test modules so `derive`, the hook and the emitter can all work from the same answers.
"""

ANSWER_WITH_TABLE_AND_RUN = """## Build report

### Board runs

| Board | Runs | Failures |
| --- | --- | --- |
| 291e | 42 | 1 |
| 296e | 28 | 0 |
| 208e | 17 | 2 |

### Timing

- Build: 42
- Test: 18
- Package: 7
"""

PROSE_ONLY = (
    "The board flashed cleanly and the DSP came up on the first attempt, so nothing else "
    "was touched.\n"
)

FENCED_CODE_ONLY = """Here is the table the script prints:

```markdown
| Board | Runs |
| --- | --- |
| 291e | 42 |
| 296e | 28 |
| 208e | 17 |

1. this ordered list
2. is inside the fence
3. and must stay invisible
```

And that is the whole of it.
"""

TWO_ROW_RUN = """### Delta

- Builds: 128
- Failures: 3
"""

STEPS_ANSWER = """### Flash procedure

1. Read the archive
2. Verify the pin
3. Flash the board
4. Confirm the LED
"""
