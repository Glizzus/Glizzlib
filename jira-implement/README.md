# jira-implement

A personal, host-agnostic [Agent Skill](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/)
that lets a coding agent (Copilot, Claude Code, Cursor, …) take a **Jira Data Center** issue key,
fetch the issue over REST with a **PAT**, locate the relevant code in the repo you're in, implement a
focused change, and verify it with the project's own checks. It stops there and leaves the edits in
the working tree for you to review.

It's built for the case where a bug is simple enough for the agent to just pull down and do.

## Contents

```
jira-implement/
├── SKILL.md                 # the procedure: fetch → assess → locate → implement → verify → hand off
├── README.md                # this file
├── scripts/
│   └── jira_issue.py        # stdlib-only fetcher → clean Markdown (no third-party deps)
└── reference/
    └── jira-api.md          # DC PAT/REST details, fields, failure table, citations
```

## How it works

1. **Fetch** the issue: `python scripts/jira_issue.py <KEY>` renders summary, description, comments, links/subtasks, and attachment names as Markdown.
2. **Assess scope** — the agent restates the change and, if the issue is ambiguous or large, asks you before coding.
3. **Locate** the relevant code in the current repo.
4. **Implement** the change minimally.
5. **Verify** by running the project's tests/build/typecheck.
6. **Hand off** — summarize and leave the diff uncommitted.

## Prerequisites

- **Python 3.11+** (the script uses only the standard library — nothing to install).
- A **Jira Data Center** instance on **8.14+** and a **Personal Access Token** (Profile → Personal access tokens).
- Two environment variables:
  ```bash
  export JIRA_BASE_URL=https://jira.example.com   # include any context path, e.g. https://host/jira
  export JIRA_PAT=<your-token>
  ```
  The base URL must be HTTPS; the script refuses to send the PAT otherwise and never prints it.

Smoke-test the fetcher before wiring it into an agent:
```bash
python scripts/jira_issue.py --self-test     # offline unit tests
python scripts/jira_issue.py PROJ-123        # live fetch against your instance
```

## Install

`SKILL.md` is the open agent-skills format read by Claude Code, GitHub Copilot, Cursor, and others.

**Personal / global** (recommended — so it's available in any repo you open):
```bash
cp -r jira-implement ~/.copilot/skills/      # GitHub Copilot
cp -r jira-implement ~/.claude/skills/       # Claude Code
```

**Project-scoped** (committed into a specific repo, shared with collaborators):
```bash
mkdir -p .agents/skills                      # also recognized: .claude/skills, .github/skills
cp -r jira-implement .agents/skills/
```

The agent auto-loads the skill when you reference an issue key (e.g. "implement PROJ-123").

## Scope

**In scope:** read one Data Center issue via PAT and implement a focused change, then verify it.

**Out of scope:** Jira Cloud (uses different auth/API); creating, editing, or transitioning issues;
downloading attachment binaries; and any commit / push / PR step — the skill stops after verification
and leaves the change in your working tree.
