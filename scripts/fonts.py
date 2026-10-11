#!/usr/bin/env python3
"""Bundle the two faces into the drawing core's stylesheet.

The desktop half is ONE ESM file, evaluated from a `blob:` URL, and it may import nothing
outside the app's SDK — so a face cannot be fetched at runtime. Not by a relative path:
nothing resolves against a `blob:` base. Not from the plugin's own folder: the only scheme
the app registers for local files streams media extensions. A shipped face therefore
travels INSIDE the stylesheet, as a `data:` URL, and that is also what makes the plugin
look the same on a machine that has none of these installed.

`desktop/fonts/*.woff2` is the source of truth; this script encodes it into
`desktop/render/core.mjs` between the `bundled-fonts` markers. `--check` fails when the
two have drifted, and the JS suite asserts the same equality, so a face cannot be swapped
in one place and stay stale in the other.

Provenance of the four files: the upstream variable fonts, subset to the Latin and Latin
Extended ranges and instanced to the 400-700 weight axis (DM Sans's optical-size axis
pinned). They are under the SIL Open Font License 1.1 — the notice and the full text sit
beside them in `desktop/fonts/OFL.txt`, which is what the licence requires to travel.

    python3 scripts/fonts.py            # write the block into core.mjs
    python3 scripts/fonts.py --check    # exit 1 when core.mjs has drifted
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "desktop" / "fonts"
CORE = ROOT / "desktop" / "render" / "core.mjs"

OPEN = "/* >>> bundled-fonts"
CLOSE = "/* <<< bundled-fonts */"

LATIN = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, "
    "U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, "
    "U+FEFF, U+FFFD"
)
LATIN_EXT = (
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, "
    "U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, "
    "U+2113, U+2C60-2C7F, U+A720-A7FF"
)

# One entry per family, in the order the stacks name them. The letterforms are the
# `--hv-round` and `--hv-sans` voices; the mono voice is the app's own face and no
# bytes travel for it.
FAMILIES = [
    ("Space Grotesk", [("space-grotesk-latin.woff2", LATIN), ("space-grotesk-latin-ext.woff2", LATIN_EXT)]),
    ("DM Sans", [("dm-sans-latin.woff2", LATIN), ("dm-sans-latin-ext.woff2", LATIN_EXT)]),
]


def block() -> str:
    """The @font-face rules, one per family and subset, as data: URLs."""
    lines = [
        f"{OPEN} — written by scripts/fonts.py from desktop/fonts/*.woff2; "
        "licence in desktop/fonts/OFL.txt */"
    ]
    for family, files in FAMILIES:
        for name, unicode_range in files:
            path = FONT_DIR / name
            if not path.is_file():
                raise SystemExit(f"missing face: {path}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            lines += [
                "@font-face {",
                f"  font-family: '{family}';",
                "  font-style: normal;",
                "  font-weight: 400 700;",
                "  font-display: swap;",
                f"  src: url(data:font/woff2;base64,{encoded}) format('woff2');",
                f"  unicode-range: {unicode_range};",
                "}",
            ]
    lines.append(CLOSE)
    return "\n".join(lines) + "\n"


def splice(source: str, fresh: str) -> str:
    """Replace the block in place, or plant it directly inside the stylesheet."""
    if OPEN in source:
        start = source.index(OPEN)
        end = source.index(CLOSE, start) + len(CLOSE) + 1
        return source[:start] + fresh + source[end:]
    anchor = "const CSS = `\n"
    at = source.index(anchor) + len(anchor)
    return source[:at] + fresh + source[at:]


def main() -> int:
    fresh = block()
    source = CORE.read_text()
    spliced = splice(source, fresh)

    if "--check" in sys.argv:
        if source != spliced:
            print("core.mjs has drifted from desktop/fonts — run: python3 scripts/fonts.py")
            return 1
        print("the bundled faces match desktop/fonts")
        return 0

    if source == spliced:
        print("core.mjs already carries the bundled faces")
        return 0
    CORE.write_text(spliced)
    print(f"wrote {len(fresh)} chars of faces into {CORE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
