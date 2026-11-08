"""Baseline: ask the same LLM once, with a single plain prompt, to 'improve' each requirement."""
from .prompts import BASELINE_SYSTEM, baseline_user


def single_prompt_rewrite(gen, project: str, text: str) -> str:
    out = gen.chat(BASELINE_SYSTEM, baseline_user(project, text), task="baseline",
                   payload={"requirement": text}).strip()
    out = out.strip("`").strip()
    if out.lower().startswith("improved requirement:"):
        out = out.split(":", 1)[1].strip()
    return out or text
