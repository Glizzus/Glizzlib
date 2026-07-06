# Turborepo 1.x → 2.x decoder — stale habits → current shapes

Training data is dominated by turbo 1.x tutorials and early-2.x docs. Current stable was **2.10.3 as of July 2026**; 3.0 was unreleased then, but 2.9/2.10 already deprecate flags for it. Everything below was verified against the live docs (turborepo.dev) and/or a local 2.10.3 install. **On any newer turbo, these tables are hypotheses** — re-check a claim with `turbo docs` or the shipped `node_modules/turbo/schema.json` before acting on it. Migration codemod: `npx @turbo/codemod migrate`.

**Docs moved twice:** `turbo.build` → `turborepo.com` → **`turborepo.dev`** (lookup tooling: `reference/caching-tasks.md` §Introspection).

## Config keys

| A 1.x-trained model writes | Current reality |
|---|---|
| `"pipeline": { ... }` | `"tasks": { ... }` — hard error, verbatim: ``Found `pipeline` field instead of `tasks` `` |
| `"outputMode": "hash-only"` | `"outputLogs"` |
| `"dotEnv": [".env"]` / `"globalDotEnv"` | Removed — add to inputs: `"inputs": ["$TURBO_DEFAULT$", ".env*"]` |
| `"$schema": "https://turbo.build/schema.json"` | `https://turborepo.dev/schema.json` |
| `$VAR` inside `dependsOn`/`globalDependencies` | Error — use `env` / `globalEnv` |
| `"daemon": true` | Deprecated 2.9, removed in 3.0 |
| no package-manager field in root package.json | Required — either `packageManager` or `devEngines.packageManager` satisfies turbo. 2.10 error, verbatim: ``x Could not resolve workspace. `->  Missing `devEngines.packageManager` or legacy `packageManager` field in package.json`` |
| package.json without `"name"` | Error — every workspace package must be named |
| cache at `node_modules/.cache/turbo` | `.turbo/cache` (configurable `cacheDir`) |

For the valid key set on the installed version, read the repo's own `node_modules/turbo/schema.json` — never a memorized list; an unknown key in an existing turbo.json is more likely a newer feature than a mistake. Placement rules that trip models: `extends` and `tags` are legal only in package-level turbo.json files; `futureFlags` only at the root.

## CLI flags

| Stale | Current |
|---|---|
| `--scope=web` | `--filter=web` (for prune: positional `turbo prune web`) |
| `--ignore`, `--since`, `--include-dependencies`, `--no-deps` | `--filter` microsyntax (see caching-tasks.md) |
| `--parallel` | Deprecated 2.9 — `persistent: true`, the `with` key, or `--concurrency=100%` |
| `--no-cache` | `--cache=local:r,remote:r` |
| `--remote-only` / `TURBO_REMOTE_ONLY` | `--cache=remote:rw` |
| `--remote-cache-read-only` | `--cache=local:rw,remote:r` |
| `turbo-ignore` | `turbo query affected --exit-code` (0 = not affected, 1 = affected) |
| `--graph=out.png/.jpg/.pdf/.json` | Still accepted in 2.10 but deprecated ("will be removed in version 3.0") — prefer `.svg/.html/.mermaid/.dot`; JSON via `turbo query` |
| filter silently matching nothing | **Exact names** now hard-error, verbatim: `No package found with name 'x' in workspace`. A **glob** that matches nothing still runs 0 tasks and exits 0 (verified) — check the `Tasks:` count |

## Behavior changes a 1.x model doesn't expect

- **Strict env mode is the default.** Tasks see only `env` + `globalEnv` + `passThroughEnv` + framework-inferred vars + a small system allowlist (`PATH`, `HOME`, `SHELL`, …). CI secrets (`AWS_*`, `NODE_AUTH_TOKEN`) vanish from task runtime unless declared — the classic 2.0-upgrade breakage. Escape hatch `"envMode": "loose"` reintroduces stale-hit risk; prefer declaring.
- **Automatic package scoping:** running `turbo build` from inside `apps/web/` scopes to web's graph, not the whole repo. Any explicit `--filter` overrides it.
- `--only` now restricts task dependencies too, not just package deps.
- Workspace root implicitly depends on all packages; `engines` in package.json is hashed.
- Since 2.9 **circular package dependencies are allowed** (only the *task* graph must be acyclic) — but boundaries/lint hygiene still applies.

## 2.x feature timeline (what exists that training data may not know)

| Version | Shipped |
|---|---|
| 2.0 (2024-06) | `tasks` rename, strict env default, `turbo watch`, TUI |
| 2.1 | `--affected`, `turbo ls` |
| 2.4 (2025-01) | `turbo boundaries` (experimental, still experimental as of 2.10), watch `--experimental-write-cache` |
| 2.5 (2025-04) | sidecar `with` key, `--continue=never\|dependencies-successful\|always`, **`turbo.jsonc`**, `$TURBO_ROOT$` in globs |
| 2.6 (2025-10) | Bun stable, microfrontends proxy |
| 2.7 (2025-12) | composable config: package turbo.json `"extends": ["//", "pkg"]` chains, `$TURBO_EXTENDS$` array-append |
| 2.8 (2026-01) | AI affordances: `turbo docs`, docs-as-`.md`, task `description` key, git-worktree-shared local cache, official agent skill (`npx skills add vercel/turborepo`) |
| 2.9 (2026-03) | `turbo query` **stable**, big deprecation batch (above), circular pkg deps allowed, `--json` structured logs (exp.), 80–96% faster startup |
| 2.10 (2026-06) | `--affected` composes with `--filter` (intersection; previously an error), deferred input hashing (`inputs` entries with `"mode": "jit"` / `"dependencyOutputs"`), local cache eviction (`cacheMaxAge`/`cacheMaxSize`), graceful SIGINT/SIGTERM forwarding |

## Package Configurations (per-package turbo.json)

A package may ship its own `turbo.json` with `"extends": ["//"]` (`//` = root; root must come first in a chain). Only `tasks` (plus `tags`) may appear; `pkg#task` keys are not allowed there (scoping is implicit). Array fields (`outputs`, `env`, `dependsOn`, …) **replace** the inherited value — start the array with `"$TURBO_EXTENDS$"` to append instead (2.7+).
