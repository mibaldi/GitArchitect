"""A tiny Markdown-subset to HTML converter.

Handles exactly the constructs Codebase Architect emits in section bodies:
``##``/``###`` headings, paragraphs, ``-`` bullet lists, pipe tables, and the
inline forms ``**bold**``, `` `code` ``, ``_italic_`` and ``[text](link)``
(``.md`` links are rewritten to in-page ``#slug`` anchors). It is intentionally
small — not a general Markdown engine.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_ITALIC = re.compile(r"(?<!\w)_(.+?)_(?!\w)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("### "):
            out.append(f"<h4>{_inline(stripped[4:])}</h4>")
            i += 1
        elif stripped.startswith("## "):
            out.append(f"<h3>{_inline(stripped[3:])}</h3>")
            i += 1
        elif stripped.startswith("|"):
            block, i = _take(lines, i, lambda s: s.strip().startswith("|"))
            out.append(_table(block))
        elif stripped.startswith("- "):
            block, i = _take(lines, i, lambda s: s.strip().startswith("- "))
            items = "".join(f"<li>{_inline(b.strip()[2:])}</li>" for b in block)
            out.append(f"<ul>{items}</ul>")
        else:
            block, i = _take(lines, i, lambda s: bool(s.strip()) and not _is_block_start(s))
            out.append(f"<p>{_inline(' '.join(b.strip() for b in block))}</p>")
    return "\n".join(out)


def _is_block_start(line: str) -> bool:
    s = line.strip()
    return s.startswith(("|", "- ", "## ", "### "))


def _take(
    lines: list[str], start: int, keep: Callable[[str], bool]
) -> tuple[list[str], int]:
    block: list[str] = []
    i = start
    while i < len(lines) and keep(lines[i]):
        block.append(lines[i])
        i += 1
    return block, i


def _table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(set(c) <= {"-", ":", " "} for c in r)]
    if not cells:
        return ""
    head, *body = cells
    thead = "".join(f"<th>{_inline(c)}</th>" for c in head)
    trows = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{trows}</tbody></table>"


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = _CODE.sub(r"<code>\1</code>", escaped)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC.sub(r"<em>\1</em>", escaped)
    escaped = _LINK.sub(_link, escaped)
    return escaped


def _link(match: re.Match[str]) -> str:
    label, href = match.group(1), match.group(2)
    if href.endswith(".md"):
        href = "#" + href[: -len(".md")]
    return f'<a href="{href}">{label}</a>'
