"""Replay raw Day 9 measurements and render publication-style comparison figures.

Numerical analysis uses only the standard library. Rendering requires the pinned
optional requirements-analysis.txt; --no-plots works in the existing runtime.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from controlled_core import ARMS, metrics, summarize


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(directory):
    directory=Path(directory).resolve()
    plan=read_json(directory/"protocol.json")
    manifest=read_json(directory/"manifest.json")
    for name,expected in manifest["sha256"].items():
        path=directory/name
        if not path.resolve().is_relative_to(directory) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError("Raw data integrity mismatch: "+name)
    recorded={}
    for path in sorted(directory.glob("d9-*/trial.json")):
        r=read_json(path)
        key=(r["block"],r["arm"])
        if key in recorded or r["trial_id"]!=path.parent.name:
            raise ValueError("Duplicate or mismatched trial identity")
        if r.get("attempted"):
            requests=[]
            with (path.parent/"requests.jsonl").open(encoding="utf-8") as stream:
                for line in stream:
                    sample=json.loads(line)
                    for name in ("started_elapsed_seconds","finished_elapsed_seconds","elapsed_seconds"):
                        if type(sample[name]) not in (int,float) or not math.isfinite(sample[name]) or sample[name]<0:
                            raise ValueError("Invalid request timing")
                    requests.append(sample)
            if r.get("effect_verified") and not any(not s["valid_response"] and s["started_elapsed_seconds"]>=r["injection_elapsed"] for s in requests):
                raise ValueError("Claimed fault impact has no raw business-failure witness")
            replay=metrics(r,requests,plan["horizon_seconds"])
            if replay!=r.get("metrics"):
                raise ValueError("Stored metrics differ from raw replay: "+r["trial_id"])
        recorded[key]=r
    rows=[]
    for slot in plan["slots"]:
        r=recorded.pop((slot["block"],slot["arm"]),None)
        rows.append(r or {**slot,"attempted":False,"status":"not_run","reason":"batch_stopped_before_slot"})
    if recorded:
        raise ValueError("Unplanned trial")
    summary=summarize(rows)
    rng=random.Random(9)
    pairs=summary["paired_native_minus_rule_restricted_seconds"]
    bootstrap=sorted(statistics.mean(rng.choices(pairs,k=len(pairs))) for _ in range(10000)) if len(pairs)>=2 else []
    errors=[]
    accuracy={"real_llm_diagnoses":0,"target_matches":0,"observable_class_matches":0,"model_output_rejected":0,"provider_failures":0}
    for r in rows:
        diagnosis=r.get("diagnosis",{})
        if diagnosis.get("source")=="llm":
            accuracy["real_llm_diagnoses"]+=1
            top=diagnosis.get("hypotheses",[{}])[0] if diagnosis.get("hypotheses") else {}
            accuracy["target_matches"]+=top.get("service")=="payment"
            accuracy["observable_class_matches"]+=top.get("classification")=="endpoint_unavailable"
        reason=diagnosis.get("provider_status","")
        accuracy["model_output_rejected"]+=reason=="model_output_rejected"
        accuracy["provider_failures"]+=reason.startswith("provider_") and reason!="provider_disabled"
        if r.get("status")!="observed" or (r.get("metrics") or {}).get("censored") or (r["arm"]!="native" and r.get("controller_result",{}).get("status")!="verified"):
            errors.append({"trial_id":r.get("trial_id"),"block":r["block"],"arm":r["arm"],"status":r.get("status"),
                           "reason":r.get("reason",r.get("error_type",reason or "no_recovery_within_horizon")),
                           "censored":(r.get("metrics") or {}).get("censored")})
    return {"schema_version":"day9-analysis-v1","protocol":plan,"summary":summary,
            "bootstrap_paired_restricted_difference_95": [bootstrap[249],bootstrap[9749]] if bootstrap else None,
            "bootstrap_note":"Exploratory resampling of matched blocks; n=5/shared cluster do not establish population precision.",
            "diagnostic_accuracy":accuracy if accuracy["real_llm_diagnoses"] else None,
            "actual_monetary_cost_usd":None,"cost_note":"No model prices/account billing supplied. Zero model requests in baseline arms is not zero total compute cost.",
            "error_analysis":errors,"trials":rows,
            "raw_manifest_sha256":hashlib.sha256((directory/"manifest.json").read_bytes()).hexdigest(),
            "conclusion_scope":"Only the isolated scale-zero fixture and the fixed one-action policy; no general recovery/AI superiority claim."}


def findings(data):
    s=data["summary"]; arms=s["arms"]
    lines=["# Day 9 controlled experiment findings","",
           "The study concerns one operator-induced payment Deployment scale-zero outage in the isolated Kubernetes lab.",
           "The 45-second horizon, five matched blocks, randomized arm order, workload and decision rules were recorded before fault injection.","",
           "| Arm | Attempted / planned | Recovered within horizon | Censored | Mean observed recovery (s) | Mean restricted time (s) | Real provider requests |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    def value(v): return "Not measured" if v is None else f"{v:.3f}"
    for arm in ARMS:
        r=arms[arm]
        lines.append(f"| {arm} | {r['attempted']} / {r['planned']} | {r['recovered_within_horizon']} | {r['censored']} | {value(r['mean_observed_recovery_seconds'])} | {value(r['mean_restricted_seconds'])} | {r['real_provider_requests']} |")
    lines += ["", "Censored trials did not recover during observation. Their actual recovery time is unknown; 45 seconds is a restricted-horizon value, not observed MTTR.","",
              f"Matched native-minus-rule restricted-time differences (seconds): {s['paired_native_minus_rule_restricted_seconds']}.",
              f"Mean matched difference: {value(s['mean_paired_restricted_difference'])} seconds.",
              f"Exploratory 95% paired bootstrap interval: {data['bootstrap_paired_restricted_difference_95']}. This is conditional small-sample resampling, not production precision.","",
              "## Interpretation and trade-offs","",
              "For this deliberately narrow configuration fault, the fixed rule can request an independently permitted restore action. Native reconciliation does not change a Deployment's desired replica count back to one. This scenario therefore favors an explicit restore policy; it is not a test of generic process self-restart.",
              "The rule path requires no model tokens or model availability. The same controller, credential scope and admission restrictions constrain every active arm. Fresh journals are operator-managed experimental episodes; continuous-production cooldown/budget behavior across journal resets is not evaluated.",""]
    if not s["ai_comparison_complete"]:
        reason="Provider settings/credentials were not available for the planned AI slots, which are retained as not run." if not data["protocol"].get("provider",{}).get("configured") else "Inspect the explicit unrun or technical-failure records; the planned real-provider cohort was not fully observed."
        lines += ["**The real AI-assisted comparison is incomplete.** "+reason+" No mock, deterministic fallback or LLM from this chat was substituted. AI accuracy, recovery benefit, token usage and monetary cost cannot be inferred from these baseline data.",""]
    else:
        lines += ["The AI arm used the configured real provider. Distinguish validated model outputs, abstentions, provider failures and policy denials in the raw diagnosis records; source fallback is never model success.",""]
    lines += ["## Limitations and error analysis","",
              "Only one scenario and five blocks on one shared cluster/machine were studied. Sequential order, shared caches, telemetry windows and host instrumentation can affect timing. The runtime waits eight seconds before decisions and samples business responses; measured times include those choices and API overhead.",
              "The workload is closed-loop: slow failures reduce request throughput. Valid-response percentages are weighted by completed requests, not elapsed-time uptime or a fixed offered-load reliability estimate.",
              "Ground truth was attached after diagnosis. The model sees normalized telemetry, not fixture labels. Target/symptom agreement does not prove the initiating mechanism. No benign-control false-positive rate, held-out accuracy or production safety rate is established.",
              "Operator cleanup occurs after measurement and is excluded from recovery metrics. All setup failures, technical failures, censored and unrun slots remain explicit; no failed trial is silently replaced.","",
              "| Trial | Arm | Status | Reason | Censored |","|---|---|---|---|---|"]
    lines += [f"| {r['trial_id']} | {r['arm']} | {r['status']} | {r['reason']} | {r['censored']} |" for r in data["error_analysis"]]
    return "\n".join(lines)+"\n"


def render(data,output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"svg.fonttype":"none"})
    labels=["Native only","Rule + safe policy","AI + safe policy"]
    colors=["#64748b","#087f8c","#7c3aed"]
    fig,ax=plt.subplots(figsize=(8.5,4.7))
    horizon=data["protocol"]["horizon_seconds"]
    for i,arm in enumerate(ARMS):
        rows=[r for r in data["trials"] if r["arm"]==arm and (r.get("metrics") or {}).get("eligible")]
        if not rows:
            label="Not run\nprovider not configured" if arm=="ai_policy" and not any(r.get("attempted") for r in data["trials"] if r["arm"]==arm) else "No eligible\nmeasurement"
            ax.text(i,horizon*.5,label,ha="center",va="center",color="#64748b",fontsize=10)
        for j,r in enumerate(rows):
            m=r["metrics"]; x=i+(j-(len(rows)-1)/2)*.055
            ax.scatter(x,m["restricted_seconds"],s=65,marker="^" if m["censored"] else "o",
                       facecolors="none" if m["censored"] else colors[i],edgecolors=colors[i],linewidths=1.6,zorder=3)
    ax.axhline(horizon,color="#94a3b8",ls="--",lw=1)
    ax.set(xticks=range(3),xticklabels=labels,ylim=(0,horizon*1.18),xlim=(-.5,2.5),ylabel="Time to verified business recovery (seconds)",title="Isolated scale-zero outage: all trial outcomes")
    ax.text(-.45,horizon*1.08,f"Open triangles: no recovery within {horizon:g} s (censored)",fontsize=9,color="#475569")
    ax.grid(axis="y",alpha=.2); fig.tight_layout()
    fig.savefig(output/"recovery_comparison.png",dpi=180); fig.savefig(output/"recovery_comparison.svg"); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.5,4.7))
    for i,arm in enumerate(ARMS):
        rows=[r for r in data["trials"] if r["arm"]==arm and (r.get("metrics") or {}).get("eligible")]
        total=sum(r["metrics"]["total_requests"] for r in rows)
        good=sum(r["metrics"]["successful_requests"] for r in rows)
        if total:
            pct=100*good/total
            ax.bar(i,pct,color=colors[i],width=.55)
            ax.text(i,pct+2,f"{pct:.1f}%\n{good}/{total} responses",ha="center",va="bottom",fontsize=9)
        else:
            ax.text(i,48,"Not measured",ha="center",color="#64748b")
    ax.set(xticks=range(3),xticklabels=labels,ylim=(0,115),xlim=(-.5,2.5),ylabel="Valid confirmed order responses (%)",title=f"Observed business responses during the {horizon:g}-second horizon")
    ax.grid(axis="y",alpha=.2); ax.set_axisbelow(True); fig.tight_layout()
    fig.savefig(output/"business_responses.png",dpi=180); fig.savefig(output/"business_responses.svg"); plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path,nargs="?")
    parser.add_argument("--render-analysis",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--no-plots",action="store_true")
    args=parser.parse_args()
    data=read_json(args.render_analysis) if args.render_analysis else analyze(args.directory)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/"analysis.json").write_text(json.dumps(data,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    (args.output/"FINDINGS.md").write_text(findings(data),encoding="utf-8",newline="\n")
    with (args.output/"trials.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["trial_id","block","arm","status","eligible","recovery_seconds","restricted_seconds","censored","provider_calls"])
        writer.writeheader()
        for r in data["trials"]:
            writer.writerow({**{k:r.get(k) for k in ("trial_id","block","arm","status","provider_calls")},
                             **{k:(r.get("metrics") or {}).get(k) for k in ("eligible","recovery_seconds","restricted_seconds","censored")}})
    if not args.no_plots:
        render(data,args.output)
    print(json.dumps(data["summary"],indent=2))


if __name__=="__main__":
    main()
