# Design

The source of Citemark's look, and of its build status. Everything here is checked in CI.

- **`tokens.json`**: every color, type style, space, radius, shadow, layer, duration and size, in a light and a dark theme. `citemark design build` checks the 25 text and control pairs against WCAG AA in both themes, then writes `static/tokens.css`. CI fails if that file is out of date.
- **`components.yaml`**: all 67 components of the four surfaces (the report, the demo page, the widget and the admin page), with each one's renderer, phase, states and the strings it shows. A component is listed here before any code.
- **`fixtures/`**: the sample data for each state the kit renders. `citemark gallery` builds one page per component, state and theme from them, and CI runs axe on every page. The data is Zulip's public help center or the made-up Acme Chat, never a client's.
- **`glyphs/`**: the icons, each drawn on a 16px grid with a round 1.5 to 1.75px stroke in the text's color.

The tokens were seeded on 2026-10-09 from the Citemark design-system prototype (its `tokens.json`, SHA-256 `811e27cd3b05c7f8e3f26029e3d0423ce1d99d64d9e33162831de92235b1c332`), and the glyphs from its drawings. From then on, this folder is the source.

```
uv run citemark design build         # check the contrast pairs, write static/tokens.css
uv run citemark gallery              # build the gallery in build/gallery
cd e2e && npm ci && npx playwright install chromium && npx playwright test   # axe on every page
```
