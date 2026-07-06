# Worked examples — Drizzle ORM v1 on SQL Server

Each example is the canonical shape for a common task. Mimic the closest one exactly; every deviation is a place a bug hides. Schema builders come from `drizzle-orm/mssql-core`, the driver from `drizzle-orm/node-mssql`, operators from `drizzle-orm`.

---

## 0. Install & the one `db` instance

```bash
npm i drizzle-orm@beta mssql            # or drizzle-orm@rc — must be the 1.x line
npm i -D drizzle-kit@beta @types/mssql
```

```ts
// src/db/index.ts — module scope, imported everywhere; NEVER created per request
import { drizzle } from 'drizzle-orm/node-mssql'
import * as schema from './schema'

export const db = drizzle(process.env.DATABASE_URL!, { schema })
// DATABASE_URL: mssql://user:password@host:1433/mydb?encrypt=true&trustServerCertificate=true
```

Explicit pool variant (needed if you share the pool with non-Drizzle code):

```ts
import mssql from 'mssql'
const pool = await mssql.connect(process.env.DATABASE_URL!)   // MUST be connected
export const db = drizzle({ client: pool, schema })
```

---

## 1. Schema — the canonical table

```ts
// src/db/schema.ts
import { sql } from 'drizzle-orm'
import {
  mssqlTable, int, nvarchar, bit, datetime2, decimal, customType,
} from 'drizzle-orm/mssql-core'

// No uniqueidentifier builder exists — this customType IS the blessed workaround
export const uniqueidentifier = customType<{ data: string }>({
  dataType: () => 'uniqueidentifier',
})

export const orders = mssqlTable('orders', {
  id: int().identity().primaryKey(),                       // IDENTITY(1,1); auto NOT NULL
  publicId: uniqueidentifier().default(sql`newsequentialid()`).notNull(),
  customer: nvarchar({ length: 200 }).notNull(),
  total: decimal({ precision: 10, scale: 2 }).notNull(),
  paid: bit().default(false).notNull(),                    // T-SQL boolean
  meta: nvarchar({ mode: 'json' }).$type<{ tags: string[] }>(),  // JSON-in-NVARCHAR
  createdAt: datetime2({ mode: 'date' })
    .default(sql`sysutcdatetime()`)                        // no .defaultNow() on MSSQL
    .notNull(),
})

export type Order = typeof orders.$inferSelect             // never hand-write row types
export type NewOrder = typeof orders.$inferInsert          // identity/defaulted cols optional
```

Property key = column name when no name is given. After any schema change: `npx drizzle-kit generate`.

---

## 2. Select — operators, TOP, and OFFSET/FETCH pagination

```ts
import { eq, and, gt, inArray, desc } from 'drizzle-orm'

const unpaid = await db.select().from(orders)
  .where(and(eq(orders.paid, false), gt(orders.total, '100')))
  .orderBy(desc(orders.createdAt))

const firstTen = await db.select().top(10).from(orders)    // top BEFORE from; no .limit()

// partial select: object of columns, keys are yours
const summaries = await db
  .select({ id: orders.id, customer: orders.customer })
  .from(orders)

// inArray: GUARD empty arrays — broken on SQL Server (issue #5632)
if (ids.length) {
  await db.select().from(orders).where(inArray(orders.id, ids))
}

// pagination — the types enforce T-SQL's grammar:
const pageSize = 20
const rows = await db.select().from(orders)
  .orderBy(orders.id)                    // REQUIRED — offset doesn't exist until orderBy
  .offset(page * pageSize)               // OFFSET n ROWS
  .fetch(pageSize)                       // FETCH NEXT m ROWS ONLY; fetch only after offset
```

Filters are always operator functions — `where({ paid: false })` does not exist in the core builder. `.top(n)` and `.offset()/.fetch()` are mutually exclusive — pick one per query.

---

## 3. Insert — `.output()` before `.values()`

```ts
// the new row back (T-SQL OUTPUT clause — this dialect's .returning()):
const [created] = await db.insert(orders)
  .output()                                        // omit fields → full inserted row
  .values({ customer: 'Ada', total: '19.99' })     // NEVER include identity columns

// just the generated id:
const [{ id }] = await db.insert(orders)
  .output({ id: orders.id })
  .values({ customer: 'Bo', total: '5.00' })

// multi-row: values takes an array, output returns an array
await db.insert(orders).values([{ customer: 'C', total: '1' }, { customer: 'D', total: '2' }])
```

Without `.output()` the result is the raw driver response (`rowsAffected`), not rows. `.output()` results are **always arrays** — destructure `[row]`.

---

## 4. Update & delete — always `.where()`, `.output()` for rows back

```ts
// UPDATE ... OUTPUT INSERTED.* (the NEW values)
const [updated] = await db.update(orders)
  .set({ paid: true })
  .output()
  .where(eq(orders.id, id))              // OMITTING .where() UPDATES EVERY ROW — and compiles

// old values instead: .output({ deleted: true })
// both, partial: .output({ deleted: { was: orders.total }, inserted: { now: orders.total } })

// DELETE ... OUTPUT DELETED.*
const [removed] = await db.delete(orders)
  .output({ id: orders.id })
  .where(eq(orders.id, id))              // same rule: no .where() = empty table
```

---

## 5. Conditional filters — never let `undefined` reach `.where()` alone

```ts
import { and, eq, gte, like, type SQL } from 'drizzle-orm'

const conds: SQL[] = []
if (filters.paid !== undefined) conds.push(eq(orders.paid, filters.paid))
if (filters.minTotal) conds.push(gte(orders.total, filters.minTotal))
if (filters.q) conds.push(like(orders.customer, `%${filters.q}%`))

const rows = await db.select().from(orders).where(and(...conds))
// and() ignores undefined members; and() of nothing = no filter — which is what you meant.
// NEVER: .where(filters.q && like(...)) — undefined silently unfilters; also never call
// .where() twice on a $dynamic() builder (the second call REPLACES the first).
```

---

## 6. Joins — `leftJoin` makes the right side nullable

```ts
const rows = await db
  .select({ order: orders, customerName: customers.name })   // customerName: string | null
  .from(orders)
  .leftJoin(customers, eq(orders.customerId, customers.id))

for (const { order, customerName } of rows) {
  console.log(order.id, customerName ?? '(no customer)')     // null-check, don't `!`
}
```

One row per match, flat — no automatic nesting. For N+1 avoidance batch with `inArray` or join; never query in a loop.

---

## 7. Transactions — `tx` only, isolation level as config

```ts
await db.transaction(async (tx) => {
  const [order] = await tx.insert(orders).output().values(newOrder)   // tx, NEVER db —
  await tx.update(inventory)                                          // db here escapes the
    .set({ stock: sql`${inventory.stock} - 1` })                      // transaction entirely
    .where(eq(inventory.sku, order.sku))

  if (somethingWrong) tx.rollback()      // throws TransactionRollbackError — expect it upstream
}, { isolationLevel: 'read committed' })  // 'snapshot' | 'serializable' | ...
```

Any throw inside the callback rolls back; there is no manual commit. Nested `tx.transaction(...)` = savepoint.

---

## 8. Upsert — there is no `.onConflictDoUpdate()` on MSSQL

Default shape — transaction, update-then-insert:

```ts
await db.transaction(async (tx) => {
  const updated = await tx.update(settings)
    .set({ value })
    .output({ inserted: { id: settings.id } })   // update takes {inserted}/{deleted}, not flat fields
    .where(eq(settings.key, key))
  if (updated.length === 0) {
    await tx.insert(settings).values({ key, value })
  }
}, { isolationLevel: 'serializable' })   // prevents the update/insert race
```

Raw `MERGE` when a single statement is required (interpolations are parameterized — safe):

```ts
await db.execute(sql`
  MERGE INTO ${settings} AS t
  USING (SELECT ${key} AS [key], ${value} AS [value]) AS s
  ON t.[key] = s.[key]
  WHEN MATCHED THEN UPDATE SET t.[value] = s.[value]
  WHEN NOT MATCHED THEN INSERT ([key], [value]) VALUES (s.[key], s.[value]);
`)
```

---

## 9. Relational queries — legacy `db._query` only (no `db.query` on MSSQL)

```ts
// schema.ts — relations() comes from the _relations subpath in v1
import { relations } from 'drizzle-orm/_relations'

export const customersRelations = relations(customers, ({ many }) => ({
  orders: many(orders),
}))
export const ordersRelations = relations(orders, ({ one }) => ({
  customer: one(customers, { fields: [orders.customerId], references: [customers.id] }),
}))
```

```ts
// db init must receive tables AND relations:
export const db = drizzle(url, { schema: { customers, orders, customersRelations, ordersRelations } })

// note the underscore — db.query does not exist for MSSQL:
const withOrders = await db._query.customers.findMany({
  with: { orders: true },
})
```

Prefer core-builder joins for new code; `_query` is a compatibility surface.

---

## 10. drizzle-kit — config and workflow

```ts
// drizzle.config.ts (project root)
import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  dialect: 'mssql',
  schema: './src/db/schema.ts',
  out: './drizzle',
  dbCredentials: { url: process.env.DATABASE_URL! },
})
```

```bash
npx drizzle-kit push        # DEV ONLY: diff schema straight into the DB, no files
npx drizzle-kit generate    # emit SQL migration from schema diff  ─┐ production
npx drizzle-kit migrate     # apply pending migrations              ─┘ pair
```

Programmatic apply (deploy scripts): `import { migrate } from 'drizzle-orm/node-mssql/migrator'` then `await migrate(db, { migrationsFolder: './drizzle' })`. Commit the `drizzle/` folder; never hand-edit an applied migration — generate a new one.

---

## 11. Prepared statements — hot paths only

```ts
import { sql } from 'drizzle-orm'

// module scope — preparing inside a handler defeats the purpose
const orderById = db.select().from(orders)
  .where(eq(orders.id, sql.placeholder('id')))
  .prepare()

const [order] = await orderById.execute({ id: 42 })
```

Hardcoding a value instead of `sql.placeholder('id')` compiles — and then `.execute({ id })` is silently ignored.
