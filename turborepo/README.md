# turborepo

A host-agnostic [Agent Skill](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/) that teaches an AI coding agent to work correctly in a **Turborepo 2.x monorepo**: turbo.json task wiring, cache-correct config, and the create/extract-an-internal-package runbook.

It exists because Turborepo is a double trap for weaker models:

- **Training data is 1.x-shaped.** `pipeline`, `--scope`, `dotEnv` — current turbo (2.10.3 as of July 2026, docs now at turborepo.dev) errors on all of them, defaults have flipped (strict env mode), and the 2.1–2.10 feature line (`--affected`, `turbo query`, `with`, boundaries, composable config) simply doesn't exist in older training data. These failures are loud — running turbo is the gate that catches them.
- **Cache misconfiguration fails silently, as success.** An env var read but not declared in `env` doesn't miss the cache — it *hits*, shipping yesterday's build. A task without `outputs` still prints `FULL TURBO` while restoring zero files. Un-gitignored `dist/` feeds back into the input hash and churns it forever. All three were reproduced live in a lab monorepo; no gate can catch a bug whose symptom is a green cache hit, so the skill enforces these as write-time hard bans.

## Contents

```
turborepo/
├── SKILL.md                      # the skill: hash model + hard bans + 3-step procedure
└── reference/
    ├── v2-decoder.md             # 1.x → 2.x config/flag decoder, behavior changes, 2.x feature timeline
    ├── new-package.md            # verified runbook: factor code into a new packages/* entry
    └── caching-tasks.md          # hash contents, env modes, task graph, filters/--affected, introspection, CI
```

## How it works

1. **Hold the hash model** — a task's hash is its package files (everything not gitignored) + declared env values + lockfile subset + task definition + upstream hashes; a hit replays logs and restores declared outputs, nothing else. Both silent failure classes fall out of this one model.
2. **Introspect, don't guess** — the skill routes the agent to turbo's machine-readable surfaces (`turbo ls --output=json`, `--dry=json`, `turbo query`, `turbo docs`, docs-as-markdown) instead of inferring the graph from directory names.
3. **Hard bans** — undeclared env reads, `inputs` without `$TURBO_DEFAULT$`, missing `outputs`, cacheable deploy tasks, build-affecting vars in `passThroughEnv`, turbo inside package scripts, `turbo gen workspace` in automation, cross-package `../` imports.
4. **The package runbook** — `reference/new-package.md` is a step-ordered extraction recipe (strategy choice → files → dependency + install → gate) with the observed error of each skipped-step failure (environment-specific where marked).
5. **Turbo itself as the gate** — run the tasks, run `turbo boundaries`, then the double-run protocol: second run must be `FULL TURBO`; delete outputs and rerun — files must come back. With an explicit list of what the gate does *not* catch.

Every claim marked "verified" was reproduced against a locally installed `turbo@2.10.3` on a scratch pnpm monorepo; current-state facts were cross-checked against the live turborepo.dev docs and vercel/turborepo releases in July 2026; an adversarial multi-agent review then re-tested the claims, and the corrections were folded back in. Quoted error text is scoped to the environment it was captured in.

Vercel ships an official skill (`npx skills add vercel/turborepo`) — a docs companion. This one is narrower and defensive: hard bans on the silent cache failures, a 1.x decoder for stale training data, and a deterministic extraction runbook.

## Install

`SKILL.md` is the open agent-skills format, read by Claude Code, GitHub Copilot, Cursor, Codex CLI, and others. Drop the folder into a skills directory — no per-host adapter needed.

**Project-scoped** (committed to a repo). Hosts read different directories — Claude Code loads project skills only from `.claude/skills/`; Copilot and other agents-standard hosts read `.agents/skills/` (or `.github/skills`):
```bash
mkdir -p .claude/skills && cp -r turborepo .claude/skills/     # Claude Code
mkdir -p .agents/skills && cp -r turborepo .agents/skills/     # Copilot / agents-standard hosts
```

**Personal / global:**
- Claude Code: `~/.claude/skills/turborepo/`
- GitHub Copilot: `~/.copilot/skills/` or `~/.agents/skills/`

The agent auto-loads the skill when a request matches the `description` in the frontmatter (e.g. "move this into packages/", "why is turbo not caching", "FULL TURBO but the files are missing").

## Scope

Handles: turbo.json (2.x `tasks` schema), task graph wiring (`^build`, transit nodes, `with`/persistent), cache correctness (env, inputs, outputs, .env files), creating/extracting internal packages, filters/`--affected`, CI + remote cache setup, introspection tooling. **Out of scope** (the skill will say so and stop): turbo 1.x repos (offer `npx @turbo/codemod migrate` first), publishable-to-npm package versioning/changesets, Nx or other monorepo tools.
