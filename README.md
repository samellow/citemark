# Citemark

A support bot for SaaS help centers that ships with proof it works: a test report, run on the client's own help center, showing how often the bot answers correctly, shows the right source, and says so when the help center doesn't cover a question. Each client runs their own copy in their own hosting account. MIT-licensed.

**Status: early.** The demo's 50 test questions were frozen on 2026-10-08, before any bot code exists, so the published results can't be fitted to them. The tag `zulip-v1-frozen` marks that commit. Nothing else runs yet.

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
- `src/citemark/db/`: the database (Postgres 16 with pgvector). The database itself refuses to change a frozen test set, and to edit or delete a passage, so an old citation always opens what it cited.

## Running it locally

You need [uv](https://docs.astral.sh/uv/) and Docker.

```
cp .env.example .env              # then add your API keys to .env
docker compose up -d db           # Postgres 16 with pgvector, on port 54320
uv run alembic upgrade head
uv run pytest
uv run citemark test check test-sets/zulip-v1.yaml --snapshot fixtures/zulip
```

## Licenses

The code is MIT (see `LICENSE`). The demo uses Zulip's open-source help center under the Apache License 2.0; see `NOTICE`. This is an unofficial demo, not affiliated with Zulip.
