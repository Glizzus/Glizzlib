# Caching, task graph, filters, CI — reference

All "verified" claims below were reproduced locally on turbo 2.10.3.

## What is actually in a task's hash

Package files (default inputs = every file in the package **not gitignored**, tracked or not) + values of declared `env`/`globalEnv` + the package's dependency subset of the lockfile + the task's turbo.json definition + hashes of upstream tasks + `globalDependencies` file contents + root package.json/lockfile. A cache hit replays logs and restores declared `outputs` — nothing else runs.

### The three verified silent failures

1. **Undeclared env var → poisoned cache.** `APP_MODE=prod turbo build` with no `"env": ["APP_MODE"]` → `cache hit`, artifact still contains the old value. Declaring it → miss + correct artifact. In strict mode (default) the var is *also stripped from the task's runtime env*, so first builds usually fail loudly — but code with fallbacks (`process.env.X ?? 'default'`) builds silently wrong.
2. **Missing `outputs` → logs-only cache.** Task caches, rerun prints `FULL TURBO`, **no files are restored**. Deleted `dist/` stays deleted. Locally masked by stale dist; fails in fresh CI.
3. **Un-gitignored outputs → hash feedback loop.** Default inputs include untracked files, so a `dist/` that isn't gitignored becomes an *input* to the next run — hash churns, cache misses "randomly" until `.gitignore` covers all generated paths. (This is also the turbo-watch infinite-loop cause.)

### Inputs

- Narrowing: always `"inputs": ["$TURBO_DEFAULT$", "!README.md"]`. A bare list opts out of default behavior **including .gitignore handling**.
- `.env` files are gitignored → outside the default hash, and turbo never *loads* them (that's the framework/dotenv's job). Cache-correctness fix: `"inputs": ["$TURBO_DEFAULT$", ".env*"]`.
- `$TURBO_ROOT$/tsconfig.json` for repo-root files in a package's inputs (2.5+).
- 2.10 deferred hashing: an inputs entry may be `{ "mode": "jit" }`-style objects (hash after deps run — for generated files) or `"dependencyOutputs"` (hash upstream outputs, e.g. only `.d.ts`). New; check `turbo docs "deferred input hashing"` before using.
- Non-determinism breaks everything: timestamps/random IDs baked into outputs, tools that mutate their own outputs post-build (Next `output: "standalone"` metadata), codegen writing into tracked source paths.

### Env modes

- `env` = hashed **and** available. `passThroughEnv` = available, **not hashed** — only for machine-local vars that must not affect the artifact (credentials for a fetch cache, etc.). A build-affecting var here = poisoning.
- Framework inference auto-adds prefixes for each package's **detected** framework (`NEXT_PUBLIC_*`, `VITE_*`, … — the table grows per release). The resolved truth for a task is `--dry=json` → `environmentVariables`; the current table is `turbo docs "framework inference"`. Disable with `--framework-inference=false`; negate with `"env": ["!NEXT_PUBLIC_INTERNAL_*"]`.
- Vars are captured when the task starts: `"build": "export STAGE=prod && vite build"` hides `STAGE` from turbo entirely.
- `eslint-config-turbo` / Biome's `noUndeclaredEnvVars` lint `process.env` reads against turbo.json — wire one in if the repo lints.

## Task graph

- `"dependsOn": ["^build"]` — dependencies' build first (the one you almost always want); `["build"]` — another task in the *same* package; `["utils#build"]` — one specific package's task. Missing `^build` = race: works locally over stale `dist/`, dies in CI with "Cannot find module '@repo/ui'".
- Nothing may depend on a `persistent: true` task. Verified error: `x "@repo/ui#dev" is a persistent task, "@repo/ui#smoke" cannot depend on it`. Co-run instead: `"dev": { "with": ["api#dev"], "persistent": true, "cache": false }`.
- `cache: false` belongs on: `dev` (with `persistent: true`), and every side-effect task (`deploy`, `db:migrate`, `publish`) — a cache hit on those *skips the side effect silently*. `--force` bypasses cache reads but still writes; it is not a substitute.
- Root tasks: `"//#format": {}` + a matching script in the **root** package.json. Sparingly — they hash broadly.
- Never let a script that turbo runs invoke `turbo` itself — there is **no recursion guard** (verified): a nested `turbo run <other-task>` silently executes a second graph inside the outer task (double-counting cache and concurrency), and a self-recursive task (`"build": "turbo run build"`) loops forever until killed.
- Cross-package type-check/lint invalidation without serializing — the **transit-node pattern**: `"transit": { "dependsOn": ["^transit"] }` (a phantom task with no script anywhere) plus `"type-check": { "dependsOn": ["transit"] }`. The transit chain propagates "an upstream input changed" through the graph so dependents' checks invalidate, while everything still runs in parallel (verified: touching a dependency's src re-ran the dependent app's type-check).
- `interruptible: true` (requires `persistent`) lets `turbo watch` restart a dev server that lacks its own file-watching. Frameworks with HMR (Next, Vite) should *not* be wrapped in `turbo watch`.

## Filters and --affected (directions verified by dry-run)

| Filter | Selects |
|---|---|
| `--filter=web` | web only. An exact name with no match is a hard error, but a **glob** matching nothing runs 0 tasks and exits 0 (verified) — in CI, assert on the `Tasks:` count |
| `--filter=web...` | web **plus its dependencies** ("build everything web needs") |
| `--filter=...@repo/ui` | ui **plus its dependents** ("re-test everything ui affects") |
| `--filter=./apps/*` | by directory |
| `--filter="...[origin/main]"` | packages changed vs ref, plus dependents |
| `--affected` | shorthand for changed-vs-base + dependents; base = `main`, override `TURBO_SCM_BASE` |

- Verified: editing `packages/ui` then `--affected` selects `@repo/ui#build` **and** `web#build`.
- 2.10+: `--affected --filter=!docs` composes (intersection). Earlier 2.x errors on the combination.
- **Shallow clones break git filters/affected** — with `fetch-depth: 1` the merge-base doesn't exist and everything is treated as changed (or errors). CI checkout needs `fetch-depth: 0` (or deep enough to reach base).

## Introspection (prefer these over guessing — all machine-readable)

- `turbo run <task> --dry=json` — full plan without executing. Per task: `taskId`, `hash`, `command`, `dependencies`, `dependents`, `environmentVariables`, `inputs`, `outputs`, `resolvedTaskDefinition`, `with` (verified key list).
- `turbo ls --output=json` — packages + paths; `turbo ls --affected`.
- `turbo query '{ packages { items { name } } }'` — GraphQL over package/task graph (stable 2.9+); the root pseudo-package appears as `"//"`. `turbo query --schema` dumps the schema. Shorthands: `turbo query affected --tasks build`, `--exit-code` for CI job-skipping.
- `turbo run <task> --summarize` — writes hash-component breakdown to `.turbo/runs/`; diff two summaries to find *why* a hash changed.
- `turbo boundaries` — flags imports of packages not declared in that package's package.json and `../` escapes (experimental but accurate; verified detection). Tag rules live under root `boundaries.tags` with per-package `"tags"` in package configs.
- `turbo docs "search terms"` (2.8+); any turborepo.dev docs URL + `.md` = raw markdown.

## CI and remote cache

- Remote cache: set `TURBO_TOKEN` (secret) + `TURBO_TEAM`. **Misconfiguration is silent** — turbo falls back to local-only and CI is just slow (`0 cached` every run); verify a hit actually happens after setup. Vercel-hosted is free on all plans; self-hosted servers implement an open OpenAPI spec.
- Integrity: `"remoteCache": { "signature": true }` + `TURBO_REMOTE_CACHE_SIGNATURE_KEY` (HMAC). Key mismatch presents as permanent cache misses, not an error.
- **Logs are cached artifacts** — anything a task prints (including echoed secrets) is stored and replayed to every machine that hits the cache.
- `--continue=dependencies-successful` in CI to surface all failures without running tasks whose deps failed.
- One dev's under-declared env on loose mode can upload a poisoned artifact **everyone** downloads — remote cache correctness is exactly as good as the env/inputs declarations.
