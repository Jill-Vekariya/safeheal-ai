"""Live execution requires an explicit project lab; plan mode remains read-only."""

import sys

import pytest

from scripts import controlled_suite as suite


def test_execute_without_lab_stops_before_any_cluster_operation(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        ["controlled_suite", "--execute", "--output", str(tmp_path / "run")],
    )
    monkeypatch.setattr(
        suite, "run", lambda *a: pytest.fail("unexpected cluster access")
    )
    with pytest.raises(SystemExit) as exc:
        suite.main()
    assert exc.value.code == 2
    assert not (tmp_path / "run").exists()


def test_explicit_ci_lab_is_recorded_in_predeclared_plan(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "controlled_suite",
            "--execute",
            "--lab",
            "safeheal-dev",
            "--repeats",
            "2",
            "--horizon",
            "30",
            "--output",
            str(tmp_path / "run"),
        ],
    )
    captured = []
    monkeypatch.setattr(
        suite, "run", lambda plan, folder: captured.append((plan, folder))
    )
    suite.main()
    assert len(captured) == 1
    plan, folder = captured[0]
    assert plan["lab"] == "safeheal-dev" and len(plan["slots"]) == 18
    assert plan["limits"]["live_provider_enabled"] is False
    assert folder == tmp_path / "run" and not folder.exists()


def test_foreign_lab_is_rejected_before_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "controlled_suite",
            "--execute",
            "--lab",
            "production",
            "--output",
            str(tmp_path / "run"),
        ],
    )
    monkeypatch.setattr(
        suite, "run", lambda *a: pytest.fail("unexpected cluster access")
    )
    with pytest.raises(SystemExit) as exc:
        suite.main()
    assert exc.value.code == 2
