"""The closed loop: score -> find weak requirements -> refine -> re-score, until they pass,
the score stops improving, or the round limit is reached."""
from dataclasses import dataclass, field

from .config import Settings
from .evaluator import evaluate_text
from .refiner import build_feedback, refine
from .smells import rule_smells, smells_as_text


@dataclass
class Item:
    id: str
    parent: str                 # id of the original requirement this one came from
    original: str
    text: str
    scores: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)
    score: float = 0.0
    orig_scores: dict = field(default_factory=dict)
    orig_reasons: dict = field(default_factory=dict)
    orig_score: float = 0.0
    assumptions: list = field(default_factory=list)
    changes: int = 0
    fails: int = 0
    trace: list = field(default_factory=list)   # (round, text, score)


class AgentReq:
    def __init__(self, gen, judge, settings: Settings, project: str, use_smells: bool = True, log=print):
        self.gen, self.judge, self.st = gen, judge, settings
        self.project, self.use_smells, self.log = project, use_smells, log

    # ---- helpers -------------------------------------------------------
    def _calls(self) -> int:
        return self.gen.calls + self.judge.calls

    def _snapshot(self, rnd: int, items: list) -> dict:
        n = len(items)
        smell_counts = [len(rule_smells(i.text)) for i in items]
        return {
            "round": rnd,
            "doc_score": sum(i.score for i in items) / n,
            "n_requirements": n,
            "n_weak": sum(1 for i in items if i.score < self.st.threshold),
            "pass_rate": sum(1 for i in items if i.score >= self.st.threshold) / n,
            "smell_total": sum(smell_counts),
            "items_with_smells": sum(1 for c in smell_counts if c),
            "llm_calls_total": self._calls(),
        }

    # ---- main loop -----------------------------------------------------
    def run(self, reqs: list, preeval: dict = None) -> dict:
        """reqs: list of {'id','text'}. preeval: optional {id: (scores, reasons, mean)} to skip
        re-scoring the originals (used by the ablation run)."""
        start_calls = self._calls()
        items = []
        for r in reqs:
            if preeval and r["id"] in preeval:
                sc, why, mean = preeval[r["id"]]
            else:
                sc, why, mean = evaluate_text(self.judge, self.project, r["text"])
            it = Item(id=r["id"], parent=r["id"], original=r["text"], text=r["text"],
                      scores=sc, reasons=why, score=mean, orig_scores=dict(sc),
                      orig_reasons=dict(why), orig_score=mean)
            it.trace.append((0, r["text"], mean))
            items.append(it)
        history = [self._snapshot(0, items)]
        self.log(f"  round 0: doc score {history[0]['doc_score']:.2f}, "
                 f"{history[0]['n_weak']}/{len(items)} below {self.st.threshold}")
        stop = "max_rounds"

        for rnd in range(1, self.st.max_rounds + 1):
            weak = [i for i in items if i.score < self.st.threshold and i.fails < self.st.max_failed_tries]
            if not weak:
                stop = "all_pass"
                break
            for it in weak:
                self._improve(it, items, rnd)
            snap = self._snapshot(rnd, items)
            history.append(snap)
            gain = snap["doc_score"] - history[-2]["doc_score"]
            self.log(f"  round {rnd}: doc score {snap['doc_score']:.2f} (+{gain:.2f}), "
                     f"{snap['n_weak']}/{snap['n_requirements']} below {self.st.threshold}")
            if gain < self.st.min_gain:
                stop = "no_gain"
                break
        else:
            stop = "max_rounds"

        return {"items": items, "history": history, "stop_reason": stop,
                "llm_calls": self._calls() - start_calls}

    def _improve(self, it: Item, items: list, rnd: int):
        smells = smells_as_text(rule_smells(it.text)) if self.use_smells else []
        feedback = build_feedback(it.scores, it.reasons, smells, self.st.threshold)
        try:
            out = refine(self.gen, self.project, it.text, feedback)
        except (ValueError, TypeError) as e:
            it.fails += 1
            self.log(f"    {it.id}: refiner reply unusable ({e})")
            return
        main_sc, main_why, main_mean = evaluate_text(self.judge, self.project, out["rewritten"])
        split_evals = [(t, *evaluate_text(self.judge, self.project, t)) for t in out["split_off"]]
        cand_mean = (main_mean + sum(e[3] for e in split_evals)) / (1 + len(split_evals))
        if cand_mean <= it.score:
            it.fails += 1          # keep the old text: never accept a worse (or equal) rewrite
            return
        it.text, it.scores, it.reasons, it.score = out["rewritten"], main_sc, main_why, main_mean
        it.assumptions += out["assumptions"]
        it.changes += 1
        it.fails = 0
        it.trace.append((rnd, it.text, it.score))
        pos = items.index(it) + 1
        for k, (t, sc, why, mean) in enumerate(split_evals, start=1):
            new = Item(id=f"{it.id}.{k}", parent=it.parent, original="", text=t, scores=sc,
                       reasons=why, score=mean, assumptions=[f"split from {it.id}"])
            new.trace.append((rnd, t, mean))
            items.insert(pos, new)
            pos += 1
