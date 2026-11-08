# AgentReq experiment summary

Run: 2026-11-07 17:49 | generator `openai/gpt-oss-20b` | judge `openai/gpt-oss-20b` | 32 requirements | threshold 4.0 | stop reason: **all_pass**

_Note: the same model rewrites and scores, so scores may be optimistic. Set JUDGE_MODEL to a different model if you can._

## Arms compared

| Arm | Doc score | Pass rate | Smells | Reqs with smells | Conflicts | LLM calls |
|---|---|---|---|---|---|---|
| Original | 3.56 | 50% | 18 | 18/32 | 0 | 33 |
| Single-prompt baseline | 4.84 | 100% | 23 | 17/32 | 0 | 65 |
| AgentReq | 4.62 | 100% | 12 | 12/32 | 0 | 37 |
| AgentReq w/o smell agent | 4.61 | 100% | 13 | 13/32 | 0 | 35 |

Pass rate = share of requirements with a mean score >= threshold. Smells are counted by regex rules, so they do not depend on the judge model.

## Score per round (AgentReq)

| Round | Doc score | Below threshold | Smells | Requirements | LLM calls so far |
|---|---|---|---|---|---|
| 0 | 3.56 | 16 | 18 | 32 | 32 |
| 1 | 4.57 | 2 | 12 | 32 | 64 |
| 2 | 4.62 | 0 | 12 | 32 | 68 |

## Mean score per characteristic

| Arm | unambiguous | complete | verifiable | singular | appropriate |
|---|---|---|---|---|---|
| Original | 3.28 | 2.50 | 3.56 | 4.62 | 3.81 |
| Single-prompt baseline | 4.78 | 4.66 | 4.97 | 4.88 | 4.94 |
| AgentReq | 4.66 | 3.81 | 4.78 | 5.00 | 4.88 |
| AgentReq w/o smell agent | 4.56 | 3.78 | 4.88 | 4.91 | 4.91 |

## Example rewrites (largest improvement)

**R03** (1.4 -> 5.0)

- Original: Folder selected must be of type the database can read and that is “name”.kdb
- Single prompt: The application must allow the user to select a folder only if the folder contains a file named exactly “name.kdb” (where “name” is the user‑supplied database name). The selected folder must be a valid directory that the database can read; otherwise the selection must be rejected and an appropriate error message displayed.
- AgentReq: The user shall select a folder that contains a file with the extension ".kdb" and that is readable by the application.

**R19** (1.6 -> 5.0)

- Original: The prefix “Auto-Type:” is required in front of each sequence
- Single prompt: **Requirement**  
When a user defines an auto‑type sequence in KeePass, the sequence must begin with the literal prefix `Auto-Type:`. The prefix is case‑sensitive, must be the first token in the sequence, and must be followed by a space before the rest of the sequence. If the prefix is omitted or misspelled, the sequence must be rejected and an error message displayed.
- AgentReq: The system shall prefix each auto‑type sequence with the string "Auto-Type:".

**R04** (1.8 -> 5.0)

- Original: Databases must have different names or else the previews one will be replace if selected
- Single prompt: All KeePass databases opened within a single session must have unique names; if a user attempts to open a database whose name matches an already open database, the application must prompt the user to choose a different name or to close the existing instance before opening the new one, thereby preventing accidental replacement of the preview.
- AgentReq: The user shall create a database with a name that is unique among all existing databases; if a database with the same name already exists, the system shall prompt the user to choose a different name before creating the new database.

## Still to do by hand

- Fill `manual_rating_sheet.csv` (two raters) and report the share of rewrites rated better.
- Confirm the values listed in `per_requirement.csv` > `assumptions_to_confirm`.
