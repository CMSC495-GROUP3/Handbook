# Continuous integration, delivery, and release evidence

Five GitHub Actions workflows plus a timer on the pilot host. CI success is
not live evaluation. Live evaluation is not a quality verdict. A healthy
deploy is not a tagged release. The `v1.0.0` screenshots and a sanitized
host journal, taken on the release candidate `7d3c779`, are in
`docs/releases/v1.0.0/evidence/`; the release links are added after the tag.

## Integration path at a glance

```text
pull request
  |-- CI -------------------- lint, locks, tests, OpenAPI, web, Docker, repo checks
  |-- Security -------------- CodeQL, advisories, dependency review, secrets
  |-- PR checks ------------- title and description contract
  `-- PR path labels -------- metadata-only area labels
             |
             v
        review + merge
             |
             v
    origin/main moves
             |
             v
  systemd timer -> auto_deploy.sh -> selective Compose rebuild/recreate
             |                         |
             |                         `-- health probe fails: do not advance
             v
  refs/deployed/main advances only after a successful probe

Live evaluation is a separate, manual measurement against real services.
```

Branch protection requires the one check named **CI status**. That job is green
only when every CI job reports `success`, including jobs that could otherwise
be skipped. OpenAPI is one of those CI jobs, not a sixth workflow. Security
and human review stay separate. A green CI badge is not permission to merge
and is not proof of answer quality.

## CI

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) ·
[Actions history](https://github.com/CMSC495-GROUP3/Sourcebook/actions/workflows/ci.yml)

**Trigger.** Every pull request, every push to `main`, and a manual
`workflow_dispatch`. A newer push to a pull request cancels its older run. On
`main` a newer push waits for the run in progress, so every merged commit gets
a finished run and its coverage artifacts.

**Jobs.** `CI status` needs all of these to succeed:

| Job | What it proves |
| --- | --- |
| Python lint and format | Ruff check and format. Then the same lock compile as `make lock`: from inside `requirements/`, `pip-compile` regenerates `api.txt`, `dev.txt`, and `ingest.txt` from the `.in` files. Compiling in that directory keeps `# via -r` annotations aligned with Dependabot (`dependabot.yml` `directory`). A compile from the repo root wrote `-r requirements/api.in` and failed every Dependabot pip PR. |
| Python tests | Pytest with an 80% coverage floor on 3.11, 3.12, 3.13, and 3.14. Synthetic fail-closed checks for the Live evaluation result validator. The 3.12 run always keeps coverage and JUnit artifacts for 14 days; failing matrix versions keep them too. A green push to `main` also keeps `python-coverage-<sha>` (`coverage.xml`, `coverage-table.md`) for 90 days as release evidence ([docs/quality.md](quality.md#where-the-release-coverage-comes-from)). |
| Evaluation dataset | Smoke and full labeled sets load and summarize by category. |
| OpenAPI document | `make openapi PY=python` then `git diff --exit-code -- docs/openapi.json`. The committed document is what a grader or client author reads; this job fails if `/docs` drifted. |
| Web lint, types, test, build | ESLint, `tsc`, Vitest with an 80% coverage floor on the files `web/vitest.config.ts` lists, Vite production build. A green push to `main` keeps `web-coverage-<sha>` (`coverage-table.md` and the Vitest JSON) for 90 days and `web-dist` for seven days. |
| Docker images and Compose | API and web images, API import smoke, provider construction, Compose validation, Caddy-to-Nginx-to-Uvicorn proxy-chain acceptance. |
| Shell, Dockerfile, workflow lint | Secret/generated-file guards, ShellCheck, auto-deploy synthetics, Hadolint, Actionlint. |

No project secrets, so fork pull requests run the same workflow. Locally,
`make check` covers test, lint, and build. `make lock` and `make openapi`
regenerate the same files CI diffs. Docker and the repo-check jobs exist
only in CI.

> **Evidence, `v1.0.0` candidate:** [CI run 36324854066](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854066),
> push to `main` on `7d3c7795c197c5be56b15aebc650576760fd75d1`, success in 1m 12s with all 11 jobs green:
> [`ci-green.png`](releases/v1.0.0/evidence/ci-green.png). The tag goes on the release pull
> request's merge commit, which adds documentation only; the write-back pull
> request links that commit's own CI run.

## Security

Workflow: [`.github/workflows/security.yml`](../.github/workflows/security.yml) ·
[Actions history](https://github.com/CMSC495-GROUP3/Sourcebook/actions/workflows/security.yml)

**Trigger.** Every pull request, every push to `main`, Mondays at 06:17 UTC,
and a manual `workflow_dispatch`. A newer push to a pull request cancels its
older run. On `main`, pushes and the weekly run wait for the run in progress,
so the release candidate and the release merge commit each get a finished run.

**Jobs.** CodeQL on Python and JavaScript/TypeScript with the
`security-and-quality` query set. `scripts/audit.sh` checks the locked Python
and npm trees (`make audit` runs the same script). Pull requests also get
GitHub dependency review, which rejects newly introduced advisories at high
severity or above. A pinned, checksum-verified Gitleaks CLI scans the full Git
history.

Security is a separate workflow so a Monday advisory can fail this path without
turning an unrelated CI change into a false claim about its code. A finding
still needs triage. Green CI does not override it.

> **Evidence, `v1.0.0` candidate:** [Security run 36324854241](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854241),
> push to `main` on `7d3c7795c197c5be56b15aebc650576760fd75d1`, success:
> [`security-green.png`](releases/v1.0.0/evidence/security-green.png). No advisory is accepted:
> `IGNORED_ADVISORIES` in `scripts/audit.sh` is empty, and the run's audit
> step reported "No known vulnerabilities found" for Python and "found 0
> vulnerabilities" for npm. Dependency review runs only on pull requests; it
> passed on the release pull request
> [#274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274) in
> [Security run 36328626429](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36328626429).

## PR checks

Workflow: [`.github/workflows/pr-checks.yml`](../.github/workflows/pr-checks.yml) ·
[Actions history](https://github.com/CMSC495-GROUP3/Sourcebook/actions/workflows/pr-checks.yml)

**Trigger.** Pull requests when opened, edited, synchronized, reopened, or
marked ready for review. A newer metadata run for the same PR cancels the older
one.

**Jobs.** Title must be `type: what changed`, using an accepted type and a
lower-case subject. Except for Dependabot, the body must keep `## What and why`
and contain real prose before `## How to check it`. Metadata only; this does
not test the implementation.

> **Evidence, `v1.0.0` release pull request:** [PR checks run
> 36328626384](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36328626384) on
> [#274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274) at `bc13639`,
> success: [`pr-checks-green.png`](releases/v1.0.0/evidence/pr-checks-green.png). Later pushes to
> #274 rerun it.

## PR path labels

Workflow: [`.github/workflows/pr-labels.yml`](../.github/workflows/pr-labels.yml) ·
[Actions history](https://github.com/CMSC495-GROUP3/Sourcebook/actions/workflows/pr-labels.yml)

**Trigger.** Pull requests when opened, synchronized, or reopened.

**What it does.** GitHub's labeler applies and synchronizes area labels from
changed-file metadata. `pull_request_target` supplies a token that can update
PR metadata, so this workflow uses the base branch's configuration, does not
check out the proposed branch, and never imports or executes PR content.
Labels help route review. Not a code or merge gate.

> **Evidence, `v1.0.0` release pull request:** [PR path labels run
> 36328625547](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36328625547) on
> [#274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274) at `bc13639`,
> success: [`pr-path-labels-green.png`](releases/v1.0.0/evidence/pr-path-labels-green.png). It
> applied `documentation`, the only label #274 carries, since the pull request
> changes only `docs/`.

## Live evaluation

Workflow: [`.github/workflows/evaluation.yml`](../.github/workflows/evaluation.yml) ·
[Actions history](https://github.com/CMSC495-GROUP3/Sourcebook/actions/workflows/evaluation.yml) ·
[method and metric definitions](evaluation.md)

**Trigger.** A maintainer starts `workflow_dispatch`, selects `smoke` or
`full`, and supplies an exact 40-hex `commit_sha` that is an ancestor of
`origin/main`. The job uses the protected `evaluation` environment because it
calls the real model provider and MongoDB Atlas. Unmerged pull-request heads
are not evaluated here; see the host procedure in
[evaluation/README.md](../evaluation/README.md).

**What it measures.** Format and `origin/main` ancestry are checked on a
trusted main checkout before the job detaches onto the requested SHA,
installs dependencies, or touches secrets. Configuration is checked next,
including empty secrets and an empty or illegal `MONGODB_DB`, so a bad
database name fails at preflight instead of after Atlas admission and paid
calls. The runner's address is admitted to the Atlas project, the labeled
set runs with `CACHE_ENABLED=0`, metrics are validated, and the address is
removed after a completed admission even when later evaluation fails.
Results stay as an artifact for 90 days.

Empty secrets, a nonzero evaluator exit, missing results, or malformed metrics
fail closed. The results validator runs with `if: always()` so a missing file
is an explicit failure, not a skipped step. If admission creates an entry but
is interrupted before returning its address, cleanup cannot identify that
entry; an Atlas operator has to verify and remove it.

A green job means the evaluator exited successfully and the result structure
passed validation. It is not the protected merge gate. It is not a claim that
answers, refusals, or prompt-injection resistance are acceptable. Those still
need human review of cited passages and the labeled cases.

> **Evidence, `v1.0.0` candidate:** [Live evaluation run
> 36325113964](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36325113964), full tier (59 cases), dispatched with
> `commit_sha` `7d3c7795c197c5be56b15aebc650576760fd75d1`, success:
> [`live-evaluation-green.png`](releases/v1.0.0/evidence/live-evaluation-green.png). The results
> JSON is retained in the run's `evaluation-results` artifact and committed as
> [`live-evaluation-results-full.json`](releases/v1.0.0/live-evaluation-results-full.json);
> the scores and the six hand-reviewed dispositions are in
> [`live-evaluation.md`](releases/v1.0.0/live-evaluation.md).

## From merge to the pilot containers

The pilot polls. It does not take a deployment webhook. The systemd unit
[`scripts/systemd/auto-deploy.timer`](../scripts/systemd/auto-deploy.timer)
starts [`auto-deploy.service`](../scripts/systemd/auto-deploy.service) two
minutes after boot and every two minutes after that. The oneshot service runs
[`scripts/auto_deploy.sh`](../scripts/auto_deploy.sh) as `ubuntu`, waits for
network and Docker, and has a 15-minute start timeout. A weekly timer prunes
the Docker build cache while retaining 300 MB; the deploy script also prunes
when the root filesystem has less than 1 GiB free.

Each tick:

1. Take a non-blocking `flock` on the checkout so a manual deployment cannot
   overlap the timer.
2. Refuse unless the checkout is on `main`, then fetch `origin/main`.
3. Refuse if the checkout has tracked or untracked local changes, then compare
   upstream with `refs/deployed/main`, the last commit whose deployment passed
   health verification. `HEAD` is not the success marker; it is fast-forwarded
   before the build finishes.
4. If the ref already matches upstream, probe `/api/health` anyway. An idle
   tick stays red while the running stack is unhealthy.
5. Diff the successful commit against the new upstream tip and select work:

   | Changed input | Deployment action |
   | --- | --- |
   | `sourcebook/`, `requirements/`, or API `Dockerfile` | build and recreate `api` |
   | `web/` | build and recreate `web` |
   | `docker-compose.yml` | build both images and allow Compose to recreate affected services, including Caddy |
   | `Caddyfile` | reload Caddy in place |
   | anything else | health-check and advance the deployed ref without rebuilding containers |

6. Fast-forward the host checkout, build selected services with refreshed base
   images, and recreate them with `--no-deps` so an API- or web-only change does
   not restart Caddy.
7. Probe `/api/health` through the web container every two seconds for up to 60
   seconds. That path hits Nginx, Uvicorn, and the connection between them.
8. Only after a successful probe, prune unused dangling images and advance
   `refs/deployed/main`. A build, Compose, reload, or health failure leaves the
   ref behind so the same change is retried on the next tick.

Failures are counted per target SHA in `.git/auto-deploy-failures`. After five
consecutive failures by default (`AUTO_DEPLOY_MAX_FAILURES`), later ticks stay
red but skip another expensive rebuild. Setting the limit to `0` allows
unbounded retries. Deleting `refs/deployed/main` clears the retry state and
forces both images to rebuild on the next tick.

The health gate stops a failed attempt from advancing `refs/deployed/main`. It
does not restore the previous containers. Recovery needs a corrected `main` or
an operator. Host `.env` edits are outside the Git diff, so they do not select
a service for rebuild; those need an explicit recreation.

[`scripts/deploy.sh`](../scripts/deploy.sh) is the on-demand route. It SSHs in,
starts the same systemd service, prints only that invocation's journal, and
returns the deployment status. It does not deploy a tag or an arbitrary
branch; the script always follows `origin/main`.

A successful probe means the selected services came up and `/api/health`
answered. It does not re-run CI, does not score answers, and does not freeze
the public site at a release tag.

> **Evidence, `v1.0.0` candidate deployment:** the pilot's auto-deploy of
> `95db28f -> 7d3c779` at 14:09:58 UTC on 2026-09-27 rebuilt and recreated
> only `api`, then printed every container up:
> [`auto-deploy-journal.txt`](releases/v1.0.0/evidence/auto-deploy-journal.txt), rendered as
> [`auto-deploy-green.png`](releases/v1.0.0/evidence/auto-deploy-green.png). The host name is
> replaced and BuildKit step lines are left out; no address, user name,
> environment value, or credential appears.

## Checking a deployment

Follow the README's [Checking a deploy](../README.md#checking-a-deploy)
procedure. It verifies three boundaries:

1. the public site serves HTTPS and `/api/health` returns 200;
2. the Compose networks fall within the proxy's trusted pools and the API has
   the expected forwarded-address setting; and
3. a forged `X-Forwarded-For` value is discarded while the API logs the real
   external client address.

The deployed commit is the host's `refs/deployed/main`. Record that full SHA
beside the verification evidence. The public site follows `main` and can move
past a release tag.

## Tag and release path

The repository has an alpha release. The final `v1.0.0` tag does not exist
because this page describes its procedure. The path is:

1. Prepare `docs/releases/v1.0.0/` with the handoff, release notes,
   measurements, and evidence index. Leave commit- and run-specific fields
   visibly pending.
2. Merge the final release PR to `main` through the normal CI, Security, and
   review gates.
3. Choose that verified `main` commit, record its full SHA, and confirm the CI
   and Security runs attached to the same SHA are green. Complete live
   evaluation and deployment evidence without treating either as the other.
4. Create and push an **annotated** `v1.0.0` tag on that exact commit. Create
   the GitHub release from `docs/releases/v1.0.0/release-notes.md` so the
   repository and release page tell the same story.
5. Open a follow-up documentation PR against `main` that writes the immutable
   tagged SHA, tag/release URL, workflow-run URLs, screenshot links, and
   sanitized deployment-journal link back into this page and the final handoff.
   That commit comes after the tag. It is not part of the tagged artifact; it
   records evidence about it.

Before the tag is pushed, the tag target (not merely the newest `main` when
someone reads the page) has to be the commit covered by every final claim. A
later deployment can move past it. The tag remains the reproducible portfolio
artifact.

> **FINAL EVIDENCE PENDING — release:** Replace this note in the follow-up PR
> with the annotated tag URL, GitHub release URL, full tagged SHA, final release
> PR, and links to the exact CI, Security, Live evaluation, and deployment
> evidence described above.
