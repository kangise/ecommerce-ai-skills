"""build_site_meta.py: share-card injection, sitemap.xml, llms.txt.

Two kinds of check here. Most build a tiny fake three-locale docs tree (mdBook
output is a black box we don't want this suite depending on — no mdbook
binary in the pytest environment) and run the script's main() against it.
The llms.txt builder is different: the task asks for it to work from repo
sources alone, with no built docs tree, so its test reads the real
i18n/en/src/SUMMARY.md and checks every chapter it lists made it into the
generated file.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_SUMMARY = ROOT / "i18n" / "en" / "src" / "SUMMARY.md"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_site_meta", ROOT / "scripts" / "build_site_meta.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/build_site_meta.py", *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )


def _page(title: str, description: str) -> str:
    """A minimal stand-in for what mdBook 0.5.4 actually emits in <head>."""
    return f"""<!DOCTYPE HTML>
<html><head>
<title>{title}</title>
<meta name="description" content="{description}">
</head>
<body>{title}</body>
</html>
"""


def build_fake_site(root: Path) -> None:
    """zh at `root`, en/ja beside it — the same shape pages.yml builds.

    Three chapters, deliberately with different language coverage so the
    hreflang fallback rules actually get exercised:
      - a1.html      : zh + en + ja (the common case)
      - sub/index.html: zh + en + ja, and a directory-index page
      - only-zh.html : zh only (no translation at all yet)
      - only-en.html : zh + en, no ja
    Plus print.html/toc.html/404.html in every locale, which must never get
    a meta block or a sitemap/llms.txt entry.
    """
    locales = {
        "": ("zh", "中文描述"),
        "en": ("EN", "English description"),
        "ja": ("ja", "日本語の説明"),
    }
    for subdir, (tag, description) in locales.items():
        base = root / subdir if subdir else root
        base.mkdir(parents=True, exist_ok=True)
        (base / "index.html").write_text(_page(f"{tag} Home", description), encoding="utf-8")
        (base / "a1.html").write_text(_page(f"{tag} Chapter One", description), encoding="utf-8")
        if subdir == "":  # only-zh.html has no translation at all yet
            (base / "only-zh.html").write_text(_page(f"{tag} Only ZH", description), encoding="utf-8")
        (base / "sub").mkdir(exist_ok=True)
        (base / "sub" / "index.html").write_text(_page(f"{tag} Sub Overview", description), encoding="utf-8")
        for excluded in ("print.html", "toc.html", "404.html"):
            (base / excluded).write_text(_page(f"{tag} {excluded}", description), encoding="utf-8")
        if subdir in ("", "en"):  # only-en.html exists in zh + en, never in ja
            (base / "only-en.html").write_text(_page(f"{tag} Only EN", description), encoding="utf-8")


def _hash_all_html(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*.html"))}


def test_injection_is_idempotent(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    first = run(str(tmp_path))
    assert first.returncode == 0, first.stdout + first.stderr
    assert "0 already had it" in first.stdout

    before = _hash_all_html(tmp_path)
    second = run(str(tmp_path))
    assert second.returncode == 0, second.stdout + second.stderr
    assert "0 pages injected" in second.stdout
    after = _hash_all_html(tmp_path)
    assert before == after, "a second run rewrote at least one html file"


def test_marker_present_exactly_once(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    for html_file in tmp_path.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8")
        assert text.count("<!-- site-meta -->") <= 1, html_file


def test_excluded_pages_are_never_touched(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    for subdir in ("", "en", "ja"):
        base = tmp_path / subdir if subdir else tmp_path
        for excluded in ("print.html", "toc.html", "404.html"):
            text = (base / excluded).read_text(encoding="utf-8")
            assert "site-meta" not in text, f"{subdir}/{excluded} should have been skipped"


def test_canonical_and_hreflang_urls(tmp_path: Path) -> None:
    module = load_module()
    build_fake_site(tmp_path)
    run(str(tmp_path))

    en_text = (tmp_path / "en" / "a1.html").read_text(encoding="utf-8")
    zh_url = module.page_url(module.SITE_BASE, "a1.html")
    en_url = module.page_url(module.SITE_BASE + "en/", "a1.html")
    ja_url = module.page_url(module.SITE_BASE + "ja/", "a1.html")

    assert f'<link rel="canonical" href="{en_url}">' in en_text
    assert f'<link rel="alternate" hreflang="zh-CN" href="{zh_url}">' in en_text
    assert f'<link rel="alternate" hreflang="en" href="{en_url}">' in en_text
    assert f'<link rel="alternate" hreflang="ja" href="{ja_url}">' in en_text
    # en exists for this page, so x-default must point at en, not zh-CN.
    assert f'<link rel="alternate" hreflang="x-default" href="{en_url}">' in en_text
    assert f'<meta property="og:url" content="{en_url}">' in en_text
    assert f'<meta property="og:locale" content="en_US">' in en_text


def test_directory_index_collapses_to_a_trailing_slash(tmp_path: Path) -> None:
    module = load_module()
    build_fake_site(tmp_path)
    run(str(tmp_path))
    text = (tmp_path / "en" / "sub" / "index.html").read_text(encoding="utf-8")
    expected = module.page_url(module.SITE_BASE + "en/", "sub/index.html")
    assert expected == module.SITE_BASE + "en/sub/"
    assert f'<link rel="canonical" href="{expected}">' in text


def test_hreflang_falls_back_to_zh_when_no_english_page_exists(tmp_path: Path) -> None:
    module = load_module()
    build_fake_site(tmp_path)
    run(str(tmp_path))
    zh_text = (tmp_path / "only-zh.html").read_text(encoding="utf-8")
    zh_url = module.page_url(module.SITE_BASE, "only-zh.html")
    # No en/ja copy of this page exists at all: only the zh-CN alternate (and
    # canonical) should be present, and x-default must fall back to it.
    assert f'<link rel="alternate" hreflang="en"' not in zh_text
    assert f'<link rel="alternate" hreflang="ja"' not in zh_text
    assert f'<link rel="alternate" hreflang="x-default" href="{zh_url}">' in zh_text


def test_missing_ja_page_is_left_out_of_its_siblings_alternates(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    en_text = (tmp_path / "en" / "only-en.html").read_text(encoding="utf-8")
    assert 'hreflang="ja"' not in en_text
    assert 'hreflang="en"' in en_text and 'hreflang="zh-CN"' in en_text


def test_og_title_reuses_and_reescapes_the_existing_title(tmp_path: Path) -> None:
    """og:title must be the page's own <title> text, unescape+re-escape — not
    a hand-written re-derivation that could disagree with what mdBook shipped."""
    tmp_path.mkdir(exist_ok=True)
    build_fake_site(tmp_path)
    text = (tmp_path / "en" / "a1.html").read_text(encoding="utf-8")
    assert "<title>EN Chapter One</title>" in text
    run(str(tmp_path))
    text = (tmp_path / "en" / "a1.html").read_text(encoding="utf-8")
    assert '<meta property="og:title" content="EN Chapter One">' in text
    assert '<meta name="twitter:title" content="EN Chapter One">' in text


def test_og_description_reuses_mdbooks_own_meta_description(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    text = (tmp_path / "en" / "a1.html").read_text(encoding="utf-8")
    assert '<meta property="og:description" content="English description">' in text
    assert '<meta name="twitter:description" content="English description">' in text
    # mdBook's own tag must still be there exactly once — not duplicated.
    assert text.count('<meta name="description"') == 1


def test_image_is_copied_and_referenced_absolutely(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    copied = tmp_path / "social-preview.png"
    assert copied.is_file()
    assert copied.read_bytes() == (ROOT / "assets" / "social-preview.png").read_bytes()
    text = (tmp_path / "en" / "a1.html").read_text(encoding="utf-8")
    image_url = "https://kangise.github.io/ecommerce-ai-skills/social-preview.png"
    assert f'<meta property="og:image" content="{image_url}">' in text
    assert '<meta property="og:image:width" content="1280">' in text
    assert '<meta property="og:image:height" content="640">' in text


def test_sitemap_lists_pages_and_excludes_print_toc_404(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    sitemap_path = tmp_path / "sitemap.xml"
    tree = ET.parse(sitemap_path)  # raises if not well-formed
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text for el in tree.getroot().findall("s:url/s:loc", ns)]

    # index/a1/sub-index in all 3 locales (9) + only-zh.html in zh alone (1)
    # + only-en.html in zh+en (2) = 12.
    assert len(locs) == 12
    assert "https://kangise.github.io/ecommerce-ai-skills/en/a1.html" in locs
    assert "https://kangise.github.io/ecommerce-ai-skills/en/sub/" in locs
    for loc in locs:
        assert not loc.endswith(("print.html", "toc.html", "404.html"))


def test_llms_txt_starts_with_h1(tmp_path: Path) -> None:
    build_fake_site(tmp_path)
    run(str(tmp_path))
    text = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith("# ")
    assert "\n> " in text


# --------------------------------------------------------------------------
# llms.txt against the real repository — no built docs tree involved.
# --------------------------------------------------------------------------

def _summary_entries() -> list[tuple[str, str]]:
    """Independent, deliberately tiny re-parse of SUMMARY.md's link syntax.

    Kept separate from module.parse_summary so this test does not just check
    the implementation against itself.
    """
    text = EN_SUMMARY.read_text(encoding="utf-8")
    return re.findall(r"^-?\s*\[([^\]]+)\]\(([^)]+)\)\s*$", text, re.M)


def _expected_html_rel(md_path: str) -> str:
    if md_path == "README.md":
        return "index.html"
    if md_path.endswith("/README.md"):
        return md_path[: -len("README.md")] + "index.html"
    return md_path[: -len(".md")] + ".html"


def test_every_summary_chapter_is_linked_in_llms_txt() -> None:
    module = load_module()
    llms_text, entry_count = module.build_llms_txt()
    entries = _summary_entries()
    assert entry_count == len(entries) == 77

    missing = []
    for _title, md_path in entries:
        url = module.SITE_BASE + "en/" + _expected_html_rel(md_path)
        # The site's own directory-index convention collapses ".../index.html".
        if url.endswith("/index.html"):
            url = url[: -len("index.html")]
        if url not in llms_text:
            missing.append((md_path, url))
    assert not missing, f"SUMMARY.md chapters missing from llms.txt: {missing}"


def test_llms_txt_has_install_and_optional_sections() -> None:
    module = load_module()
    llms_text, _ = module.build_llms_txt()
    assert "\n## Install" in llms_text
    assert "\n## Optional" in llms_text
    assert "dist/SKILL.md" in llms_text
    assert "integration/mcp.md" in llms_text
    assert "https://kangise.github.io/ecommerce-ai-skills/ja/" in llms_text


# ---------------------------------------------------------------------------
# llms.txt notes: what counts as a description of the page
# ---------------------------------------------------------------------------

def test_note_is_not_cut_at_an_abbreviation() -> None:
    """The glossary's first definition was cut at "e.g." — a letter plus a
    period reads as a sentence end unless abbreviations are recognised."""
    module = load_module()
    md = "# T\n\nFeeds carry product data, e.g. title and price, to shopping engines.\n"
    assert module.first_prose_sentence(md) == (
        "Feeds carry product data, e.g. title and price, to shopping engines.")


def test_questions_citations_and_completion_criteria_are_not_notes() -> None:
    module = load_module()
    for opener in (
        "Why doesn't ChatGPT know your product details?",
        "Sources: SegmentStream, Black Bear Media, Flyweel.",
        "Path A is done when: you have worked through the six modules.",
    ):
        md = f"# T\n\n{opener}\n\nThis chapter builds a restock plan from sales history.\n"
        assert module.first_prose_sentence(md) == (
            "This chapter builds a restock plan from sales history."), opener


def test_short_hook_takes_the_next_sentence_of_its_paragraph() -> None:
    module = load_module()
    md = "# T\n\nPinterest is a search engine. Pins keep getting traffic for months after posting.\n"
    assert module.first_prose_sentence(md) == (
        "Pinterest is a search engine. Pins keep getting traffic for months after posting.")


def test_failure_boundary_section_never_supplies_the_note() -> None:
    """That section says when the chapter does not apply; a note taken from it
    describes the opposite of the page (platform-comparison did this)."""
    module = load_module()
    md = ("# T\n\n| a | b |\n|---|---|\n\n## When this doesn't work\n\n"
          "- **You want to pick a platform straight off the table.** It does not decide for you.\n")
    assert module.first_prose_sentence(md) == ""


def test_no_qualifying_sentence_means_no_note_not_a_fallback() -> None:
    module = load_module()
    md = "# T\n\nAudience: sourcing and operations roles\n\n- Generate brand stories with AI\n"
    assert module.first_prose_sentence(md) == ""


def test_glossary_has_a_note_that_describes_the_page() -> None:
    module = load_module()
    text, _ = module.build_llms_txt()
    line = next(l for l in text.splitlines() if "resources/glossary.html" in l)
    assert "Definitions of the domain terms" in line
