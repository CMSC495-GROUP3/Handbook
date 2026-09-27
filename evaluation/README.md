# Evaluation sets

`questions.json` is the smoke tier and `questions_full.json` the full tier.
What they measure and how to run them is in [docs/evaluation.md](../docs/evaluation.md).

## Live evaluation job contract (fail-closed)

The GitHub Actions workflow **Live evaluation** is a measuring instrument. A
green conclusion means only that configuration and results were trustworthy
enough to record — not that product quality passed a gate.

**Actions evaluates merged canonical-main history only.** The
`workflow_dispatch` input `commit_sha` must be exactly 40 lowercase hex
characters and an ancestor of `origin/main`. Unmerged pull-request heads
(including `refs/pull/*/head`) are not evaluated in Actions; use the host
procedure below.

The job **must exit nonzero** when any of the following is true:

| Failure | Gate |
|---|---|
| `commit_sha` missing/blank, short SHA, branch/tag/ref, or not exactly 40 lowercase hex | workflow format step before any checkout of the eval target |
| `commit_sha` nonexistent, fork-only, or not an ancestor of `origin/main` | `git merge-base --is-ancestor` on trusted main checkout (`fetch-depth: 0`) before detach / deps / secrets / Atlas |
| Checked-out `HEAD` ≠ requested SHA after ancestry-approved detach | workflow SHA step before secrets / Atlas / paid calls |
| `OPENAI_API_KEY`, `MONGODB_URI`, or `MONGODB_DB` missing or blank | `scripts/validate_live_evaluation.py --check-env` |
| `MONGODB_DB` is not a legal MongoDB database name (empty, any whitespace including padding, `. $ / \\ "`, NUL, or 64 bytes and longer) | same preflight, plus the CLI runner |
| Evaluator process exits nonzero | `set -euo pipefail` on the `python \| tee` pipeline |
| `evaluation/results.json` missing, not JSON, or missing required identity/metrics/cases (including `requested_sha` / `tested_sha`) | `scripts/validate_live_evaluation.py --results` (`if: always()`) |

Empty `MONGODB_DB` is never treated as success. The name is checked exactly
as the client will use it, with no trimming, because a padded secret would
otherwise pass preflight and fail inside PyMongo after the paid run started.
The results step runs with `if: always()`, so a missing file fails that step
explicitly instead of the step being skipped, and the gate keeps working if a
step above it ever gets `continue-on-error`.

These checks do not call the paid provider or Atlas. Prove them locally with:

```bash
pytest tests/test_live_evaluation_fail_closed.py
```

## Host procedure for unmerged pull-request heads

When a maintainer needs smoke numbers for a branch that is not yet on
`origin/main` (for example before merging a grounding fix), run evaluation on
the demo host — not through the Actions workflow:

1. On the host, clone or fetch the pull-request head into a **separate**
   directory (do not displace the deployed checkout).
2. Check out the exact head SHA to measure.
3. With the host's existing live credentials, run the smoke tier:

   ```bash
   python -m sourcebook.rag.evaluation --tier smoke --yes --output evaluation/results.json
   ```

4. Local runs record `requested_sha` / `tested_sha` from `git rev-parse HEAD`
   when those env vars are unset, so the artifact names the measured commit.
5. Post `evaluation/results.json` (or a summary link) on the pull request.

That host path is separately controlled. Actions remains restricted to
ancestors of canonical `main`.
