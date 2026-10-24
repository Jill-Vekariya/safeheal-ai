from copy import deepcopy
import json

import pytest

from scripts.controlled_core import ARMS, ai_support, metrics, protocol, rule_support, summarize
from scripts.evaluate_robustness import make_bundle, Model
from services.diagnosis.agent import DiagnosisAgent


def row(start=2,end=47):
    return {"block":1,"arm":"native","attempted":True,"status":"observed","injection_elapsed":start,
            "injection_verified":True,"effect_verified":True,"observation_elapsed_end":end}


def sample(at,valid=True,duration=.1):
    return {"started_elapsed_seconds":at-duration,"finished_elapsed_seconds":at,
            "elapsed_seconds":duration,"valid_response":valid}


def test_seeded_blocks_and_horizon_are_declared():
    p=protocol()
    assert p==protocol() and len(p["slots"])==15
    assert p["horizon_seconds"]==45 and p["decision_delay_seconds"]==8
    for block in range(1,6):
        assert sorted(s["arm"] for s in p["slots"] if s["block"]==block)==sorted(ARMS)
    assert protocol(seed=10)["slots"]!=p["slots"]


@pytest.mark.parametrize("kwargs",[{"repeats":True},{"repeats":0},{"repeats":11},{"horizon":0},{"horizon":121}])
def test_invalid_protocol_is_rejected(kwargs):
    with pytest.raises(ValueError):
        protocol(**kwargs)


def test_censoring_is_not_an_observed_recovery_time():
    r=row()
    m=metrics(r,[sample(3,False),sample(46,False)],45)
    assert m["eligible"] and m["censored"] and m["restricted_seconds"]==45
    assert m["recovery_seconds"] is None


def test_raw_timing_replays_first_sustained_recovery():
    r=row()
    samples=[sample(3,False),sample(5),sample(6),sample(7),sample(8),sample(9)]
    m=metrics(r,samples,45)
    assert m["eligible"] and not m["censored"] and m["recovery_seconds"]==5
    assert m["restricted_seconds"]==5 and m["total_requests"]==6


def test_in_flight_pre_fault_success_cannot_establish_recovery():
    samples=[sample(2.2,True,1),sample(3),sample(5),sample(6),sample(7,False)]
    m=metrics(row(),samples,45)
    assert m["recovery_seconds"] is None


def test_short_observation_cannot_be_imputed_to_full_horizon():
    r=row(end=10)
    m=metrics(r,[sample(3,False)],45)
    assert not m["eligible"] and m["restricted_seconds"] is None


def test_unverified_fault_has_no_recovery_metric():
    r=row(); r["effect_verified"]=False
    assert not metrics(r,[sample(3)],45)["eligible"]


def test_slow_responses_do_not_count_as_healthy_recovery():
    m=metrics(row(),[sample(3,False),sample(7,True,1),sample(9,True,1),sample(11,True,1)],45)
    assert m["censored"]


def test_ai_bridge_never_promotes_fallback_or_low_confidence():
    diagnosis=DiagnosisAgent(Model("normal")).diagnose(make_bundle("fault"))
    assert not ai_support(diagnosis)  # server-error evidence is not the allowlisted endpoint gate.
    from scripts.evaluate_robustness import raw_metrics,T0
    from services.diagnosis.evidence import Aggregator
    agg=Aggregator(T0); agg.snapshot({"at":T0,"raw":raw_metrics(T0,errors=0,down=True)})
    bundle=agg.finish()
    assert rule_support(bundle)
    assert ai_support(DiagnosisAgent(Model("normal")).diagnose(bundle))
    assert not ai_support(DiagnosisAgent().diagnose(bundle))
    assert not ai_support(DiagnosisAgent(Model("low")).diagnose(bundle))
    assert not ai_support(DiagnosisAgent(Model("unsafe_command")).diagnose(bundle))


def test_not_run_ai_slots_are_not_fabricated_zero_time_or_cost():
    rows=[]
    for arm in ARMS:
        r=row(); r["arm"]=arm
        if arm=="ai_policy":
            r={"arm":arm,"block":1,"attempted":False,"status":"not_run","reason":"provider_missing"}
        else:
            r["metrics"]=metrics(r,[sample(3,False)],45)
        rows.append(r)
    summary=summarize(rows)
    assert summary["arms"]["ai_policy"]["not_run"]==1
    assert summary["arms"]["ai_policy"]["mean_restricted_seconds"] is None
    assert not summary["ai_comparison_complete"]


def test_missing_provider_is_explicit_and_no_model_is_selected(tmp_path):
    from scripts.controlled_experiment import provider_profile
    provider,metadata=provider_profile(tmp_path/"absent.json")
    assert provider is None and metadata=={"configured":False,"reason":"provider_profile_missing"}


def test_profile_rejects_unbudgeted_or_extra_authority_fields(tmp_path):
    from scripts.controlled_experiment import provider_profile
    path=tmp_path/"provider.json"
    path.write_text(json.dumps({"base_url":"https://example.com","model":"example","api_key":"unsafe-extra"}))
    with pytest.raises(ValueError):
        provider_profile(path)


def test_raw_manifest_refuses_running_trials_and_overwrite(tmp_path):
    from scripts.finalize_controlled import finalize
    (tmp_path/"run.json").write_text(json.dumps({"completed":True}))
    (tmp_path/"protocol.json").write_text(json.dumps({"slots":[{"block":1,"arm":"native"}]}))
    path=tmp_path/"d9-1"; path.mkdir()
    record={"block":1,"arm":"native","status":"running"}
    (path/"trial.json").write_text(json.dumps(record))
    with pytest.raises(ValueError):
        finalize(tmp_path)
    record["status"]="observed"
    (path/"trial.json").write_text(json.dumps(record))
    assert len(finalize(tmp_path)["sha256"])==3
    with pytest.raises(FileExistsError):
        finalize(tmp_path)


def test_analysis_checks_raw_integrity_and_replays_metrics(tmp_path):
    from scripts.analyze_controlled import analyze
    from scripts.finalize_controlled import finalize
    p=protocol(repeats=1)
    (tmp_path/"protocol.json").write_text(json.dumps(p))
    (tmp_path/"run.json").write_text(json.dumps({"completed":True}))
    for arm in ARMS:
        folder=tmp_path/("d9-"+arm); folder.mkdir()
        r={**row(),"arm":arm,"trial_id":folder.name}
        samples=[sample(3,False),sample(5),sample(6),sample(7)]
        r["metrics"]=metrics(r,samples,45)
        (folder/"requests.jsonl").write_text("\n".join(json.dumps(s) for s in samples)+"\n")
        (folder/"trial.json").write_text(json.dumps(r))
    finalize(tmp_path)
    result=analyze(tmp_path)
    assert result["summary"]["arms"]["native"]["mean_observed_recovery_seconds"]==5
    (tmp_path/"d9-native/requests.jsonl").write_text("corrupt")
    with pytest.raises(ValueError,match="integrity"):
        analyze(tmp_path)


def test_chart_input_with_null_unrun_metrics_writes_empty_csv_fields(tmp_path,monkeypatch):
    import csv
    from scripts.analyze_controlled import main
    rows=[]
    for arm in ARMS:
        r={**row(),"arm":arm,"trial_id":arm}
        if arm=="ai_policy":
            r.update(attempted=False,status="not_run")
        else:
            r["metrics"]=metrics(r,[sample(3,False)],45)
        rows.append(r)
    data={"protocol":protocol(repeats=1),"summary":summarize(rows),"trials":rows,
          "error_analysis":[],"bootstrap_paired_restricted_difference_95":None}
    rows[-1]["metrics"]=None
    source=tmp_path/"analysis.json"; source.write_text(json.dumps(data))
    output=tmp_path/"render"
    monkeypatch.setattr("sys.argv",["analyze_controlled.py","--render-analysis",str(source),"--output",str(output),"--no-plots"])
    main()
    with (output/"trials.csv").open() as stream:
        records=list(csv.DictReader(stream))
    assert records[-1]["recovery_seconds"]=="" and records[-1]["restricted_seconds"]==""
