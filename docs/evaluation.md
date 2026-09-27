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
was measured on `evaluation/question_pairs.json`: 60 pairs that are one
question in two wordings ("same") and 60 pairs on one topic that need different
answers ("different"), drawn from the sample policies. The first 80 were
written for #287 and the last 40 for #293.

```bash
OPENAI_API_KEY=... python scripts/measure_question_groups.py \
  --out evaluation/question_pairs_results.json
```

Run on 2026-09-27 with `text-embedding-3-small`:

| Pairs | Min | Median | Max |
| --- | ---: | ---: | ---: |
| same (60) | 0.468 | 0.720 | 0.973 |
| different (60) | 0.321 | 0.656 | 0.907 |

| Threshold | Paraphrases left apart | Different questions merged |
| ---: | ---: | ---: |
| 0.70 | 25 of 60 | 21 of 60 |
| 0.76 | 42 | 9 |
| 0.80 | 49 | 6 |
| 0.84 | 53 | 2 |
| 0.85 | 54 | 2 |
| 0.90 | 57 | 1 |
| 0.91 (default) | 57 | 0 |

The two distributions overlap from 0.47 to 0.91, so no cosine threshold
separates them. "Can I work from home when I'm sick?" and "Can I work from
home when my child is sick?" score 0.907 and need different answers, and "Can
I use my HSA for dental work?" against the same question about an FSA scores
0.862. Those are the two different pairs 0.85 merges. "How many days off do I
get when a family member dies?" and "What is the bereavement leave policy?"
score 0.468 and are one question. On the first 80 pairs the closest different
pair scored 0.833, which is why 0.85 was picked first; the 40 added for #293
include pairs that differ by one word, and two of them clear it. The default
is now 0.91, the lowest round value above every different pair again, and
pairs between the floor and it go to the model check below. On cosine alone,
which is what the page falls back to when that check fails, 0.91 groups only
case and punctuation changes (3 of 60 paraphrases) and nothing else. Grouping
most paraphrases needs a second check, not a lower threshold.

A hundred and twenty pairs on a fictional corpus are evidence for this
corpus's topics. Rerun the script after changing the embedding model.

### The model check below the threshold

Pairs from `QUESTION_JUDGE_FLOOR` up to the threshold go to the utility model, which
decides whether they are one question (#293). `--judge` scores that combined
rule on the same pairs. Each floor is judged on its own: its band goes to the
model in batches the size of `QUESTION_JUDGE_MAX_PAIRS`, closest first, as the
page would send them at that floor. A pair's neighbours in a batch can change
its verdict, so one floor's verdicts are never reused for another. The output
records each floor's verdicts and how many replies did not parse:

```bash
OPENAI_API_KEY=... python scripts/measure_question_groups.py --judge \
  --out evaluation/question_pairs_results.json
```

The floor bounds recall no matter what the model says. From the cosine scores
above, with the threshold at 0.91:

| Floor | Pairs sent | Paraphrases the rule can reach | Different pairs sent |
| ---: | ---: | ---: | ---: |
| 0.50 | 107 | 59 of 60 | 51 |
| 0.55 | 101 | 58 | 46 |
| 0.60 | 88 | 55 | 36 |
| 0.65 | 74 | 45 | 32 |
| 0.70 (default) | 53 | 35 | 21 |

Three `--judge` runs on 2026-09-27 with `gpt-4o-mini`, prompt v3, 50 pairs per
batch, threshold 0.91. Each cell is paraphrases merged of 60, then different
pairs merged. Run 1 is the one in `evaluation/question_pairs_results.json`.

| Floor | Run 1 | Run 2 | Run 3 |
| ---: | ---: | ---: | ---: |
| 0.45 | 22, 2 | 22, 2 | 21, 2 |
| 0.50 | 23, 1 | 21, 2 | 21, 2 |
| 0.55 | 22, 2 | 21, 2 | 22, 2 |
| 0.60 | 25, 2 | 22, 2 | 25, 2 |
| 0.65 | 21, 2 | 23, 2 | 19, 2 |
| 0.70 (default) | 18, 0 | 16, 1 | 16, 1 |

The model turned down both one-word pairs (HSA and FSA, a sick employee and a
sick child) in every run. The one different pair it merged at 0.70 was "How
long is parental leave?" with "Is parental leave paid?" (0.783).

Four earlier runs used the threshold at 0.85. There two of the false merges in
every cell are the cosine pairs above 0.85, which the model never saw.

| Floor | Run 1 | Run 2 | Run 3 | Run 4 |
| ---: | ---: | ---: | ---: | ---: |
| 0.45 | 46, 6 | 47, 5 | 44, 7 | 45, 9 |
| 0.50 | 45, 6 | 46, 6 | 43, 6 | 44, 8 |
| 0.55 | 44, 6 | 43, 6 | 45, 9 | 39, 6 |
| 0.60 | 46, 7 | 46, 6 | 43, 8 | 40, 7 |
| 0.65 | 37, 7 | 37, 6 | 38, 7 | 35, 9 |
| 0.70 | 29, 2 | 29, 3 | 29, 2 | 29, 3 |

Below 0.70 the model merges the same handful of different pairs run after
run, all between 0.57 and 0.68: "How does PTO accrue?" with "Does unused PTO
carry over?", overtime pay with overtime approval, hiring a relative with a
relative in my department, the 401k match with vesting in it. From 0.70 up it
merged one different pair in two of four runs, a different one each time
("How is severance pay calculated?" with "Is severance pay taxed?", 0.711;
"Can I take PTO before it accrues?" with "Can I cash out my PTO?", 0.728), and
it took paraphrases merged from 6 to 29 of 60 in every run. The default floor is
0.70 for that reason, at either threshold.

Moving the threshold from 0.85 to 0.91 trades recall for fewer false merges:
paraphrases merged fall from 29 to 16 to 18 of 60, and different pairs merged
fall from 2 or 3 to 0 or 1. A false merge hides an unanswered question behind
a covered neighbour, while a missed merge only lists one question twice, so
the default takes the second trade. `QUESTION_GROUP_THRESHOLD=0.85` restores
the other. The #293 target, half the paraphrases with no different pair
merged, is not met at either setting.

Two other setups were measured and rejected. Prompt v1 asked for one boolean
per pair, and at 50 pairs `gpt-4o-mini` returned the wrong count so often that
at the 0.60 floor every batch failed to parse and nothing below the threshold
merged. Prompt v3 asks for the numbers of the pairs that are the same, so a
miscount can only leave a pair out. Batches of 10 instead of 50
merged a few more paraphrases (49 of 60 at 0.60) but twice the different
pairs (11 at 0.60, 3 at 0.70), so the batch stays at 50.

