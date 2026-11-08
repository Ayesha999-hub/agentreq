"""Evaluator agent: scores one requirement 1-5 on each ISO 29148 characteristic."""
from .config import CRITERIA
from .prompts import EVAL_SYSTEM, eval_user


def _parse(data) -> tuple:
    scores, reasons = {}, {}
    if not isinstance(data, dict):
        raise ValueError("evaluator reply is not an object")
    for c in CRITERIA:
        item = data.get(c)
        if isinstance(item, dict):
            val, why = item.get("score"), item.get("reason", "")
        else:
            val, why = item, ""
        val = float(val)
        scores[c] = min(5.0, max(1.0, val))
        reasons[c] = str(why)
    return scores, reasons


def evaluate_text(judge, project: str, text: str) -> tuple:
    """Returns (scores dict, reasons dict, mean score)."""
    payload = {"requirement": text}
    last_err = None
    for _ in range(2):
        try:
            data = judge.chat_json(EVAL_SYSTEM, eval_user(project, text), task="evaluate", payload=payload)
            scores, reasons = _parse(data)
            return scores, reasons, sum(scores.values()) / len(scores)
        except (ValueError, TypeError) as e:
            last_err = e
    raise RuntimeError(f"Evaluator could not parse the judge reply for: {text!r} ({last_err})")
