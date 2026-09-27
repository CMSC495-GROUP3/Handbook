# Unit 8 portfolio

This is the grader's entry point for Sourcebook's Unit 8 final. Each row below
is one item from the assignment, linked to the evidence for it on `main` and,
after the tag, in the tagged tree.

Submitted version: [`v1.0.0`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.0.0) on
[`a0f7810`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/a0f7810c2d5705dcf0245f203e766db4f2e86a7b), which runs the
candidate code at `7d3c779` named in [handoff.md](handoff.md). Earlier releases:
[`v0.1.0-alpha.1`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.1.0-alpha.1)
and [`v0.2.0`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.2.0).

Stakeholder video: Pending, linked after upload
([#216](https://github.com/CMSC495-GROUP3/Sourcebook/issues/216)).

## Two ways in

1. **The pilot** at <https://sourcebook.duckdns.org>. Two passwords come
   through the course channel, never this repository: the reviewer password
   opens What People Ask as a manager sees it, and the HR password also opens
   HR Requests and the unfiltered report
   ([Passwords on the pilot](handoff.md#passwords-on-the-pilot)). The pilot
   follows `main`; the tag is the submitted version.
2. **Locally, with no accounts:** [docs/install.md](../../install.md), or
   `git clone` then `make setup && make stub`. It uses a fake model and an
   in-memory database, so answer quality can't be judged this way.

## Rubric

| Assignment item | Evidence | Measured on the final commit |
| --- | --- | --- |
| Integrated system | [README](../../../README.md); the pilot; [handoff.md](handoff.md) | end-to-end pass in [handoff.md](handoff.md#end-to-end-pass-by-hand) |
| Working AI feature | README: [How a question is answered](../../../README.md#how-a-question-is-answered), [Keeping the model honest](../../../README.md#keeping-the-model-honest) | smoke and full tier in [live-evaluation.md](live-evaluation.md); the beta fixed the refusal gap, 0% to 100% ([beta evaluation](../v0.2.0/live-evaluation.md)) |
| CI/CD evidence | [docs/ci-cd.md](../../ci-cd.md): each workflow and the auto-deploy path | screenshots of green runs on the final commit in [evidence/](evidence/README.md) ([#207](https://github.com/CMSC495-GROUP3/Sourcebook/issues/207)) |
| README | [README.md](../../../README.md) | release row and video link, written after the tag |
| API documentation | [docs/api.md](../../api.md), [docs/openapi.json](../../openapi.json) | CI fails when the committed OpenAPI document is stale |
| Installation guide | [docs/install.md](../../install.md) | none needed |
| User manual | [docs/user-guide.md](../../user-guide.md) ([#206](https://github.com/CMSC495-GROUP3/Sourcebook/issues/206)) | screenshots from the final browser pass in [evidence/](evidence/README.md) |
| Code reviews | [docs/quality.md](../../quality.md): CODEOWNERS rule, PR checks, review counts, and threads where review changed the code | counts refreshed at the freeze |
| Coverage | [evidence/coverage.md](evidence/coverage.md): Python and web, with the CI run | copied from the final commit's coverage artifacts ([#210](https://github.com/CMSC495-GROUP3/Sourcebook/issues/210)) |
| Performance benchmarks | [live-benchmark.md](live-benchmark.md); synthetic [docs/load-testing.md](../../load-testing.md) | bounded real-service run; load run against the pilot, [docs/load-testing-pilot.md](../../load-testing-pilot.md) ([#212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212)); Lighthouse in [docs/quality.md](../../quality.md) ([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)) |
| Collaboration evidence | [docs/quality.md](../../quality.md); the pull requests and reviews on GitHub | totals in [evidence/numbers.md](evidence/numbers.md) |
| Individual contributions | [docs/team.md](../../team.md) ([#209](https://github.com/CMSC495-GROUP3/Sourcebook/issues/209)); README [Team](../../../README.md#team) | five of seven members confirmed their own row; Gavin's and Dominick's are marked unconfirmed |

## What the release does not establish

See [handoff.md](handoff.md#what-this-release-does-not-establish). Known
defects are in [release-notes.md](release-notes.md#known-defects).
