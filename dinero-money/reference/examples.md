# Worked examples — money code with dinero.js v2 (USD, decimal-string columns)

Mimic the closest shape exactly; every deviation is a place a cent goes missing. Everything imports from `'dinero.js'` (`npm i dinero.js`, must resolve ≥ 2.0.2).

---

## 1. The money module — the ONLY place raw representations cross

Create once at `src/lib/money.ts` (or find the project's existing one). Everything else passes `Money` values and never touches a raw amount.

```ts
import {
  dinero, toDecimal, toSnapshot, transformScale, halfEven,
  USD, type Dinero,
} from 'dinero.js'

export type Money = Dinero<number, 'USD'>   // branded: mixing currencies is a compile error

export const ZERO: Money = dinero({ amount: 0, currency: USD })

export function moneyFromCents(cents: number): Money {
  if (!Number.isSafeInteger(cents)) throw new Error(`Not an integer cent amount: ${cents}`)
  return dinero({ amount: cents, currency: USD })
}

// DB decimal(p,2) string -> Money. String surgery only — the value NEVER passes through a float.
// Handles "19.99", "5", "5.1", "-0.50" (sign applied last: Number("-0") loses it otherwise).
export function moneyFromDb(value: string): Money {
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value.trim())
  if (!m) throw new Error(`Not a decimal string: ${value}`)
  const [, sign, whole, frac = ''] = m
  if (frac.length > 2) throw new Error(`More than 2 decimal places: ${value}`)
  const minor = BigInt(whole) * 100n + BigInt(frac.padEnd(2, '0') || '0')
  const amount = Number(sign ? -minor : minor)
  if (!Number.isSafeInteger(amount)) throw new Error(`Amount exceeds safe integer: ${value}`)
  return dinero({ amount, currency: USD })
}

// Money -> DB decimal string. Refuses unrounded intermediates so the DATABASE never rounds
// (SQL Server would coerce >2dp half-away-from-zero — a different policy than ours).
export function moneyToDb(d: Money): string {
  if (toSnapshot(d).scale !== 2) {
    throw new Error('Round before persisting: transformScale(d, 2, halfEven)')
  }
  return toDecimal(d)   // "19.99" — pads ("5.00") and keeps sign ("-0.50")
}

// Display only. The Number() here is legal ONLY because nothing downstream computes with it.
const usdFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export function moneyToDisplay(d: Money): string {
  return usdFormat.format(Number(toDecimal(transformScale(d, 2, halfEven))))
}
```

---

## 2. Arithmetic — through the API, never operators

```ts
import { dinero, add, subtract, USD } from 'dinero.js'
import { ZERO, moneyFromCents, type Money } from '@/lib/money'

const a: Money = dinero({ amount: 1999, currency: USD })   // $19.99 — integer minor units
// dinero({ amount: 19.99, currency: USD })                // THROWS: Amount is invalid.

const withShipping: Money = add(subtotal, shipping)
const refund: Money = subtract(paid, returned)

// summing a list: fold with ZERO — there is no sum() and no + operator
const total: Money = lineTotals.reduce((acc, x) => add(acc, x), ZERO)
```

Objects are immutable; mixed-scale operands take the higher scale — exactness is preserved, rounding still happens only at the boundary.

---

## 3. Percentages and tax — scaled multiplier, round ONCE

A rate is `{ amount, scale }`: 8.25% = 825/10⁴ = `{ amount: 825, scale: 4 }`. Float factors throw; integer factors (`multiply(unitPrice, quantity)`) are exact and keep scale 2.

```ts
import { multiply, transformScale, halfEven } from 'dinero.js'

const TAX_RATE = { amount: 825, scale: 4 }                 // from config, never a float

const taxExact = multiply(subtotal, TAX_RATE)              // EXACT: scale grew to 6, nothing rounded
const tax: Money = transformScale(taxExact, 2, halfEven)   // the single, deliberate rounding step
const total: Money = add(subtotal, tax)
```

**Where you round changes the answer**: two lines with exact tax $0.575 each give `0.58 + 0.58 = $1.16` per-line but `round(1.15) = $1.15` per-invoice. The project's policy block decides which; you follow it.

---

## 4. Splits and proration — `allocate`, never divide

```ts
import { allocate, transformScale, halfEven } from 'dinero.js'

// $100.00 three ways — parts sum EXACTLY to the input; total/3 would lose a penny
const [p1, p2, p3] = allocate(total, [1, 1, 1])            // 33.34, 33.33, 33.33

// uneven split: ratios are relative weights
const [payout, fee] = allocate(total, [97, 3])

// fractional ratios: scaled amounts (floats throw) — results come back at a HIGHER scale
const parts = allocate(total, [{ amount: 305, scale: 1 }, { amount: 695, scale: 1 }])
  .map((part) => transformScale(part, 2, halfEven))
```

Remainder cents go to the largest ratio first (ties: earlier position). Zero ratios receive nothing; negative or all-zero ratios throw.

---

## 5. Comparisons and output

```ts
import {
  equal, compare, greaterThanOrEqual, isZero, isNegative, minimum,
  toDecimal, toUnits, toSnapshot,
} from 'dinero.js'
import { moneyFromCents, moneyToDb, moneyToDisplay, type Money } from '@/lib/money'

if (greaterThanOrEqual(subtotal, moneyFromCents(5000))) applyFreeShipping()
if (isZero(balance)) markSettled()
const cheapest: Money = minimum([priceA, priceB])
const sorted = prices.toSorted(compare)                    // compare returns -1 | 0 | 1

const forDb: string = moneyToDb(total)          // "123.45" — persist to decimal(p,2)
const forScreen: string = moneyToDisplay(total) // "$123.45" — humans only
const wire = toSnapshot(total)                  // { amount, currency, scale } — JSON/API; rebuild with dinero(wire)
const [dollars, cents] = toUnits(total)         // [123, 45]
```

Never compare or compute with `toSnapshot(x).amount` — that's a raw number again, and it breaks the moment scales differ.

---

## 6. The Drizzle boundary — decimal columns are strings

```ts
// schema: total: decimal({ precision: 19, scale: 2 }).notNull()  → row.total: string

// READ: strings become Money at the boundary, immediately
const rows = await db.select().from(orders).where(eq(orders.customerId, id))
const totals: Money[] = rows.map((r) => moneyFromDb(r.total))

// WRITE: Money becomes a string at the boundary — moneyToDb refuses unrounded values
await db.insert(orders)
  .output()
  .values({ customerId: id, total: moneyToDb(orderTotal) })

// SQL aggregation carve-out (policy): SUM over STORED amounts is allowed — T-SQL decimal
// arithmetic is exact. The string result re-enters through the same door as any column read.
const [row] = await db.select({ sum: sql<string | null>`sum(${orders.total})` }).from(orders)
const grandTotal: Money = moneyFromDb(row.sum ?? '0')

// STILL BANNED in SQL: deriving amounts — no price * quantity, no tax math in queries.
```

Never "fix" the string type with `Number(row.total)` — that is the exact bug this setup exists to prevent.

---

## 7. End to end — pricing an invoice

Every rule above in one function. Policy assumed: per-invoice tax, halfEven — **check the project's AGENTS.md policy block before copying.**

```ts
import { add, multiply, transformScale, halfEven, type DineroScaledAmount } from 'dinero.js'
import { moneyFromDb, moneyToDb, ZERO, type Money } from '@/lib/money'

type InvoiceLine = { unitPrice: string; quantity: number }   // unitPrice: decimal string from DB

export function priceInvoice(lines: InvoiceLine[], taxRate: DineroScaledAmount<number>) {
  // strings -> Money at the boundary; integer quantity multiply is exact (scale stays 2)
  const lineTotals: Money[] = lines.map((l) => multiply(moneyFromDb(l.unitPrice), l.quantity))

  const subtotal: Money = lineTotals.reduce((acc, x) => add(acc, x), ZERO)   // exact

  // tax on the invoice total, rounded ONCE (per-invoice policy)
  const tax: Money = transformScale(multiply(subtotal, taxRate), 2, halfEven)

  const total: Money = add(subtotal, tax)

  return {
    subtotal: moneyToDb(subtotal),   // strings out at the boundary — nothing upstream
    tax: moneyToDb(tax),             // of these lines ever rounded
    total: moneyToDb(total),
  }
}
```

For per-*line* tax policy instead: round each line's `multiply(lineTotal, taxRate)` to scale 2 first, then sum the rounded taxes.
