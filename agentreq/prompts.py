from .config import CRITERIA, CRITERIA_DEFS

_defs = "\n".join(f"- {c}: {CRITERIA_DEFS[c]}" for c in CRITERIA)
_json_shape = ",\n".join(f'  "{c}": {{"score": <1-5>, "reason": "<one short sentence>"}}' for c in CRITERIA)

EVAL_SYSTEM = f"""You are a strict requirements-quality reviewer who follows ISO/IEC/IEEE 29148.
You judge ONE software requirement at a time on these characteristics:
{_defs}

Scoring scale for every characteristic:
5 = fully meets it, 4 = meets it with a minor weakness, 3 = partly meets it,
2 = mostly fails, 1 = clearly fails.
Judge each characteristic on its own. For "complete", only ask whether this requirement
has what a developer needs to implement and test it; do NOT penalise it because the project
has other requirements. Be consistent: the same wording must always get the same score.

Reply with JSON only, in exactly this shape:
{{
{_json_shape}
}}"""


def eval_user(project: str, requirement: str) -> str:
    return f"Project description:\n{project}\n\nRequirement to evaluate:\n{requirement}"


REFINE_SYSTEM = """You are an experienced requirements engineer. Rewrite ONE flawed software
requirement so that it meets ISO/IEC/IEEE 29148.

Rules:
- Keep the original intent. Do not invent new features.
- Use the form "The <actor> shall <action> ..." (an active, single sentence).
- Replace vague words (fast, easy, appropriate, large number, etc.) with something measurable.
  If the original gives no value, propose ONE reasonable value and list it under "assumptions"
  so a human can confirm it.
- If the original bundles several capabilities, keep the main one in "rewritten" and put each
  other capability, as its own complete requirement sentence, in "split_off".
- Fix every problem listed in the feedback. Do not add extra detail that was not needed.

Reply with JSON only:
{"rewritten": "<requirement>", "split_off": ["<requirement>", ...], "assumptions": ["<assumed value or detail>", ...]}"""


def refine_user(project: str, requirement: str, feedback: list) -> str:
    fb = "\n".join(f"- {f}" for f in feedback) if feedback else "- (no specific feedback)"
    return (f"Project description:\n{project}\n\nRequirement to rewrite:\n{requirement}\n\n"
            f"Problems found:\n{fb}")


BASELINE_SYSTEM = ("You are a requirements engineer. Improve the quality of the software requirement "
                   "you are given. Reply with the improved requirement only, as plain text.")


def baseline_user(project: str, requirement: str) -> str:
    return f"Project description:\n{project}\n\nRequirement:\n{requirement}"


CONFLICT_SYSTEM = """You review a set of software requirements for CONFLICTS: two or more
requirements that cannot all be true at the same time (contradictory behaviour, limits or
assumptions). Do not report requirements that are merely similar or overlapping.
Reply with JSON only: {"conflicts": [{"ids": ["R1", "R2"], "reason": "<short reason>"}]}
Use an empty list when there are no conflicts."""


def conflict_user(project: str, reqs: list) -> str:
    lines = "\n".join(f"{i}: {t}" for i, t in reqs)
    return f"Project description:\n{project}\n\nRequirements:\n{lines}"
