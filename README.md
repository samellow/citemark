# Citemark

A support bot for SaaS help centers that ships with proof it works: a test report, run on the client's own help center, showing how often the bot answers correctly, shows the right source, and says so when the help center doesn't cover a question. Each client runs their own copy in their own hosting account. MIT-licensed.

**Status: early.** The demo's 50 test questions were frozen on 2026-10-08, before any bot code exists, so the published results can't be fitted to them. The tag `zulip-v1-frozen` marks that commit. The bot can load a help center, keep it up to date, find the passages that answer a question, answer with sources or decline, and run its own test set, scored and judged, three times over when a decision rests on it. The report that publishes those results and the demo page that serves the bot are built; the decision runs that fill them come next.

## What's here so far

- `test-sets/zulip-v1.yaml`: the frozen questions, with their expected answers and sources
  - `zulip-v1.lock.json` holds the file's SHA-256, the date it was frozen, and the review counts.
  - `zulip-v1.draft.yaml` is the AI-assisted draft the questions were edited from, kept unchanged so the two can be compared.
  - `zulip-v1.review.md` records how they were reviewed.
- `citemark test check` and `citemark test freeze`: check a file of test questions against a saved copy of the help center, then freeze it
- `src/citemark/evals/` and `citemark test run`: ask the bot a frozen test set, then score and judge every reply.
  - It refuses a test set that changed after it was frozen.
  - It shows a cost estimate first, and stops before passing its budget. `citemark test resume` finishes a run that stopped, without asking any question twice.
  - Whether the bot looked in the right place, showed the right source and declined what it should is scored mechanically, so `citemark test rescore` gives the same scores every time. Claude Opus 5.5 judges the answers against a written rubric, `prompts/judge.v1.md`.
  - `--runs 3` makes a decision run: three runs of the same settings, from committed code, reported as each measure's median and range (`citemark test decision`). A model and its judge don't answer the same way twice, so decisions aren't made on one run. When the judge grades a question differently across the three, a person grades those answers, and that grade counts.
  - `citemark grade` checks the judge against a person. You grade the answers blind, seeing what the judge read but never its verdict. Once every answer is graded, the grades lock, and only then are the judge's verdicts shown: how often you agreed, and where you didn't. `--sample` re-checks the judge on 10 answers, picked the same way every time.
  - An abuse set (`kind: abuse`) tries to make the bot misbehave: invent a policy or a promise, obey instructions planted in a question or in an article, reveal its instructions, or repeat a customer's personal details. It's scored mechanically, never by the judge, and kept apart from the accuracy numbers. Inventing a policy and obeying planted instructions are a release gate: every such question must be resisted in all three runs of a decision run, and `citemark test decision` exits 1 until it is. The demo's abuse set is being drafted.
- `src/citemark/report/` and `citemark report build`: the accuracy report, one HTML file that opens offline, reads without JavaScript and prints in light.
  - It's built from decision runs only, and opens with pass, not pass or baseline against the pass mark agreed with the client (`citemark test threshold`), then the five measures, one question traced step by step, a fix plan, every question with its evidence, and how the test was done.
  - Numbers round against the bot, and a measure's state comes from its exact value, so a shown number never looks better than it was.
  - It refuses to build rather than claim what it can't show: without the frozen test set the runs used, the judge's agreement with a person's grading, an estimate for each group of failures, or who agreed the pass mark and when.
  - Every word is in `content/en/report.json`, and the gallery shows a sample report with made-up content.
- `src/citemark/web/` and `citemark serve`: the public demo page and its ask box, one FastAPI app with the job worker running inside it.
  - The unofficial-demo label sits at the top of every page. Until the decision runs are published (`DEMO_RESULTS`), the page leaves out everything that would say the bot was tested: the counts, the recorded exchange, the suggested questions and the report link.
  - Answers come from the same pipeline as the test runs, each shown as its evidence: where the bot looked, what it quoted, what it answered. The ask box works without JavaScript.
  - Each visitor may ask 10 questions an hour, counted in memory under a salted hash of their address, never stored. Behind a host's proxy, `CLIENT_IP_HEADER` names the header the proxy puts the address in (CF-Connecting-IP on Render). A daily spend cap, $1 unless `citemark demo spend-cap` sets another, stops answers for the rest of the day.
  - No cookies and no analytics scripts: page views, audit-button clicks (through `/go/audit`), suggested-question taps and report opens are counted per day and per pitch variant (`?v=`), never per person.
- `design/`, `static/` and `citemark gallery`: how the report, the demo page and later the widget and admin page look.
  - `design/tokens.json` holds every color, type style and size, in a light and a dark theme. `citemark design build` checks the 25 text and control color pairs against WCAG AA in both themes, then writes `static/tokens.css`.
  - `static/citemark.css` holds the base styles and the shared parts: the wordmark, citation markers, state marks (always a glyph and a word, never color alone), buttons and form fields. Fonts are IBM Plex, self-hosted, so no page asks Google for them.
  - `design/components.yaml` lists all 67 components of the four surfaces, with their states and the strings they show.
  - `citemark gallery` builds one page per component state, in both themes, and CI runs axe on every page (`e2e/`). It also opens the sample report with the network blocked and JavaScript off, and checks that it prints in light, whole, and within A4's width.
- `fixtures/zulip/`: the text of Zulip's help center, saved on 2026-10-06, used for the demo. The raw HTML is attached to the `zulip-v1-frozen` release.
- `scripts/snapshot.py`: how that copy was made. `scripts/verify_snapshot.py` checks what the extraction kept.
- `scripts/api_check.py`: checks what the bot assumes about the Claude and Voyage APIs, on each model, before anything is built on it. The results from 2026-10-08 are next to it.
- `src/citemark/jobs/` and `citemark jobs work`: background jobs that survive a restart (a job whose worker is killed finishes exactly once, and a test proves it), and the daily purge of conversations older than 90 days.
- `tests/recordings/`: real API replies the tests replay, so they're free and repeatable, and no test can reach the network. `uv run pytest <test> --record` records a test's replies again, which calls the real APIs.
- `src/citemark/db/`: the database (Postgres 16 with pgvector). The database itself refuses to change a frozen test set, and to edit or delete a passage, so an old citation always opens what it cited.
- `src/citemark/ingest/` and `citemark sources`: loading a help center from a sitemap, a start page or one address, or from uploaded PDF, Markdown and HTML files.
  - It keeps what a reader sees: tab labels ("Mobile:"), Note and Tip callouts, and every step. On Zulip's help center it gives the same text, byte for byte, that `scripts/verify_snapshot.py` checked.
  - Each section becomes a passage that starts with its headings and links to its anchor.
  - It's polite: robots.txt, at most 2 requests a second, and only the source's own pages. It never connects to a private or internal address, including after a redirect.
  - Re-indexing embeds only pages that changed, so an unchanged site costs nothing. A page that fails keeps its old passages, and a page only counts as removed after a crawl that reached every page.
- `src/citemark/embed/`: embeddings and reranking, with Voyage's `voyage-4` and `rerank-3` behind small interfaces.
- `src/citemark/retrieve/` and `citemark search "question"`: the passages the bot would be given for a question, with their scores.
  - The question is searched two ways, by meaning and by its words. The two lists are merged by reciprocal rank fusion, and a reranker picks the best 5.
  - A follow-up ("how do I turn that off?") is first rewritten to stand alone, using `prompts/rewrite.v1.md`.
  - Full-context mode gathers every passage instead, and is refused for a model whose window can't hold them.
  - The same passages always give the same results, so two test runs differ only in what changed.
- `src/citemark/answer/`, `src/citemark/models/` and `citemark ask "question" --company Zulip`: the bot's reply, with its sources and what it cost.
  - Claude cites the passages itself. Every quote under an answer is copied from the help center by the API, not written by the model.
  - The server decides what's shown. A decline, a clarifying question or small talk shows a fixed sentence, never the model's own words, and an answer with no source is shown as a decline.
  - The instructions are `prompts/answer.v1.md` and `prompts/tools.v1.json`. Every call is priced from a dated price table, so an old report keeps its old prices.

## Running it locally

You need [uv](https://docs.astral.sh/uv/) and Docker.

```
cp .env.example .env              # then add your API keys to .env
docker compose up -d db           # Postgres 16 with pgvector, on port 54320
uv run alembic upgrade head
gh release download zulip-v1-frozen -p raw.tar.gz -D fixtures/zulip && tar -xzf fixtures/zulip/raw.tar.gz -C fixtures/zulip
uv run pytest                     # the raw HTML above is what the extraction tests read
uv run citemark test check test-sets/zulip-v1.yaml --snapshot fixtures/zulip
```

To load Zulip's live help center (needs `VOYAGE_API_KEY`; embedding it costs an estimated cent at Voyage's list price):

```
uv run citemark sources add start-page https://zulip.com/help/ --selector .sl-markdown-content
uv run citemark sources index
uv run citemark test check test-sets/zulip-v1.yaml --snapshot fixtures/zulip --against-db
uv run citemark ask "Can I stop people from seeing when I'm typing?" --company Zulip   # also needs ANTHROPIC_API_KEY
```

An abuse set's planted article must never reach an accuracy run, so the abuse set runs in a copy of that database. Every run checks: an accuracy run refuses a database holding a planted article, and an abuse run refuses one without its own, as it was frozen.

```
docker compose exec db createdb -U citemark -T citemark citemark_abuse   # while nothing else is connected
export DATABASE_URL=postgresql://citemark:citemark@localhost:54320/citemark_abuse
uv run citemark sources upload test-sets/<the set's>.planted.md
uv run citemark test run test-sets/<the abuse set>.yaml --company Zulip --budget 1 --runs 3
```

To build a report, set the pass mark agreed with the client, then name what the report covers in a small YAML file (`src/citemark/report/inputs.py` describes it) and set `BUILDER_NAME` in `.env`. A report that names an abuse run reads it from `ABUSE_DATABASE_URL`. `reports/` is ignored by git, so a client's report never lands in this public repository.

```
uv run citemark test threshold test-sets/<the set>.yaml --agreed-by "<their name>" --on 2026-10-20 \
  --targets correct_answers=90,right_source=90,correct_declines=95,wrongly_declined=5,right_place=95
uv run citemark report build reports/<client>.yaml --out reports/<client>.html
```

To serve the demo page, set `DEMO_COMPANY`, `BUILDER_NAME`, `DEMO_AUDIT_URL` and both API keys in `.env`. Its answers call Claude and Voyage, within the limits above.

```
uv run citemark serve              # http://127.0.0.1:8000; a host passes --host 0.0.0.0 and sets PORT
uv run citemark demo spend-cap     # the cap and today's spend; add an amount, such as 2.00, to change it
```

## Licenses

The code is MIT (see `LICENSE`). The demo uses Zulip's open-source help center under the Apache License 2.0; see `NOTICE`. This is an unofficial demo, not affiliated with Zulip.
