"""Upstream watcher.

The value of this script is entirely in whether it fires when an upstream moves
and stays quiet when it does not. Network is mocked; what is pinned here is the
comparison logic, the blast-radius reporting, and the failure modes — a watcher
that silently reports "unchanged" after a failed probe would be worse than none.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "maintenance" / "source-watch.yaml"
STATE = ROOT / "maintenance" / "source-watch-state.json"


def load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "watch_sources", ROOT / "scripts" / "watch_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/watch_sources.py", *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )


def test_list_needs_no_network() -> None:
    """--list must work offline; it is how you inspect the watchlist on a plane."""
    result = run("--list")
    assert result.returncode == 0, result.stdout + result.stderr
    for source in yaml.safe_load(WATCHLIST.read_text())["sources"]:
        assert source["id"] in result.stdout


def test_every_source_declares_its_blast_radius() -> None:
    """A change with nothing attached to it is noise the reader has to triage."""
    for source in yaml.safe_load(WATCHLIST.read_text())["sources"]:
        affects = source.get("affects") or {}
        attached = (affects.get("constraint_prefixes") or []) \
            + (affects.get("code") or []) + (affects.get("chapters") or [])
        assert attached, f"{source['id']} affects nothing"
        assert source.get("why", "").strip(), f"{source['id']} has no rationale"


def test_declared_paths_exist() -> None:
    """A watchlist pointing at deleted files sends reviewers to nowhere."""
    for source in yaml.safe_load(WATCHLIST.read_text())["sources"]:
        affects = source.get("affects") or {}
        for path in (affects.get("code") or []) + (affects.get("chapters") or []):
            assert (ROOT / path).exists(), f"{source['id']} -> missing {path}"


def test_state_file_is_committed_not_just_present() -> None:
    """Presence on disk is not the invariant — being in the repo is.

    .gitignore carries a blanket `*.json`, so this file was silently untracked
    while sitting in the working tree. Every local run passed and every CI run
    failed, because CI clones. Assert what actually matters.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(STATE.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert tracked.returncode == 0, (
        f"{STATE.relative_to(ROOT)} is not tracked by git; a fresh clone will not "
        "have it. Check .gitignore for a pattern swallowing it.")


def test_state_file_covers_the_watchlist() -> None:
    """Committed state is the baseline; a missing id means the next run cries wolf."""
    assert STATE.exists(), f"{STATE.relative_to(ROOT)} missing"
    state = json.loads(STATE.read_text())
    for source in yaml.safe_load(WATCHLIST.read_text())["sources"]:
        assert source["id"] in state, f"no recorded baseline for {source['id']}"
        assert state[source["id"]].get("revision")


def test_changed_revision_is_detected(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "load_state",
                        lambda: {"x": {"revision": "old"}})
    monkeypatch.setattr(module, "load_watchlist", lambda: {
        "sources": [{"id": "x", "kind": "github", "repo": "a/b", "why": "w",
                     "affects": {"code": ["setup.py"]}}]})
    monkeypatch.setattr(module, "probe",
                        lambda s, ua: ({"revision": "new", "at": None, "url": "u"}, None))
    monkeypatch.setattr(sys, "argv", ["watch_sources.py", "--fail-on-change"])
    assert module.main() == 1


def test_same_revision_is_quiet(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "load_state", lambda: {"x": {"revision": "same"}})
    monkeypatch.setattr(module, "load_watchlist", lambda: {
        "sources": [{"id": "x", "kind": "github", "repo": "a/b", "why": "w",
                     "affects": {"code": ["setup.py"]}}]})
    monkeypatch.setattr(module, "probe",
                        lambda s, ua: ({"revision": "same", "at": None, "url": "u"}, None))
    monkeypatch.setattr(sys, "argv", ["watch_sources.py", "--fail-on-change"])
    assert module.main() == 0


def test_probe_failure_does_not_read_as_unchanged(monkeypatch, capsys) -> None:
    """A failed probe must surface as an error, never be folded into 'nothing moved'."""
    module = load_module()
    monkeypatch.setattr(module, "load_state", lambda: {"x": {"revision": "old"}})
    monkeypatch.setattr(module, "load_watchlist", lambda: {
        "sources": [{"id": "x", "kind": "github", "repo": "a/b", "why": "w",
                     "affects": {"code": ["setup.py"]}}]})
    monkeypatch.setattr(module, "probe", lambda s, ua: (None, "HTTP 500"))
    monkeypatch.setattr(sys, "argv", ["watch_sources.py"])

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "error" in out and "HTTP 500" in out
    assert "no upstream moved" not in out


def test_tls_failure_is_named_as_a_local_problem(monkeypatch) -> None:
    """"unreachable" would send the reader to check GitHub's status page."""
    module = load_module()

    def raise_ssl(url, ua, accept):
        raise urllib.error.URLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    monkeypatch.setattr(module, "_request", raise_ssl)

    _, error = module.probe({"id": "x", "kind": "github", "repo": "a/b"}, "ua")
    assert "client problem" in error and "certifi" in error


def test_rate_limit_names_the_fix(monkeypatch) -> None:
    module = load_module()

    def raise_403(url, ua, accept):
        raise urllib.error.HTTPError(url, 403, "rate limited", {}, None)
    monkeypatch.setattr(module, "_request", raise_403)

    _, error = module.probe({"id": "x", "kind": "github", "repo": "a/b"}, "ua")
    assert "GITHUB_TOKEN" in error


def test_tag_pattern_tracks_the_newest_matching_release(monkeypatch) -> None:
    """The MCP SDK's main is the 2.x line; our pin installs from 1.x.

    Watching the default branch reported drift we cannot install and hid the
    v1.* releases we do pick up. With `tag_pattern`, the fingerprint is the
    newest tag matching the pattern, ordered numerically (v1.30.0 > v1.9.1),
    never a 2.x tag.
    """
    module = load_module()
    calls = []

    def fake_request(url, user_agent, accept):
        calls.append(url)
        if url.endswith("/tags?per_page=100"):
            return json.dumps([
                {"name": "v2.2.0", "commit": {"sha": "2" * 40}},
                {"name": "v1.9.1", "commit": {"sha": "9" * 40}},
                {"name": "v1.30.0", "commit": {"sha": "a" * 40}},
                {"name": "v1.29.1", "commit": {"sha": "b" * 40}},
            ]).encode()
        if url.endswith("/commits/" + "a" * 40):
            return json.dumps({"commit": {"committer": {"date": "2026-09-07T00:00:00Z"}}}).encode()
        raise AssertionError(f"unexpected request {url}")

    monkeypatch.setattr(module, "_request", fake_request)
    fingerprint, error = module.probe(
        {"id": "x", "kind": "github", "repo": "modelcontextprotocol/python-sdk", "tag_pattern": r"^v1\."},
        "ua")
    assert error is None
    assert fingerprint["tag"] == "v1.30.0"
    assert fingerprint["revision"] == "a" * 40
    assert fingerprint["at"] == "2026-09-07T00:00:00Z"
    assert fingerprint["url"].endswith("/releases/tag/v1.30.0")
    assert not any("commits?per_page=1" in url for url in calls)


def test_tag_pattern_with_no_match_is_an_error_not_unchanged(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "_request",
                        lambda url, ua, accept: json.dumps([{"name": "v2.0.0", "commit": {"sha": "2" * 40}}]).encode())
    fingerprint, error = module.probe(
        {"id": "x", "kind": "github", "repo": "o/r", "tag_pattern": r"^v1\."}, "ua")
    assert fingerprint is None
    assert "no tag matches" in error


def test_watchlist_mcp_entry_tracks_the_1x_release_line() -> None:
    """Guards the watchlist itself: if someone drops the pattern, the watcher
    silently goes back to reporting 2.x commits our pin cannot install."""
    module = load_module()
    sources = {s["id"]: s for s in module.load_watchlist()["sources"]}
    assert sources["mcp-python-sdk"].get("tag_pattern") == r"^v1\."

