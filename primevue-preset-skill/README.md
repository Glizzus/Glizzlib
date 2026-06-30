# primevue-preset-editor

A host-agnostic [Agent Skill](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/) that teaches an AI coding agent to make a focused, correct change to a **PrimeVue (v4 / `@primeuix/themes`) theme preset** via `definePreset`, then prove it with the project's type-check.

It is deliberately narrow — `definePreset` only — so even a weaker model stays on rails: one API, the right token tier, and type-check as the authoritative gate for token names.

## Contents

```
primevue-preset-editor/
├── SKILL.md                  # the skill: frontmatter + procedure
└── reference/
    ├── token-tiers.md        # 3-tier token model + {reference} syntax
    └── examples.md           # canonical definePreset edits
```

## How it works

1. **Hold the token-tier model** — `primitive` / `semantic` / `components`. Picking the right tier is the one judgment call.
2. **Get real token names** — from the `@primevue/mcp` server if connected, else from the project's existing preset. No guessing.
3. **Edit the `definePreset` call** directly, minimally.
4. **Type-check** — `@primeuix/themes` ships TS types, so a bad token name or value shape fails compilation. That, not an intermediate validator, is the gate.

## Install

`SKILL.md` is the open agent-skills format, read by Claude Code, GitHub Copilot, Cursor, Codex CLI, and others. Drop the folder into a skills directory — no per-host adapter needed.

**Project-scoped** (committed to a repo, works in any supported agent):
```bash
mkdir -p .agents/skills            # also recognized: .claude/skills, .github/skills
cp -r primevue-preset-editor .agents/skills/
```

**Personal / global:**
- Claude Code: `~/.claude/skills/primevue-preset-editor/`
- GitHub Copilot: `~/.copilot/skills/` or `~/.agents/skills/`

The agent auto-loads the skill when a request matches the `description` in the frontmatter (e.g. "make the Card darker", "change the primary color").

## Recommended companion: the PrimeVue MCP server

The skill works without it, but connecting the official MCP server gives the agent authoritative token names instead of relying on the existing preset:

```bash
claude mcp add primevue -s user -- npx -y @primevue/mcp
```

For other editors, point an MCP config entry at `npx -y @primevue/mcp`. See https://primevue.dev/mcp/.

## Scope

Handles: static, app-wide preset styling via `definePreset`. **Out of scope** (the skill will say so and stop): runtime theme changes (`updatePreset` / `usePreset`) and per-instance overrides (the `dt` prop).
