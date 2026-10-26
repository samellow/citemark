---
version: 1
slug: "src-citemark-web-templates-demo-html"
primary_target: "src/citemark/web/templates/demo.html"
related_targets: ["src/citemark/web/templates/demo_parts.html","src/citemark/web/templates/ask.html","static/demo.css","static/demo.js"]
---

# Demo page

## Scope and mode

The public demo page (PRD 8.2): `/`, served by `web/page.py` and `templates/demo.html`, `demo_parts.html`, `ask.html`, `static/demo.css`, `static/demo.js`. Mode: Persuade. Redesign of composition inside the established Citemark world (design system 03, `design/tokens.json`); the report, widget and admin are out of scope.

## Audience, job, action

A non-technical founder or head of support arriving from an Upwork listing, afraid a bot will make things up. In seconds they must see it cite a real passage and refuse what the docs don't cover, then try it, then open the report or the audit offer. Proof: the two recorded turns, the three suggested questions, the five measure counts, all from the published run. Constraints: the unofficial-demo label stays first; nothing claims a test before a run is published; every word comes from the strings files; works as a plain form without JavaScript; no inline style or script; WCAG 2.2 AA in both themes.

## Direction contract

THESIS: The headline's two halves become two working exhibits, a cited answer under "shows its source" and an honest decline under "says it doesn't know". Refuses the category default of a headline beside a chat box, and the trace-first log that buried the answer last.

OWN-WORLD: Citemark's inspection-certificate world as built: IBM Plex Sans Condensed headings, Plex Sans body, Plex Mono counts; verification-ink blue only on markers, links and the primary action; state colors only with glyph and word; white bordered panels on the cool ground; the ¹ marker as the signature, filled ink when its quote is open.

STORY: The visitor reads the claim, sees both halves proven by real recorded turns, tries one suggested question of each kind (answers, doesn't cover, asks which one), reads the counts with their targets, then takes the audit offer or opens the report.

FIRST VIEWPORT: Label bar; subhead line; the headline set at about 61px, split across two columns, second half muted; under each half its panel: left the recorded answer with source 1's quote open, right the recorded decline with where it looked. On a phone the halves and panels stack. The question box opens the next section.

FORM: Two promises, side by side, position 4 of 7 on the ordered list, seed key 7825e781.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Memorable moment

A marker's quote opening in place under the answer, its sentence highlighted, while the decline beside it shows the articles it read and still said no.

## Unresolved

- The 61px headline is outside the token scale (39px max); kept local to demo.css until a system change is approved.
- Before a run is published the page keeps today's rule: no panels, suggestions, counts or offer. Showing suggestions without a run is a content-rule change the user hasn't decided.
- System follow-up, not patched here: the shared StateMark primitive `.cm-state` (static/citemark.css, also used by the report) has 2px vertical padding against its tint; the design detector flags it as cramped. A change belongs to the design system and the report, not this surface.
- Limits: the day's cap closes the box until tomorrow; the hour's limit rests Send, the suggestions and the options for the minutes it names, and demo.js opens them again when they lapse.
