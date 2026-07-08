---
name: tanstack-vue-query
description: Use when writing or fixing server-state code with TanStack Query in a Vue 3 app (@tanstack/vue-query) — e.g. "fetch this list with vue-query", "add a mutation", "the query doesn't refetch when the id changes", "invalidate after saving", "paginate / infinite scroll this", "make this update optimistic". Enforces the v5 API and Vue reactivity rules (refs/getters in queryKey, toValue only in queryFn), then gates with type-check.
---

# TanStack Query for Vue 3 (v5 only)

Write **@tanstack/vue-query v5** code with the Vue 3 Composition API: queries, mutations, invalidation, and the advanced patterns (pagination, infinite queries, optimistic updates, prefetching). Deliberately scoped to **v5 + Vue 3** — if the project has v4, uses React Query, or the task is Nuxt/SSR hydration, say so and stop.

vue-query code fails in two predictable ways: **stale v4/React API shapes**, which the type-check gate catches; and **broken reactivity** — a plain value where a ref/getter belongs — which **compiles cleanly and silently never refetches**. Only the write-time rules below catch the second class.

## The model you must hold

`<script setup>` runs **once**. React re-runs the component function on every render, so plain values in a hook stay fresh; Vue does not. Anything that can change must cross the `useQuery`/`useMutation` boundary as a **ref, computed, or getter function** — never as an unwrapped value.

Three rules, one per direction:

| Direction | Rule | Wrong | Right |
|---|---|---|---|
| **IN** | Reactive inputs go into `queryKey` / `enabled` **raw** — a ref, or a getter `() => …`. Never unwrap in the key. | `queryKey: ['todo', props.id]` <br> `queryKey: ['todo', id.value]` <br> `enabled: !!id.value` | `queryKey: ['todo', () => props.id]` <br> `queryKey: ['todo', id]` <br> `enabled: () => !!toValue(id)` |
| **UNWRAP** | Unwrap **only inside `queryFn`**, with `toValue()`. | `queryFn: () => fetchTodo(id)` (passes a ref to the API) | `queryFn: () => fetchTodo(toValue(id))` |
| **OUT** | The return is an **object of refs**. Destructuring is safe and idiomatic. `.value` in script; **no** `.value` in templates (refs auto-unwrap). | `data.map(...)` in script <br> `{{ data.value }}` in template | `data.value?.map(...)` in script <br> `{{ data }}` in template |

## Compiles but wrong — the gate cannot catch these

1. **Every variable `queryFn` reads must be in the key.** The key is the cache identity *and* the refetch trigger; a missing dependency means stale cache collisions and no refetch.
2. **Composables take `MaybeRefOrGetter<T>`** — passed into the key raw, unwrapped with `toValue()` only in `queryFn`. Callers pass `() => props.id`, a ref, or a constant — never `props.id` or `x.value` (that freezes the value forever). Prefer getters over `computed()` for pass-through values.
3. **`queryFn` must throw on failure.** `fetch()` resolves on 404/500 — without `if (!res.ok) throw ...`, `isError` never fires. (axios throws by itself.)
4. **Every mutation invalidates.** Capture `const queryClient = useQueryClient()` in setup; in the mutation's `onSuccess`, invalidate every list/detail the write affects (or `setQueryData` explicitly). Otherwise the UI goes stale.
5. **`mutate` is fire-and-forget** (results via callbacks); `mutateAsync` returns a promise that **throws** — only with try/catch. Never `await mutate(...)` — it returns `undefined`.
6. **`data` is immutable.** Never `v-model` onto query results or mutate them — clone into local state first.
7. **`staleTime` controls refetching; `gcTime` controls memory.** To refetch more, lower `staleTime`; `gcTime: 0` is almost never the right tool.

## Never write (stale shapes — the gate catches these; fix from the decoder)

- `import ... from '@tanstack/react-query'` or `'react-query'` — the only source is **`@tanstack/vue-query`**
- `useQuery(key, fn, options)` positional arguments — v5 is **single options object only** (same for `useMutation`, `invalidateQueries`, …)
- `onSuccess` / `onError` / `onSettled` on **`useQuery`** — removed in v5 (`watch` the returned refs). Still valid on **`useMutation`** — that's where invalidation lives.
- `isLoading` for first-load state → **`isPending`**; `status === 'loading'` → `'pending'`
- `cacheTime` → **`gcTime`**; `useErrorBoundary` → **`throwOnError`**; `keepPreviousData: true` → **`placeholderData: keepPreviousData`** (imported function)
- `useSuspenseQuery` — does not exist in vue-query
- `refetch(params)` — `refetch` takes no arguments; put the changing param in the reactive key and the fetch happens by itself
- `useQuery` / `useMutation` / `useQueryClient` outside setup — not in event handlers, `watch`, lifecycle hooks, or after the first `await` in `async setup()`. Call at the top of `<script setup>`; use the captured `queryClient` inside handlers. (Fails at runtime, far from the cause.)

Full v4→v5 table and error-message decoder: `reference/v5-changes.md`.

## Step 1 — Verify version and wiring (do not assume)

1. `package.json`: require `@tanstack/vue-query` **^5**. v4 or missing → say so and stop (offer to install v5).
2. Confirm `app.use(VueQueryPlugin)` in the app entry; add it if missing — nothing works without it, and the runtime error appears far from the cause.
3. Reuse the project's conventions: existing `useQuery` composables, `queryOptions()` usage, key structure, file layout.

## Step 2 — Write from the canonical shapes

Mimic the closest example in `reference/examples.md` — component query, reactive-props query, composable, dependent query, mutation + invalidation, pagination, infinite query, optimistic update, prefetch. The blessed composable shape, memorize it:

```ts
import { useQuery } from '@tanstack/vue-query'
import { toValue, type MaybeRefOrGetter } from 'vue'

export function useTodo(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: ['todos', id],                 // ref/getter goes in RAW
    queryFn: () => fetchTodo(toValue(id)),   // unwrap ONLY here
    enabled: () => !!toValue(id),            // getter, never a plain boolean
  })
}
// callers: useTodo('1') · useTodo(userId /* ref */) · useTodo(() => props.id)
```

## Step 3 — Type-check (the gate)

```bash
npm run type-check   # or: npx vue-tsc --noEmit
```

If it errors on your change, an option name or call shape is stale v4/React — fix from `reference/v5-changes.md` and re-run until clean. Then re-read your diff against the IN/UNWRAP/OUT table and the **Compiles but wrong** list — those compile fine, refetch never, and no error will remind you.
