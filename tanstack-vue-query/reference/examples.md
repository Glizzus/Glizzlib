# Worked examples — @tanstack/vue-query v5

Each example is the canonical shape for a common task. Mimic the closest one exactly; every deviation from these shapes is a place a bug hides. All imports come from `@tanstack/vue-query` and `vue`.

---

## 0. Wiring the plugin (once, in the app entry)

```ts
// main.ts
import { VueQueryPlugin } from '@tanstack/vue-query'

app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: { queries: { staleTime: 30_000 } }, // optional
  },
})
```

---

## 1. Basic query in a component

The return is an object of refs — destructure freely, `.value` in script, bare names in the template.

```vue
<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'

const { data, isPending, isError, error } = useQuery({
  queryKey: ['todos'],
  queryFn: fetchTodos,
})
</script>

<template>
  <span v-if="isPending">Loading…</span>
  <span v-else-if="isError">{{ error?.message }}</span>
  <ul v-else>
    <li v-for="todo in data" :key="todo.id">{{ todo.title }}</li>
  </ul>
</template>
```

If the fetcher uses `fetch`, it must throw — `fetch` resolves on 404/500, and without this `isError` never fires (axios throws by itself):

```ts
queryFn: async () => {
  const res = await fetch(`/api/todos`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<Todo[]>
}
```

---

## 2. Query keyed on a prop (refetch when it changes)

The single most common bug is freezing `props.id` into the key. The getter goes in **raw**; the query refetches (and caches per-id) automatically when the prop changes.

```vue
<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'

const props = defineProps<{ id: string }>()

const { data, isPending } = useQuery({
  queryKey: ['todos', () => props.id],                 // getter, NOT props.id
  queryFn: ({ queryKey: [, id] }) => fetchTodo(id),    // context key: already plain
})
</script>
```

No `watch`, no `refetch()` call — the reactive key does all of it.

---

## 3. Reusable query composable (the blessed pattern)

```ts
// composables/useTodo.ts
import { useQuery } from '@tanstack/vue-query'
import { toValue, type MaybeRefOrGetter } from 'vue'

export function useTodo(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: ['todos', id],                  // ref/getter goes in RAW
    queryFn: () => fetchTodo(toValue(id)),    // unwrap ONLY here
  })
}
```

```ts
// call sites — all stay reactive:
useTodo('static-id')
useTodo(selectedId)          // a ref
useTodo(() => props.id)      // a getter (preferred over computed(() => props.id))
```

Never `useTodo(props.id)` or `useTodo(selectedId.value)` — that freezes the value forever.

---

## 4. Dependent query (`enabled`)

`enabled` must be a getter/computed/ref — a plain boolean is evaluated once and never turns the query on.

```ts
const userId = ref<string>()

const { data: projects } = useQuery({
  queryKey: ['projects', userId],
  queryFn: () => fetchProjects(userId.value!),
  enabled: () => !!userId.value,          // getter — never `!!userId.value`
})
```

---

## 5. Mutation + invalidation (the complete write path)

`useMutation` and `useQueryClient` are called **in setup**; the handler only calls `mutate`. v5 removed query callbacks, but mutation callbacks are alive and are where invalidation belongs.

```vue
<script setup lang="ts">
import { useMutation, useQueryClient } from '@tanstack/vue-query'

const queryClient = useQueryClient()        // setup, NOT inside the handler

const { mutate: addTodo, isPending: isSaving } = useMutation({
  mutationFn: (newTodo: NewTodo) => postTodo(newTodo),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] })  // every affected list/detail
  },
})
</script>

<template>
  <button :disabled="isSaving" @click="addTodo({ title: 'x' })">Add</button>
</template>
```

`mutate` is fire-and-forget (handle results via callbacks). If you need the promise, use `mutateAsync` **with** try/catch — it throws on error. Never `await mutate(...)`; it returns `undefined`.

---

## 6. Paginated query (keep old page visible)

```ts
import { useQuery, keepPreviousData } from '@tanstack/vue-query'

const page = ref(1)

const { data, isPlaceholderData } = useQuery({
  queryKey: ['todos', page],                      // page ref in the key — no refetch() needed
  queryFn: () => fetchTodoPage(page.value),
  placeholderData: keepPreviousData,              // v5 replacement for keepPreviousData: true
})
// next page: page.value++  — that's the whole pagination logic
```

Disable "Next" while `isPlaceholderData` is true if the last page is unknown.

---

## 7. Infinite query

`initialPageParam` is required in v5; the next param comes only from `getNextPageParam`.

```ts
import { useInfiniteQuery } from '@tanstack/vue-query'

const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
  queryKey: ['todos', 'infinite'],
  queryFn: ({ pageParam }) => fetchTodoPage(pageParam),
  initialPageParam: 1,                                        // REQUIRED
  getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined, // undefined = no more
})
// template: pages are data.pages — v-for="page in data?.pages"
// load more: fetchNextPage()  — never fetchNextPage(someParam)
```

---

## 8. Optimistic update (with rollback)

```ts
const queryClient = useQueryClient()

const { mutate: toggleTodo } = useMutation({
  mutationFn: (todo: Todo) => patchTodo(todo),
  onMutate: async (newTodo) => {
    await queryClient.cancelQueries({ queryKey: ['todos'] })      // don't let a refetch clobber us
    const previous = queryClient.getQueryData<Todo[]>(['todos'])
    queryClient.setQueryData<Todo[]>(['todos'], (old) =>
      old?.map((t) => (t.id === newTodo.id ? newTodo : t)),
    )
    return { previous }                                            // context for rollback
  },
  onError: (_err, _newTodo, context) => {
    queryClient.setQueryData(['todos'], context?.previous)         // roll back
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] })         // reconcile with server
  },
})
```

All three callbacks are required for a correct optimistic update: snapshot, rollback, reconcile.

---

## 9. Prefetching

In setup (e.g. warm a detail view the user will likely open):

```ts
import { usePrefetchQuery } from '@tanstack/vue-query'

usePrefetchQuery({ queryKey: ['todos', 1], queryFn: () => fetchTodo(1) })
```

Outside setup (event handler, router guard) use the client instance — the `use*` composables are setup-only:

```ts
queryClient.prefetchQuery({ queryKey: ['todos', id], queryFn: () => fetchTodo(id) })
```

---

## 10. Reacting to query results (v5 has no onSuccess on queries)

```ts
const { data } = useQuery({ queryKey: ['todos'], queryFn: fetchTodos })

watch(data, (todos) => {
  if (todos) selection.value = todos[0]?.id   // what v4's onSuccess used to do
})
```

Do not copy `data` into local state as a habit — render from `data` directly; `watch` is for genuine side effects only.
