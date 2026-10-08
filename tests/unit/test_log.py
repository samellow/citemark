"""Logs keep a failure's traceback but never its local variables, which can hold API keys."""

import json

import structlog

from citemark import log


def test_a_logged_failure_keeps_its_traceback_but_not_its_local_variables(capsys):
    def call_the_api():
        api_key = "do-not-log-this-value"  # noqa: F841 (a local, as a request's headers would be)
        raise RuntimeError("Voyage answered with status 429")

    log.configure()
    try:
        try:
            call_the_api()
        except RuntimeError:
            structlog.get_logger().exception("job_failed")
        line = capsys.readouterr().out.strip().splitlines()[-1]
    finally:
        structlog.reset_defaults()
    entry = json.loads(line)
    [exception] = entry["exception"]
    assert entry["event"] == "job_failed"
    assert exception["exc_value"] == "Voyage answered with status 429"
    assert any(frame["name"] == "call_the_api" for frame in exception["frames"])
    assert "do-not-log-this-value" not in line
