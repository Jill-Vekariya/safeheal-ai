import json

from scripts import verify_model_study as study


def test_disjoint_ai_outcomes_or_missing_audit_cannot_qualify(tmp_path, monkeypatch):
    """Positive aggregate counts must not substitute for one complete AI path."""
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "run.json").write_text(json.dumps({
        "completed": True, "attempted_slots": 15, "planned_slots": 15,
    }))
    rows = [{"arm": arm, "attempted": True, "status": "observed", "cleanup_passed": True,
             "denied_access": [{"status_code": 403}] * 8}
            for arm in ("native", "rule_policy", "ai_policy") for _ in range(5)]
    for i, row in enumerate(rows):
        row["trial_id"] = f"d9-{i:02d}-{row['arm']}"
    ai = [r for r in rows if r["arm"] == "ai_policy"]
    for r in ai:
        r.update(provider_calls=1, diagnosis={"source": "llm", "provider_status": "validated"})
    ai[0]["controller_result"] = {"status": "verified"}
    ai[1]["metrics"] = {"recovery_seconds": 20}
    audit = tmp_path / ai[0]["trial_id"] / "audit.sqlite3"
    audit.parent.mkdir()
    audit.touch()
    monkeypatch.setattr(study, "analyze", lambda _: {"trials": rows})
    monkeypatch.setattr(study, "audit_events", lambda _: 4)

    report, _ = study.verify(tmp_path)
    assert report["ai_controller_verified"] == report["ai_business_recovered"] == 1
    assert report["passed"] is False

    ai[0]["metrics"] = {"recovery_seconds": 18}
    assert study.verify(tmp_path)[0]["passed"] is True

    other = tmp_path / "d9-rule-other" / "audit.sqlite3"
    other.parent.mkdir()
    other.touch()
    audit.unlink()
    report, _ = study.verify(tmp_path)
    assert report["audit_events"] > 0
    assert report["passed"] is False
