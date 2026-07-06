---
name: drizzle-mssql
description: Use when writing or fixing Drizzle ORM code against SQL Server / MSSQL (drizzle-orm v1 beta/rc, drizzle-orm/node-mssql) — e.g. "define a table with Drizzle", "insert and get the new id back", "paginate this query", "upsert this row", "generate a migration", "why is there no .returning() / .limit()". Enforces the T-SQL builder grammar (output, top, offset/fetch) and idiomatic Drizzle, then gates with type-check.
---

# Drizzle ORM on SQL Server (v1 beta/rc only)

Write Drizzle ORM v1 code against SQL Server using `drizzle-orm/mssql-core` + `drizzle-orm/node-mssql` (the `mssql` npm driver). MSSQL support exists **only in the 1.0.0 beta/rc line**. If `package.json` has `drizzle-orm` 0.x (no MSSQL support at all) or the project targets another dialect, say so and stop.

Drizzle-on-MSSQL code fails in two predictable ways: **wrong-dialect shapes** (training data is overwhelmingly Drizzle-on-Postgres — `.returning()`, `.limit()`, `pgTable` don't exist here), which the type-check gate catches; and **compiles-but-wrong** — valid TypeScript that destroys or leaks data, which only the write-time rules below catch.

## The model you must hold

Drizzle is a **typed SQL builder, not Prisma**: you write the T-SQL shape in TypeScript. Schema declared with `mssqlTable` is the source of truth; types are inferred (`typeof users.$inferSelect`), never hand-written; filters are **operator functions from `'drizzle-orm'`** (`eq`, `and`, `inArray`, …); nothing runs until `await`; results are **plain arrays** (single row = `rows[0]`, possibly `undefined`).

On top of that, the five T-SQL facts that differ from every Postgres example you have memorized:

| Postgres habit | SQL Server reality |
|---|---|
| `.returning()` | **`.output()`** — on insert it goes **before `.values()`**; no `.output()` = you get a driver result, not rows |
| `.limit(n)` | **`.top(n)` before `.from()`**, or `.orderBy(…).offset(n).fetch(m)` — the types enforce this order: `offset` exists only after `orderBy`, `fetch` only after `offset` |
| `serial` / `uuid` / `boolean` / `timestamp` | `int().identity()` / `customType` uniqueidentifier / `bit()` / `datetime2()` — see `reference/mssql-differences.md` |
| `.onConflictDoUpdate(…)` | **No upsert API.** Transaction with explicit update-then-insert, or raw `sql\`MERGE …\`` |
| `db.query.users.findMany(…)` | **RQBv2 is not supported on MSSQL.** Prefer the core builder + joins; legacy `db._query` exists (see examples) |

## Compiles but wrong — the gate cannot catch these

1. **Every `update`/`delete` gets a `.where()`.** Without one it compiles and hits the entire table.
2. **`.where(undefined)` means "no filter".** `cond && eq(...)` can evaluate to `undefined` and silently unfilter. Build conditions as a `SQL[]` array and pass `and(...conds)` — `and()` ignores `undefined` members.
3. **Inside `db.transaction(async (tx) => {...})`, only `tx` touches the database.** A `db.` call inside the callback escapes the transaction and is not rolled back. Throwing rolls back; `tx.rollback()` throws `TransactionRollbackError`.
4. **`sql\`…\`` interpolation is parameterized; `sql.raw()` is a string splice.** Never put a variable inside `sql.raw()`.
5. **One `db` instance at module scope.** Never create a connection/pool inside a request handler.
6. **Guard `inArray` against empty arrays** (`if (!ids.length) return []`) — broken on SQL Server in the beta (issue #5632).

## Never write (foreign shapes — the gate catches these; fix from the decoder)

- `import ... from 'drizzle-orm/pg-core'` or `'mysql-core'` — schema from **`mssql-core`**, driver from **`node-mssql`**
- `.returning(...)` → `.output(...)`
- `.limit(n)` → `.top(n)` / `.orderBy(…).offset(n).fetch(m)`
- `.onConflictDoUpdate` / `.onDuplicateKeyUpdate` → no upsert API; examples §8
- `serial()`, `uuid()`, `boolean()`, `timestamp()`, `jsonb()`, `.defaultNow()` → MSSQL column set; `.default(sql\`sysutcdatetime()\`)`
- `where: { id: 1 }` object filters or `db.select('id', 'name')` → operator functions; partial select is `db.select({ id: users.id })`
- `drizzle({ connection: { connectionString } })` (old beta blogs) → `drizzle(url)` or `drizzle({ client: pool })`

Full dialect decoder, column-type table, and known beta issues: `reference/mssql-differences.md`.

## Step 1 — Verify version and wiring (do not assume)

1. `package.json`: `drizzle-orm` at **1.x** (`1.0.0-beta.*` / `1.0.0-rc.*`) plus the **`mssql`** driver. 0.x → say so and stop (offer to install the v1 line).
2. `drizzle.config.ts` has `dialect: 'mssql'`; find the module-scope `db` (import from `'drizzle-orm/node-mssql'`). Create from example §0 if missing.
3. Reuse the project's conventions: schema files, column naming, migration workflow (`generate`+`migrate` vs `push`).

## Step 2 — Write from the canonical shapes

Mimic the closest example in `reference/examples.md`. The shapes to memorize — insert that returns the new row, and the only two legal pagination forms:

```ts
const [created] = await db.insert(users)
  .output()                                  // BEFORE .values(); omit fields = full row back
  .values({ name: 'Ada' })                   // never pass identity columns

const firstTen = await db.select().top(10).from(users)          // top BEFORE from

const page = await db.select().from(users)
  .orderBy(users.id)                         // required — offset/fetch don't exist until orderBy
  .offset(20).fetch(10)                      // OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY
```

While writing, also enforce: identity columns never appear in `.values()`; `bigint` requires a `mode`; `varchar`/`nvarchar` take `{ length }` (or `'max'`); schema changes are followed by `drizzle-kit generate` (never hand-edit applied migrations).

## Step 3 — Type-check (the gate)

```bash
npm run type-check   # or: npx tsc --noEmit
```

If it errors on your change, the shape is almost certainly a Postgres/v0 habit — fix from `reference/mssql-differences.md` and re-run until clean. Then re-read your diff against the **Compiles but wrong** list above — those were your responsibility in Step 2, and no error will remind you.
