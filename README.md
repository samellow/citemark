# Citemark

A support bot for SaaS help centers that ships with proof it works: a test report, run on the client's own help center, showing how often the bot answers correctly, shows the right source, and says so when the help center doesn't cover a question. Each client runs their own copy in their own hosting account. MIT-licensed.

**Status: early.** The demo's 50 test questions were frozen on 2026-10-08, before any bot code exists, so the published results can't be fitted to them. The tag `zulip-v1-frozen` marks that commit. The bot can load a help center and keep it up to date, but it can't answer questions yet.

## What's here so far

- `test-sets/zulip-v1.yaml`: the frozen questions, with their expected answers and sources
  - `zulip-v1.lock.json` holds the file's SHA-256, the date it was frozen, and the review counts.
  - `zulip-v1.draft.yaml` is the AI-assisted draft the questions were edited from, kept unchanged so the two can be compared.
  - `zulip-v1.review.md` records how they were reviewed.
- `citemark test check` and `citemark test freeze`: check a file of test questions against a saved copy of the help center, then freeze it
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
- `src/citemark/embed/`: embeddings, with Voyage's `voyage-4` behind a small interface.

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
```

## Licenses

The code is MIT (see `LICENSE`). The demo uses Zulip's open-source help center under the Apache License 2.0; see `NOTICE`. This is an unofficial demo, not affiliated with Zulip.
