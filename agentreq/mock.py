"""Offline stand-in for an LLM. It exists ONLY so the pipeline can be tested without an API key.
Its scores and rewrites come from simple rules, so numbers produced with it mean nothing
for the project and must never be reported as results."""
import json
import re

from .config import CRITERIA
from .smells import rule_smells

_REPLACE = {
    r"\bfast and respond quickly\b": "respond within 2 seconds",
    r"\bfast\b": "within 2 seconds",
    r"\bquickly\b": "within 5 seconds",
    r"\buser-friendly and easy to use\b": "usable by a first-time user without training",
    r"\bsimple and clean\b": "uncluttered, with at most 3 taps to reach any function",
    r"\bsupport a large number of\b": "support at least 50",
    r"\bappropriate security\b": "AES-256 encryption",
    r"\bmost of the time\b": "99.5% of the time",
    r"\bcommon smart home devices\b": "devices that use the Zigbee or Z-Wave protocols",
    r"\bmost phones\b": "Android 10 and later and iOS 15 and later",
    r"\bas needed\b": "when the room temperature differs from the target by more than 1 degree Celsius",
    r"\bquickly after\b": "within 30 seconds after",
    r"\betc\.?": "",
    r"\bshould\b": "shall",
}


def _rewrite(text: str, full: bool = True) -> str:
    out = text
    items = list(_REPLACE.items()) if full else list(_REPLACE.items())[:3]
    for pat, rep in items:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).replace(" ,", ",").replace(" .", ".").strip()


def _split(text: str):
    parts = re.split(r"\s+and\s+(?=(?:allow|send|notify|lock|delete|export|respond)\b)", text, maxsplit=3)
    if len(parts) == 1:
        return text, []
    head = parts[0].rstrip(". ")
    rest = []
    actor = "The system"
    for p in parts[1:]:
        rest.append(f"{actor} shall {p.strip().rstrip('.')}.")
    return head + ".", rest


def mock_reply(task: str, payload: dict) -> str:
    if task == "evaluate":
        text = payload["requirement"]
        sm = rule_smells(text)
        vague = sum(1 for s in sm if s["type"] == "vague_term")
        scores = {
            "unambiguous": max(1, 5 - 2 * vague),
            "complete": 3 if len(text.split()) < 9 else 4,
            "verifiable": 4 if re.search(r"\d", text) else 2,
            "singular": 2 if any(s["type"] == "not_singular" for s in sm) else 5,
            "appropriate": 4,
        }
        return json.dumps({c: {"score": scores[c], "reason": "mock score"} for c in CRITERIA})
    if task == "refine":
        main, split_off = _split(_rewrite(payload["requirement"]))
        return json.dumps({"rewritten": main, "split_off": split_off, "assumptions": ["mock value"]})
    if task == "baseline":
        return _rewrite(payload["requirement"], full=False)
    if task == "conflicts":
        return json.dumps({"conflicts": []})
    raise ValueError(f"mock: unknown task {task}")
