"""Refiner agent: rewrites one weak requirement using the evaluator's reasons and the smells."""
from .config import CRITERIA
from .prompts import REFINE_SYSTEM, refine_user


def build_feedback(scores: dict, reasons: dict, smells_text: list, pass_mark: float = 4.0) -> list:
    fb = [f"{c} scored {scores[c]:.0f}/5: {reasons.get(c, '')}".strip()
          for c in CRITERIA if scores[c] < pass_mark]
    fb += [f"smell detected -> {s}" for s in smells_text]
    return fb


def refine(gen, project: str, text: str, feedback: list) -> dict:
    payload = {"requirement": text, "feedback": feedback}
    data = gen.chat_json(REFINE_SYSTEM, refine_user(project, text, feedback), task="refine", payload=payload)
    if not isinstance(data, dict) or not str(data.get("rewritten", "")).strip():
        raise ValueError("refiner reply has no 'rewritten' text")
    return {
        "rewritten": str(data["rewritten"]).strip(),
        "split_off": [str(s).strip() for s in data.get("split_off", []) if str(s).strip()],
        "assumptions": [str(a).strip() for a in data.get("assumptions", []) if str(a).strip()],
    }
