# Design tokens & reference syntax

PrimeVue styled mode resolves a theme from **design tokens** organized in three tiers. A `definePreset` override object may only contain these three top-level keys:

- `primitive` — raw, context-free values. The color palettes live here (`blue.50`…`blue.950`, `zinc`, `emerald`, etc.), plus things like `borderRadius`. No semantic meaning.
- `semantic` — role-based tokens that **map to primitives**. Examples: `primary.color`, `primary.contrastColor`, the `surface` scale (`surface.0`…`surface.950`), `formField.*`, `focusRing.*`. This is what most theme-wide changes touch.
- `components` — per-component tokens that **map to semantic** tokens. Examples: `button.background`, `card.colorScheme.light.root.background`, `inputtext.color`.

## Reference syntax

A token *value* can be:

- **A reference to another token**, written in curly braces: `"{surface.0}"`, `"{primary.color}"`, `"{blue.500}"`. The dotted path inside the braces points into the token tree. Prefer references — they keep the theme cohesive across light/dark and palette changes.
- **A raw CSS value**: `"#0f172a"`, `"0.5rem"`, `"8px"`, `"1px solid {surface.200}"`. Allowed, but a bare value bypasses the palette — use it deliberately.

A string that *looks* like a token path but is missing braces (e.g. `"surface.0"`) is almost always a bug: it ships the literal text `surface.0` as the CSS value instead of resolving the token.

## Light / dark color schemes

Color values that differ between light and dark mode go under a `colorScheme` block with `light` and `dark` children:

```json
"card": {
  "colorScheme": {
    "light": { "root": { "background": "{surface.0}",   "color": "{surface.700}" } },
    "dark":  { "root": { "background": "{surface.900}", "color": "{surface.0}"   } }
  }
}
```

Non-color tokens (sizes, radii, font weights) that are the same in both modes sit directly on the component, outside `colorScheme`:

```json
"button": { "root": { "borderRadius": "{borderRadius.lg}", "paddingX": "1rem" } }
```

## Common semantic roots (subset)

`primary.*`, `surface.0`–`surface.950`, `formField.*`, `focusRing.*`, `content.*`, `text.*`, `overlay.*`, `list.*`, `navigation.*`, `disabledOpacity`, `maskBackground`, `borderRadius`, `transitionDuration`.

## Common primitive palettes (subset)

`emerald green lime red orange amber yellow teal cyan sky blue indigo violet purple fuchsia pink rose slate gray zinc neutral stone` — each with steps `50 100 200 300 400 500 600 700 800 900 950`. Plus `black`, `white`, `borderRadius.*`.

These lists are a memory aid, not authoritative. When an MCP server is available, prefer its `get_component_tokens` output; otherwise reuse names from the project's existing preset. Either way, the project's type-check is the final word on whether a token name resolves.
