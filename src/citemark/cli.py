"""The citemark command line."""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from citemark.evals import checks, testset
from citemark.evals.snapshot import HelpCenterSnapshot

app = typer.Typer(help="Citemark: a support bot tested against its own help center.", no_args_is_help=True)
test_app = typer.Typer(help="Test questions: check them, then freeze them.", no_args_is_help=True)
app.add_typer(test_app, name="test")
jobs_app = typer.Typer(help="Background jobs, such as the daily purge of old conversations.", no_args_is_help=True)
app.add_typer(jobs_app, name="jobs")
sources_app = typer.Typer(
    help="Where answers come from: add a help center, index it, upload files.", no_args_is_help=True
)
app.add_typer(sources_app, name="sources")


FileArg = Annotated[Path, typer.Argument(help="The test-set YAML file.", exists=True, dir_okay=False)]
SnapshotOpt = Annotated[
    Path,
    typer.Option(help="Folder holding the help center's manifest.json and text/.", exists=True, file_okay=False),
]
ExpectOpt = Annotated[str | None, typer.Option(help="Required counts per type, for example answerable=32,partial=5.")]
MaxPerArticleOpt = Annotated[int | None, typer.Option(help="The most questions allowed to use one article.")]
DraftOpt = Annotated[
    Path | None,
    typer.Option(
        help="The AI draft this set was edited from, kept unchanged. Counts what the wording check flagged "
        "and what changed in review. Needed to freeze a set with a drafting block.",
        exists=True,
        dir_okay=False,
    ),
]


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def _with_db[T](work: Callable[..., Awaitable[T]]) -> T:
    """Run `work(engine)` against the database, printing an ingestion or embedding error as one
    plain sentence."""
    from citemark.db.session import make_engine
    from citemark.embed import EmbedError
    from citemark.ingest import IngestError
    from citemark.retrieve import RetrievalError

    async def main() -> T:
        engine = make_engine()
        try:
            return await work(engine)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(main())
    except (IngestError, EmbedError, RetrievalError) as exc:
        _fail(str(exc))


def _voyage_key() -> str:
    from citemark.settings import get_settings

    key = get_settings().voyage_api_key
    if key is None:
        _fail("VOYAGE_API_KEY isn't set, so passages can't be embedded. Add it to .env or the environment.")
    return key.get_secret_value()


def _source_id(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        _fail(f"{value} isn't a source ID. citemark sources list shows them.")


def _load(path: Path, draft: bool = False) -> testset.TestSetFile:
    try:
        return testset.load_draft(path) if draft else testset.load(path)
    except testset.TestSetError as exc:
        _fail(str(exc))


def _expect(spec: str | None) -> dict[str, int] | None:
    try:
        return checks.parse_expect(spec)
    except ValueError as exc:
        _fail(f"--expect: {exc}")


def _report(findings: list[checks.Finding]) -> int:
    for f in sorted(findings, key=lambda f: (f.question_id or "", f.check)):
        level = "fix " if f.blocking else "note"
        typer.echo(f"  {level}  {f.question_id or '-':<5} {f.check:<13} {f.message}")
    return sum(f.blocking for f in findings)


@test_app.command("check")
def check(
    file: FileArg,
    snapshot: SnapshotOpt,
    expect: ExpectOpt = None,
    max_per_article: MaxPerArticleOpt = None,
    draft: DraftOpt = None,
    against_db: Annotated[
        bool,
        typer.Option(
            "--against-db",
            help="Also find every expected source among the indexed passages, after citemark sources index.",
        ),
    ] = False,
) -> None:
    """Check a test set against the saved help center. Exits 1 if anything must be fixed."""
    test_set = _load(file)
    help_center = HelpCenterSnapshot(snapshot)
    findings = checks.run_checks(test_set, help_center, _expect(expect), max_per_article)
    if against_db:
        from citemark.db.session import make_sessionmaker
        from citemark.evals.dbcheck import check_sources_in_db

        async def in_db(engine) -> list[checks.Finding]:
            async with make_sessionmaker(engine)() as session:
                return await check_sources_in_db(test_set, session)

        findings += _with_db(in_db)
    try:
        testset.verify_unchanged(file)
    except testset.TestSetChanged as exc:
        findings.append(checks.Finding("lock", str(exc)))
    counts = Counter(q.type.value for q in test_set.questions)
    summary = ", ".join(f"{n} {qtype}" for qtype, n in sorted(counts.items()))
    typer.echo(f"{test_set.name} v{test_set.version}: {len(test_set.questions)} questions ({summary})")
    blocking = _report(findings)
    if draft:
        flagged, edited = checks.review_counts(_load(draft, draft=True), test_set, help_center)
        typer.echo(
            f"Compared with the draft: the wording check flagged {flagged}, "
            f"and {edited} of {len(test_set.questions)} changed in review."
        )
    if blocking:
        when = "" if testset.read_lock(file) else " before freezing"
        _fail(f"{blocking} {'problem' if blocking == 1 else 'problems'} to fix{when}.")
    typer.echo("No problems to fix.")


@test_app.command("freeze")
def freeze(
    file: FileArg,
    snapshot: SnapshotOpt,
    expect: ExpectOpt = None,
    max_per_article: MaxPerArticleOpt = None,
    draft: DraftOpt = None,
) -> None:
    """Freeze a test set. After this, its questions can't change under this version."""
    test_set = _load(file)
    help_center = HelpCenterSnapshot(snapshot)
    blocking = [f for f in checks.run_checks(test_set, help_center, _expect(expect), max_per_article) if f.blocking]
    if blocking:
        _report(blocking)
        _fail("Not frozen. Fix these first; citemark test check shows them.")
    if test_set.drafting and not draft:
        _fail("Not frozen. This set has a drafting block, so pass --draft with the draft it was edited from.")
    flagged = edited = draft_sha256 = None
    if draft:
        flagged, edited = checks.review_counts(_load(draft, draft=True), test_set, help_center)
        draft_sha256 = testset.fingerprint(draft)
    try:
        lock = testset.freeze(
            file, test_set, help_center.manifest_sha256, flagged=flagged, edited=edited, draft_sha256=draft_sha256
        )
    except testset.AlreadyFrozen as exc:
        _fail(str(exc))
    typer.echo(
        f"Frozen: {test_set.name} v{test_set.version}, {lock['questions']} questions, fingerprint {lock['sha256'][:8]}."
    )
    if draft:
        typer.echo(f"Wording check flagged {flagged} in the draft; {edited} of {lock['questions']} changed in review.")
    files = [file.name, testset.lock_path(file).name, *([draft.name] if draft else [])]
    typer.echo(f"Commit {', '.join(files)} together.")


@jobs_app.command("work")
def jobs_work(
    until_idle: Annotated[bool, typer.Option(help="Stop once no job is waiting, instead of waiting for more.")] = False,
) -> None:
    """Run the job worker in this process. If it's stopped mid-job, the job resumes next time."""
    import asyncio

    from citemark import log
    from citemark.jobs.worker import run_worker

    log.configure()
    asyncio.run(run_worker(until_idle=until_idle))


class Kind(StrEnum):
    START_PAGE = "start-page"
    SITEMAP = "sitemap"
    URL = "url"


@sources_app.command("add")
def sources_add(
    kind: Annotated[
        Kind,
        typer.Argument(
            help="start-page: crawl from an index page, following links under its folder (for help centers "
            "without a sitemap). sitemap: the pages a sitemap lists. url: one page or PDF."
        ),
    ],
    url: Annotated[str, typer.Argument(help="The start page, sitemap or page address.")],
    path_prefix: Annotated[
        str | None,
        typer.Option(help="Only pages whose path starts with this. Default: the start page's folder, or /."),
    ] = None,
    selector: Annotated[
        str | None,
        typer.Option(help="A CSS selector for the element holding each article, when the extractor picks wrongly."),
    ] = None,
    include: Annotated[list[str] | None, typer.Option(help="Only paths matching this glob. Repeat for more.")] = None,
    exclude: Annotated[list[str] | None, typer.Option(help="Skip paths matching this glob. Repeat for more.")] = None,
) -> None:
    """Add a help center (or one page) to answer from. Index it next with citemark sources index."""
    from citemark.db.session import make_sessionmaker
    from citemark.ingest import sources

    async def add(engine):
        return await sources.add_source(
            make_sessionmaker(engine),
            kind.value.replace("-", "_"),
            url,
            path_prefix=path_prefix,
            content_selector=selector,
            include=include or [],
            exclude=exclude or [],
        )

    source = _with_db(add)
    typer.echo(f"Added {kind.value} source {source.id}. Index it with: citemark sources index {source.id}")


@sources_app.command("list")
def sources_list() -> None:
    """Each source with its articles and passages, as last indexed."""
    from citemark.db.session import make_sessionmaker
    from citemark.ingest import sources

    found = _with_db(lambda engine: sources.summaries(make_sessionmaker(engine)))
    if not found:
        typer.echo("No sources yet. Add one with: citemark sources add")
        return
    for source in found:
        when = f"indexed {source.last_crawled_at:%Y-%m-%d %H:%M} UTC" if source.last_crawled_at else "never indexed"
        failed = f", {source.failed:,} failed" if source.failed else ""
        typer.echo(f"{source.id}  {source.kind}  {source.url or '(uploaded files)'}")
        typer.echo(f"    {source.documents:,} articles{failed}, {source.passages:,} passages, {when}")


@sources_app.command("index")
def sources_index(
    source: Annotated[
        str | None, typer.Argument(help="The source's ID, from citemark sources list. Leave out for every one.")
    ] = None,
) -> None:
    """Fetch the source's pages and embed whatever changed, showing progress as counts.

    Only changed pages are embedded again. If this stops partway, the next run picks up where it
    stopped, and every page keeps its passages until new ones are saved."""
    import logging

    from citemark import log
    from citemark.ingest import sources

    source_id = _source_id(source)
    _voyage_key()
    log.configure(logging.WARNING)  # the progress lines, without the job log around them
    terminal = sys.stdout.isatty()

    def show(line: str) -> None:
        # In a terminal the count updates in place; in a log, each change is a line of its own
        typer.echo(f"\r{line}\033[K" if terminal else line, nl=not terminal)

    errors = _with_db(lambda engine: sources.index_and_show(engine, source_id, show))
    if terminal:
        typer.echo()
    if errors:
        _fail("\n".join(errors))
    typer.echo("Done.")


@sources_app.command("upload")
def sources_upload(
    files: Annotated[
        list[Path], typer.Argument(help="PDF, Markdown or HTML files.", exists=True, dir_okay=False, readable=True)
    ],
    source: Annotated[str | None, typer.Option(help="The upload source to add them to. Default: the first.")] = None,
) -> None:
    """Add files to answer from. A file uploaded again under the same name replaces the old one."""
    from citemark.db.session import make_sessionmaker
    from citemark.ingest import sources

    source_id, key = _source_id(source), _voyage_key()
    result = _with_db(lambda engine: sources.upload_files(make_sessionmaker(engine), files, source_id, key))
    typer.echo(
        f"{result.added} added, {result.updated} replaced, {result.unchanged} unchanged, {result.failed} failed; "
        f"{result.passages:,} passages embedded."
    )
    if result.failed:
        _fail("\n".join(result.problems))


@app.command("search")
def search(
    question: Annotated[str, typer.Argument(help="A question, as a customer would ask it.")],
    top_k: Annotated[int | None, typer.Option(help="How many passages to show. Default: the setting.")] = None,
    rerank: Annotated[
        bool | None, typer.Option("--rerank/--no-rerank", help="Rerank, or keep the fused order. Default: the setting.")
    ] = None,
) -> None:
    """Show the passages the bot would be given for a question, with their scores. Calls Voyage."""
    import httpx2

    from citemark.db.session import make_sessionmaker
    from citemark.embed.voyage import VoyageEmbedder, VoyageReranker
    from citemark.retrieve import RetrievalConfig, load_config
    from citemark.retrieve.search import retrieve

    key = _voyage_key()

    async def run(engine):
        async with make_sessionmaker(engine)() as session, httpx2.AsyncClient() as api:
            saved = await load_config(session)
            changes = {name: value for name, value in {"top_k": top_k, "rerank": rerank}.items() if value is not None}
            config = RetrievalConfig.model_validate({**saved.model_dump(), **changes})
            reranker = VoyageReranker(key, api, model=config.reranker) if config.rerank else None
            embedder = VoyageEmbedder(key, api)
            return await retrieve(session, question, embedder=embedder, reranker=reranker, config=config)

    result = _with_db(run)
    if not result.hits:
        typer.echo("No passages found. Is a source indexed? citemark sources list shows them.")
        return
    for hit in result.hits:
        named = (("rerank", hit.rerank_score), ("vector", hit.vector_score), ("keyword", hit.keyword_score))
        scores = [f"{name} {value:.3f}" for name, value in named if value is not None]
        typer.echo(f"{hit.rank}. {hit.heading_path}")
        typer.echo(f"   {hit.anchor_url or hit.url}")
        typer.echo("   " + " \u00b7 ".join(scores))
    typer.echo(
        f"Voyage counted {result.embed_tokens:,} tokens to embed the question and {result.rerank_tokens:,} to rerank."
    )
