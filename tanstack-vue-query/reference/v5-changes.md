# v5 API decoder — stale v4 / React habits → correct v5 Vue

Training data is dominated by React Query and TanStack Query v4. This table maps every stale shape to the current one. When type-check flags your vue-query code, the fix is almost always in this file.

## Import & registration

| Stale / wrong | Correct v5 Vue |
|---|---|
| `import { useQuery } from '@tanstack/react-query'` or `'react-query'` | `import { useQuery } from '@tanstack/vue-query'` |
| `<QueryClientProvider client={queryClient}>` (React JSX) | `app.use(VueQueryPlugin)` in the app entry |
| `app.use(VueQueryPlugin)` with no config, but defaults wanted | `app.use(VueQueryPlugin, { queryClientConfig: { defaultOptions: { queries: { staleTime: 30_000 } } } })` |

## Call signatures

| Stale (v4) | Correct v5 |
|---|---|
| `useQuery(['todos'], fetchTodos, { staleTime })` | `useQuery({ queryKey: ['todos'], queryFn: fetchTodos, staleTime })` — single object, everywhere |
| `useMutation(updateTodo, { onSuccess })` | `useMutation({ mutationFn: updateTodo, onSuccess })` |
| `queryClient.invalidateQueries(['todos'])` | `queryClient.invalidateQueries({ queryKey: ['todos'] })` |
| `queryClient.getQueryData(key, filters)` | `queryClient.getQueryData(queryKey)` — key only |
| `const { remove } = useQuery(...)` then `remove()` | `queryClient.removeQueries({ queryKey })` |
| `hashQueryKey(key)` | `hashKey(key)` |

## Renamed / removed options

| Stale (v4) | Correct v5 |
|---|---|
| `cacheTime` | `gcTime` |
| `isLoading` (meaning "first load"), `status === 'loading'` | `isPending`, `status === 'pending'` (v5 `isLoading` = `isPending && isFetching`) |
| `keepPreviousData: true`, `isPreviousData` | `placeholderData: keepPreviousData` (import the function from `@tanstack/vue-query`), `isPlaceholderData` |
| `useErrorBoundary` | `throwOnError` |
| `onSuccess` / `onError` / `onSettled` on **useQuery** | **Removed.** `watch` the returned `data`/`error` refs, or set global `QueryCache` callbacks. Still valid on **useMutation** and per-`mutate` call. |
| `useQuery({ suspense: true })` / `useSuspenseQuery` | No `useSuspenseQuery` in vue-query. Experimental: `const { data, suspense } = useQuery(...)` then `await suspense()` in `async setup()` under `<Suspense>`. |
| `useInfiniteQuery` without `initialPageParam` | `initialPageParam` is **required**; `fetchNextPage(pageParam)` no longer accepts a page param override |
| `useQueries` returning a `reactive` object (vue-query v4) | returns a `ref` in v5 |

## Error-message decoder

| Runtime error | Cause | Fix |
|---|---|---|
| `vue-query hooks can only be used inside setup() function or functions that support injection context` | `useQuery`/`useMutation`/`useQueryClient` called in an event handler, `watch`, lifecycle hook, or after the first `await` in `async setup()` | Move the call to the top of `<script setup>` (before any `await`). In handlers, use a `queryClient` captured in setup, or `queryClient.fetchQuery`/`ensureQueryData`. |
| `No 'queryClient' found in Vue context, use 'VueQueryPlugin'` | `app.use(VueQueryPlugin)` missing — including in Vitest component tests | Register the plugin in the app entry; in tests add `VueQueryPlugin` to `config.global.plugins` / `mount(..., { global: { plugins: [[VueQueryPlugin]] } })`. |
| Query fetches once but never refetches when a prop/ref changes | Plain value in `queryKey`, or value unwrapped at the composable boundary (`useTodo(props.id)`) | Pass a ref/getter into the key raw; composable params typed `MaybeRefOrGetter<T>`; unwrap with `toValue()` only in `queryFn`. Not a type error — must be caught by reading the code. |
| Dependent query never starts | `enabled: !!x.value` evaluated once at setup | `enabled: () => !!toValue(x)` (getter) or a `computed` |
| `isError` never true although the API returns 4xx/5xx | `fetch()` resolves on HTTP errors | `if (!res.ok) throw new Error(...)` in `queryFn` |
| UI stale after a mutation succeeds | No invalidation | `queryClient.invalidateQueries({ queryKey: [...] })` in the mutation's `onSuccess` (client captured in setup) |

## `queryOptions()` and reactivity

`queryOptions()` (and `infiniteQueryOptions`, `mutationOptions`) exist in vue-query and are the right tool for sharing key+fn between `useQuery`, `prefetchQuery`, `setQueryData`, etc. Keep the factory **pure** (plain unwrapped params, plain return). To combine with reactivity, wrap the whole options object in `computed` at the call site:

```ts
const todoOptions = (id: string) => queryOptions({
  queryKey: ['todos', id],
  queryFn: () => fetchTodo(id),
})

useQuery(computed(() => ({ ...todoOptions(toValue(id)), staleTime: 5_000 })))
```

Some patch versions have had type regressions around refs inside `queryOptions` — if type-check rejects a ref in a `queryOptions` key, use the pure-factory + `computed`-wrapper pattern above instead of fighting the types.

## `queryFn` context: already unwrapped

Refs inside `queryKey` are deep-unwrapped by vue-query before your `queryFn` sees them. So:

```ts
queryFn: ({ queryKey: [, id] }) => fetchTodo(id)   // id is a PLAIN value — no toValue()
```

Reading params from the context key (instead of closing over refs) is the most robust pattern — it can't go stale between an invalidation and the fetch.
