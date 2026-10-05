# Sourcebook v1.1.1 handoff

`v1.1.1` follows [`v1.1.0`](../v1.1.0/handoff.md) and adds no feature. It
ships one fix to the What People Ask refresh and a round of dependency
updates, among them a new OpenAI client for every answer the demo site gives.
This page names the code under test, says which checks ran on it, and says
which measurements were taken again. Graders still start at the `v1.0.0`
[portfolio](../v1.0.0/portfolio.md).

## The released version

| Field | Value |
| --- | --- |
| Code under test | [`ccd9688`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/ccd96881f5cc55a4ddcef1c375a678c318f4b828), the merge of #321 on 2026-10-05. It is the last commit on `main` that changed code or dependencies |
| CI | [37389834036](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/37389834036) on `ccd9688`, green |
| Security | [37389834676](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/37389834676) on `ccd9688`, green, including Dependency advisories |
| Live evaluation | Smoke [37389949312](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/37389949312) and full [37389952311](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/37389952311) on `ccd9688`, both green. See [live-evaluation.md](live-evaluation.md) |
| Tagged commit | The merge of this release's pull request. It changes documentation only, so the tag runs the same code as `ccd9688`. The [release page](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.1) names the commit |
| Tag and release | [`v1.1.1`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.1), annotated, a full release |
| Running at | <https://sourcebook.duckdns.org> |
| Deployed commit | `ccd9688` in both `HEAD` and `refs/deployed/main` on the demo host, checked about 23:50 UTC on 2026-10-05. The API container started at 23:36 UTC for that deploy, reports openai 3.23.0, fastapi 0.142.2, and pyjwt 2.15.1, and logged no errors since |

## What changed since v1.1.0

| Pull request | Change |
| --- | --- |
| [#315](https://github.com/CMSC495-GROUP3/Sourcebook/pull/315), refs [#291](https://github.com/CMSC495-GROUP3/Sourcebook/issues/291) | An API that shuts down between refreshes deletes its What People Ask refresh lease, so the API that replaces it refreshes as it starts instead of waiting up to 12 minutes |
| [#319](https://github.com/CMSC495-GROUP3/Sourcebook/pull/319) | Python dependencies. In the API image: openai 3.15.0 to 3.23.0, fastapi 0.141.1 to 0.142.2 (which adds opentelemetry-api 1.45.0), pyjwt 2.14.0 to 2.15.1 (PYSEC-2026-4141), pymongo 4.18.1 to 4.18.2, python-dotenv 1.2.3 to 1.2.4, uvicorn 0.53.0 to 0.54.0. Ingestion and development only: boto3 1.43.97 to 1.43.107, ruff 0.16.8 to 0.16.10 |
| [#318](https://github.com/CMSC495-GROUP3/Sourcebook/pull/318) | Web dependencies. In the built app: lucide-react 1.47.0 to 1.49.0. Build and test tools: vite 8.3.0 to 8.3.2, vitest coverage 5.0.1 to 5.0.3, eslint 10.10.0 to 10.11.0, jsdom 30.1.0 to 30.1.1, and three typing and lint packages |
| [#321](https://github.com/CMSC495-GROUP3/Sourcebook/pull/321) | urllib3 2.7.0 to 2.8.0 (PYSEC-2026-4175, 4176, 4177), which botocore and requests pull into the ingestion and development locks; the API image does not install it. brace-expansion 5.0.9 to 5.0.12 (three denial-of-service advisories), which eslint pulls in; development only. Dependabot's grouped updates skip both because neither is a direct dependency |

Dependabot's separate urllib3 pull request,
[#320](https://github.com/CMSC495-GROUP3/Sourcebook/pull/320), closed
unmerged because #321 already made the change.

## Verification

| Check | Result | Source |
| --- | --- | --- |
| Tests, lint, type check, build | Green on `ccd9688` | CI run above |
| Known vulnerabilities | pip-audit on `requirements/dev.txt` finds none; `npm audit --audit-level=high` finds none. Before #321 the check failed on `main` | Security run above |
| API lock on its own | `requirements/api.txt` installed alone in a clean `python:3.12` container passes `pip check`, and the app imports. This catches a runtime dependency that only the development lock carries | Run by hand at #319's head |
| Answer quality, smoke and full tier | Every metric equals `v1.0.0`; every case answered or refused as it did then | [live-evaluation.md](live-evaluation.md) |
| Answers from the deployed container | A covered question answered through both the non-streaming and the streaming call with follow-ups; an uncovered one refused before generation. Nothing written to the database | [live-evaluation.md](live-evaluation.md#on-the-demo-host) |
| Refresh after a deploy (#315) | The API started at 23:36:18 UTC. Its snapshots carried `until` 23:46:24, two five-minute intervals after a first refresh at 23:36:24, six seconds after start. The old API's lease did not hold it back | The snapshot command under [The tag](#the-tag), run about 23:49 UTC on 2026-10-05 |

## What carries over

These `v1.0.0` measurements were not taken again:

- the [live benchmark](../v1.0.0/live-benchmark.md) of latency against the
  demo site. The live evaluation scores answers but does not time them, so
  nothing here shows whether openai 3.23.0 is faster or slower;
- the [demo-site load run](../../load-testing-demo.md), which already
  predated the report's extra writes per ask;
- [Lighthouse](../v1.0.0/evidence/lighthouse.md). The only change to the
  shipped web bundle is the icon library's patch release and the vite
  version that builds it;
- the [evidence sheet](../v1.0.0/evidence/numbers.md), whose counts stop at
  the `v1.0.0` tag.

## What this release does not establish

Everything in the `v1.1.0`
[list](../v1.1.0/handoff.md#what-this-release-does-not-establish) still holds.
In addition:

- **Latency on the new client.** See the benchmark item above.
- **A deploy that lands mid-refresh.** It still waits out the old lease, up
  to 12 minutes. The check above caught a shutdown between refreshes, the
  common case.

## The tag

The tag waits for this release's pull request to merge. To recheck the
snapshots on the demo host, which prints ids and times only:

```bash
docker compose exec -T api python -c 'from sourcebook.rag.mongo import get_collection as g
for d in g("query_log_report").find({}, {"until": 1, "expires_at": 1}): print(d)' < /dev/null
```

Then, on this pull request's merge commit:

```bash
git fetch upstream
git tag -a v1.1.1 <merge commit> -m "Dependency updates and refresh lease fix: verified per docs/releases/v1.1.1/handoff.md"
git push upstream v1.1.1
gh release create v1.1.1 --repo CMSC495-GROUP3/Sourcebook \
  --title "v1.1.1" --latest --notes-file <release notes with absolute links>
```

Rewrite the relative links in the release notes to absolute links into the
tagged tree before publishing, as for `v1.1.0`.
