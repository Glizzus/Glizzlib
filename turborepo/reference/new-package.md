# Creating / extracting an internal package — the verified runbook

Factoring code out of an app into a new workspace package is a fixed sequence. Do the steps **in order**; the ones people skip (5 and 7) produce the errors quoted below. Verified end-to-end on turbo 2.10.3 + **pnpm** — quoted error text is environment-specific where marked.

**Do not use `turbo gen workspace` from automation.** It prompts interactively ("Add workspace dependencies?", "Where should X be added?") even when `--name`, `--type`, `--empty`, and `--destination` are all supplied, and piped stdin mis-feeds the prompt loop (verified hang). Hand-creating the files below is 4 small files and fully deterministic. (Custom Plop generators run non-interactively via `turbo gen <name> --args a b c` — fine *if the repo already has one* under `turbo/generators/config.ts`.)

## Step 0 — Pick the strategy

| | Just-in-Time | Compiled (default) |
|---|---|---|
| `exports` points at | raw `./src/*.ts(x)` | `types` → `./src/*.ts`, `default` → `./dist/*.js` |
| build script | none | `"build": "tsc"` |
| turbo can cache the build | **no** | yes |
| requires | every consumer bundles/transpiles TS (Next/Vite/Bun) | nothing special |

Pick in this order:

1. **Match the siblings.** `exports` pointing at `./src/*.ts(x)` with no build script means the repo runs JIT (create-turbo starters do); mirror whatever the existing packages chose.
2. **No precedent, or any plain-node consumer → Compiled** (what the official docs model; a plain-node consumer of a JIT package crashes at import time).
3. **JIT only when every consumer transpiles TS.**

Publishable-to-npm is a third tier (versioning/changesets) — out of scope here.

## Step 1 — Directory, chosen from the repo's workspace globs

Read the repo's globs first — `pnpm-workspace.yaml`, or `"workspaces"` in the root package.json for npm/yarn — and create the directory under one of them, next to the sibling packages. `packages/<name>/src/` is the common convention, but a repo whose globs say `libs/*` wants `libs/<name>/`. Globs are **flat** — `packages/*` does not match `packages/group/name`; add `packages/group/*` explicitly. Nested `packages/**` is unsupported.

## Step 2 — package.json

```json
{
  "name": "@repo/utils",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "exports": {
    "./slug": { "types": "./src/slug.ts", "default": "./dist/slug.js" }
  },
  "scripts": { "build": "tsc", "type-check": "tsc --noEmit" },
  "devDependencies": { "@repo/typescript-config": "workspace:*", "typescript": "^5.8.0" }
}
```

- Declare internal deps **the way sibling packages declare theirs**. The template's `"workspace:*"` is the pnpm/bun form; npm and classic yarn use `"*"` — here and in Step 5.
- `name` is exactly what consumers import — namespace it (`@repo/*`) and never rename casually.
- **Per-entrypoint `exports`, no barrel file.** One entry per module (`"./slug"`, `"./dates"`); docs recommend this over a root `"."` index for compiler perf and to keep the import surface explicit. `exports` over `main` — `main` is legacy.
- The `types` → `src`, `default` → `dist` split makes go-to-definition land on source while runtime uses compiled output.
- Copy the scripts/devDeps conventions from a sibling package if the repo has them (shared `@repo/typescript-config` / `@repo/eslint-config` packages are the standard pattern).

## Step 3 — tsconfig.json

```json
{
  "extends": "@repo/typescript-config/base.json",
  "compilerOptions": { "outDir": "dist", "rootDir": "src", "declaration": true, "declarationMap": true },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

If there is no shared config package, inline a base (`strict`, `module: "NodeNext"`, `target: "es2022"`, `isolatedModules`). Notes:
- **No TypeScript project references** — the docs explicitly recommend against them with Turborepo (a second config+cache layer) — **unless the repo already uses them** (`composite: true`, `references` arrays, `tsc -b`): then match the siblings, because one non-composite package breaks the build graph.
- **No `compilerOptions.paths` aliases to internal packages** — the workspace dependency + `exports` map *is* the alias.
- `include: ["src"]` with an empty `src/` fails the whole task with `error TS18003: No inputs were found` — move the code in before running the gate.

## Step 4 — Move the code

Move the module into `src/`, one file per intended entrypoint. Inside the package, imports are relative; **nothing** imports across package directories with `../`.

## Step 5 — Declare the dependency, then INSTALL (the skipped step)

In each consumer's package.json:

```json
"dependencies": { "@repo/utils": "workspace:*" }
```

(Same syntax rule as Step 2.) Then run the package manager's install — the lockfile must learn the new workspace. Skipping install fails with **environment-specific** messages; don't pattern-match on exact text. Observed on pnpm with a plain-node consumer:

```
WARNING  Unable to calculate transitive closures: Workspace 'packages/utils' not found in lockfile.
Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@repo/utils' imported from …
```

Bundlers phrase it their own way (`Module not found: Can't resolve …`), and some setups auto-install and mask the mistake until CI. The durable rule: any "cannot find/resolve @repo/…" right after adding a workspace dep = run install first, before touching config.

Now rewrite the consumer's imports: `import { slug } from '@repo/utils/slug'` (entrypoint paths, exactly as in `exports`).

## Step 6 — turbo.json

Usually zero changes: the new package's `build` is picked up by the existing `"build": { "dependsOn": ["^build"], "outputs": ["dist/**"] }`. Verify: `outputs` covers this package's `dist/**` (outputs are per-package-relative), and `^build` exists so consumers build after it. If the package's built files must be gitignored (they must), confirm `.gitignore` covers `dist/`.

## Step 7 — Gate

Run the SKILL.md Step 3 gate scoped to the new package: `turbo boundaries` first (it catches an import you forgot to declare in the new package.json), then the build/type-check and double-run protocol with `--filter=...@repo/<name>`.

Failure decoder (messages as printed by turbo 2.10.3):
- ``x Cyclic dependency detected:`` followed by ``The cycle can be broken by removing any of these sets of dependencies:`` — the extracted package and the app import each other (dev/peer deps count too). Take one of the suggested cuts: move the shared piece down or split the package.
- `x "pkg#dev" is a persistent task, "pkg#x" cannot depend on it` — you wired a task graph edge onto a dev server; use `"with"`.
- Module not found **only after** a fresh clone / in CI, fine locally — `exports.default` points at `dist/` that nothing builds: check `^build` and `outputs`.
- `No package found with name 'x' in workspace` — filter/name typo, or the new directory isn't matched by the workspace globs (Step 1).

## Wiring type-check across packages

A bare `"type-check": {}` caches per package and **won't re-run the app's type-check when a dependency's types change** — false green. Use the transit-node pattern (`"transit": { "dependsOn": ["^transit"] }`, `"type-check": { "dependsOn": ["transit"] }`) — explained in `reference/caching-tasks.md` §Task graph.
