#!/usr/bin/env python3
"""Fetch a single Jira Data Center issue via a PAT and render it as clean Markdown.

Reads JIRA_BASE_URL and JIRA_PAT from the environment, GETs the issue over the
Data Center REST API (api/2, Bearer auth), and prints a compact Markdown summary
(description + comments + linked issues + subtasks + attachment names) to stdout
for a coding agent to read. Stdlib only — no third-party dependencies.

Usage:
    export JIRA_BASE_URL=https://jira.example.com        # may include a context path, e.g. .../jira
    export JIRA_PAT=<personal-access-token>
    python jira_issue.py PROJ-123
    python jira_issue.py PROJ-123 --no-comments
    python jira_issue.py PROJ-123 --json                 # raw issue JSON (debug escape hatch)

Tests:
    python jira_issue.py --self-test                     # offline unit tests for the pure helpers

Notes:
    - Data Center only (Bearer PAT). Jira Cloud uses Basic email:token and api/3 + ADF — unsupported here.
    - The PAT and Authorization header are never printed, including in error output.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from html.parser import HTMLParser
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

JsonDict = dict[str, Any]

FIELDS = "summary,issuetype,status,priority,description,comment,issuelinks,subtasks,attachment"
TIMEOUT_SECONDS = 30


class _HTMLToText(HTMLParser):
    """Minimal HTML -> text converter for Jira's renderedFields HTML.

    Drops tags, turns block-level boundaries into newlines, and collapses runs
    of blank lines. Good enough to hand rendered descriptions/comments to an LLM.
    """

    _BLOCK_TAGS = {
        "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "table", "ul", "ol",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0  # depth of script/style we're inside

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs  # unused; required by the base-class signature
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return collapse_blank_lines("".join(self._parts))


def collapse_blank_lines(text: str) -> str:
    """Trim trailing whitespace per line and collapse 3+ newlines into 2."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    blanks = 0
    for line in lines:
        if line:
            blanks = 0
            out.append(line)
        else:
            blanks += 1
            if blanks <= 1:
                out.append("")
    return "\n".join(out).strip()


def html_to_text(html: str) -> str:
    """Convert rendered HTML to plain text."""
    parser = _HTMLToText()
    parser.feed(html)
    return parser.text()


def render_text(rendered: object, raw: object) -> str:
    """Prefer DC renderedFields HTML; fall back to the raw wiki-markup string.

    Fall back on the *converted text* being empty, not just the HTML — a
    rendered field like ``<p>&nbsp;</p>`` or an image-only body strips to "",
    and the raw wiki markup (e.g. ``!image.png!``) is the better content.
    """
    if isinstance(rendered, str) and rendered.strip():
        text = html_to_text(rendered)
        if text:
            return text
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "_(empty)_"


def build_url(base_url: str, issue_key: str) -> str:
    """Build the issue endpoint, preserving any context path in the base URL."""
    base = base_url.rstrip("/")
    query = urlencode({"fields": FIELDS, "expand": "renderedFields"})
    return f"{base}/rest/api/2/issue/{quote(issue_key)}?{query}"


def status_message(code: int) -> str:
    """Map an HTTP status to an actionable, non-sensitive message."""
    if code == 401:
        return "401 Unauthorized — JIRA_PAT is missing, invalid, or expired. Create a new token."
    if code == 403:
        return "403 Forbidden — token is valid but lacks permission (or CAPTCHA is required after failed logins)."
    if code == 404:
        return "404 Not Found — issue does not exist, or your account lacks Browse permission for it."
    if code == 400:
        return "400 Bad Request — malformed issue key or query parameters."
    if code == 429:
        return "429 Too Many Requests — rate limited; retry after a pause."
    return f"HTTP {code} — unexpected response from Jira."


def fetch_issue(base_url: str, pat: str, issue_key: str) -> JsonDict:
    """GET the issue JSON. Raises RuntimeError with a clean message on failure."""
    url = build_url(base_url, issue_key)
    request = Request(url, headers={
        "Authorization": f"Bearer {pat}",
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            # errors="replace": a non-UTF-8/compressed proxy body must not raise an
            # uncaught UnicodeDecodeError; garbled bytes then fail the JSON parse below
            # and surface the clean SSO/login message instead.
            payload = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(status_message(exc.code)) from None
    except URLError as exc:
        raise RuntimeError(
            f"Could not reach Jira at the configured base URL ({exc.reason}). "
            "Check JIRA_BASE_URL, including any context path (e.g. https://host/jira), and HTTPS."
        ) from None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        raise RuntimeError(
            "Response was not JSON — the base URL may be hitting an SSO/login page "
            "instead of the REST API (check context path and that the token reaches Jira)."
        ) from None
    # Parseable JSON that isn't an issue object (an array, a scalar, or an error
    # object without "fields") must not render as a blank "success" — surface it.
    if not isinstance(parsed, dict) or "fields" not in parsed:
        raise RuntimeError(
            "Response was JSON but not a Jira issue (no 'fields'). The base URL may be "
            "returning an error or non-issue payload — check the issue key and context path."
        )
    return cast(JsonDict, parsed)


# --- typed accessors for dynamic JSON -------------------------------------
# json.loads returns Any; these narrow it to concrete types so the rest of the
# code stays fully typed and never calls .get/.append on an unknown value.

def as_dict(value: object) -> JsonDict:
    return cast(JsonDict, value) if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    return cast("list[Any]", value) if isinstance(value, list) else []


def as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def field(node: object, *path: str) -> object:
    """Walk a dotted path through nested JSON dicts, returning None if absent."""
    for key in path:
        node = as_dict(node).get(key)
    return node


def issue_ref(node: object) -> str:
    """Format the key/summary/status reference shared by linked issues and subtasks."""
    ref = as_dict(node)
    ref_fields = as_dict(ref.get("fields"))
    key = as_str(ref.get("key"), "?")
    summary = as_str(ref_fields.get("summary"))
    status = as_str(field(ref_fields, "status", "name"))
    suffix = f" [{status}]" if status else ""
    return f"{key} — {summary}{suffix}"


def render_markdown(issue: JsonDict, include_comments: bool = True) -> str:
    """Render the issue JSON as compact Markdown for an agent."""
    fields = as_dict(issue.get("fields"))
    rendered = as_dict(issue.get("renderedFields"))

    key = as_str(issue.get("key"), "?")
    summary = as_str(fields.get("summary")) or "(no summary)"
    lines: list[str] = [f"# {key} — {summary}", ""]

    meta = [
        ("Type", as_str(field(fields, "issuetype", "name"))),
        ("Status", as_str(field(fields, "status", "name"))),
        ("Priority", as_str(field(fields, "priority", "name"))),
    ]
    meta_str = " · ".join(f"**{label}:** {value}" for label, value in meta if value)
    if meta_str:
        lines += [meta_str, ""]

    description = render_text(rendered.get("description"), fields.get("description"))
    lines += ["## Description", "", description, ""]

    if include_comments:
        comments = as_list(field(fields, "comment", "comments"))
        rendered_comments = as_list(field(rendered, "comment", "comments"))
        if comments:
            lines += [f"## Comments ({len(comments)})", ""]
            for i, raw_comment in enumerate(comments):
                comment = as_dict(raw_comment)
                author = as_str(field(comment, "author", "displayName")) or "Unknown"
                created = as_str(comment.get("created"))
                # renderedFields.comment.comments is parallel to fields.comment.comments;
                # Jira returns them in lockstep, so pair the rendered body by index.
                rendered_body = as_dict(rendered_comments[i]).get("body") if i < len(rendered_comments) else None
                body = render_text(rendered_body, comment.get("body"))
                lines += [f"**{author}** · {created}", "", body, ""]

    link_bullets: list[str] = []
    for raw_link in as_list(fields.get("issuelinks")):
        link = as_dict(raw_link)
        link_type = as_str(field(link, "type", "name")) or "relates to"
        for direction in ("outwardIssue", "inwardIssue"):
            target = as_dict(link.get(direction))
            if target:
                link_bullets.append(f"- {link_type}: {issue_ref(target)}")
    if link_bullets:
        lines += ["## Linked issues", "", *link_bullets, ""]

    subtask_bullets = [f"- {issue_ref(sub)}" for sub in as_list(fields.get("subtasks"))]
    if subtask_bullets:
        lines += ["## Subtasks", "", *subtask_bullets, ""]

    attachment_bullets: list[str] = []
    for raw_att in as_list(fields.get("attachment")):
        att = as_dict(raw_att)
        name = as_str(att.get("filename"), "?")
        mime = as_str(att.get("mimeType"))
        size = att.get("size")
        size_str = f", {size} bytes" if isinstance(size, int) else ""
        attachment_bullets.append(f"- {name} ({mime}{size_str})")
    if attachment_bullets:
        lines += ["## Attachments", "", *attachment_bullets, ""]

    return collapse_blank_lines("\n".join(lines)) + "\n"


def run(args: argparse.Namespace) -> int:
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    pat = os.environ.get("JIRA_PAT", "").strip()
    if not base_url or not pat:
        missing = " and ".join(
            name for name, val in (("JIRA_BASE_URL", base_url), ("JIRA_PAT", pat)) if not val
        )
        print(f"Error: {missing} not set in the environment.", file=sys.stderr)
        return 2
    if not base_url.lower().startswith("https://"):
        print(
            f"Error: JIRA_BASE_URL must use https (got {base_url!r}); refusing to send the PAT over an insecure connection.",
            file=sys.stderr,
        )
        return 2

    issue_key: str = args.issue_key
    try:
        issue = fetch_issue(base_url, pat, issue_key)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(issue, indent=2))
    else:
        print(render_markdown(issue, include_comments=not args.no_comments))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fetch a Jira Data Center issue via PAT as Markdown.")
    parser.add_argument("issue_key", nargs="?", help="Issue key, e.g. PROJ-123")
    parser.add_argument("--no-comments", action="store_true", help="Omit the comment thread")
    parser.add_argument("--json", action="store_true", help="Print the raw issue JSON instead of Markdown")
    parser.add_argument("--self-test", action="store_true", help="Run offline unit tests and exit")
    args = parser.parse_args(argv)

    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(_SelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    if not args.issue_key:
        parser.error("issue_key is required (or pass --self-test)")
    return run(args)


class _SelfTest(unittest.TestCase):
    def test_html_to_text_strips_and_breaks(self) -> None:
        html = "<h2>Bug</h2><p>Line one</p><ul><li>a</li><li>b</li></ul><script>x=1</script>"
        text = html_to_text(html)
        self.assertIn("Bug", text)
        self.assertIn("Line one", text)
        self.assertIn("- a", text)
        self.assertIn("- b", text)
        self.assertNotIn("x=1", text)
        self.assertNotIn("<", text)

    def test_collapse_blank_lines(self) -> None:
        self.assertEqual(collapse_blank_lines("a\n\n\n\nb"), "a\n\nb")
        self.assertEqual(collapse_blank_lines("  a  \n  \nb "), "a\n\nb")

    def test_render_text_prefers_rendered(self) -> None:
        self.assertEqual(render_text("<p>hello</p>", "*hello*"), "hello")

    def test_render_text_falls_back_to_raw(self) -> None:
        self.assertEqual(render_text("", "h2. Heading"), "h2. Heading")
        self.assertEqual(render_text(None, None), "_(empty)_")

    def test_render_text_falls_back_when_rendered_strips_to_empty(self) -> None:
        # rendered HTML is non-empty but converts to no text (nbsp / image-only):
        # must use the raw wiki markup, not emit a blank body.
        self.assertEqual(render_text("<p>&nbsp;</p>", "!image.png!"), "!image.png!")
        self.assertEqual(render_text("<p>   </p>", None), "_(empty)_")

    def test_accessors_narrow_safely(self) -> None:
        self.assertEqual(as_dict({"a": 1}), {"a": 1})
        self.assertEqual(as_dict("not a dict"), {})
        self.assertEqual(as_list([1, 2]), [1, 2])
        self.assertEqual(as_list(None), [])
        self.assertEqual(as_str("x"), "x")
        self.assertEqual(as_str(None, "?"), "?")

    def test_field_walks_and_handles_missing(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(field(data, "a", "b", "c"), 1)
        self.assertIsNone(field(data, "a", "x", "c"))
        self.assertIsNone(field("not a dict", "a"))

    def test_build_url_preserves_context_path(self) -> None:
        url = build_url("https://host/jira/", "PROJ-1")
        self.assertTrue(url.startswith("https://host/jira/rest/api/2/issue/PROJ-1?"))
        self.assertIn("expand=renderedFields", url)
        self.assertIn("fields=", url)

    def test_status_messages(self) -> None:
        self.assertIn("expired", status_message(401))
        self.assertIn("permission", status_message(403))
        self.assertIn("Browse permission", status_message(404))

    def test_render_markdown_sections(self) -> None:
        issue: JsonDict = {
            "key": "PROJ-7",
            "fields": {
                "summary": "Null deref on save",
                "issuetype": {"name": "Bug"},
                "status": {"name": "Open"},
                "priority": {"name": "High"},
                "description": "h2. Steps",
                "comment": {"comments": [
                    {"author": {"displayName": "Sam"}, "created": "2026-01-02", "body": "repro attached"},
                ]},
                "issuelinks": [
                    {"type": {"name": "blocks"}, "outwardIssue": {
                        "key": "PROJ-8", "fields": {"summary": "Other", "status": {"name": "Done"}}}},
                ],
                "subtasks": [
                    {"key": "PROJ-9", "fields": {"summary": "Sub", "status": {"name": "Open"}}},
                ],
                "attachment": [
                    {"filename": "log.txt", "size": 12, "mimeType": "text/plain"},
                ],
            },
            "renderedFields": {
                "description": "<h2>Steps</h2><p>do x</p>",
                "comment": {"comments": [{"body": "<p>repro attached</p>"}]},
            },
        }
        md = render_markdown(issue)
        self.assertIn("# PROJ-7 — Null deref on save", md)
        self.assertIn("**Type:** Bug", md)
        self.assertIn("do x", md)            # rendered description preferred
        self.assertIn("## Comments (1)", md)
        self.assertIn("Sam", md)
        self.assertIn("blocks: PROJ-8", md)
        self.assertIn("PROJ-9 — Sub [Open]", md)
        self.assertIn("log.txt (text/plain, 12 bytes)", md)

    def test_render_markdown_no_comments_flag(self) -> None:
        issue: JsonDict = {"key": "P-1", "fields": {"summary": "x", "comment": {"comments": [
            {"author": {"displayName": "A"}, "created": "", "body": "hidden"}]}}}
        md = render_markdown(issue, include_comments=False)
        self.assertNotIn("## Comments", md)

    def test_render_markdown_tolerates_malformed_nodes(self) -> None:
        # issuelinks as a string, subtasks missing, attachment item not a dict — must not raise.
        issue: JsonDict = {"key": "P-2", "fields": {"summary": "y", "issuelinks": "oops", "attachment": ["x"]}}
        md = render_markdown(issue)
        self.assertIn("# P-2 — y", md)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
