"""The citemark command line."""

from __future__ import annotations

import asyncio
import datetime as dt
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
    from citemark.costs import PriceMissing
    from citemark.db.session import make_engine
    from citemark.embed import EmbedError
    from citemark.evals.runner import RunError
    from citemark.ingest import IngestError
    from citemark.models.registry import ModelError
    from citemark.retrieve import RetrievalError

    async def main() -> T:
        engine = make_engine()
        try:
            return await work(engine)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(main())
    except (IngestError, EmbedError, RetrievalError, ModelError, PriceMissing, RunError) as exc:
        _fail(str(exc))
    except (testset.TestSetChanged, testset.TestSetError) as exc:
        _fail(str(exc))


def _anthropic_key() -> str:
    from citemark.settings import get_settings

    key = get_settings().anthropic_api_key
    if key is None:
        _fail("ANTHROPIC_API_KEY isn't set, so no answer can be written. Add it to .env or the environment.")
    return key.get_secret_value()


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


class RunMode(StrEnum):
    retrieval = "retrieval"
    full_context = "full_context"


MEASURES = (  # the names readers see (content spec 5.2)
    ("correct_answers", "Correct answers"),
    ("right_source", "Right source shown"),
    ("correct_declines", 'Correctly said "not covered"'),
    ("wrongly_declined", 'Wrongly said "not covered" (lower is better)'),
    ("right_place", "Looked in the right place"),
)


def _print_summary(found) -> None:
    run = found.run
    typer.echo(f"\nRun {run.id}: {run.model}, {run.mode.replace('_', ' ')}, {run.status}.")
    typer.echo(f"{found.finished} of {found.total} questions answered.")
    for field, name in MEASURES:
        measure = getattr(found.measures, field)
        typer.echo(f"  {name}: " + ("n/a" if measure is None else f"{measure.passed} of {measure.total}"))
    failures = ", ".join(f"{kind} {count}" for kind, count in sorted(found.measures.failures.items()))
    typer.echo(f"  Failures: {failures or 'none'}")
    typer.echo(f"  Text shown, then swapped for a decision: {found.measures.swapped}")
    for question_id, problems in found.voice.items():
        typer.echo(f"  Voice check, {question_id}: {'; '.join(problems)}")
    if found.median_ttfw_ms is not None:
        typer.echo(f"  Median time to first word: {found.median_ttfw_ms / 1000:.2f} s, without a network between.")
    typer.echo(f"  Spent: ${run.cost_usd:.4f} at list prices, of a ${run.budget_usd:.2f} budget.")


def _runs_text(numbers: list[int]) -> str:
    if len(numbers) == 1:
        return f"run {numbers[0]}"
    return "runs " + ", ".join(str(n) for n in numbers[:-1]) + f" and {numbers[-1]}"


def _print_decision(found) -> None:
    """A decision run's medians and ranges (content spec 5.2), and the grading queue. The judge's
    verdicts on the queue aren't shown, so they can't sway your grade."""
    first = found.runs[0]
    typer.echo(
        f"\nDecision run {found.group}: {len(found.runs)} runs of {first.model}, {first.mode.replace('_', ' ')}, "
        f"commit {first.git_sha[:12]}."
    )
    for field, name in MEASURES:
        measure = found.measures[field]
        if measure is None:
            typer.echo(f"  {name}: n/a")
            continue
        if field == "correct_answers" and found.provisional:  # its range would hint at the judge's verdicts
            typer.echo(f"  {name}: shown once you've graded the answers waiting, so it can't sway your grade")
            continue
        runs = (
            f"Same in all {len(found.runs)} runs"
            if measure.same
            else f"{len(found.runs)} runs: {measure.low}\u2013{measure.high}"
        )
        typer.echo(f"  {name}: {measure.median} of {measure.total} (median) \u00b7 {runs}")
    questions = sorted({entry.question for entry in found.queue})
    if not questions:
        typer.echo(
            "  The judge gave each answered question the same verdict in every run, so nothing waits for your grade."
        )
    else:
        typer.echo(
            f"  The judge graded {len(questions)} question(s) differently across the runs, so your grade counts "
            f"on their {len(found.queue)} answers."
        )
        waiting = {q: [e.run for e in found.waiting if e.question == q] for q in questions}
        if listing := ", ".join(f"{q} ({_runs_text(runs)})" for q, runs in waiting.items() if runs):
            typer.echo(f"  Waiting for your grade: {listing}. Until they're graded, the decision is provisional.")
        else:
            typer.echo("  Every answer in the queue is graded, so your grades count.")
    typer.echo(f"  Spent: ${found.spent:.4f} at list prices, of a ${found.budget:.2f} budget.")


def _run_tests(
    file: Path | None,
    run_id: uuid.UUID | None,
    *,
    company,
    model,
    mode,
    budget,
    runs: int = 1,
    yes: bool,
    force: bool = False,
) -> None:
    """Start a run of `file`, or three sharing a decision group, or resume `run_id` with the rest
    of its decision run. Prints each result, then the summary. Exits 1 when a run failed or
    reached its budget, so a script can tell."""
    import functools
    from decimal import Decimal

    import anthropic
    import httpx2

    from citemark.db.models import TestRun
    from citemark.db.session import make_sessionmaker
    from citemark.embed.voyage import VoyageEmbedder, VoyageReranker
    from citemark.evals import decision as deciding
    from citemark.evals import judge as judging
    from citemark.evals import runner
    from citemark.models.claude import ClaudeAnswerer
    from citemark.retrieve import RetrievalConfig, load_config

    sha = runner.git_sha()
    many = file is not None and runs == deciding.RUNS
    if many:
        try:
            deciding.committed(sha)  # before anything is called
        except deciding.DecisionError as exc:
            _fail(str(exc))
    voyage, claude = _voyage_key(), _anthropic_key()

    def show(question_id: str, result) -> None:
        typer.echo(f"  {question_id}  {result.kind:<20} {result.failure_type or 'passed'}")

    def announce(number: int, run) -> None:
        typer.echo(f"Run {number} of {deciding.RUNS} ({run.id}):")

    async def work(engine):
        sessions = make_sessionmaker(engine)
        async with httpx2.AsyncClient() as api, anthropic.AsyncAnthropic(api_key=claude) as client:

            def services(run_mode: str, run_model: str, run_company: str, config: RetrievalConfig) -> runner.Services:
                reranker = VoyageReranker(voyage, api, model=config.reranker) if config.rerank else None
                return runner.Services(
                    answerer=ClaudeAnswerer(client, run_model, company=run_company),
                    client=client,
                    embedder=VoyageEmbedder(voyage, api),
                    reranker=reranker if run_mode == "retrieval" else None,
                    judge=functools.partial(judging.judge, client),
                )

            if run_id is None:
                async with sessions() as session, session.begin():  # the set's copy is kept either way
                    test_set = await runner.load_test_set(session, file)
                    config = await load_config(session)
                    chosen = services(mode.value, model, company, config)
                    prepared = await runner.prepare(
                        session,
                        test_set.id,
                        mode=mode.value,
                        answerer=chosen.answerer,
                        embedder=chosen.embedder,
                        reranker=chosen.reranker,
                        on=dt.datetime.now(dt.UTC).date(),
                    )
                where = f"{len(prepared.questions)} questions on {model}, {mode.value.replace('_', ' ')}"
                if many:
                    typer.echo(
                        f"A decision run: {deciding.RUNS} runs of {where}, from commit {sha[:12]}. Estimated cost: "
                        f"about ${prepared.estimate * deciding.RUNS:.2f} for all {deciding.RUNS} at list prices "
                        f"(an estimate). Budget: ${budget:.2f}, a third for each run."
                    )
                else:
                    typer.echo(
                        f"{where}. Estimated cost: about ${prepared.estimate:.2f} at list prices (an estimate). "
                        f"Budget: ${budget:.2f}."
                    )
                if not yes and not typer.confirm("Start?"):  # no transaction is open while it waits
                    raise typer.Exit(0)
                async with sessions() as session, session.begin():
                    if many:
                        created = await deciding.create_group(
                            session,
                            test_set,
                            mode=mode.value,
                            answerer=chosen.answerer,
                            config=config,
                            budget_usd=Decimal(str(budget)),
                            sha=sha,
                        )
                        started, group = created[0].id, created[0].decision_group
                    else:
                        run = await runner.create_run(
                            session,
                            test_set,
                            mode=mode.value,
                            answerer=chosen.answerer,
                            config=config,
                            budget_usd=Decimal(str(budget)),
                            sha=sha,
                        )
                        started, group = run.id, None
            else:
                async with sessions() as session:
                    found = await session.get(TestRun, run_id)
                    if found is None:
                        raise runner.RunError(f"There's no test run {run_id}.")
                config = RetrievalConfig.model_validate(found.retrieval_config or {})
                chosen = services(found.mode, found.model, found.company, config)
                started, group = run_id, found.decision_group

            if group is None:
                typer.echo(f"Run {started}:")
                await runner.run_tests(
                    started, sessions=sessions, services=chosen, on_result=show, force=force, sha=sha
                )
                async with sessions() as session:
                    return await runner.summary(session, started), None, None
            ended = await deciding.finish_group(
                group,
                sessions=sessions,
                services=chosen,
                sha=sha,
                force=run_id if force else None,
                on_run=announce,
                on_result=show,
            )
            async with sessions() as session:
                if ended and (stopped := ended[-1])[1].status != "done":
                    numbered = await deciding.group_runs(session, group)
                    position = [run.id for run in numbered].index(stopped[0].id) + 1
                    return await runner.summary(session, stopped[0].id), None, position
                return None, await deciding.decision(session, group), None

    found, decided, position = _with_db(work)
    if decided is not None:
        _print_decision(decided)
        return
    _print_summary(found)
    which = f"Run {position} of {deciding.RUNS}" if position else "The run"
    if found.run.status == "failed":
        whole = "the decision run" if position else "it"
        _fail(f"{which} stopped before it finished. Finish {whole} with: citemark test resume {found.run.id}")
    if found.run.status == "over_budget":
        if position:
            _fail(
                f"{which} stopped at its budget, so this decision run can't be completed. "
                "Start a new one with a bigger budget."
            )
        _fail(f"The run stopped at its budget, so its results cover {found.finished} of {found.total} questions.")
    if position:  # any other way a run of the group ended short
        _fail(f"{which} ended {found.run.status.replace('_', ' ')}, so this decision run has no result yet.")


@test_app.command("run")
def run_tests(
    file: FileArg,
    company: Annotated[str, typer.Option(help="The product the help center is for, as the bot names it.")],
    budget: Annotated[
        float,
        typer.Option(
            min=0.01,
            help="The most it may spend, in US dollars; a decision run gives each of its runs a third. "
            "It stops short of it.",
        ),
    ],
    mode: Annotated[RunMode, typer.Option(help="Search for passages, or read the whole help center.")] = (
        RunMode.retrieval
    ),
    model: Annotated[str, typer.Option(help="The answer model.")] = "claude-haiku-5-5",
    runs: Annotated[
        int,
        typer.Option(help="1 for a single run, or 3 for a decision run: three runs whose medians decide."),
    ] = 1,
    yes: Annotated[bool, typer.Option("--yes", help="Start without asking, after showing the estimate.")] = False,
) -> None:
    """Run a frozen test set: ask every question, score the replies and judge the answers. Calls Claude and Voyage."""
    if runs not in (1, 3):
        _fail("--runs takes 1 for a single run, or 3 for a decision run.")
    _run_tests(file, None, company=company, model=model, mode=mode, budget=budget, runs=runs, yes=yes)


@test_app.command("resume")
def resume_tests(
    run_id: Annotated[str, typer.Argument(help="The run that stopped.")],
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Resume a run still marked as running, because its process stopped without finishing."
        ),
    ] = False,
) -> None:
    """Finish a run that stopped, asking only unanswered questions. A decision run's other runs follow."""
    try:
        found = uuid.UUID(run_id)
    except ValueError:
        _fail(f"{run_id} isn't a run ID.")
    _run_tests(None, found, company=None, model=None, mode=None, budget=None, yes=True, force=force)


@test_app.command("rescore")
def rescore(run_id: Annotated[str, typer.Argument(help="The run to score again.")]) -> None:
    """Recompute a run's scores from its stored results. Nothing is asked again; the judge's verdicts stand."""
    from citemark.db.session import make_sessionmaker
    from citemark.evals import runner

    try:
        found = uuid.UUID(run_id)
    except ValueError:
        _fail(f"{run_id} isn't a run ID.")

    async def work(engine):
        async with make_sessionmaker(engine)() as session, session.begin():
            await runner.rescore(session, found)
        async with make_sessionmaker(engine)() as session:
            return await runner.summary(session, found)

    _print_summary(_with_db(work))


@test_app.command("decision")
def decision_summary(
    run_id: Annotated[str, typer.Argument(help="The decision run, or any of its three runs.")],
) -> None:
    """Show a decision run's medians and ranges, and which answers wait for your grade."""
    from citemark.db.session import make_sessionmaker
    from citemark.evals import decision as deciding

    try:
        found = uuid.UUID(run_id)
    except ValueError:
        _fail(f"{run_id} isn't a run ID.")

    async def work(engine):
        async with make_sessionmaker(engine)() as session:
            return await deciding.decision(session, await deciding.find_group(session, found))

    _print_decision(_with_db(work))


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


@app.command("ask")
def ask(
    question: Annotated[str, typer.Argument(help="A question, as a customer would ask it.")],
    company: Annotated[str, typer.Option(help="The product the help center is for, as the bot names it.")],
    model: Annotated[str, typer.Option(help="The answer model.")] = "claude-haiku-5-5",
) -> None:
    """Answer a question as the bot would, with its sources and what it cost. Calls Claude and Voyage."""
    import anthropic
    import httpx2

    from citemark.answer.pipeline import respond
    from citemark.db.session import make_sessionmaker
    from citemark.embed.voyage import VoyageEmbedder, VoyageReranker
    from citemark.models.claude import ClaudeAnswerer
    from citemark.retrieve import load_config

    voyage, claude = _voyage_key(), _anthropic_key()

    async def run(engine):
        async with (
            make_sessionmaker(engine)() as session,
            httpx2.AsyncClient() as api,
            anthropic.AsyncAnthropic(api_key=claude) as client,
        ):
            config = await load_config(session)
            bot = ClaudeAnswerer(client, model, company=company)
            reranker = VoyageReranker(voyage, api, model=config.reranker) if config.rerank else None
            embedder = VoyageEmbedder(voyage, api)
            return await respond(
                session, question, model=bot, rewriter=client, embedder=embedder, reranker=reranker, config=config
            )

    result = _with_db(run)
    reply = result.reply
    typer.echo(f"[{reply.kind}{', swapped after text was shown' if reply.swapped else ''}]")
    if reply.segments:
        typer.echo("".join(s.text + "".join(f"[{marker}]" for marker in s.markers) for s in reply.segments))
    else:
        typer.echo(reply.text)
    if reply.clarify_options:
        typer.echo("Options: " + " / ".join(reply.clarify_options))
    if reply.gap_line:
        typer.echo(reply.gap_line)
    for source in reply.sources:
        typer.echo(f"[{source.marker}] {source.title}\n    {source.url}")
    if reply.problems:
        typer.echo("Broke the rules: " + "; ".join(reply.problems))
    first = f"First word after {result.ttfw_ms / 1000:.2f} s, " if result.ttfw_ms is not None else ""
    typer.echo(f"{first}{result.total_ms / 1000:.2f} s in all. Cost about ${result.cost_usd:.4f} at list prices.")
