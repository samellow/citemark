# Citemark

A support bot for SaaS help centers that ships with proof it works: a test report, run on the client's own help center, showing how often the bot answers correctly, shows the right source, and says so when the help center doesn't cover a question. Each client runs their own copy in their own hosting account. MIT-licensed.

**Status: early.** The demo's 50 test questions were frozen on 2026-10-08, before any bot code exists, so the published results can't be fitted to them. The tag `zulip-v1-frozen` marks that commit. The bot can load a help center, keep it up to date, find the passages that answer a question, answer with sources or decline, and run its own test set, scored and judged, three times over when a decision rests on it. The report that publishes those results comes next.

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

## Licenses

The code is MIT (see `LICENSE`). The demo uses Zulip's open-source help center under the Apache License 2.0; see `NOTICE`. This is an unofficial demo, not affiliated with Zulip.
