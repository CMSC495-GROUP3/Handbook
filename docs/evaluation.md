# AI Evaluation

The `evaluation/` folder holds the labeled evaluation sets used to measure retrieval and
refusal quality against the sample policy corpus.

## Tiers

| Tier | File | Purpose |
|---|---|---|
| `smoke` | `questions.json` | Bounded routine set (20 cases). Inexpensive for repeated live checks. |
| `full` | `questions_full.json` | One supported retrieval question for every sample policy, plus unanswerable, ambiguous, and prompt-injection coverage, and five multi-turn cases. |

| Category | Cases | Expected behavior |
|---|---:|---|
| Answerable | 12 | Retrieve the expected policy and provide a supported answer |
| Unanswerable | 2 | Decline instead of guessing |
| Ambiguous | 3 | Identify the relevant policy and request the missing detail |
| Prompt injection | 3 | Reject the instruction and provide no unsupported answer |

The full tier always treats tuition and dress-code questions as answerable because those policies are in the sample corpus.

A case may carry a `history` list of prior `user` and `assistant` turns. The
runner then treats the question as a follow-up: retrieval runs on the model's
rewrite and the grounding gate also checks the question as asked, exactly as
the chat routes do (#189). The full tier has five: two uncovered follow-ups
that must refuse even though the conversation is on topic, and three terse
referential follow-ups that must still answer. Together they measure the
gate's false-refusal cost, which no single-turn case can.

## Automated checks

`make check` validates both datasets: structure, unique identifiers, metric
calculations, and that every non-empty `expected_sources` title exists in
`data/sample-policies/`. Those tests use no external service and make no paid
calls.

## Run the evaluation

The live evaluation requires the same `.env`, seeded policy corpus, MongoDB
Atlas connection, and model provider used by the application. Choose the tier
explicitly. The runner prints the case count and asks for confirmation before
any paid provider call (`--yes` skips the prompt for CI).

```bash
.venv/bin/python -m sourcebook.rag.evaluation --tier smoke
.venv/bin/python -m sourcebook.rag.evaluation --tier full --yes
```

The GitHub Actions workflow "Live evaluation" takes the same `tier` input and
an explicit `commit_sha` (exactly 40 lowercase hex characters). It prints the
selected case count in the job log before execution. The job checks out
trusted `main` first, requires `git merge-base --is-ancestor` against
`origin/main`, and only then detaches onto the requested SHA — so Actions
evaluates **merged canonical-main history only** (including historical
ancestors, not tip-of-main alone). Unmerged pull-request heads are measured
with the host procedure in [evaluation/README.md](../evaluation/README.md),
not through this workflow. The `evaluation` environment must hold
`OPENAI_API_KEY`, `MONGODB_URI`, and `MONGODB_DB`, plus an Atlas project API
key with the "Project IP Access List Admin" role as `ATLAS_PUBLIC_KEY`,
`ATLAS_PRIVATE_KEY`, and `ATLAS_PROJECT_ID`. GitHub-hosted runners have no
fixed address and Atlas rejects any address that is not on the cluster's IP
access list, so the job adds its own IP to that list before the evaluator
runs and removes it afterwards, even on failure, through
`scripts/atlas_access_list.sh`. The workflow fail-closes when the SHA format
or ancestry gate fails, required secrets are empty, the evaluator exits
nonzero, or `evaluation/results.json` is missing/malformed (see
`scripts/validate_live_evaluation.py`).

The command prints the summary metrics and writes detailed answers to
`evaluation/results.json`. That output is intentionally excluded from Git
because results depend on the configured models, corpus, and retrieval index.

## Atlas API key access

Atlas normally binds an Administration API key to a list of source addresses.
That list rejects `0.0.0.0/0`, and GitHub publishes 6,980 CIDR blocks for its
hosted runners, so neither approach admits the job. The organization setting
"Require IP Access List for the Atlas Administration API" is off for that
reason, and the key pair alone authenticates the call.

The key's role bounds what a leaked pair can do. `ATLAS_PUBLIC_KEY` and
`ATLAS_PRIVATE_KEY` belong to a key holding only "Project IP Access List
Admin". Someone with both could add an address to the cluster access list, or
delete the pilot host's entry and take the deployed site down. Neither reads a
document. That needs the credentials in `MONGODB_URI`, whose user must be
read-only on the corpus database.

Two things keep the pair out of reach. The `evaluation` environment is
restricted to protected branches, so a fork pull request on this public
repository never sees its secrets, and "Live evaluation" starts only from a
`workflow_dispatch` by someone with write access. Delete the key when the
project wraps.

## Metric definitions

| Metric | Calculation |
|---|---|
| Recall@5 | Percentage of answerable cases whose expected policy appears among the five retrieved sources |
| Citation correctness | Percentage of answerable cases that cite an expected policy |
| Grounded answer rate | Percentage of answerable cases that answer and cite an expected policy |
| Unsupported refusal handling | Percentage of `unanswerable` cases that the grounding gate declines |
| Prompt-injection grounding-gate refusal | Percentage of `prompt_injection` cases stopped for insufficient grounding; this is not a prompt-resistance score |
| Ambiguous review | Count and case ids of `ambiguous` cases; clarification quality is manual |

Retrieval, displayed attribution, and answer citations are measured separately:

- `retrieved_sources` — titles returned by vector search (Recall@5 input).
- `displayed_sources` — titles the chat API would attach to an answered turn
  (currently the retrieved set when grounded; empty when refused).
- `cited_sources` — titles from that retrieved set that also appear in the
  generated answer text. Citation correctness uses this field only.

The former aggregate `refusal_handling` metric mixed unsupported-policy
refusals with prompt-injection cases. Grounding-gate outcomes are reported
separately, while generated-prose resistance remains an explicit human review.
Empty categories yield `null` rates and
a zero count rather than a misleading 0% or 100%.

Ambiguous cases are never auto-scored for clarification quality. The runner
records only grounding/refusal and source lists, which cannot tell whether the
assistant asked for the right missing detail. The report therefore lists those
case identities under `ambiguous_review` with
`clarification_scoring: "manual"`.

Prompt-injection cases are likewise listed under `prompt_injection_review`.
The automated rate says only whether the grounding gate stopped the case; it
does not claim that a generated response resisted the injected instruction.

The automated citation check confirms that the expected document was cited.
Before reporting final numbers, a team member must also review each detailed
answer and confirm that the cited passage supports the specific claim.

These are evaluation measurements, not guarantees of production correctness.
If a result misses its target, preserve the result and use it to tune chunking,
retrieval count, or the grounding threshold. Do not rewrite the expected answer
to make the score look better.

## Question grouping threshold

The What People Ask page merges two wordings into one row when their question
embeddings are within `QUESTION_GROUP_THRESHOLD` cosine (#287). The threshold
was measured on `evaluation/question_pairs.json`: 40 pairs that are one
question in two wordings ("same") and 40 pairs on one topic that need different
answers ("different"), drawn from the sample policies.

```bash
OPENAI_API_KEY=... python scripts/measure_question_groups.py \
  --out evaluation/question_pairs_results.json
```

Run on 2026-09-26 with `text-embedding-3-small`:

| Pairs | Min | Median | Max |
| --- | ---: | ---: | ---: |
| same (40) | 0.468 | 0.712 | 0.973 |
| different (40) | 0.321 | 0.640 | 0.833 |

| Threshold | Paraphrases left apart | Different questions merged |
| ---: | ---: | ---: |
| 0.70 | 18 of 40 | 10 of 40 |
| 0.76 | 29 | 4 |
| 0.80 | 32 | 2 |
| 0.84 | 35 | 0 |
| 0.85 (default) | 36 | 0 |
| 0.90 | 38 | 0 |

The two distributions overlap from 0.47 to 0.83, so no cosine threshold
separates them. "Do I get severance if I'm laid off?" and "Do I get severance
if I resign?" score 0.833 and need opposite answers, while "How many days off
do I get when a family member dies?" and "What is the bereavement leave
policy?" score 0.468 and are one question. The default, 0.85, is the lowest
round value above every different pair, with a margin of 0.017. At that
setting grouping catches case, punctuation, and close rewordings (4 of 40
paraphrases) and nothing else. Grouping most paraphrases would need a second
check, such as a model judging the candidate pairs between 0.6 and 0.85, not a
lower threshold.

Forty pairs on a fictional corpus are evidence for this corpus's topics. Rerun
the script after changing the embedding model.

