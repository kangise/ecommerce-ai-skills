#!/usr/bin/env python3
"""Give the built mdBook site share-card metadata, a sitemap, and an llms.txt.

Why this exists
----------------
pages.yml builds three mdBook books (zh at the site root, en/ under /en/, ja/
under /ja/) and ships them as-is. mdBook's own <head> is minimal — a <title>,
one <meta name="description"> sourced from book.toml, and asset links — so a
chapter link pasted into X/Slack/Discord/WeChat unfurls as a bare URL, search
engines have no canonical/hreflang signal across the three languages, and
there is no sitemap.xml or llms.txt (an emerging convention some LLM tools
check for a plain-text map of a site). This is a *post*-build step: it edits
the HTML mdBook already produced, so it must run after `mdbook build` and
before the Pages upload.

Deliberately not done here: robots.txt. Crawlers fetch /robots.txt from the
*host* root (kangise.github.io), which this project site does not control —
shipping one at /ecommerce-ai-skills/robots.txt would just be a file nobody
reads, and would misleadingly imply this repo can set crawl policy for the
whole kangise.github.io domain.

What "og:description" copies. mdBook already renders
`<meta name="description" content="...">` from each book's book.toml, with
attribute-escaping already applied. Rather than re-deriving that string (and
risking drift from book.toml), this script reads it back out of the page and
reuses it verbatim for og:description/twitter:description — one source of
truth, and it can never disagree with what mdBook already shipped.

Idempotency. Each injected page gets a single `<!-- site-meta -->` marker.
A page that already has it is left untouched (not re-diffed, not
re-written) — safe to run this script twice over the same build.

Usage:
  python3 scripts/build_site_meta.py <docs-dir>

<docs-dir> is a built site with the zh book at its root and the en/ja books
under <docs-dir>/en and <docs-dir>/ja (matching pages.yml's `mdbook build`,
`mdbook build i18n/en --dest-dir docs/en`, `... i18n/ja --dest-dir docs/ja`).
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent

SITE_BASE = "https://kangise.github.io/ecommerce-ai-skills/"
GITHUB_REPO = "https://github.com/kangise/ecommerce-ai-skills"

# hreflang code -> (subdirectory under <docs-dir>, book.toml path, og:locale)
LOCALES: dict[str, tuple[str, Path, str]] = {
    "zh-CN": ("", ROOT / "book.toml", "zh_CN"),
    "en": ("en", ROOT / "i18n" / "en" / "book.toml", "en_US"),
    "ja": ("ja", ROOT / "i18n" / "ja" / "book.toml", "ja_JP"),
}
# Emit alternates in a fixed order regardless of dict iteration.
LOCALE_ORDER = ["zh-CN", "en", "ja"]

# mdBook pages that are not "chapters" and get no share metadata or sitemap entry.
EXCLUDED_PAGES = {"print.html", "toc.html", "404.html"}

MARKER = "<!-- site-meta -->"

EN_SRC = ROOT / "i18n" / "en" / "src"
EN_SUMMARY = EN_SRC / "SUMMARY.md"


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------

def md_to_html_rel(md_rel: str) -> str:
    """Map a SUMMARY.md-style path to the html file mdBook renders it as.

    mdBook renders every `<dir>/README.md` (including the top-level one) to
    `<dir>/index.html`; every other `<dir>/name.md` becomes `<dir>/name.html`.
    """
    posix = md_rel.replace("\\", "/")
    if posix == "README.md":
        return "index.html"
    if posix.endswith("/README.md"):
        return posix[: -len("README.md")] + "index.html"
    return posix[: -len(".md")] + ".html" if posix.endswith(".md") else posix


def page_url(base: str, rel_html: str) -> str:
    """Absolute URL for a book-relative html path, collapsing .../index.html."""
    if rel_html == "index.html":
        return base
    if rel_html.endswith("/index.html"):
        return base + rel_html[: -len("index.html")]
    return base + rel_html


def escape_attr(text: str) -> str:
    """Escape text for use inside a double-quoted HTML attribute value."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def book_title(locale: str) -> str:
    _, toml_path, _ = LOCALES[locale]
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    return data["book"]["title"]


def book_description(locale: str) -> str:
    _, toml_path, _ = LOCALES[locale]
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    return data["book"]["description"]


# --------------------------------------------------------------------------
# Discovering pages in a built docs tree
# --------------------------------------------------------------------------

def discover_pages(root: Path, *, skip_top_dirs: frozenset[str] = frozenset()) -> list[str]:
    """Sorted book-relative POSIX paths of real content pages under `root`."""
    pages = []
    for path in root.rglob("*.html"):
        rel = path.relative_to(root).as_posix()
        top = rel.split("/", 1)[0]
        if top in skip_top_dirs or rel in EXCLUDED_PAGES:
            continue
        pages.append(rel)
    return sorted(pages)


# --------------------------------------------------------------------------
# Per-page <head> injection
# --------------------------------------------------------------------------

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_DESCRIPTION_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"\s*/?>')


def build_head_block(
    *,
    self_locale: str,
    self_url: str,
    alternates: dict[str, str],
    title_text: str,
    description_attr: str,
    image_url: str,
) -> str:
    _, _, og_locale = LOCALES[self_locale]
    site_name = escape_attr(book_title(self_locale))
    title_attr = escape_attr(html.unescape(title_text))

    lines = [MARKER, f'<link rel="canonical" href="{self_url}">']
    for loc in LOCALE_ORDER:
        if loc in alternates:
            lines.append(f'<link rel="alternate" hreflang="{loc}" href="{alternates[loc]}">')
    x_default = alternates.get("en") or alternates.get("zh-CN") or self_url
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{x_default}">')
    lines += [
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{site_name}">',
        f'<meta property="og:title" content="{title_attr}">',
        f'<meta property="og:description" content="{description_attr}">',
        f'<meta property="og:url" content="{self_url}">',
        f'<meta property="og:image" content="{image_url}">',
        '<meta property="og:image:width" content="1280">',
        '<meta property="og:image:height" content="640">',
        f'<meta property="og:locale" content="{og_locale}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title_attr}">',
        f'<meta name="twitter:description" content="{description_attr}">',
        f'<meta name="twitter:image" content="{image_url}">',
    ]
    return "\n".join(lines) + "\n"


def inject_page(
    path: Path,
    *,
    self_locale: str,
    self_url: str,
    alternates: dict[str, str],
    image_url: str,
) -> bool:
    """Insert the meta block before </head>. Returns False if already present."""
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False

    title_m = _TITLE_RE.search(text)
    if not title_m:
        raise SystemExit(f"{path}: no <title> to derive og:title from")
    desc_m = _DESCRIPTION_RE.search(text)
    description_attr = desc_m.group(1) if desc_m else escape_attr(book_description(self_locale))

    block = build_head_block(
        self_locale=self_locale,
        self_url=self_url,
        alternates=alternates,
        title_text=title_m.group(1),
        description_attr=description_attr,
        image_url=image_url,
    )
    if "</head>" not in text:
        raise SystemExit(f"{path}: no </head> to inject before")
    text = text.replace("</head>", block + "</head>", 1)
    path.write_text(text, encoding="utf-8")
    return True


# --------------------------------------------------------------------------
# sitemap.xml
# --------------------------------------------------------------------------

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"


def write_sitemap(entries: list[tuple[str, dict[str, str]]], dest: Path) -> int:
    """entries: list of (self_url, alternates-including-self), sitemaps.org XML."""
    ET.register_namespace("", SITEMAP_NS)
    ET.register_namespace("xhtml", XHTML_NS)
    urlset = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for self_url, alternates in sorted(entries, key=lambda e: e[0]):
        url_el = ET.SubElement(urlset, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(url_el, f"{{{SITEMAP_NS}}}loc").text = self_url
        x_default = alternates.get("en") or alternates.get("zh-CN") or self_url
        links = [(loc, href) for loc, href in alternates.items()] + [("x-default", x_default)]
        for loc, href in links:
            link_el = ET.SubElement(url_el, f"{{{XHTML_NS}}}link")
            link_el.set("rel", "alternate")
            link_el.set("hreflang", loc)
            link_el.set("href", href)
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    tree.write(dest, encoding="UTF-8", xml_declaration=True)
    return len(entries)


# --------------------------------------------------------------------------
# llms.txt  (https://llmstxt.org) — built only from repo sources, no docs tree needed
# --------------------------------------------------------------------------

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_HR_RE = re.compile(r"^[-*_]{3,}\s*$")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPHASIS_RE = re.compile(r"(\*\*\*|\*\*|\*|___|__|_)")
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
# A letter (not a digit) right before the punctuation rules out list numbering
# like "1." — the one recurring false positive in this book's "## Chapter
# Navigation" index lines (see the after_nav_heading handling below).
_SENTENCE_END_RE = re.compile(r"(?<=[A-Za-z])[.!?](?=\s|$)")


_LIST_MARKER_RE = re.compile(r"^(?:[-*+]|\d+\.)\s+")
# resources/glossary.md's surviving "- **EN**: <definition>" bullet (see
# _is_mostly_ascii_prose below) still carries its bold language label once the
# list marker is gone — a bare 2-4 letter all-caps token then ":" is
# unambiguously a label, never the start of a real sentence.
# Only the glossary's language labels; a general "2-4 capitals + colon" rule
# also ate "POV:" and left a sentence fragment.
_LABEL_PREFIX_RE = re.compile(r"^(?:ZH|EN|JA):\s+")
# The failure-boundary section says when a chapter does NOT apply; a note
# taken from it describes the opposite of the page.
_BOUNDARY_HEADING_RE = re.compile(r"when this (?:doesn't|does not) work|where this stops working", re.I)


def _clean_inline(text: str) -> str:
    text = _LIST_MARKER_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _EMPHASIS_RE.sub("", text)
    text = _LABEL_PREFIX_RE.sub("", text)
    return " ".join(text.split())


def _is_mostly_ascii_prose(text: str) -> bool:
    """Reject a candidate paragraph that is mostly non-Latin script.

    resources/glossary.md pairs a "- **ZH**: ..." definition with a
    "- **EN**: ..." one on the very next line (no blank line between them,
    so without this check they'd merge into one candidate paragraph). This
    file builds an *English* llms.txt, so a paragraph has to actually be
    English to serve as its description.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(c.isascii() for c in letters) / len(letters) >= 0.6


def _cap(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit(" ", 1)[0]
    return truncated.rstrip(",;:.- ") + "…"


def first_prose_sentence(markdown: str, cap: int = 160) -> str:
    """The chapter's first real prose sentence, as plain text.

    Skips headings, blockquote metadata ("> **Track**: ..."), tables, fenced
    code, and HTML comments, per the llms.txt entry spec. Two more lines this
    book's chapters consistently open with would otherwise win by default and
    produce garbage: every chapter's "## Chapter Navigation" section is one
    line of bare `N. [title](#anchor)` cross-links (no prose at all — the
    stray periods after the numbers are list markers, not sentence ends,
    which is what _SENTENCE_END_RE's letter-lookbehind is for); some open
    with a bare Colab-badge line (`[![Open In Colab](...)](...)`) that is
    pure link/image markup once cleaned. Both are dropped by the
    "nothing left after stripping links/images" check below.
    """
    text = _HTML_COMMENT_RE.sub("", markdown)
    kept: list[str | None] = []  # None = paragraph break
    in_fence = False
    discard_paragraph = False
    after_nav_heading = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped:
            kept.append(None)
            discard_paragraph = False
            continue
        heading_m = _HEADING_RE.match(stripped)
        if heading_m:
            if _BOUNDARY_HEADING_RE.search(heading_m.group(1)):
                break
            after_nav_heading = heading_m.group(1).strip().lower() == "chapter navigation"
            continue
        if after_nav_heading:
            discard_paragraph = True
            after_nav_heading = False
        if discard_paragraph or stripped.startswith(">") or "|" in stripped or _HR_RE.match(stripped):
            continue
        residual = _LINK_RE.sub("", _IMAGE_RE.sub("", stripped)).strip(" ·-|")
        if not residual:
            continue
        # A list item is its own unit even without a blank line before it —
        # this book often runs a lead-in straight into a bullet list, e.g.
        # "After this module you'll be able to:\n- Bulk-analyze...". Without
        # forcing a break here the two merge into one ungrammatical paragraph.
        if _LIST_MARKER_RE.match(stripped) and kept and kept[-1] is not None:
            kept.append(None)
        kept.append(stripped)

    paragraphs, current = [], []
    for item in kept:
        if item is None:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(item)
    if current:
        paragraphs.append(" ".join(current))

    for para in paragraphs:
        cleaned = _clean_inline(para)
        if not cleaned or not _is_mostly_ascii_prose(cleaned):
            continue
        sentences = _sentences(cleaned)
        if not sentences or _not_a_description(sentences[0]):
            continue
        # A short hook ("Pinterest is a search engine.") says little on its
        # own; keep adding sentences from the same paragraph until there is
        # enough to describe the page.
        picked = sentences[0]
        for nxt in sentences[1:]:
            if len(picked) >= _MIN_DESCRIPTION or len(picked) + 1 + len(nxt) > cap:
                break
            picked = f"{picked} {nxt}"
        return _cap(picked, cap)
    # Nothing qualified. An entry without notes is valid llms.txt; a note that
    # is a citation list or a glossary definition is worse than none.
    return ""


# "e.g." and friends end in a letter plus a period, which _SENTENCE_END_RE
# reads as a sentence end — the glossary's first definition was cut at "e.g.".
_ABBREVIATIONS = ("e.g", "i.e", "vs", "etc", "approx", "incl", "cf")
_MIN_DESCRIPTION = 60


def _sentences(text: str) -> list[str]:
    out, start = [], 0
    for m in _SENTENCE_END_RE.finditer(text):
        token = text[start:m.start()].rsplit(" ", 1)[-1].lower()
        if token in _ABBREVIATIONS:
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    # A paragraph with no sentence end is a label or a list item
    # ("Audience: ...", "Generate brand stories with AI"), not a description.
    return [s for s in out if s]


def _not_a_description(sentence: str) -> bool:
    """Openers that are true to the chapter but do not say what it is: a
    rhetorical question, a citation line, or a track's completion criterion
    ("Path A is done when: ...")."""
    return (
        sentence.endswith("?")
        or sentence.lower().startswith(("source:", "sources:"))
        or " is done when" in sentence
    )


def parse_summary(summary_text: str) -> tuple[list[tuple[str, str]], dict[str, list[tuple[str, str]]]]:
    """Return (preface_entries, {track_name: [(title, md_path), ...]}).

    Mirrors SUMMARY.md's own structure: a "# Contents" H1 (dropped — it never
    collects any list items, since the bare "[Preface](README.md)" link that
    follows it is diverted to its own bucket, not "the current track"), then
    per-track H1s each followed by "- [title](path)" list items.
    """
    bare_re = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)\s*$")
    item_re = re.compile(r"^-\s*\[([^\]]+)\]\(([^)]+)\)")
    tracks: dict[str, list[tuple[str, str]]] = {}
    preface: list[tuple[str, str]] = []
    current: str | None = None
    for raw in summary_text.splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("# "):
            current = line[2:].strip()
            tracks.setdefault(current, [])
            continue
        bare_m = bare_re.match(line)
        item_m = item_re.match(line)
        if bare_m:
            preface.append((bare_m.group(1), bare_m.group(2)))
        elif item_m:
            tracks.setdefault(current or "Preface", []).append((item_m.group(1), item_m.group(2)))
    return preface, tracks


# Pages whose body has no introduction to take a sentence from.
_NOTE_OVERRIDES = {
    # Every heading is an entry, so the "first sentence" is one term's definition.
    "resources/glossary.md": "Definitions of the domain terms used across the book, in Chinese, English and Japanese, generated from the ontology.",
}


def build_llms_txt() -> tuple[str, int]:
    en_title = book_title("en")
    en_description = book_description("en")
    en_base = SITE_BASE + "en/"

    summary_text = EN_SUMMARY.read_text(encoding="utf-8")
    preface, tracks = parse_summary(summary_text)

    sections: list[tuple[str, list[tuple[str, str]]]] = [("Preface", preface)]
    sections += [(name, entries) for name, entries in tracks.items() if entries]

    lines = [f"# {en_title}", "", f"> {en_description}", ""]
    lines.append(
        "This file lists every chapter grouped by track, each with its canonical "
        "English URL and a one-line synopsis taken from the chapter's own opening "
        "sentence. The Chinese and Japanese translations of the same chapters are "
        "linked under Optional, not repeated here."
    )
    lines.append("")

    entry_count = 0
    for name, entries in sections:
        lines.append(f"## {name}")
        for title, md_path in entries:
            html_rel = md_to_html_rel(md_path)
            url = page_url(en_base, html_rel)
            chapter_md = EN_SRC / md_path
            description = _NOTE_OVERRIDES.get(md_path) or (
                first_prose_sentence(chapter_md.read_text(encoding="utf-8")) if chapter_md.is_file() else "")
            entry_count += 1
            if description:
                lines.append(f"- [{title}]({url}): {description}")
            else:
                lines.append(f"- [{title}]({url})")
        lines.append("")

    lines.append("## Install")
    lines.append(f"- [Project README]({GITHUB_REPO}/blob/main/README.md): setup and overview.")
    lines.append(f"- [SKILL.md]({GITHUB_REPO}/blob/main/dist/SKILL.md): the packaged skill definition.")
    lines.append(f"- [MCP integration guide]({GITHUB_REPO}/blob/main/integration/mcp.md): wiring up the MCP server.")
    lines.append("")

    lines.append("## Optional")
    lines.append(f"- [Chinese site]({SITE_BASE}): 中文版，与英文版章节一一对应。")
    lines.append(f"- [Japanese site]({SITE_BASE}ja/): 日本語版。英語版と章立てが一致。")
    lines.append("")

    return "\n".join(lines), entry_count


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs_dir", help="built site root (zh at its root, en/ and ja/ subdirs)")
    args = parser.parse_args()
    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.is_dir():
        raise SystemExit(f"not a directory: {docs_dir}")

    other_subdirs = frozenset(sub for loc, (sub, _, _) in LOCALES.items() if sub)
    pages_by_locale: dict[str, set[str]] = {}
    for locale, (subdir, _, _) in LOCALES.items():
        root = docs_dir / subdir if subdir else docs_dir
        skip = other_subdirs if not subdir else frozenset()
        pages_by_locale[locale] = set(discover_pages(root, skip_top_dirs=skip)) if root.is_dir() else set()

    universe = sorted(set().union(*pages_by_locale.values()))

    image_url = SITE_BASE + "social-preview.png"
    injected = 0
    already_done = 0
    sitemap_entries: list[tuple[str, dict[str, str]]] = []
    for rel in universe:
        alternates = {
            loc: page_url(SITE_BASE + subdir + ("/" if subdir else ""), rel)
            for loc, (subdir, _, _) in LOCALES.items()
            if rel in pages_by_locale[loc]
        }
        for locale in alternates:
            subdir = LOCALES[locale][0]
            root = docs_dir / subdir if subdir else docs_dir
            self_url = alternates[locale]
            sitemap_entries.append((self_url, alternates))
            if inject_page(
                root / rel,
                self_locale=locale,
                self_url=self_url,
                alternates=alternates,
                image_url=image_url,
            ):
                injected += 1
            else:
                already_done += 1

    shutil.copyfile(ROOT / "assets" / "social-preview.png", docs_dir / "social-preview.png")

    sitemap_path = docs_dir / "sitemap.xml"
    url_count = write_sitemap(sitemap_entries, sitemap_path)

    llms_text, entry_count = build_llms_txt()
    (docs_dir / "llms.txt").write_text(llms_text, encoding="utf-8")

    print(
        f"site-meta: {injected} pages injected, {already_done} already had it, "
        f"sitemap.xml has {url_count} urls, llms.txt has {entry_count} chapter links"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
