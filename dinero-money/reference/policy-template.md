# Money policy template

Copy the block below into the project's `AGENTS.md` (or `CLAUDE.md`) and resolve every `[DECIDE]`. The skill reads this block before writing money code and **stops to ask** when a required line is missing — an agent that invents a rounding policy is a silent financial bug.

Pre-filled lines reflect this project's standing decisions; change them only deliberately.

---

```markdown
## Money policy (read by the dinero-money skill — every line is binding)

- **Currency:** USD only. Any other currency is out of scope — escalate to a human.
- **Representation:** dinero.js v2 `Money` (`Dinero<number, 'USD'>`) everywhere inside the app.
  Raw representations exist only inside `src/lib/money.ts`.
- **Storage:** SQL Server `decimal(19,2)` via Drizzle (strings in TypeScript). Never a float
  column. Strings enter through `moneyFromDb`, leave through `moneyToDb`.
- **Scale:** 2 for amounts. Rates are scaled amounts (8.25% = `{ amount: 825, scale: 4 }`),
  defined in config — never float literals.
- **Rounding mode:** [DECIDE — ask whoever owns the books: halfEven (banker's; unbiased, .NET
  default) or halfAwayFromZero (matches SQL Server ROUND; everyday "normal rounding").
  Every layer defaults differently — see the table in reference/v2-changes.md — so exactly
  one written choice is what matters. No opinion → halfEven.]
- **Rounding boundaries:** round ONLY when (a) persisting, (b) displaying, (c) finalizing an
  invoice/charge. Intermediates stay exact. Every scale-reducing `transformScale` passes the
  mode above explicitly.
- **Tax rounding level:** [DECIDE — jurisdiction/accounting question; ask whoever files the
  taxes: per-invoice (sum exact line taxes, round once) or per-line (round each line's tax,
  sum the rounded values). They differ by real cents: two lines of exact tax $0.575 →
  $1.16 per-line vs $1.15 per-invoice. Both are "correct" somewhere; consistency is the law.]
- **Splits/proration:** `allocate()` only — parts must sum exactly to the whole.
- **SQL boundary:** SQL may `SUM()` amounts that already exist in rows (results re-enter via
  `moneyFromDb`). SQL never derives amounts: no `price * quantity`, no tax, no discounts in
  queries.
- **Arithmetic location:** all business math in app code (testability); the SQL boundary line
  above is the single exception.
```
