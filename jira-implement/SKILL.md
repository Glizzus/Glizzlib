---
name: jira-implement
description: Use when the user gives a Jira Data Center issue key (e.g. "implement PROJ-123", "fix JIRA ticket ABC-45", "pull down DEV-9 and do it") to read and implement in code. Fetches the issue over REST with a PAT, locates the relevant code in the current repo, makes a focused change, and verifies it with the project's own checks.
---

# Jira Implement (Data Center)

Take a single Jira **Data Center** issue, understand it, and implement the change in the repository
that is currently open. Built for bugs and small changes that are simple enough to do confidently in
one pass. It is scoped to Jira **Data Center with a PAT** — not Jira Cloud, and it does not create or
transition issues.

## Prerequisites

The fetch script reads two environment variables (stdlib only, no install):

- `JIRA_BASE_URL` — e.g. `https://jira.example.com` (include any context path, e.g. `https://host/jira`). Must be HTTPS.
- `JIRA_PAT` — a Personal Access Token (Jira DC 8.14+; Profile → Personal access tokens).

If either is unset the script exits with a clear message — relay it and stop.

## Step 1 — Fetch the issue

Run the helper and read its Markdown output. The script lives at `scripts/jira_issue.py`
**inside this skill's own directory** — your working directory is the user's project, not the
skill, so invoke it by its absolute path (substitute the directory this `SKILL.md` is in):

```bash
python <skill-dir>/scripts/jira_issue.py <ISSUE-KEY>          # e.g. PROJ-123
python <skill-dir>/scripts/jira_issue.py <ISSUE-KEY> --no-comments   # if the thread is noisy
```

It prints the summary, type/status/priority, description, comments, linked issues, subtasks, and
attachment names. If it exits non-zero, **relay the error message verbatim and stop** — common cases:
401 (token missing/invalid/expired), 403 (no permission), 404 (issue missing *or* no Browse
permission). See `reference/jira-api.md` for the full failure table.

## Step 2 — Assess scope (guardrail)

Restate, in one or two sentences, what the bug is and the change you intend to make. **If the issue
is ambiguous, underspecified, or clearly large / spans multiple areas, surface that and ask the user
before writing code** rather than guessing. This skill is for changes you can make confidently in one
pass; punt anything bigger back to the user.

## Step 3 — Locate the code

Search the current repo for the symbols, error strings, file paths, or feature names the issue
mentions. Read the surrounding code before changing it so the fix matches existing patterns.

## Step 4 — Implement

Make the change minimally and in the style of the surrounding code. Touch only what the issue
requires.

## Step 5 — Verify

Detect and run the project's own checks — tests, build, typecheck, lint — from whatever the repo
uses (`package.json` scripts, `pyproject.toml`, `Makefile`, etc.). Fix until they pass. If the repo
has no automated checks, say so explicitly and describe how you otherwise confirmed the change.

## Step 6 — Hand off

Summarize what you changed and how it maps to the issue, and leave the edits in the working tree for
the user to review.
