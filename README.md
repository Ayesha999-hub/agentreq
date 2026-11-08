# AgentReq: closed-loop requirement quality improvement

A small multi-agent LLM workflow that finds quality problems in software requirements, scores
them on the ISO/IEC/IEEE 29148 characteristics, rewrites the weak ones and repeats until the
score passes a threshold. Group project by Ayesha Suleman (22I-2002) and Maheen Kamal (21I-1351),
BS Data Science, FAST-NUCES Islamabad. The design is inspired by MARE (Jin et al., 2024).

## How it works

1. **Evaluator agent** scores each requirement 1-5 on five characteristics: unambiguous,
   complete, verifiable, singular, appropriate. Requirement score = mean of the five.
   Document score = mean over all requirements.
2. **Smell agent** finds vague terms, weak modals, missing modals and bundled actions
   (rule-based, no LLM), and conflicts between requirements (LLM).
3. **Refiner agent** rewrites each requirement below the threshold (4.0) using the evaluator's
   reasons and the smells. Values it had to assume are listed for a human to confirm. Bundled
   requirements can be split.
4. **Controller loop** re-scores, keeps a rewrite only if it scores strictly better, and stops
   when everything passes, the gain is under 0.02, 4 rounds are used, or one requirement fails twice.
   Every round is logged.

The agents are prompt-based roles and the loop order is fixed in code. No LLM decides the next step.

## Results (PURE KeePass SRS, 32 requirements, gpt-oss-20b as writer and judge)

| Version | Document score (1-5) | Requirements >= 4.0 | Rule-based smells |
|---|---|---|---|
| Original | 3.56 | 50% | 18 |
| Single-prompt baseline | 4.84 | 100% | 23 |
| **AgentReq** | 4.62 | 100% | **12** |
| AgentReq without smell feedback (ablation) | 4.61 | 100% | 13 |

The loop went 3.56, 4.57, 4.62 over its rounds. The single-prompt baseline gets the highest
judged score but adds smells. AgentReq leaves the fewest smells. Smell counts come from rules, so
they do not depend on the LLM judge. The smell feedback itself adds only a small gain here.

**Limits:** one document, one model family, and the same model writes and judges, so scores may
be optimistic. Conflicts are detected but not yet fed to the Refiner. We did not compare with MARE.
LLM output can vary slightly between runs.

## Run it (Windows PowerShell or any shell)

```
pip install -r requirements.txt
copy .env.example .env        # then put your API key in .env (Linux/Mac: cp)
python run_experiment.py --ablation
```

Everything lands in `outputs/`:

| File | Use |
|---|---|
| `summary.md` | tables and example rewrites |
| `score_by_iteration.png` | document score per round |
| `criteria_by_arm.png`, `smells_by_arm.png` | extra figures |
| `arms_summary.csv`, `iteration_log.csv` | raw numbers |
| `per_requirement.csv` | original vs baseline vs AgentReq for each requirement |
| `manual_rating_sheet.csv` | two raters fill better / same / worse |
| `run_log.json` | full trace of every rewrite |

Options: `--data`, `--project`, `--out`, `--threshold`, `--rounds`, `--limit`, `--ablation`.

Answers are cached in `.llm_cache.jsonl`, so if a run stops (daily token limit, internet), run
the same command again and it continues. Delete the file, or set `LLM_NO_CACHE=1`, for a fresh run.
Set `JUDGE_MODEL` in `.env` to use a different model as the judge.
`LLM_PROVIDER=mock` is an offline stub for testing the code only. Never report its numbers.

## Code map

`agentreq/evaluator.py`, `smells.py`, `refiner.py`, `pipeline.py` (the loop), `baseline.py`,
`prompts.py` (all prompts), `llm.py` (any OpenAI-compatible API), `config.py` (criteria and
settings), `mock.py` (offline stub), and `run_experiment.py` (runs everything and writes outputs).

## Data and licence

Requirements come from the PURE dataset (Ferrari et al., Zenodo 10.5281/zenodo.1414117, CC BY 4.0),
see `data/README.md`. Code is under the MIT licence.
