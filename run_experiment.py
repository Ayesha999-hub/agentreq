#!/usr/bin/env python3
"""Runs the whole AgentReq experiment and writes tables, charts and a summary to --out.

  python run_experiment.py                      # uses data/requirements.csv
  python run_experiment.py --data my_reqs.csv --ablation
"""
import argparse
import csv
import datetime
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agentreq.baseline import single_prompt_rewrite
from agentreq.config import CRITERIA, Settings
from agentreq.evaluator import evaluate_text
from agentreq.llm import LLMClient, LLMError
from agentreq.pipeline import AgentReq
from agentreq.smells import find_conflicts, rule_smells


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_requirements(path):
    if path.endswith(".txt"):
        lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
        return [{"id": f"R{i:02d}", "text": t} for i, t in enumerate(lines, 1)]
    with open(path, newline="", encoding="utf-8") as f:
        rows = [{"id": r["id"].strip(), "text": r["text"].strip()} for r in csv.DictReader(f)]
    return [r for r in rows if r["id"] and r["text"]]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def arm_metrics(name, texts, evals, conflicts, calls, threshold):
    smell_counts = [len(rule_smells(t)) for t in texts]
    return {
        "arm": name,
        "n_requirements": len(texts),
        "doc_score": mean(e[2] for e in evals),
        "pass_rate": mean(1 if e[2] >= threshold else 0 for e in evals),
        "smell_total": sum(smell_counts),
        "items_with_smells": sum(1 for c in smell_counts if c),
        "conflicts": len(conflicts),
        "llm_calls": calls,
        **{f"crit_{c}": mean(e[0][c] for e in evals) for c in CRITERIA},
    }


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/requirements.csv")
    ap.add_argument("--project", default="data/project.txt")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--threshold", type=float, default=4.0)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="use only the first N requirements")
    ap.add_argument("--ablation", action="store_true", help="also run AgentReq without the smell feedback")
    args = ap.parse_args()

    load_env()
    try:
        gen, judge = LLMClient("LLM"), LLMClient("JUDGE")
    except LLMError as e:
        sys.exit(f"Setup problem: {e}")
    mock = gen.is_mock or judge.is_mock
    if mock:
        print("!" * 70 + "\n MOCK MODE: offline stub, results are NOT real. Testing only.\n" + "!" * 70)

    reqs = load_requirements(args.data)
    if args.limit:
        reqs = reqs[:args.limit]
    project = open(args.project, encoding="utf-8").read().strip() if os.path.exists(args.project) else ""
    st = Settings(threshold=args.threshold, max_rounds=args.rounds)
    os.makedirs(args.out, exist_ok=True)
    calls = lambda: gen.calls + judge.calls
    print(f"{len(reqs)} requirements | generator: {gen.model} | judge: {judge.model}")

    # ---- Arm: AgentReq (round 0 of this run also scores the originals) ----
    print("AgentReq (smell agent + evaluator + refiner loop):")
    agent = AgentReq(gen, judge, st, project, use_smells=True)
    res = agent.run(reqs)
    items = res["items"]
    originals = [i for i in items if i.original]
    orig_evals = [(i.orig_scores, i.orig_reasons, i.orig_score) for i in originals]
    orig_texts = [i.original for i in originals]

    c0 = calls()
    conf_orig = find_conflicts(judge, project, [(i.id, i.original) for i in originals])
    orig_conf_calls = calls() - c0
    c0 = calls()
    conf_final = find_conflicts(judge, project, [(i.id, i.text) for i in items])
    final_conf_calls = calls() - c0

    # ---- Arm: single-prompt baseline ----
    print("Single-prompt baseline:")
    c0 = calls()
    base_texts = [single_prompt_rewrite(gen, project, r["text"]) for r in reqs]
    base_evals = [evaluate_text(judge, project, t) for t in base_texts]
    conf_base = find_conflicts(judge, project, [(r["id"], t) for r, t in zip(reqs, base_texts)])
    base_calls = calls() - c0
    print(f"  doc score {mean(e[2] for e in base_evals):.2f}")

    arms = [
        arm_metrics("Original", orig_texts, orig_evals, conf_orig, len(reqs) + orig_conf_calls, st.threshold),
        arm_metrics("Single-prompt baseline", base_texts, base_evals, conf_base, base_calls, st.threshold),
        arm_metrics("AgentReq", [i.text for i in items], [(i.scores, i.reasons, i.score) for i in items],
                    conf_final, res["llm_calls"] - len(reqs) + final_conf_calls, st.threshold),
    ]

    # ---- Optional ablation: no smell feedback ----
    abl_res = None
    if args.ablation:
        print("Ablation (AgentReq without smell feedback):")
        pre = {i.id: (i.orig_scores, i.orig_reasons, i.orig_score) for i in originals}
        abl_agent = AgentReq(gen, judge, st, project, use_smells=False)
        abl_res = abl_agent.run(reqs, preeval=pre)
        abl_items = abl_res["items"]
        c0 = calls()
        conf_abl = find_conflicts(judge, project, [(i.id, i.text) for i in abl_items])
        arms.append(arm_metrics("AgentReq w/o smell agent", [i.text for i in abl_items],
                                [(i.scores, i.reasons, i.score) for i in abl_items], conf_abl,
                                abl_res["llm_calls"] + calls() - c0, st.threshold))

    # ---- Write outputs ----
    out = lambda name: os.path.join(args.out, name)
    write_csv(out("arms_summary.csv"), arms)
    write_csv(out("iteration_log.csv"), res["history"])
    if abl_res:
        write_csv(out("iteration_log_ablation.csv"), abl_res["history"])

    per_req = []
    for r, bt, be in zip(reqs, base_texts, base_evals):
        lineage = [i for i in items if i.parent == r["id"]]
        orig = next(i for i in lineage if i.original)
        per_req.append({
            "id": r["id"],
            "original": r["text"],
            "baseline_rewrite": bt,
            "agentreq_rewrite": " || ".join(i.text for i in lineage),
            "orig_score": round(orig.orig_score, 2),
            "baseline_score": round(be[2], 2),
            "agentreq_score": round(mean(i.score for i in lineage), 2),
            "orig_smells": len(rule_smells(r["text"])),
            "baseline_smells": len(rule_smells(bt)),
            "agentreq_smells": sum(len(rule_smells(i.text)) for i in lineage),
            "rounds_changed": orig.changes,
            "assumptions_to_confirm": " | ".join(a for i in lineage for a in i.assumptions),
        })
    write_csv(out("per_requirement.csv"), per_req)

    write_csv(out("manual_rating_sheet.csv"), [
        {"id": p["id"], "original": p["original"], "baseline_rewrite": p["baseline_rewrite"],
         "agentreq_rewrite": p["agentreq_rewrite"],
         "rater1_baseline_vs_original": "", "rater1_agentreq_vs_original": "",
         "rater2_baseline_vs_original": "", "rater2_agentreq_vs_original": "",
         "note": "fill with: better / same / worse"} for p in per_req])

    json.dump({
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "mock_mode": mock, "generator_model": gen.model, "judge_model": judge.model,
        "settings": vars(st), "stop_reason": res["stop_reason"],
        "conflicts_original": conf_orig, "conflicts_agentreq": conf_final,
        "items": [{"id": i.id, "parent": i.parent, "original": i.original, "final": i.text,
                   "trace": i.trace, "assumptions": i.assumptions, "final_reasons": i.reasons}
                  for i in items],
    }, open(out("run_log.json"), "w", encoding="utf-8"), indent=2)

    # ---- Charts ----
    names = {a["arm"]: a for a in arms}
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot([h["round"] for h in res["history"]], [h["doc_score"] for h in res["history"]],
            marker="o", linewidth=2.4, label="AgentReq", color="#1f4e9c")
    if abl_res:
        ax.plot([h["round"] for h in abl_res["history"]], [h["doc_score"] for h in abl_res["history"]],
                marker="s", linewidth=1.8, linestyle="-.", label="AgentReq w/o smell agent", color="#2a9d8f")
    ax.axhline(names["Original"]["doc_score"], linestyle="--", color="#777", label="Original")
    ax.axhline(names["Single-prompt baseline"]["doc_score"], linestyle=":", color="#d4651c",
               linewidth=2, label="Single-prompt baseline")
    ax.axhline(st.threshold, linestyle=(0, (1, 4)), color="#444", linewidth=1, label=f"Threshold {st.threshold}")
    ax.set_xlabel("Refinement round")
    ax.set_ylabel("Document quality score (1-5)")
    ax.set_title("Document quality score per round" + (" (MOCK)" if mock else ""))
    ax.set_ylim(1, 5.2)
    ax.set_xticks(range(0, max(h["round"] for h in res["history"]) + 1))
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out("score_by_iteration.png"), dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    width = 0.8 / len(arms)
    colours = ["#8d99ae", "#d4651c", "#1f4e9c", "#2a9d8f"]
    for k, a in enumerate(arms):
        xs = [i + k * width for i in range(len(CRITERIA))]
        ax.bar(xs, [a[f"crit_{c}"] for c in CRITERIA], width, label=a["arm"], color=colours[k])
    ax.set_xticks([i + width * (len(arms) - 1) / 2 for i in range(len(CRITERIA))])
    ax.set_xticklabels(CRITERIA)
    ax.set_ylabel("Mean score (1-5)")
    ax.set_ylim(0, 5.3)
    ax.set_title("Score per ISO 29148 characteristic" + (" (MOCK)" if mock else ""))
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out("criteria_by_arm.png"), dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar([a["arm"] for a in arms], [a["smell_total"] for a in arms], color=colours[:len(arms)])
    ax.bar_label(bars)
    ax.set_ylabel("Rule-based smells found (all requirements)")
    ax.set_title("Requirement smells (no LLM involved)" + (" (MOCK)" if mock else ""))
    plt.setp(ax.get_xticklabels(), rotation=12, ha="right")
    fig.tight_layout()
    fig.savefig(out("smells_by_arm.png"), dpi=200)
    plt.close(fig)

    # ---- Summary ----
    L = []
    if mock:
        L.append("> **MOCK MODE: these numbers come from an offline stub and are NOT results.**\n")
    L.append(f"# AgentReq experiment summary\n\nRun: {datetime.datetime.now():%Y-%m-%d %H:%M} | "
             f"generator `{gen.model}` | judge `{judge.model}` | {len(reqs)} requirements | "
             f"threshold {st.threshold} | stop reason: **{res['stop_reason']}**\n")
    if gen.model == judge.model:
        L.append("_Note: the same model rewrites and scores, so scores may be optimistic. "
                 "Set JUDGE_MODEL to a different model if you can._\n")
    L.append("## Arms compared\n\n| Arm | Doc score | Pass rate | Smells | Reqs with smells | Conflicts | LLM calls |\n|---|---|---|---|---|---|---|")
    for a in arms:
        L.append(f"| {a['arm']} | {a['doc_score']:.2f} | {a['pass_rate']*100:.0f}% | {a['smell_total']} | "
                 f"{a['items_with_smells']}/{a['n_requirements']} | {a['conflicts']} | {a['llm_calls']} |")
    L.append("\nPass rate = share of requirements with a mean score >= threshold. "
             "Smells are counted by regex rules, so they do not depend on the judge model.\n")
    L.append("## Score per round (AgentReq)\n\n| Round | Doc score | Below threshold | Smells | Requirements | LLM calls so far |\n|---|---|---|---|---|---|")
    for h in res["history"]:
        L.append(f"| {h['round']} | {h['doc_score']:.2f} | {h['n_weak']} | {h['smell_total']} | "
                 f"{h['n_requirements']} | {h['llm_calls_total']} |")
    L.append("\n## Mean score per characteristic\n\n| Arm | " + " | ".join(CRITERIA) + " |\n|---|" + "---|" * len(CRITERIA))
    for a in arms:
        L.append(f"| {a['arm']} | " + " | ".join(f"{a[f'crit_{c}']:.2f}" for c in CRITERIA) + " |")
    best = sorted(per_req, key=lambda p: p["agentreq_score"] - p["orig_score"], reverse=True)[:3]
    L.append("\n## Example rewrites (largest improvement)\n")
    for p in best:
        L.append(f"**{p['id']}** ({p['orig_score']} -> {p['agentreq_score']})\n\n- Original: {p['original']}\n"
                 f"- Single prompt: {p['baseline_rewrite']}\n- AgentReq: {p['agentreq_rewrite']}\n")
    L.append("## Still to do by hand\n\n- Fill `manual_rating_sheet.csv` (two raters) and report the share of rewrites rated better.\n"
             "- Confirm the values listed in `per_requirement.csv` > `assumptions_to_confirm`.\n")
    open(out("summary.md"), "w", encoding="utf-8").write("\n".join(L))

    print(f"\nDone. See {args.out}/summary.md")
    for a in arms:
        print(f"  {a['arm']:<26} doc score {a['doc_score']:.2f}  pass {a['pass_rate']*100:.0f}%  smells {a['smell_total']}")


if __name__ == "__main__":
    try:
        main()
    except LLMError as e:
        sys.exit(f"\nStopped: {e}")