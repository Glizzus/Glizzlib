# Worked `definePreset` examples

Each example shows the source edit for a common change. Mimic the closest one. All assume the base preset is `Aura` — swap in the project's actual base.

```javascript
import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';
```

---

## 1. Style one component (most common): make Card darker

Component styling lives in `components.<name>`. Color values that differ light/dark go under `colorScheme`.

```javascript
const MyPreset = definePreset(Aura, {
  components: {
    card: {
      colorScheme: {
        light: { root: { background: '{surface.100}', color: '{surface.700}' } },
        dark:  { root: { background: '{surface.950}', color: '{surface.0}' } }
      }
    }
  }
});
```

---

## 2. Theme-wide change: switch primary color to indigo

Recoloring the whole app edits the **semantic** tier, not a component.

```javascript
const MyPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '{indigo.50}', 100: '{indigo.100}', 200: '{indigo.200}',
      300: '{indigo.300}', 400: '{indigo.400}', 500: '{indigo.500}',
      600: '{indigo.600}', 700: '{indigo.700}', 800: '{indigo.800}',
      900: '{indigo.900}', 950: '{indigo.950}'
    }
  }
});
```

---

## 3. Non-color component token: round Button corners

Size/radius tokens sit directly on the component, **outside** `colorScheme`.

```javascript
const MyPreset = definePreset(Aura, {
  components: {
    button: { root: { borderRadius: '0.75rem' } }
  }
});
```

---

## 4. New raw scale: add a custom primitive palette

Touch `primitive` only when introducing raw values, then reference them from the semantic/component tiers. Raw hex values bypass the palette — use them deliberately.

```javascript
const MyPreset = definePreset(Aura, {
  primitive: {
    brand: { 500: '#6d28d9', 600: '#5b21b6' }
  },
  semantic: {
    colorScheme: {
      light: { primary: { color: '{brand.500}', hoverColor: '{brand.600}' } },
      dark:  { primary: { color: '{brand.500}', hoverColor: '{brand.600}' } }
    }
  }
});
```

---

## Wiring the preset into the app

```javascript
import PrimeVue from 'primevue/config';

app.use(PrimeVue, {
  theme: { preset: MyPreset }
});
```
