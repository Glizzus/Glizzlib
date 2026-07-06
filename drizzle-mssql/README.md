# drizzle-mssql

A host-agnostic [Agent Skill](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/) that teaches an AI coding agent to write correct **Drizzle ORM v1 (beta/rc)** code against **SQL Server** (`drizzle-orm/mssql-core` + `drizzle-orm/node-mssql`).

It exists because MSSQL support only landed in the drizzle-orm 1.0 beta line — there is essentially **no training data** for it — so models fall back on Drizzle-on-Postgres habits. The resulting bugs split into two classes:

- **Wrong-dialect API shapes** (`.returning()`, `.limit()`, `pgTable`, `serial`, `onConflictDoUpdate`) — none exist on MSSQL; caught by type-check, which the skill uses as its gate. Helpfully, the MSSQL types encode T-SQL's grammar (`offset` only after `orderBy`, `fetch` only after `offset`, `output` before `values`), so the gate has real teeth.
- **Compiles-but-wrong** (an `update`/`delete` with no `.where()` — updates every row; `db` instead of `tx` inside a transaction; `undefined` swallowed by `.where()`; a variable in `sql.raw()`). No gate catches these, so the skill front-loads them as write-time hard rules.

## Contents

```
drizzle-mssql/
├── SKILL.md                      # the skill: mental model + hard bans + 3-step procedure
└── reference/
    ├── mssql-differences.md      # Postgres/v0 → MSSQL v1 decoder, column types, known beta issues
    └── examples.md               # 12 canonical shapes (schema, output, top/offset-fetch, upsert, …)
```

## How it works

1. **Hold the dialect model** — Drizzle is a typed SQL builder and here you are writing *T-SQL*: `OUTPUT` not `RETURNING`, `TOP`/`OFFSET-FETCH` not `LIMIT`, no upsert clause, no RQBv2.
2. **Refuse foreign shapes** — a hard-ban list of Postgres/Prisma/v0 patterns the model must never emit.
3. **Verify version and wiring** — drizzle-orm must be the 1.x beta/rc line (0.x has no MSSQL at all), `dialect: 'mssql'`, one module-scope `db`.
4. **Write from canonical examples** — 12 worked shapes to mimic rather than improvise, including the beta's real workarounds (`customType` for `uniqueidentifier`, `db._query` for relations, MERGE-via-`sql` for upsert).
5. **Type-check as the gate** — with an explicit list of what the gate does *not* catch (unfiltered `update`/`delete` compiles fine), enforced at write time instead.

## Install

`SKILL.md` is the open agent-skills format, read by Claude Code, GitHub Copilot, Cursor, Codex CLI, and others. Drop the folder into a skills directory — no per-host adapter needed.

**Project-scoped** (committed to a repo, works in any supported agent):
```bash
mkdir -p .agents/skills            # also recognized: .claude/skills, .github/skills
cp -r drizzle-mssql .agents/skills/
```

**Personal / global:**
- Claude Code: `~/.claude/skills/drizzle-mssql/`
- GitHub Copilot: `~/.copilot/skills/` or `~/.agents/skills/`

The agent auto-loads the skill when a request matches the `description` in the frontmatter (e.g. "insert and get the new id back", "why is there no .returning()").

## Scope

Handles: Drizzle ORM **1.0.0-beta/rc** against SQL Server — schema, queries, mutations with `OUTPUT`, pagination, transactions, upserts, legacy relational queries, drizzle-kit migrations, prepared statements. **Out of scope** (the skill will say so and stop): drizzle-orm 0.x (no MSSQL support exists there) and other database dialects.
