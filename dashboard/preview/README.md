# dashboard/preview — see the page without the app

The settings page is a plugin bundle: it renders nothing until the host injects the SDK globals and
answers `GET /api/plugins/hermes-viz/settings`. This folder reproduces both, so the *real*
`dashboard/dist/index.js` can be rendered and screenshotted at chosen widths — the acceptance for a
round that changes how the page looks.

```bash
HERMES_HOME=~/.hermes/hermes-agent node dashboard/preview/build.mjs   # writes .build/preview.html
```

Then open `.build/preview.html` in a browser at 1400px and at 500px.

| File | What it is |
|---|---|
| `build.mjs` | bundles the harness with React from the local Hermes install, writes the API fixture, copies the app stylesheet, emits `preview.html` |
| `app.mjs` | the host stand-ins: SDK globals, minimal components carrying the page's roles and classes, a stub `fetchJSON` |
| `fixture.py` | prints the real `GET /settings` payload by importing `plugin_api.py` with a small stub for fastapi/pydantic/the settings reader |
| `settings-1400.png`, `settings-500.png` | the committed screenshots |

`.build/` is git-ignored. The components in `app.mjs` are stand-ins — the host's real ones live in an
un-published design system — so treat the screenshots as evidence of *layout, hierarchy and overflow*,
not of pixel-exact component chrome. The stylesheet, the page and the API payload are real.
