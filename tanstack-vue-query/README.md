# tanstack-vue-query

A host-agnostic [Agent Skill](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/) that teaches an AI coding agent to write correct **TanStack Query v5** code in **Vue 3** (`@tanstack/vue-query`): queries, mutations, invalidation, pagination, infinite queries, optimistic updates, and prefetching.

It exists because weaker models are trained overwhelmingly on **React Query and v4** examples, and the resulting bugs split into two classes:

- **API-shape bugs** (React imports, positional arguments, `cacheTime`, `onSuccess` on queries) — caught by type-check, which the skill uses as its gate.
- **Reactivity bugs** (a plain value in `queryKey`, a boolean `enabled`, a value unwrapped at a composable boundary) — these **compile cleanly and silently never refetch**, because Vue's `<script setup>` runs once where React re-renders. No gate catches them, so the skill front-loads three hard rules (IN raw / UNWRAP only in `queryFn` / OUT as refs) and canonical shapes to mimic.

## Contents

```
tanstack-vue-query/
├── SKILL.md                  # the skill: mental model + hard bans + 3-step procedure
└── reference/
    ├── v5-changes.md         # v4/React → v5 Vue decoder table + error-message decoder
    └── examples.md           # 10 canonical shapes (query, composable, mutation, optimistic, …)
```

## How it works

1. **Hold the reactivity model** — setup runs once; anything that changes crosses into vue-query as a ref/getter, is unwrapped with `toValue()` only inside `queryFn`, and comes back out as refs.
2. **Refuse stale shapes** — a hard-ban list of React/v4 patterns the model must never emit.
3. **Verify version and wiring** — require `@tanstack/vue-query` ^5 in `package.json` and `app.use(VueQueryPlugin)`; stop on v4 rather than mixing APIs.
4. **Write from canonical examples** — 10 worked shapes to mimic rather than improvise.
5. **Type-check as the gate** — `vue-tsc` proves the API shapes; the skill is explicit about what the gate does *not* catch so reactivity is enforced at write time.

## Install

`SKILL.md` is the open agent-skills format, read by Claude Code, GitHub Copilot, Cursor, Codex CLI, and others. Drop the folder into a skills directory — no per-host adapter needed.

**Project-scoped** (committed to a repo, works in any supported agent):
```bash
mkdir -p .agents/skills            # also recognized: .claude/skills, .github/skills
cp -r tanstack-vue-query .agents/skills/
```

**Personal / global:**
- Claude Code: `~/.claude/skills/tanstack-vue-query/`
- GitHub Copilot: `~/.copilot/skills/` or `~/.agents/skills/`

The agent auto-loads the skill when a request matches the `description` in the frontmatter (e.g. "add a mutation", "the query doesn't refetch when the id changes").

## Scope

Handles: `@tanstack/vue-query` **v5** with the Vue 3 Composition API — the full client-side surface. **Out of scope** (the skill will say so and stop): v4 codebases, React Query, and Nuxt/SSR hydration.
