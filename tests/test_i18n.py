import json
import re
import subprocess
from pathlib import Path
from html.parser import HTMLParser


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "ecommerce_ai_skills/runtime/web/i18n.js"
APP_JS = ROOT / "ecommerce_ai_skills/runtime/web/app.js"


def _catalogs():
    script = """
      global.window = {localStorage: {getItem: () => null, setItem: () => {}}};
      global.document = undefined;
      require(process.argv[1]);
      process.stdout.write(JSON.stringify(window.CommerceI18n.CATALOG));
    """
    result = subprocess.run(["node", "-e", script, str(I18N)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_bilingual_catalog_is_symmetric_and_nonempty():
    catalogs = _catalogs()
    assert set(catalogs) == {"zh-CN", "en", "ja"}
    assert set(catalogs["zh-CN"]) == set(catalogs["en"]) == set(catalogs["ja"])
    assert all(isinstance(v, str) and v.strip() for locale in catalogs.values() for v in locale.values())
    assert all("Localized interface copy" not in v for locale in catalogs.values() for v in locale.values())
    assert all(not re.search(r"[\u4e00-\u9fff]", value) for value in catalogs["en"].values())
    assert len(catalogs["zh-CN"]) == len(set(catalogs["zh-CN"]))
    # ja must be a genuine translation, not a copy of zh-CN, for every key
    # where the zh-CN and en source values actually differ (i.e. a key that
    # is demonstrably translatable rather than a stable brand/product term).
    # The locale switcher's own Japanese-language label is a deliberate
    # exception: like a brand name, "日本語" (Japanese for "Japanese") is the autonym
    # shown on the button regardless of the active locale, so zh-CN and ja
    # intentionally share that exact value; only en names it in English.
    autonym_labels = {"日本語"}
    translatable = [k for k in catalogs["zh-CN"] if catalogs["zh-CN"][k] != catalogs["en"][k] and k not in autonym_labels]
    copied_from_zh = [k for k in translatable if catalogs["ja"][k] == catalogs["zh-CN"][k]]
    assert not copied_from_zh, f"ja copies zh-CN verbatim for: {copied_from_zh}"


def test_required_status_terms_and_product_surface_are_present():
    catalogs = _catalogs()
    required = {"connected", "disconnected", "pending", "running", "completed", "failed", "blocked", "approved", "rejected", "expired", "viewer", "operator", "admin", "owner", "需要 admin 或 owner 角色", "创建提案", "导入 Evidence"}
    assert required <= set(catalogs["zh-CN"])
    assert required <= set(catalogs["en"])
    assert required <= set(catalogs["ja"])
    # Brand/API names are not translated; generic Evidence remains a deliberate
    # product term in the UI, so it is allowed as a phrase key.
    # Runtime is a deliberate product term; brands and credential labels remain
    # stable and are only translated when embedded in a larger UI phrase.
    assert {"Amazon", "Shopify", "API Key"}.isdisjoint(set(catalogs["zh-CN"]))


class _VisibleSurface(HTMLParser):
    """Collect fixed user-facing HTML copy, excluding code/data containers."""
    def __init__(self):
        super().__init__(); self.skip = 0; self.values = set()
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "code", "pre"}: self.skip += 1
        if not self.skip:
            for name, value in attrs:
                if name in {"aria-label", "title", "placeholder"} and value and re.search(r"[\u4e00-\u9fff]", value):
                    self.values.add(value.strip())
    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "code", "pre"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        value = data.strip()
        if not self.skip and value and re.search(r"[\u4e00-\u9fff]", value): self.values.add(value)


def test_mission_control_fixed_cjk_surface_has_english_catalog_coverage():
    parser = _VisibleSurface()
    parser.feed((ROOT / "ecommerce_ai_skills/runtime/web/mission-control.html").read_text(encoding="utf-8"))
    catalogs = _catalogs()
    # Templates and JSON payloads are data, not fixed UI copy.
    fixed = {value for value in parser.values if not value.startswith("{") and "${" not in value}
    missing = sorted(value for value in fixed if value not in catalogs["en"])
    assert not missing, f"missing en catalog entries: {missing}"
    assert all(not re.search(r"[\u4e00-\u9fff]", catalogs["en"][value]) for value in fixed)


def test_key_app_feedback_and_permission_copy_has_english_coverage():
    catalogs = _catalogs()
    required = {"暂无同步活动", "暂无后台任务", "暂无行动提案", "无法加载提案", "界面语言已更新。", "提案已提交审批。", "健康检查已完成。", "需要 admin 或 owner 角色"}
    assert required <= set(catalogs["zh-CN"]) == set(catalogs["en"]) == set(catalogs["ja"])
    assert all(not re.search(r"[\u4e00-\u9fff]", catalogs["en"][key]) for key in required)
    assert all(catalogs["ja"][key].strip() for key in required)


def test_common_navigation_theme_and_recovery_terms_are_bilingual():
    catalogs = _catalogs()
    required = {"Agents", "Evidence", "Connections", "Connection Center", "Runtime", "Marketplace", "AI", "Reports", "Light", "Dark", "加载失败", "保存失败", "连接失败", "修复", "立即修复"}
    assert required <= set(catalogs["zh-CN"]) | set(catalogs["en"])
    assert required <= set(catalogs["ja"])
    assert catalogs["zh-CN"]["Agents"] == "智能体"
    assert catalogs["zh-CN"]["Evidence"] == "证据"
    assert catalogs["zh-CN"]["Light"] == "浅色"
    assert catalogs["en"]["Light"] == "Light"
    assert catalogs["ja"]["Agents"] == "エージェント"
    assert catalogs["ja"]["Evidence"] == "証拠"
    assert catalogs["ja"]["Light"] == "ライト"
    assert catalogs["zh-CN"]["Marketplace connection"] == "平台连接"
    assert catalogs["zh-CN"]["Runtime API"] == "运行时 API"
    assert catalogs["en"]["连接 Amazon SP-API、Amazon Ads 与 Shopify；保存环境变量引用，不保存密钥值。"].startswith("Connect Amazon SP-API")


def test_javascript_syntax_and_locale_storage_is_non_sensitive():
    result = subprocess.run(["node", "--check", str(I18N)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    source = I18N.read_text(encoding="utf-8")
    assert "localStorage.setItem(STORAGE_KEY, next)" in source
    assert "apiKey" not in source
    assert "API_KEY" not in source
    assert "sessionStorage" not in source


def test_dom_apply_round_trips_and_tracks_dynamic_text():
    script = r'''
      const fs = require("fs");
      let stored = "zh-CN";
      const html = {lang: "", attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }};
      const text = {nodeValue: "今日简报", parentElement: {tagName: "DIV"}};
      const button = {attrs: {"aria-label": "主导航"}, hasAttribute(k) { return k in this.attrs; }, getAttribute(k) { return this.attrs[k]; }, setAttribute(k, v) { this.attrs[k] = v; }};
      const doc = {title: "Commerce Agent OS · 今日简报", documentElement: html, body: {},
        createTreeWalker() { let done = false; return {nextNode() { if (done) return false; done = true; this.currentNode = text; return true; }}; },
        querySelectorAll() { return [button]; }};
      global.window = {document: doc, localStorage: {getItem() { return stored; }, setItem(k, v) { stored = v; }}};
      require(process.argv[1]);
      window.CommerceI18n.setLocale("en");
      if (text.nodeValue !== "Daily Briefing" || doc.title !== "Commerce Agent OS · Daily Briefing" || button.attrs["aria-label"] !== "Main navigation") process.exit(2);
      window.CommerceI18n.setLocale("ja");
      if (text.nodeValue !== "今日のブリーフィング" || doc.title !== "Commerce Agent OS · 今日のブリーフィング" || button.attrs["aria-label"] !== "メインナビゲーション") process.exit(5);
      window.CommerceI18n.setLocale("zh-CN");
      if (text.nodeValue !== "今日简报" || doc.title !== "Commerce Agent OS · 今日简报" || button.attrs["aria-label"] !== "主导航") process.exit(3);
      text.nodeValue = "查看今日简报";
      window.CommerceI18n.apply(doc);
      if (text.nodeValue !== "查看今日简报") process.exit(4);
    '''
    result = subprocess.run(["node", "-e", script, str(I18N)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_dynamic_counters_translate_without_touching_user_data():
    script = r'''
      global.window = {localStorage: {getItem: () => null, setItem: () => {}}};
      require(process.argv[1]);
      const i = window.CommerceI18n;
      if (i.translate("12 present", "zh-CN") !== "12 存在") process.exit(2);
      if (i.translate("3 checks passed", "zh-CN") !== "3 检查项通过") process.exit(3);
      if (i.translate("4 sources", "en") !== "4 Sources") process.exit(4);
      if (i.translate("customer sources", "zh-CN") !== "customer sources") process.exit(5);
      if (i.translate("5 present", "ja") !== "5 検出済み") process.exit(6);
      if (i.translate("2 rows", "ja") !== "2 レコード") process.exit(7);
    '''
    result = subprocess.run(["node", "-e", script, str(I18N)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_storage_failure_is_visible_in_document_state():
    script = r'''
      const html = {attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }};
      global.window = {document: {documentElement: html}, localStorage: {getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }}};
      require(process.argv[1]);
      window.CommerceI18n.getLocale();
      if (html.attrs["data-locale-storage"] !== "unavailable") process.exit(2);
    '''
    result = subprocess.run(["node", "-e", script, str(I18N)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_storage_failure_keeps_locale_in_memory_for_current_page():
    script = r'''
      const html = {attrs: {}, lang: "", setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute() {}};
      const text = {nodeValue: "今日简报", parentElement: {tagName: "DIV"}};
      const doc = {title: "Commerce Agent OS · 今日简报", documentElement: html, body: {},
        createTreeWalker() { let done = false; return {nextNode() { if (done) return false; done = true; this.currentNode = text; return true; }}; },
        querySelectorAll() { return []; }};
      global.window = {document: doc, localStorage: {getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }}};
      require(process.argv[1]);
      window.CommerceI18n.setLocale("en");
      if (window.CommerceI18n.getLocale() !== "en" || text.nodeValue !== "Daily Briefing" || html.attrs["data-locale-storage"] !== "unavailable") process.exit(2);
    '''
    result = subprocess.run(["node", "-e", script, str(I18N)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


_REGEX_ALLOWED_BEFORE_KEYWORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "else", "yield", "case", "do", "throw",
}


def _regex_allowed_before(source, pos):
    """True if a `/` at `pos` can start a regex literal rather than being a
    division operator, based on the nearest significant token before it."""
    j = pos - 1
    while j >= 0 and source[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return True
    ch = source[j]
    if ch.isalnum() or ch in "_$":
        k = j
        while k >= 0 and (source[k].isalnum() or source[k] in "_$"):
            k -= 1
        return source[k + 1:j + 1] in _REGEX_ALLOWED_BEFORE_KEYWORDS
    if ch in ")]`'\"":
        return False
    return True


def _iter_js_string_tokens(source):
    """Yield (kind, text, line, preceding) for every string-literal value
    and template-literal quasi (static text chunk) in a JS source, skipping
    comments and regex literals. `kind` is "string" or "template"; for
    "string" tokens, `preceding` is a slice of source right before the
    opening quote, used to sniff the enclosing call (e.g. `console.error(`).

    This is a hand-rolled lexer, not a real parser -- but its output was
    cross-checked line-for-line against an acorn AST walk of this exact
    file (every CJK-containing Literal/TemplateElement node) with zero
    differences, including through the file's two `${...}` interpolation
    nesting patterns and its five regex literals.
    """
    i, n, line = 0, len(source), 1
    stack = [{"kind": "TOP"}]

    def advance(count):
        nonlocal i, line
        line += source.count("\n", i, i + count)
        i += count

    while i < n:
        frame = stack[-1]
        if frame["kind"] == "TMPL":
            ch = source[i]
            if ch == "\\" and i + 1 < n:
                frame["buf"].append(source[i + 1])
                advance(2)
                continue
            if ch == "`":
                yield ("template", "".join(frame["buf"]), frame["start_line"], "")
                stack.pop()
                advance(1)
                continue
            if ch == "$" and i + 1 < n and source[i + 1] == "{":
                yield ("template", "".join(frame["buf"]), frame["start_line"], "")
                frame["buf"] = []
                advance(2)
                stack.append({"kind": "INTERP", "depth": 0})
                continue
            frame["buf"].append(ch)
            advance(1)
            continue
        ch = source[i]
        if ch == "\n":
            advance(1)
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            j = source.find("\n", i)
            advance((n if j == -1 else j) - i)
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            j = source.find("*/", i + 2)
            end = n if j == -1 else j + 2
            advance(end - i)
            continue
        if ch in ("'", '"'):
            start_line, start = line, i
            advance(1)
            buf = []
            while i < n and source[i] != ch:
                if source[i] == "\\" and i + 1 < n:
                    buf.append(source[i + 1])
                    advance(2)
                    continue
                buf.append(source[i])
                advance(1)
            advance(1)
            yield ("string", "".join(buf), start_line, source[max(0, start - 60):start])
            continue
        if ch == "`":
            stack.append({"kind": "TMPL", "buf": [], "start_line": line})
            advance(1)
            continue
        if ch == "/" and _regex_allowed_before(source, i):
            advance(1)
            in_class = False
            while i < n:
                c = source[i]
                if c == "\\" and i + 1 < n:
                    advance(2)
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class:
                    advance(1)
                    break
                elif c == "\n":
                    break
                advance(1)
            while i < n and source[i].isalpha():
                advance(1)
            continue
        if frame["kind"] == "INTERP":
            if ch == "{":
                frame["depth"] += 1
                advance(1)
                continue
            if ch == "}":
                if frame["depth"] > 0:
                    frame["depth"] -= 1
                    advance(1)
                    continue
                stack.pop()
                advance(1)
                continue
        advance(1)


def test_app_js_has_no_raw_cjk_literal_outside_the_catalog():
    """Every CJK-containing string literal or template-literal text chunk in
    app.js must be translatable under en/ja: it must be a key already
    present in the catalog, which is how it reaches a locale -- whether via
    a direct `tr("...")` call, via a helper that calls `tr()` on the
    argument internally (`notice`, `badge`, `designedEmpty`, `act`,
    `showDetail`), or via a local variable/object-lookup that is later
    passed to one of those.

    Catalog membership, not "is this a tr() call syntactically", is what
    this test checks, because a string can be a direct argument of tr() and
    still render as raw Chinese under en/ja if nobody added it to the
    catalog -- that is exactly the bug this test caught in `busy()`, which
    called `tr("处理中…")` for a key the catalog did not have (the catalog
    had "处理中" via the `processing` status key, but not the ellipsis
    variant actually used here).

    A tiny, reasoned set of exceptions covers text that structurally never
    reaches the rendered page.
    """
    source = APP_JS.read_text(encoding="utf-8")
    catalog_keys = set(_catalogs()["zh-CN"])
    cjk = re.compile(r"[一-鿿]")
    console_call = re.compile(r"console\.(?:log|warn|error|info|debug)\s*\($")

    # A few lines hold a `state.locale === "en" ? ... : state.locale === "ja"
    # ? ... : ...` ternary whose template-literal branches are hand-written
    # per locale (updateTodayLabel's "today" label, the evidence-count
    # sentences in renderBriefing). There is deliberately no catalog lookup
    # for these chunks: the correct language is selected by the `? :` itself.
    # They are recognised by that pattern on the same source line, not by
    # line number, so an edit elsewhere in the file cannot break this test.
    inline_locale_branch_lines = {
        number for number, line in enumerate(source.splitlines(), 1)
        if 'state.locale === "en" ?' in line and 'state.locale === "ja" ?' in line
    }
    assert 1 <= len(inline_locale_branch_lines) <= 6, inline_locale_branch_lines

    # Literals that never reach the rendered page. Empty at the moment:
    # payload template defaults (proposalPayloadTemplates) are rendered through
    # tr() at serialisation time, so they are ordinary catalog keys.
    allowlisted_literals = {}

    violations = []
    for kind, text, line, preceding in _iter_js_string_tokens(source):
        if not cjk.search(text):
            continue  # not Chinese text -- comments, English, punctuation, etc.
        if kind == "template" and line in inline_locale_branch_lines:
            continue
        if kind == "string" and console_call.search(preceding):
            continue  # developer diagnostic text; never rendered on the page
        if text in allowlisted_literals:
            continue
        if text in catalog_keys:
            continue
        violations.append((line, kind, text))

    assert not violations, "raw or uncataloged CJK literal(s) in app.js:\n" + "\n".join(
        f"  line {line} ({kind}): {text!r}" for line, kind, text in violations
    )
