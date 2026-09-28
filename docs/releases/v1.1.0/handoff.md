# Sourcebook v1.1.0 handoff

`v1.1.0` follows [`v1.0.0`](../v1.0.0/handoff.md) and changes one page, What
People Ask. This page names the code under test, says which checks ran on it,
and explains why the `v1.0.0` measurements carry over. Graders still start at
the `v1.0.0` [portfolio](../v1.0.0/portfolio.md); nothing in it is out of date
except the What People Ask timing, covered below.

## The released version

| Field | Value |
| --- | --- |
| Code under test | [`1059d73`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/1059d73bfd4e57e03cd248a72d23fa7cba3061a2), the merge of #313 on 2026-09-27. It is the last commit on `main` that changed code |
| CI | [36355326962](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36355326962) on `1059d73`, green |
| Security | [36355326918](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36355326918) on `1059d73`, green |
| Tagged commit | The merge of this release's pull request, which follows #292's merge `d4ebc78`. Both change documentation only, so the tag runs the same code as `1059d73`. The [release page](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.0) names the commit |
| Tag and release | [`v1.1.0`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.0), annotated, a full release |
| Running at | <https://sourcebook.duckdns.org> |
| Deployed commit | `1059d73` in both `HEAD` and `refs/deployed/main` on the demo host, checked about 22:30 UTC on 2026-09-27. The API container had restarted for that deploy 5 minutes earlier and logged no errors or warnings since. #292's merge `d4ebc78` deployed after this check; it changed only `docs/quality.md`, so the API was not rebuilt |

## What changed since v1.0.0

Code, all in the What People Ask report's reads and the query log's writes:

| Pull request | Change |
| --- | --- |
| [#308](https://github.com/CMSC495-GROUP3/Sourcebook/pull/308), closes [#291](https://github.com/CMSC495-GROUP3/Sourcebook/issues/291) | A per-day rollup (`sourcebook/rag/query_log_rollup.py`) and five-minute background snapshots (`sourcebook/rag/report_snapshots.py`); `REPORT_REFRESH_SECONDS`; a one-time backfill for older rows |
| [#313](https://github.com/CMSC495-GROUP3/Sourcebook/pull/313) | Falls back when the covering index is missing, budgets the refresh lease for the sample-text lookups, and makes a rerun backfill skip rows it already counted |

Documentation: [#307](https://github.com/CMSC495-GROUP3/Sourcebook/pull/307)
(team page), [#309](https://github.com/CMSC495-GROUP3/Sourcebook/pull/309)
(docs follow-up to #308), [#310](https://github.com/CMSC495-GROUP3/Sourcebook/pull/310)
(evidence sheet, closes #217), [#311](https://github.com/CMSC495-GROUP3/Sourcebook/pull/311)
(README by reader, `docs/architecture.md`), [#312](https://github.com/CMSC495-GROUP3/Sourcebook/pull/312)
(capstone framing, "pilot" removed), and
[#292](https://github.com/CMSC495-GROUP3/Sourcebook/pull/292) (Lighthouse table
in `quality.md`). #311 and #312 also changed code comments and two error
message strings that pointed at moved README sections; no behavior changed.

## Verification

| Check | Result | Source |
| --- | --- | --- |
| Tests, lint, type check, build | Green on `1059d73`. #313 reports 760 Python tests and 130 web tests passing locally | CI run above |
| Coverage | 93% Python at #308; `report_snapshots.py` 100%, `query_log_rollup.py` 90%, the reports route 99% | [#308](https://github.com/CMSC495-GROUP3/Sourcebook/pull/308) |
| Timing at the planned volume | 7 million questions a day for 90 days on a local MongoDB 7: snapshot read 1 ms; refresh of all three windows 8.4 s at 50,000 distinct questions a day and 56.2 s at 200,000 | [load-testing.md](../../load-testing.md#the-per-day-rollup) |
| By hand, local | Startup built the covering index, the thread stored all three snapshots, the 30-day page served its snapshot, and a 14-day window computed live | [#308](https://github.com/CMSC495-GROUP3/Sourcebook/pull/308) |
| Backfill on the demo host | Run after #308 deployed | [install.md](../../install.md#query-log-report-and-rollup-backfill) |
| Snapshots on the demo host | Pending: the three `query_log_report` documents exist and their `until` is under 5 minutes old | The command under [The tag](#the-tag) |

## What carries over from v1.0.0

The chat, retrieval, grounding gate, coverage judge, prompts, and corpus are
unchanged since `v1.0.0`. Outside the report, the diff from `v1.0.0` to `1059d73` touches
`sourcebook/rag/llm.py`, `embed_documents.py`, `seed_documents.py`, and
`question_groups.py`, and `sourcebook/api/routes/auth.py`, only in comments
and in message strings that name a docs page. `config.py` gains
`REPORT_REFRESH_SECONDS`; its other edits are comments. So these `v1.0.0` measurements describe this release too, and it
repeats none of them:

- the [live evaluation](../v1.0.0/live-evaluation.md), smoke and full tier;
- the [live benchmark](../v1.0.0/live-benchmark.md) against the demo site;
- the [demo-site load run](../../load-testing-demo.md);
- [Lighthouse](../v1.0.0/evidence/lighthouse.md), since `web/` did not change;
- the [evidence sheet](../v1.0.0/evidence/numbers.md), whose counts stop at
  the `v1.0.0` tag.

Each ask now does up to three more small writes, one upsert and one or two
markers. The load run above predates that; the extra writes are not measured
on the demo site.

## What this release does not establish

Everything in the `v1.0.0`
[list](../v1.0.0/handoff.md#what-this-release-does-not-establish) still holds,
except that What People Ask now fits its time limit at the planned volume on a
local database. It was not timed on Atlas: the seed writes about 30 GB, which
does not belong in the demo site's cluster. The read with the least headroom
is the conversation-id lookup, 4.4 s once on a cold cache at 200,000 questions
a day, against the route's 5 s limit.

## The tag

The tag waits for this release's pull request to merge and for the snapshot
check. To run the snapshot check on the demo host, which prints ids
and times only:

```bash
docker compose exec -T api python -c 'from sourcebook.rag.mongo import get_collection as g
for d in g("query_log_report").find({}, {"until": 1, "expires_at": 1}): print(d)' < /dev/null
```

Expect `refresh-lease` and three snapshots, `7d|...`, `30d|...`, and `90d|...`, each with an
`until` under 15 minutes old (normally under 5).
After a restart the new API waits out the old one's refresh lease, up to 12
minutes, which is why the bound is looser than the refresh interval. Then, on this pull request's merge commit:

```bash
git fetch upstream
git tag -a v1.1.0 <merge commit> -m "What People Ask at planned volume: verified per docs/releases/v1.1.0/handoff.md"
git push upstream v1.1.0
gh release create v1.1.0 --repo CMSC495-GROUP3/Sourcebook \
  --title "v1.1.0" --latest --notes-file <release notes with absolute links>
```

Rewrite the relative links in the release notes to absolute links into the
tagged tree before publishing, as for `v1.0.0`. No follow-up pull request is
planned: the release page records the tagged commit.
