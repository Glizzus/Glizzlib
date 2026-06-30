---
name: primevue-preset-skill
description: Use when adding or changing a style in a PrimeVue theme preset via definePreset — e.g. "make the Card darker", "change the primary color", "round the Button corners", "tweak InputText focus ring". Edits the correct design-token tier inside the definePreset config, using verified token names and type-check to keep the change valid.
---

# PrimeVue Preset Editor (definePreset only)

Make a focused, correct change to a PrimeVue (v4 / `@primeuix/themes`) theme preset using **`definePreset`** — the static, app-wide customization API. This skill is deliberately scoped to `definePreset`; it does not handle runtime theme swaps (`updatePreset` / `usePreset`) or per-instance overrides (`dt` prop). If the user asks for those, say so and stop.

`definePreset` edits fail in two predictable ways: editing the **wrong token tier**, and using **token names that don't resolve**. The tier you handle yourself.

For bad token names, know exactly what the gate does and does not catch. `@primeuix/themes` ships TypeScript types, so type-check (Step 3) catches a wrong **token-object key** — e.g. `card.colorScheme.light.root.backgroundd`. But a token **reference target inside `{...}`** (e.g. `background: '{surface.7000}'`) is just a `string` to TypeScript: a typo there compiles cleanly and silently renders an unresolved/empty CSS variable. So `{...}` reference paths must be verified by hand in Step 1 — type-check will not save you.

## The model you must hold

PrimeVue styled mode = **3 tiers of design tokens**. Tokens reference each other with `{curly.brace}` syntax.

| Tier | Meaning | Example | Edit it when… |
|------|---------|---------|---------------|
| `primitive` | raw palette, no meaning | `{blue.500}`, `{zinc.900}` | you're adding/altering the raw color scale |
| `semantic` | role-based, maps to primitives | `{primary.color}`, `{surface.0}` | you're changing a *theme-wide* role (primary color, surface scale) |
| `components` | per-component, maps to semantic | `button.background`, `card.color` | you're styling **one component** (the common case) |

**Rule of thumb:** "style this component" → edit `components.<name>`. "recolor the whole app" → edit `semantic`. Touch `primitive` only to introduce a new raw scale. Picking the right tier is the one judgment call this skill asks of you — get it right and the rest is mechanical.

See `reference/token-tiers.md` for the full reference-syntax rules (light/dark color schemes, raw values vs `{...}` references).

## How `definePreset` works

```javascript
import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

const MyPreset = definePreset(Aura, {
  // only these top-level keys: primitive, semantic, components
});
```

First arg is the base preset (`Aura`, `Material`, `Lara`, or `Nora`); second is the token overrides to merge in. It is wired into the app via the PrimeVue config `theme: { preset: MyPreset }`.

## Step 1 — Get authoritative token names (do not guess)

Token names are the #1 source of broken presets. Resolve them, in this order:

1. **If a PrimeVue MCP server is connected** (`@primevue/mcp`), call its tools:
   - `get_component_tokens <component>` — exact token keys for the component
   - `get_theming_guide` — current styled-mode rules
   - `search_all` / `get_component` — discovery
2. **Else, read the existing preset/config file** in the project (search for `definePreset`, `@primeuix/themes`, or `theme:`) and reuse the token names already present there.

Don't invent token keys, and verify every `{...}` reference path against one of these sources before using it — those reference targets are *not* checked by type-check (see above), so an unverified one fails silently at runtime.

## Step 2 — Edit the `definePreset` call

Make the change directly in the PrimeVue config. Merge your token overrides into the existing `definePreset(<base>, { ... })` call, creating the call and the `theme: { preset: ... }` wiring if they don't exist yet. Keep the edit minimal — only the tokens you're changing. Show the user the diff.

Use `{token.path}` references rather than raw CSS values wherever possible, so the change stays consistent across light/dark and palette changes.

## Step 3 — Type-check (the gate)

Run the project's TypeScript check — this is what actually proves the token names and value shapes are valid:

```bash
npm run type-check   # or: npx vue-tsc --noEmit  /  npx tsc --noEmit  /  the project's configured script
```

Prefer the project's existing script (check `package.json`). **If type-check reports an error pointing at your preset change, a token name or value shape is wrong — fix it and re-run until clean.** Then run lint/build if the project has them.

## Worked examples

See `reference/examples.md` for canonical `definePreset` edits (component styling, theme-wide primary color, non-color tokens, new primitive scale). When unsure, mimic the closest example exactly.
F