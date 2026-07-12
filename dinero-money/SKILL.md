---
name: dinero-money
description: Use when writing or fixing code that touches money — prices, totals, tax, discounts, refunds, invoices, payouts, decimal columns, dinero.js — e.g. "add a discount", "calculate tax", "split this payment", "sum order totals", "why is the total off by a cent". Enforces integer minor-unit arithmetic via dinero.js v2, the single db-string↔Money boundary, and the project's rounding policy; gates with type-check.
---

# Money code (dinero.js v2, USD, decimal columns)

Write money-handling code using **dinero.js v2 (≥ 2.0.2, ESM-only, Node ≥ 20)** in a TypeScript app where amounts live in SQL `decimal(p,2)` columns that the ORM reads/writes as **strings** (`"19.99"`). If `package.json` has dinero 1.x or `2.0.0-alpha.*`, or money sits in `float` columns, say so and stop — that needs migration, not new code on top.

Money bugs are almost entirely **compiles-but-wrong**: `subtotal * 1.0825`, `Number(row.total)`, rounding lines before summing — all valid TypeScript, all silently losing cents. The type-check gate (Step 3) catches only stale API shapes and currency mixing. For everything else, the rules below are the only defense — apply them at write time.

## The model you must hold

An amount is **an integer count of minor units + a currency + a scale** — never a JS float. `dinero({ amount: 1999, currency: USD })` is $19.99; a float amount throws at runtime. All arithmetic goes through dinero's functions; `+ - * /` never touch an amount. Objects are immutable.

1. **Decimal strings never pass through `Number()`.** `Number('19.99') * 100 === 1998.9999999999998` — ~6.6% of everyday prices break this way. Only the string-surgery parser `moneyFromDb` turns strings into money.
2. **`multiply` is exact — rounding is a separate, deliberate step.** `multiply($19.99, { amount: 825, scale: 4 })` (8.25%) grows the scale instead of rounding. Round **once**, at a boundary (persist / display / invoice-close), via `transformScale(d, 2, halfEven)` — and always pass the rounding function: **without it, `transformScale` truncates**.
3. **Money never divides — it allocates.** `total / 3` loses a penny; `allocate(total, [1, 1, 1])` returns parts that sum exactly to the input.

The app has **exactly one boundary module** (`src/lib/money.ts`, verbatim in `reference/examples.md` §1): `moneyFromDb`, `moneyToDb` (refuses unrounded scale), `moneyFromCents`, `moneyToDisplay`, `ZERO`. All other code passes `Money` (`Dinero<number, 'USD'>`) values and never sees a raw amount.

## Policy is not yours to choose

Before writing, read the **Money policy** block in the project's `AGENTS.md` (template: `reference/policy-template.md`). It fixes what code cannot derive: rounding mode, rounding boundaries, per-line vs per-invoice tax. **If a required line is missing, stop and ask — never invent a rounding policy.**

## Never write (hard bans)

- `+ - * / %` on any amount, including `.amount` from `toSnapshot()` — dinero functions only
- `Number(...)` / `parseFloat` / unary `+` on a DB decimal string — `moneyFromDb` only
- Float literals as amounts, multipliers, or ratios (`dinero({ amount: 19.99 })`, `multiply(d, 0.0825)`) — they throw; use integer minor units and `{ amount, scale }`
- `total / n` for splits or `.toFixed()` in money math — `allocate()` / `transformScale`
- Rounding intermediates, or any scale-reducing `transformScale` without an explicit rounding function (the default truncates)
- v1 chainable API (`Dinero({...}).add(...)`, `.toFormat()`) or `@dinero.js/*` imports — dead; decoder in `reference/v2-changes.md`
- `float`/`real` money columns, or persisting an unrounded object — `moneyToDb` enforces scale 2
- Deriving amounts in SQL (`price * quantity`, tax math) — SQL may only `SUM` stored amounts
- Hand-rolled currency objects — `import { USD } from 'dinero.js'`

## Step 1 — Verify wiring and policy

1. `package.json`: `dinero.js` ≥ 2.0.2. Imports come from `'dinero.js'` (root exports everything, including `USD`).
2. Find the money module (`moneyFromDb`/`moneyToDb`); if missing, create it verbatim from `reference/examples.md` §1 — never inline parsing at call sites.
3. Read the AGENTS.md Money policy block. Missing or incomplete → stop and ask.

## Step 2 — Write from the canonical shapes

Mimic the closest shape in `reference/examples.md`. The three lines to memorize:

```ts
const price = moneyFromDb(row.unitPrice)                        // strings enter here, nowhere else
const tax   = transformScale(multiply(subtotal, { amount: 825, scale: 4 }), 2, halfEven)
const parts = allocate(total, [1, 1, 1])                        // splits sum exactly; / loses pennies
```

Also: sums fold with `reduce((acc, x) => add(acc, x), ZERO)`; compare with `greaterThan`/`equal`/`isZero`/… (never compare `.amount`s); `Number()` is legal in exactly one place — inside `moneyToDisplay`, where nothing downstream computes with it.

## Step 3 — Type-check (the gate)

```bash
npm run type-check   # or: npx tsc --noEmit
```

The gate catches stale v1/alpha shapes and currency mixing (`Money` is literal-typed). It does **not** catch: native arithmetic on numbers that used to be money, `Number()` on a decimal string, premature rounding, a missing `allocate`, SQL-side derivation. Re-read your diff against the hard bans before declaring done.
