"""
Converts the assistant's raw markdown output into Telegram-safe text.

Telegram supports basic Markdown (bold, italic) but has no table rendering
at all. Rather than having the LLM produce different output per interface,
it always produces full markdown (used as-is by the web frontend), and this
module strips/reformats the parts Telegram can't render — specifically,
markdown tables get converted into plain "Label: value" lines.
"""

import re


def _convert_table_to_lines(table_block: str) -> str:
    """
    Convert one markdown table block into plain label:value lines.

    Assumes the first column is a label-like field and remaining columns
    are values — reasonable for this product's tables (sector rankings,
    CPI breakdowns, etc.), though not a general-purpose table interpreter.
    """
    rows = [r.strip() for r in table_block.strip().split("\n") if r.strip()]
    if len(rows) < 2:
        return table_block  # not actually a table, leave as-is

    def split_row(row: str) -> list[str]:
        cells = row.strip().strip("|").split("|")
        return [c.strip() for c in cells]

    header = split_row(rows[0])
    # rows[1] is the '---|---|---' separator — skip it
    data_rows = [split_row(r) for r in rows[2:]]

    # If the first column is purely numeric (a rank/index like "1", "2"),
    # it's not a meaningful label — use the next column instead so output
    # reads as "Technology — Avg Abs Move: 1.69%" rather than "1 — Sector:
    # Technology, Avg Abs Move: 1.69%".
    label_col = 0
    if data_rows and all(row[0].strip().isdigit() for row in data_rows if row):
        label_col = 1 if len(header) > 1 else 0

    lines = []
    for row in data_rows:
        if not row or label_col >= len(row):
            continue
        label = row[label_col]
        other_indices = [i for i in range(len(header)) if i != label_col and i < len(row)]
        rest = ", ".join(f"{header[i]}: {row[i]}" for i in other_indices)
        lines.append(f"• {label} — {rest}" if rest else f"• {label}")

    return "\n".join(lines)


def to_telegram_text(markdown_text: str) -> str:
    """
    Convert full markdown (as produced by the assistant) into Telegram-safe
    text: markdown tables become plain lines, bold/italic markdown is left
    as-is (Telegram renders standard Markdown natively).
    """
    # Match blocks that look like markdown tables: a header row, a
    # separator row of dashes/pipes, then one or more data rows.
    table_pattern = re.compile(
        r"(\|.+\|\n\|[-\s|:]+\|\n(?:\|.+\|\n?)+)", re.MULTILINE
    )

    def replace_table(match: re.Match) -> str:
        return _convert_table_to_lines(match.group(1))

    return table_pattern.sub(replace_table, markdown_text)
