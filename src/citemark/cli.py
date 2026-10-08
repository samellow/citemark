"""The citemark command line."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from citemark.evals import checks, testset
from citemark.evals.snapshot import HelpCenterSnapshot

app = typer.Typer(help="Citemark: a support bot tested against its own help center.", no_args_is_help=True)
test_app = typer.Typer(help="Test questions: check them, then freeze them.", no_args_is_help=True)
app.add_typer(test_app, name="test")

FileArg = Annotated[Path, typer.Argument(help="The test-set YAML file.", exists=True, dir_okay=False)]
SnapshotOpt = Annotated[
    Path,
    typer.Option(help="Folder holding the help center's manifest.json and text/.", exists=True, file_okay=False),
]
ExpectOpt = Annotated[
    str | None, typer.Option(help="Required counts per type, for example answerable=32,partial=5.")
]
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
) -> None:
    """Check a test set against the saved help center. Exits 1 if anything must be fixed."""
    test_set = _load(file)
    help_center = HelpCenterSnapshot(snapshot)
    findings = checks.run_checks(test_set, help_center, _expect(expect), max_per_article)
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
        _fail(f"{blocking} {'problem' if blocking == 1 else 'problems'} to fix before freezing.")
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
    typer.echo(f"Frozen: {test_set.name} v{test_set.version}, {lock['questions']} questions, "
               f"fingerprint {lock['sha256'][:8]}.")
    if draft:
        typer.echo(f"Wording check flagged {flagged} in the draft; {edited} of {lock['questions']} changed in review.")
    files = [file.name, testset.lock_path(file).name, *([draft.name] if draft else [])]
    typer.echo(f"Commit {', '.join(files)} together.")
