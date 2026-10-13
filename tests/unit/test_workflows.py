"""The workflows' own shell steps, run as GitHub runs them. A schema check says a workflow is
well formed; it doesn't say a failing step fails."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"


def step(workflow: str, job: str, containing: str) -> dict:
    jobs = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))["jobs"]
    [found] = [each for each in jobs[job]["steps"] if containing in each.get("run", "")]
    return found


@pytest.mark.parametrize("code", [1, 0])
def test_the_nightly_step_ends_as_the_live_run_does(tmp_path, code):
    """The first live run failed its check and showed green (2026-10-13): the step pipes the run
    into tee, and GitHub's `bash -e` reported tee's success. Its output is kept either way."""
    asking = step("nightly.yml", "live", "citemark test live")
    assert "shell" not in asking  # so GitHub runs it as `bash -e {0}`, as below
    stub = tmp_path / "bin" / "uv"
    stub.parent.mkdir()
    stub.write_text(f"#!/bin/sh\necho 'Failed:' >&2\nexit {code}\n", encoding="utf-8")
    stub.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(asking["run"], encoding="utf-8")
    env = {"PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}"}
    done = subprocess.run(["bash", "-e", str(script)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert done.returncode == code
    assert (tmp_path / "live.txt").read_text(encoding="utf-8") == "Failed:\n"
