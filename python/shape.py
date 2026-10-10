"""The answering-format post-pass — the two repairs the model's own directives still need.

Round 13 gives the agent half a narrow licence to *repair* an answer's own drawings on a surface that
draws, and only for three things, each provable without reading meaning:

1. a directive the app and the core would refuse is **demoted** to the markdown it held (round 12) —
   that lives in ``python/viz_dsl.py`` (``demote_directives``), and the hook runs it before this pass;
2. the **same kind with the same payload** already drawn in this answer — the repeat is dropped;
3. more drawings than ``max_widgets`` — the extras are dropped, keeping the first ``max_widgets`` in
   the answer's own order.  The cap counts what the answer draws, derived and authored alike.

This module is (2) and (3).  A **drawing** is a ``::viz{...}`` directive or a ```mermaid fence — the
boards and diagrams ``transform`` derives and the ones a model writes — counted in one budget.

Nothing else moves: prose, headings, tables, code fences and ``::preview`` are never touched, a
directive inside a fenced code block is left alone, the pass never invents a directive, and an answer
that violates nothing comes back **byte-identical**.
"""

import re
from typing import Any

try:  # loaded as part of the plugin package
    from .viz_dsl import _FENCE_RE, _attrs, _mentions
except ImportError:  # loaded as a plain top-level module (tests, scripts)
    from viz_dsl import _FENCE_RE, _attrs, _mentions

__all__ = ["shape", "drawing_key", "drawing_count"]

#: A fence that opens a diagram: the model's own and the one ``transform`` emits are the same shape.
MERMAID_FENCE_RE = re.compile(r"^\s*(?:```|~~~)\s*mermaid\b", re.IGNORECASE)


def drawing_key(attrs: dict) -> tuple:
    """The ``(kind, payload)`` pair #2 dedupes on — a title, unit or palette is not a new drawing."""
    return (str(attrs.get("k") or "").strip().lower(), str(attrs.get("d") or ""))


def _budget(max_widgets: Any):
    """The cap as a non-negative int, or None when there is no cap."""
    if max_widgets is None:
        return None
    try:
        return max(0, int(max_widgets))
    except (TypeError, ValueError):
        return None


def _blocks(text: str):
    """Yield ``(is_fence, lines)`` in the answer's own order, one fenced block or one bare line each.

    A fenced block is a whole ``\\`\\`\\``` ``/``~~~`` span; everything outside a fence is a single line,
    because a ``::viz`` can sit anywhere on one.  A ````mermaid` fence is a drawing, any other fence
    is inert — a reader being *shown* the grammar is not a reader being shown a widget.
    """
    lines = text.split("\n")
    index, total = 0, len(lines)
    while index < total:
        line = lines[index]
        if _FENCE_RE.match(line):
            block = [line]
            index += 1
            while index < total:
                block.append(lines[index])
                closed = bool(_FENCE_RE.match(lines[index]))
                index += 1
                if closed:
                    break
            yield True, block
            continue
        yield False, [line]
        index += 1


def _is_mermaid(block: list) -> bool:
    return bool(block) and bool(MERMAID_FENCE_RE.match(block[0]))


def _fresh(key: tuple, seen: set, kept: int, limit) -> bool:
    """True when this drawing is kept: a repeat of one already kept, or past the cap, is not."""
    return key not in seen and (limit is None or kept < limit)


def shape(text: str, max_widgets: Any = None) -> str:
    """*text* with a repeated drawing dropped and no more than *max_widgets* drawings kept.

    A directive is left exactly as written unless it repeats one already kept or stands past the
    budget; a directive inside a fenced code block is never a drawing.  When nothing violates the
    rule the text is returned unchanged, byte for byte.
    """
    if not isinstance(text, str) or ("::viz" not in text and "mermaid" not in text):
        return text

    limit = _budget(max_widgets)
    out: list[str] = []
    changed = False
    seen: set = set()
    kept = 0

    for is_fence, block in _blocks(text):
        if is_fence:
            if _is_mermaid(block) and not _fresh(("mermaid", "\n".join(block)), seen, kept, limit):
                changed = True
                continue
            if _is_mermaid(block):
                seen.add(("mermaid", "\n".join(block)))
                kept += 1
            out.extend(block)
            continue

        line = block[0]
        spans = _mentions(line)
        if not spans:
            out.append(line)
            continue

        keep: list[bool] = []
        for _start, _end, attrs_text, _whole in spans:
            key = drawing_key(_attrs(attrs_text)[0])
            if _fresh(key, seen, kept, limit):
                seen.add(key)
                kept += 1
                keep.append(True)
            else:
                keep.append(False)

        if all(keep):
            out.append(line)
            continue

        changed = True
        pieces: list[str] = []
        cursor = 0
        for (start, end, _attrs_text, _whole), flag in zip(spans, keep):
            pieces.append(line[cursor:start])
            if flag:
                pieces.append(line[start:end])
            cursor = end
        pieces.append(line[cursor:])
        rest = "".join(pieces)
        if rest.strip():  # a line that was nothing but dropped directives leaves nothing behind
            out.append(rest)

    if not changed:
        return text

    collapsed: list[str] = []
    for line in out:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    return "\n".join(collapsed)


def drawing_count(text: str) -> int:
    """How many drawings *text* already carries, in the answer's own order.

    The deriver is given the rest of the ``max_widgets`` budget, so a diagram the model wrote and a
    board ``transform`` emits spend from the one cap together.
    """
    if not isinstance(text, str):
        return 0
    count = 0
    for is_fence, block in _blocks(text):
        if is_fence:
            count += 1 if _is_mermaid(block) else 0
        else:
            count += len(_mentions(block[0]))
    return count
