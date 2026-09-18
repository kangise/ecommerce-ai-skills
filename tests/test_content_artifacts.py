"""Tool residue that must not reach readers.

AI research and translation tools leave notes in their output. One of them,
"Content rephrased for compliance with licensing restrictions.", came in with
the March 2026 imports and sat in 135 chapter files — as its own paragraph in
the middle of Chinese and Japanese text — until it was removed in 2026-09. It
carries no information (the sources it refers to are cited inline), so any
occurrence is a defect. This is a test, not a content gate, so the published
gate count does not change.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREES = ("src", "i18n/en/src", "i18n/ja/src")
ARTIFACTS = (
    "Content rephrased for compliance with licensing restrictions",
    "Sources cited inline.",
)


def test_no_research_tool_notes_in_chapters() -> None:
    hits = []
    for tree in TREES:
        for md in sorted((ROOT / tree).rglob("*.md")):
            for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                if any(a in line for a in ARTIFACTS):
                    hits.append(f"{md.relative_to(ROOT)}:{n}: {line.strip()[:80]}")
    assert not hits, "tool residue in chapters:\n" + "\n".join(hits[:20])
