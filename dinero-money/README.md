# dinero-money

A host-agnostic [Agent Skill](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/) that teaches an AI coding agent to write correct **money-handling code**: dinero.js v2 (stable, ≥ 2.0.2), USD, amounts stored in SQL `decimal(p,2)` columns that the ORM reads/writes as strings.

It exists because money bugs are almost entirely **compiles-but-wrong** — `subtotal * 1.0825`, `Number(row.total)`, rounding each line before summing, `total / 3` — all valid TypeScript, all silently losing cents. Models *know* float hazards when asked; they stop applying that knowledge mid-task. On top of that, two seams are genuinely undertrained:

- **dinero.js v2 went stable in March 2026** and consolidated all `@dinero.js/*` scoped packages into one — alpha-era imports and v1's chainable API (both dominating training data) no longer exist. Caught by type-check.
- **The ORM boundary**: decimal columns arrive as strings, and the reflexive `Number()` "fix" reintroduces IEEE-754 exactly where the discipline mattered (`Number('19.99') * 100 === 1998.9999999999998`). Not caught by anything except write-time rules.

Unlike a pure-library skill, this one splits ownership: **universal money correctness lives in the skill; project policy lives in the project.** The skill refuses to invent rounding policy — it reads a Money-policy block from the host project's `AGENTS.md` (template included) and stops to ask when a decision is missing.

## Contents

```
dinero-money/
├── SKILL.md                      # the skill: money model + hard bans + 3-step procedure
└── reference/
    ├── v2-changes.md             # v1/alpha → stable 2.0.2 decoder, rounding-defaults table, error decoder
    ├── examples.md               # 7 canonical shapes (money module, tax, allocate, ORM boundary, invoice)
    └── policy-template.md        # the AGENTS.md Money-policy block to copy and fill in
```

## How it works

1. **Hold the money model** — an amount is an integer count of minor units + currency + scale; JS operators never touch it; `multiply` is exact (scale grows); rounding is one deliberate `transformScale(d, 2, halfEven)` at a boundary; splits `allocate()`.
2. **One boundary module** — `moneyFromDb`/`moneyToDb` in `src/lib/money.ts` are the only door between decimal strings and `Money`; the parser is string-surgery (no float ever), the serializer refuses unrounded scale.
3. **Policy is external** — rounding mode and tax-rounding level come from the project's AGENTS.md policy block; missing policy is a stop-and-ask, not a guess.
4. **Hard bans** — native arithmetic on amounts, `Number()` on decimal strings, `toFixed`, division, bare `transformScale` (it truncates!), v1/alpha API shapes, deriving amounts in SQL.
5. **Type-check as the gate** — catches API shapes and (thanks to stable v2's literal-typed currencies, `Dinero<number, 'USD'>`) cross-currency mixing at compile time; with an explicit list of what it does *not* catch, enforced at write time instead.

Every identifier and behavior was verified against an installed `dinero.js@2.0.2` (signatures, `transformScale`'s truncating default, `allocate` remainder order, `toDecimal` padding/sign, throw messages), and all example shapes compile under strict `tsc`. The dinero maintainers also publish official skills (`npx skills add dinerojs/skills`) — this one is narrower and stack-specific: USD-only policy discipline plus the decimal-string ORM boundary.

## Install

`SKILL.md` is the open agent-skills format, read by Claude Code, GitHub Copilot, Cursor, Codex CLI, and others. Drop the folder into a skills directory — no per-host adapter needed.

**Project-scoped** (committed to a repo, works in any supported agent):
```bash
mkdir -p .agents/skills            # also recognized: .claude/skills, .github/skills
cp -r dinero-money .agents/skills/
```

**Personal / global:**
- Claude Code: `~/.claude/skills/dinero-money/`
- GitHub Copilot: `~/.copilot/skills/` or `~/.agents/skills/`

Then copy `reference/policy-template.md`'s block into the project's `AGENTS.md` and resolve the `[DECIDE]` lines.

## Scope

Handles: constructing/parsing/persisting USD amounts, arithmetic, percentages and tax, rounding policy, splits/proration, comparisons, formatting, the Drizzle/decimal-string boundary, SQL aggregation rules. **Out of scope** (the skill will say so and stop): dinero.js 1.x or 2.0.0-alpha codebases (migrate first), float money columns (migrate first), multi-currency (escalate — the policy forbids improvising it).
