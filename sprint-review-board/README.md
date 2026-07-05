# Sprint Review Board

Full-screen board shown at the start of sprint review. One Vue component, content
driven by YAML files in `yaml/` — the highest-numbered `sprint-<n>.yaml` is what
renders. Files are validated against `sprint.schema.json`.

## Each sprint

```sh
npm run new-sprint   # creates yaml/sprint-<next>.yaml from the template
```

Fill in `dates`, `agenda`, and `demos`, then:

```sh
npm run dev          # local preview
npm run build        # static build in dist/
```

On the board itself: press **F** (or the button, bottom right) for fullscreen.
The project/department logos are inline SVGs in `src/App.vue`.
