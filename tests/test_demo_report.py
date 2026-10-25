"""A demo must never present old, partial or failed execution as a passing fresh run."""
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest
from scripts.demo_report import STEPS, begin, build_report, finish, trial_checks

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def approval():
    with zipfile.ZipFile(ROOT/"evidence/final/ci-40142094894/artifacts.zip") as archive:
        for name in archive.namelist():
            if "/d7-approval-" in name and name.endswith("/acceptance.json"):
                row = json.loads(archive.read(name))
                if row.get("admission_ready"):
                    return row
    raise AssertionError("No retained current approval trial")


def test_retained_real_gate_record_is_supported(approval):
    assert all(trial_checks(approval).values())


@pytest.mark.parametrize("change", [
    lambda r: r.update(passed=False),
    lambda r: r["dry_run"].update(execution_allowed=True),
    lambda r: r["denied_access"][0].update(status_code=200),
    lambda r: r["controller_result"]["observations"][-1].update(ready=False),
    lambda r: r["unapproved_denial"].update(status="verified"),
    lambda r: r["business_check"].update(passed=False),
    lambda r: r.update(operator_cleanup_restore=True),
    lambda r: r.update(llm_calls=1),
])
def test_failed_or_unsafe_evidence_cannot_pass(approval, change):
    change(approval)
    assert not all(trial_checks(approval).values())


def test_failed_workflow_step_cannot_pass():
    outcomes = {name: {"outcome": "success"} for name in STEPS}
    trials = [{"mode": mode, "passed": True} for mode in ("approval", "autonomous")]
    assert build_report("a"*40, outcomes, trials)["passed"]
    outcomes["checks"]["outcome"] = "failure"
    assert not build_report("a"*40, outcomes, trials)["passed"]


@pytest.mark.parametrize("trials", [
    [{"mode": "approval", "passed": True}],
    [{"mode": "approval", "passed": True}, {"mode": "approval", "passed": True}],
    [{"mode": "approval", "passed": False}, {"mode": "autonomous", "passed": True}],
])
def test_two_distinct_successful_modes_required(trials):
    assert not build_report("a"*40, {n: {"outcome": "success"} for n in STEPS}, trials)["passed"]


def test_old_trials_do_not_count_as_fresh_success(tmp_path):
    old = tmp_path/"evidence/day7/d7-approval-0123456789"
    old.mkdir(parents=True)
    (old/"acceptance.json").write_text('{"passed":true}', encoding="utf-8")
    output = tmp_path/"demo"
    begin(tmp_path, output, "a"*40)
    report = finish(tmp_path, output, {n: {"outcome": "success"} for n in STEPS})
    assert not report["passed"] and report["trials"] == []
    assert (output/"manifest.json").is_file()
