from dataclasses import dataclass

# ISO/IEC/IEEE 29148 characteristics we score (a subset of the nine, the ones
# an LLM can judge from the text of one requirement).
CRITERIA = ["unambiguous", "complete", "verifiable", "singular", "appropriate"]

CRITERIA_DEFS = {
    "unambiguous": "Stated clearly, allows only one interpretation, no vague words.",
    "complete": "Contains everything needed to understand and implement it "
                "(actor, action, condition, limits) without guessing.",
    "verifiable": "Written so that fulfilment can be proven or measured by a test.",
    "singular": "Describes exactly one capability or constraint.",
    "appropriate": "Right level of abstraction: no unnecessary design or "
                   "implementation detail, no unneeded constraints.",
}


@dataclass
class Settings:
    threshold: float = 4.0    # a requirement passes when its mean score >= this
    max_rounds: int = 4       # hard limit on refinement rounds
    min_gain: float = 0.02    # stop if the document score improves by less
    max_failed_tries: int = 2  # give up on a requirement after this many non-improving rewrites
