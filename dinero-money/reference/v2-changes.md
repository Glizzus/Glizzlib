# dinero.js v2 stable decoder — v1 habits / alpha-era docs → correct 2.0.2 code

dinero.js v2 went **stable in March 2026** (2.0.0 → 2.0.2 within two weeks). Training data is dominated by v1 (chainable API) and the 2.0.0-alpha line — both now wrong in specific ways. Everything here is verified against `dinero.js@2.0.2`.

**Version rules:** require `dinero.js >= 2.0.2` (2.0.0 shipped without `"type": "module"`, 2.0.1 had a type-only enum that broke bundles). ESM-only — no `require()` path. Node ≥ 20.

## Imports (the single biggest alpha→stable change)

All `@dinero.js/*` scoped packages were **removed and deprecated** — everything consolidated into one package with four entrypoints: `dinero.js`, `dinero.js/currencies`, `dinero.js/bigint`, `dinero.js/bigint/currencies`.

| Stale / wrong | Correct |
|---|---|
| `import { USD } from '@dinero.js/currencies'` | `import { USD } from 'dinero.js'` (root re-exports all currencies) or `from 'dinero.js/currencies'` |
| `import { dinero } from '@dinero.js/core'` | `import { dinero } from 'dinero.js'` |
| `@dinero.js/calculator-bigint` | `import { dinero } from 'dinero.js/bigint'` + currencies from `'dinero.js/bigint/currencies'` (number and bigint currency objects are **not** interchangeable) |
| `import type { Currency, Snapshot, Options, Calculator }` | Renamed with prefix: `DineroCurrency`, `DineroSnapshot`, `DineroOptions`, `DineroCalculator` |
| `import Dinero from 'dinero.js'` (v1 default export) | No default export — named `dinero` factory |

Currency data tracks live ISO 4217: 166 currencies in 2.0.2; alpha-era `HRK`, `CUC`, `SLL`, `VEF` no longer exist (compile error). Pin the package version if currency metadata stability matters.

## v1 → v2 method decoder

| v1 (chainable) | v2 (functional) |
|---|---|
| `Dinero({ amount: 500, currency: 'USD' })` | `dinero({ amount: 500, currency: USD })` — currency is an **object**, not a string |
| `d1.add(d2)` / `d1.subtract(d2)` | `add(d1, d2)` / `subtract(d1, d2)` |
| `d.multiply(0.0825)` | `multiply(d, { amount: 825, scale: 4 })` — float factors **throw** |
| `d.divide(3)` | **Removed.** `allocate(d, [1, 1, 1])` |
| `d.percentage(50)` | **Removed.** `multiply(d, { amount: 50, scale: 2 })` |
| `d.allocate([50, 50])` | `allocate(d, [50, 50])` |
| `d.equalsTo(d2)` | `equal(d, d2)` |
| `d.getAmount()` / `d.getCurrency()` | **Removed.** `toSnapshot(d).amount` / `.currency` — serialization only, never arithmetic |
| `d.toFormat('$0,0.00')` | **Removed.** `toDecimal(d)` + `Intl.NumberFormat`, or `toDecimal(d, ({ value, currency }) => ...)` |
| `d.toUnit()` / `d.toRoundedUnit(2)` | **Removed.** `toDecimal` / `toUnits` (returns `[dollars, cents]`) |
| `d.convertPrecision(4)` | `transformScale(d, 4)` — and see the truncation trap below |
| `Dinero.minimum([...])` / `.maximum([...])` | `minimum([d1, d2])` / `maximum([d1, d2])` |
| v1 global/locale settings (`Dinero.globalLocale`, …) | **Removed.** Compose with `Intl.NumberFormat` |

Naming traps: it's `haveSameCurrency([a, b])` / `haveSameAmount([a, b])` (plural *have*); `equal`, not `equals`; 8 rounding functions including `halfOdd`.

## Verified signatures (2.0.2)

```ts
dinero({ amount: number, currency: DineroCurrency, scale?: number }): Dinero<number, TCurrency>
add(a, b) / subtract(a, b)                    // b: Dinero<TAmount, NoInfer<TCurrency>> — cross-currency = COMPILE error
multiply(d, factor)                            // factor: integer | { amount, scale } — EXACT, result scale grows
allocate(d, ratios)                            // ratios: (integer | { amount, scale })[] — results sum exactly to d
transformScale(d, newScale, divide?)           // divide: down|up|halfUp|halfDown|halfEven|halfOdd|halfTowardsZero|halfAwayFromZero
trimScale(d)                                   // lossless: strips trailing zeros down to currency exponent
normalizeScale([a, b, ...])                    // brings all to the highest scale
compare(a, b): -1 | 0 | 1                      // also equal, greaterThan(OrEqual), lessThan(OrEqual), minimum([...]), maximum([...])
isZero(d) / isPositive(d) / isNegative(d) / hasSubUnits(d)
toDecimal(d): string                           // "19.99" — pads ("5" → "5.00"), keeps sign ("-0.50"), FOLLOWS CURRENT SCALE
toUnits(d): readonly number[]                  // [19, 99]
toSnapshot(d): { amount, currency, scale }     // serialization/tests only — never do math on .amount
```

**Rounding is only ever a `transformScale` concern.** `multiply`, `allocate`, `convert`, `toDecimal` take no rounding parameter — they are exact (scale-raising) or scale-faithful. And the trap: **`transformScale(d, 2)` with no third argument truncates when scaling down** (verified: `1.649175` → `1.64`). Every scale-reducing call must pass the policy's rounding function.

`allocate` semantics (≥ alpha.15 / stable): remainder cents go to the **largest ratio first**, ties broken by earlier position (`$10.03` over `[1, 3]` → `2.50, 7.53`; over `[1, 1, 1]` → first element gets the extra cent). Zero ratios are allowed and receive nothing; all-zero or negative ratios throw. Scaled ratios (`{ amount: 505, scale: 1 }`) **raise the scale of every result** — `transformScale(part, 2, halfEven)` after.

## Why the `Number()` bans are absolute

`Number(s) * 100` on two-decimal strings is off-by-nearly-one for ~6.6% of all values under 10,000 — truncation (`Math.trunc`, `parseInt`, `|0`) then loses a full cent:

| Input | `Number(s) * 100` |
|---|---|
| `"19.99"` | `1998.9999999999998` |
| `"1.15"` | `114.99999999999999` |
| `"0.29"` | `28.999999999999996` |
| `"2.22"` | `222.00000000000003` |

`Math.round(...)` happens to repair all 2-decimal cases — but breaks on ≥3-decimal strings (`"1.005"` → `100.4999…` → 100; the half was lost in the double *before* rounding — same reason `(1.005).toFixed(2) === "1.00"`) and on large magnitudes. The official docs' `dineroFromFloat` helper (`Math.round(float * factor)`, with an "isn't tested" caveat) is for values that are *already* floats. For DB strings, parse the **string** (`moneyFromDb`, examples §1) — and note the sign trap it handles: for `"-0.50"`, `Number("-0") === -0`, so naive `whole * 100 + frac` yields **+50**; the sign must come from the string and be applied last.

## Nobody agrees on rounding defaults (why policy must be written down)

| System | Tie-breaking default |
|---|---|
| dinero `transformScale` (no 3rd arg) | **truncation** (`down`) |
| JS `Math.round` | half toward +∞ (`Math.round(-2.5) === -2` — asymmetric) |
| `Intl.NumberFormat` | half away from zero (`halfExpand`) |
| SQL Server `ROUND()` / decimal coercion | half away from zero — **no banker's rounding available** |
| .NET `Math.Round` | half to even (banker's) |
| IEEE 754 arithmetic | half to even |

Corollary for this stack: if the app writes a >2-decimal string into a `decimal(p,2)` column, SQL Server silently rounds it **half-away-from-zero** — a different policy than the app's. `moneyToDb` refuses non-scale-2 objects precisely so the database never gets to round.

## Runtime error decoder

| Error | Cause | Fix |
|---|---|---|
| `[Dinero.js] Amount is invalid.` | Float passed as `amount`, multiplier, or ratio (`dinero({ amount: 19.99 })`, `multiply(d, 0.0825)`) | Integer minor units; `{ amount, scale }` for fractions |
| `[Dinero.js] Objects must have the same currency.` | Mixed currencies at runtime (compile error too if currency literals are typed) | Same-currency operands; this app is USD-only |
| `ERR_REQUIRE_ESM` / `require() of ES Module` | dinero.js 2.x is ESM-only | `import`, or bundler with ESM support; Node ≥ 20 |
| `'"dinero.js"' has no exported member 'HRK'` (etc.) | ISO 4217 drift — currency removed | Current currency list only |
| Type error: `Dinero<number, "USD">` vs `Dinero<number, "EUR">` | Cross-currency `add`/`compare` — working as intended | Don't mix; convert explicitly with `convert()` and real rates |
| DB shows `19.990000` or truncated cents | Persisted an unrounded intermediate; `toDecimal` follows current scale | `transformScale(d, 2, halfEven)` before `moneyToDb` — the helper enforces this |
| Total off by one cent vs sum of lines | Rounded per-line when policy says per-invoice (or vice versa), or a `Number()` snuck in | Follow the policy block; round once at the boundary |
