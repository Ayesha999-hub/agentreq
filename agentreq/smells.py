"""Requirement smell detection: a rule-based part (no LLM, so it is a judge-independent
metric) and an LLM part that looks for conflicts between requirements."""
import re

from .prompts import CONFLICT_SYSTEM, conflict_user

VAGUE_TERMS = [
    "fast", "quick", "quickly", "rapid", "rapidly", "easy", "easily", "user-friendly",
    "user friendly", "intuitive", "simple", "clean", "efficient", "efficiently",
    "flexible", "robust", "appropriate", "adequate", "sufficient", "reasonable",
    "as needed", "as required", "as appropriate", "as per", "as much as possible",
    "if possible", "where possible", "optimal", "optimized", "minimal", "significant",
    "large number", "most of the time", "most phones", "common", "several", "various",
    "some", "many", "few", "and so on", "and/or", "tbd", "tbc", "to be determined",
    "state-of-the-art", "modern", "seamless", "seamlessly", "high performance",
    "good", "better", "best", "normal", "usual", "secure", "reliable", "scalable",
    "maintainable",
]
_VAGUE_RE = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(t) for t in sorted(VAGUE_TERMS, key=len, reverse=True)) + r")(?![\w-])",
    re.IGNORECASE,
)
_ETC_RE = re.compile(r"\betc\b\.?", re.IGNORECASE)
_WEAK_RE = re.compile(r"\b(should|may|might|could)\b", re.IGNORECASE)
_MODAL_RE = re.compile(r"\b(shall|must|will|should)\b", re.IGNORECASE)
_ACTION_VERBS = (
    "allow|display|send|notify|store|log|delete|export|turn|lock|provide|support|set|"
    "create|alert|show|record|respond|encrypt|generate|update|remove|add|share|"
    "monitor|detect|schedule|sync|upload|download|print|report"
)
_MULTI_RE = re.compile(r"\b(and|or)\b\s+(?:\w+\s+){0,3}?(?:" + _ACTION_VERBS + r")\b", re.IGNORECASE)


def rule_smells(text: str) -> list:
    """Return a list of {'type', 'text'} smells found by simple rules."""
    smells = []
    for m in _VAGUE_RE.finditer(text):
        smells.append({"type": "vague_term", "text": m.group(1).lower()})
    for m in _ETC_RE.finditer(text):
        smells.append({"type": "vague_term", "text": "etc."})
    for m in _WEAK_RE.finditer(text):
        if m.group(1).lower() != "should":  # 'should' is handled by the modal check below
            smells.append({"type": "weak_modal", "text": m.group(1).lower()})
    modals = [m.group(1).lower() for m in _MODAL_RE.finditer(text)]
    if not modals:
        smells.append({"type": "no_modal", "text": "no shall/must"})
    elif "shall" not in modals and "must" not in modals:
        smells.append({"type": "weak_modal", "text": modals[0]})
    if len(re.findall(r"\bshall\b", text, re.IGNORECASE)) >= 2 or _MULTI_RE.search(text):
        smells.append({"type": "not_singular", "text": "several actions joined by and/or"})
    return smells


def smells_as_text(smells: list) -> list:
    return [f"{s['type']}: {s['text']}" for s in smells]


def find_conflicts(llm, project: str, reqs: list) -> list:
    """reqs: list of (id, text). Returns a list of {'ids': [...], 'reason': str}."""
    if len(reqs) < 2:
        return []
    data = llm.chat_json(
        CONFLICT_SYSTEM, conflict_user(project, reqs),
        task="conflicts", payload={"reqs": reqs},
    )
    out = []
    if isinstance(data, dict):
        data = data.get("conflicts", [])
    for c in data or []:
        if isinstance(c, dict) and len(c.get("ids", [])) >= 2:
            out.append({"ids": [str(i) for i in c["ids"]], "reason": str(c.get("reason", ""))})
    return out
