# MSSQL dialect decoder — Postgres/MySQL/v0 habits → correct Drizzle v1 on SQL Server

Training data is dominated by Drizzle-on-Postgres and drizzle-orm 0.x. When type-check flags your code, the fix is almost always in this file. Everything here is verified against `drizzle-orm@1.0.0-beta.22` / `1.0.0-rc.4`.

## Imports & wiring

| Stale / wrong | Correct |
|---|---|
| `from 'drizzle-orm/pg-core'`, `'drizzle-orm/mysql-core'` | `from 'drizzle-orm/mssql-core'` |
| `from 'drizzle-orm/node-postgres'`, `postgres()`, `new Pool()` | `import { drizzle } from 'drizzle-orm/node-mssql'` wrapping the `mssql` npm package |
| `drizzle({ connection: { connectionString, ssl } })` (old beta blog) | `drizzle(process.env.DATABASE_URL!)` or `const pool = await mssql.connect(...); drizzle({ client: pool })` |
| `drizzle(client, { casing: 'snake_case' })` (v0) | Removed in v1 — use the `snakeCase` / `camelCase` table helpers from `mssql-core` (`snakeCase.table('users', {...})`) |
| `import { migrate } from 'drizzle-orm/node-postgres/migrator'` | `from 'drizzle-orm/node-mssql/migrator'` |
| `pgTable`, `mysqlTable` | `mssqlTable` (also: `mssqlSchema`, `mssqlView`, `mssqlTableCreator`) |

Connection string form the driver parses: `mssql://user:password@host:1433/database?encrypt=true&trustServerCertificate=true`.

## Column types

Builders that exist in `mssql-core` (complete list): `int`, `smallint`, `tinyint`, `bigint({ mode })`, `bit`, `decimal`, `numeric`, `float`, `real`, `char`, `nchar`, `varchar`, `nvarchar`, `text`, `ntext`, `binary`, `varbinary`, `date`, `datetime`, `datetime2`, `datetimeoffset`, `time`, `customType`.

| Postgres habit | MSSQL correct |
|---|---|
| `serial('id').primaryKey()` | `int().identity().primaryKey()` — identity is auto-`NOT NULL` and **excluded from insert types**; optional `identity({ seed, increment })` |
| `uuid('id').defaultRandom()` | No `uniqueidentifier` builder exists. `const uniqueidentifier = customType<{ data: string }>({ dataType: () => 'uniqueidentifier' })`, default via `.default(sql\`newsequentialid()\`)` |
| `boolean('active')` | `bit()` — JS `true`/`false` in and out |
| `timestamp('at').defaultNow()` | `datetime2({ mode: 'date' }).default(sql\`sysutcdatetime()\`)` — there is **no** `.defaultNow()` |
| `text('body')` | `nvarchar({ length: 'max' })` for Unicode text (T-SQL `text`/`ntext` are deprecated types — they exist as builders but avoid for new columns) |
| `jsonb('meta')` | `nvarchar({ mode: 'json' }).$type<Meta>()` — stored as NVARCHAR, (de)serialized for you |
| `pgEnum(...)` | No enums in T-SQL — `varchar({ length })` + `text({ enum: [...] })`-style union typing, or a `check()` constraint |
| `bigint('n', { mode: 'number' })` | Same, and `{ mode }` is **required**: `'number' \| 'bigint' \| 'string'` |
| `money` / `smallmoney` / `xml` columns | No builders — `decimal({ precision, scale })`, or `customType` |

v1 note: column names are optional — `int()` uses the property key as the column name; `varchar({ length: 255 })` and friends take config-only.

## Query grammar (the types enforce this)

| Stale / wrong | Correct |
|---|---|
| `.insert(t).values(v).returning()` | `.insert(t).output().values(v)` — **output before values**; `.output({ id: t.id })` for specific columns |
| `.update(t).set(v).returning()` | `.update(t).set(v).output().where(...)` — `.output()` = new values; `.output({ deleted: true })` = old values; `.output({ deleted: {...}, inserted: {...} })` = both, partial. **Update output never takes flat fields** — `{ id: t.id }` is insert/delete syntax; on update wrap it: `{ inserted: { id: t.id } }` |
| `.delete(t).returning()` | `.delete(t).output({ id: t.id }).where(...)` — emits `OUTPUT DELETED.*` |
| insert/update/delete without `.output()` returning rows | Without `.output()` they resolve to the raw driver result (`rowsAffected`), **not** rows |
| `.limit(10)` | `.top(10)` immediately after `db.select(...)`, before `.from()` |
| `.limit(10).offset(20)` | `.orderBy(...).offset(20).fetch(10)` — `offset` only exists after `orderBy`; `fetch` only after `offset`; `top` and `offset/fetch` are mutually exclusive branches |
| `.onConflictDoUpdate` / upsert | Does not exist. Transaction with update-then-insert, or `db.execute(sql\`MERGE ...\`)` — see examples |
| `insert().select(...)` | "Currently not supported" for MSSQL |
| `db.query.users.findMany({...})` | RQBv2 / `defineRelations` is **not wired for MSSQL**. Core builder + joins, or legacy `db._query` (below) |
| `getTableColumns(t)` (v0) | `getColumns(t)` in v1 |

Transactions: `db.transaction(async (tx) => {...}, { isolationLevel: 'read committed' | 'read uncommitted' | 'repeatable read' | 'serializable' | 'snapshot' })`. Nested `tx.transaction()` = savepoints.

## Legacy relational queries (`db._query`)

v1's new relational API (`defineRelations` + `db.query`) does not support MSSQL yet. The v0-style API survives, renamed with an underscore:

- Define with `relations()` imported from **`drizzle-orm/_relations`** (it is no longer exported from the root).
- Pass tables *and* relations in the schema: `drizzle(url, { schema: { users, posts, usersRelations, postsRelations } })`.
- Query with `db._query.users.findMany({ with: { posts: true } })`.

The underscore means "kept for compatibility" — prefer the core builder + joins for new code; use `_query` only when nested results genuinely pay for it.

## drizzle-kit

```ts
// drizzle.config.ts
import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  dialect: 'mssql',                       // exactly this string
  schema: './src/db/schema.ts',
  out: './drizzle',
  dbCredentials: { url: process.env.DATABASE_URL! },
  // object form instead of url: { server, port, user, password, database,
  //   options?: { encrypt, trustServerCertificate } } — note `server` (not host), port required
})
```

Workflow: **dev** = `drizzle-kit push` (schema → DB directly, no files); **production** = `drizzle-kit generate` (emit SQL migration) + `drizzle-kit migrate` (apply, tracked in the migrations table). Never both against the same long-lived database, and never hand-edit an already-applied migration — generate a new one. v1 kit writes one folder per migration (no `journal.json`); `drizzle-kit drop` is gone. `drizzle-kit pull` (introspect) exists for MSSQL but has open bug reports — don't rely on it.

## Known beta/rc issues (verified open as of 2026-07)

| Issue | Impact | Defense |
|---|---|---|
| #5632 empty `inArray`/`notInArray` broken on SQL Server | runtime error / wrong SQL | guard: `if (!ids.length) return []` before the query |
| #5883 no `WITH (NOLOCK)` table hints | can't express dirty-read hints | use `{ isolationLevel: 'read uncommitted' }` on a transaction, or raw `sql` |
| #5328 "transaction is not a function" | client passed without a connected pool | `const pool = await mssql.connect(...)` then `drizzle({ client: pool })` |
| #5220 `drizzle-kit pull` crashes on some MSSQL schemas | introspection unreliable | write schema by hand |
| #5881 computed (`generatedAlwaysAs`) columns included in INSERT (error 271) | insert fails | fixed in `1.0.0-rc.4` — upgrade if hit |
| No `OUTER APPLY`/`CROSS APPLY` builder (#5511) | some lateral-join queries | raw `sql` |

## Runtime error decoder

| Error | Cause | Fix |
|---|---|---|
| `Cannot read properties of undefined (reading 'findMany')` on `db.query.x` | RQBv2 not supported on MSSQL | `db._query` with legacy `relations()`, or core builder |
| `db._query.users` is a `DrizzleTypeError` about missing schema generic | tables/relations not passed to `drizzle(url, { schema })` | pass the full schema object at init |
| `transaction is not a function` | un-awaited / unconnected `mssql` client | `await mssql.connect(...)` before `drizzle({ client: pool })` |
| Insert fails with "Cannot insert explicit value for identity column" | identity column in `.values()` | remove it — identity columns are generated |
| `Violation of PRIMARY KEY constraint` on your "upsert" | no ON CONFLICT on MSSQL; plain insert raced | transaction update-then-insert or `MERGE` (examples §8) |
| Whole table updated/deleted | missing `.where()` — it compiles | always chain `.where(...)`; restore from backup, then add the ESLint rules `drizzle/enforce-update-with-where`, `drizzle/enforce-delete-with-where` |
