---
name: turborepo
description: Use when working in a Turborepo monorepo — editing turbo.json, creating or extracting a packages/* entry, wiring build/lint/type-check tasks, debugging caching, or setting up CI — e.g. "add a shared package", "move this into packages/", "why is turbo not caching", "FULL TURBO but the files are missing", "set up turbo for CI", "Found `pipeline` field". Enforces cache-correct task config and the internal-package recipe, then gates by running turbo itself.
---

# Turborepo (2.x — verified against 2.10.3)

Work on a Turborepo 2.x monorepo: `turbo.json` config, task wiring, internal packages, CI. Version rules, in order:

- `turbo --version` prints 1.x → say so and stop; offer `npx @turbo/codemod migrate` first.
- Newer than 2.10 (especially 3.x): this skill was verified on 2.10.3. Treat the decoder tables and quoted errors as hypotheses — re-check the specific claim with `turbo docs "…"` or the shipped `node_modules/turbo/schema.json` before acting on it.
- Older 2.x: some commands used here don't exist yet (`turbo ls` 2.1+, `boundaries` 2.4+, `docs` 2.8+ — timeline in `reference/v2-decoder.md`). Skip a missing command; don't hunt for a substitute.

Turborepo code fails in two predictable ways. **Stale 1.x shapes**: turbo errors on them loudly, so the Step 3 gate catches them. **Silently-wrong caching**: config that runs green today and serves a stale or incomplete build tomorrow — it *looks like success* (a cache hit IS the bug), so only the write-time rules below defend against it.

## The model you must hold

Turbo is a task scheduler plus cache sitting on your package manager's workspace graph. Every task run gets a **hash** of: the package's files (default = everything not gitignored), the **declared** `env` values, the dependency subset of the lockfile, the task's turbo.json definition, and its upstream tasks' hashes. Same hash → turbo replays the logs and restores the **declared** `outputs`. Nothing else. Two corollaries generate almost every rule:

1. **Anything that affects the output but is not in the hash poisons the cache.** Strict env mode (the 2.x default) strips undeclared vars from the task's runtime env, so a first build usually fails loudly. The *silent* version bites when code has a fallback (`process.env.X ?? 'default'`) or `envMode` is `"loose"`: the undeclared var doesn't miss the cache — it *hits*, and ships the previous build. (Verified: `APP_MODE=prod turbo build` returned the `APP_MODE=unset` artifact.)
2. **Anything the task produces but doesn't declare in `outputs` is not restored.** The rerun still prints `FULL TURBO` — logs are cached even when files aren't — and downstream finds no `dist/`. Works locally (stale dist masks it), breaks in fresh CI.

## Wrong but silent (hard bans — the gate cannot catch these)

- `process.env.X` in task-executed code without `X` in that task's `env` (or `globalEnv`). Framework prefixes (`NEXT_PUBLIC_*`, `VITE_*`, …) are auto-included **only in packages where turbo detects that framework** — a plain tsc/tsup package gets no inference (verified), and server-side vars are never inferred anywhere.
- A build-affecting variable in `passThroughEnv` — passthrough is available at runtime but **excluded from the hash**; it recreates the poisoning inside strict mode.
- `inputs` that doesn't start with `"$TURBO_DEFAULT$"` — a bare list also disables `.gitignore` handling. Narrowing to a small file set is documented and occasionally right: do it only deliberately, and say why.
- A task that writes files with no `outputs` — cache hits restore nothing. Tests and lint declare `"outputs": []` deliberately.
- A deploy/migrate/publish task without `"cache": false` — a cache hit silently *skips the side effect*.
- Build outputs that aren't gitignored — un-ignored `dist/` feeds back into the next run's *inputs* and churns the hash forever (verified).
- `turbo run …` inside a package's scripts — there is **no recursion guard** (verified): nested runs silently double-execute and self-recursion loops forever. Turbo commands belong in the root package.json only; details in `reference/caching-tasks.md` §Task graph.
- `"dev": "export MODE=x && next dev"` — env is hashed at task start; vars set inside the script are invisible to turbo.
- `turbo gen workspace` in automation — prompts interactively regardless of flags (verified hang). Create the files by hand: `reference/new-package.md`.
- Cross-package `../` deep imports — only a package's `exports` entrypoints; `turbo boundaries` (2.4+) flags violations.

## Never write (stale 1.x shapes — the gate catches these; fix from the decoder)

`"pipeline"` (→ `tasks`), `"outputMode"` (→ `outputLogs`), `dotEnv`/`globalDotEnv` (→ `inputs` + `".env*"`), `--scope`/`--ignore`/`--since` (→ `--filter`), `$VAR` inside `dependsOn`, `https://turbo.build/schema.json`. Full decoder and 2.x feature timeline: `reference/v2-decoder.md`.

## Step 1 — Verify wiring, and introspect instead of guessing

1. Check `turbo --version` against the rules at the top. Root package.json declares the package manager — `packageManager` or `devEngines.packageManager`; turbo accepts either. Workspace globs are flat (`packages/*`, not `packages/**`).
2. Read the real state with turbo's own machine-readable tools — never infer the graph from directory names:
   - `turbo ls --output=json` — packages and paths; `turbo run <task> --dry=json --filter=<pkg>` — resolved tasks, hashes, `environmentVariables`, `dependencies` (scope it — unfiltered output is the whole repo's plan); `turbo query '<graphql>'` for anything deeper.
   - Docs answer: `turbo docs "your question"`, or fetch any `https://turborepo.dev/docs/...` URL with `.md` appended for raw markdown.
3. Declare internal deps the way sibling packages already declare theirs; with no precedent, `"workspace:*"` on pnpm/bun, `"*"` on npm/classic yarn.

## Step 2 — Write from the canonical shapes

New/extracted package → follow `reference/new-package.md` step by step; the two steps agents skip are declaring + installing the new dependency (Step 5 — the lockfile must learn the workspace) and the final gate (Step 7). Task config → mimic:

```jsonc
{
  "$schema": "https://turborepo.dev/schema.json",
  "tasks": {
    "build":      { "dependsOn": ["^build"], "outputs": ["dist/**"], "env": ["APP_MODE"] },
    "test":       { "dependsOn": ["^build"], "outputs": [] },
    "type-check": { "dependsOn": ["transit"] },          // transit-node pattern — reference/caching-tasks.md §Task graph
    "transit":    { "dependsOn": ["^transit"] },
    "dev":        { "cache": false, "persistent": true }
  }
}
```

`^build` = dependencies' build first (topological); bare `build` = same package; `pkg#task` = that specific package. Nothing may `dependsOn` a `persistent` task (hard error) — co-run with `"with": ["api#dev"]` instead. Full cache/graph/filter/CI reference: `reference/caching-tasks.md`.

## Step 3 — Run turbo (the gate)

Cheap static check first — it catches what a successful build won't:

```bash
turbo boundaries                          # undeclared/out-of-package imports (2.4+)
```

Then execute the affected tasks. Scope with `--filter` in a large repo, and **never include a persistent task** (`dev`, `watch` never exit — an unattended run hangs):

```bash
turbo build type-check --filter=...<changed-pkg>   # the change plus its dependents; drop the filter in small repos
```

Then the **double-run protocol** for any task whose config you touched: run it twice — the second must be `FULL TURBO`; a miss means something un-gitignored or nondeterministic is churning the hash. For tasks that declare non-empty `outputs`, also delete the output dir and run again — the files must come back, or `outputs` is wrong.

The gate catches stale 1.x shapes, graph errors, and missing outputs. It does **not** catch: an undeclared env var (that's a *successful-looking hit*), a hash-excluded `passThroughEnv` var, a cacheable deploy task, or a glob `--filter` that matches nothing (0 tasks, exit 0 — check the `Tasks:` count; only exact names error). Re-read your diff against the hard bans before declaring done.
