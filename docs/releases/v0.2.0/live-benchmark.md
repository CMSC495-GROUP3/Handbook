# Beta performance benchmark against the real services

The same bounded workload as the alpha, against the deployed demo site with
OpenAI, Atlas, Caddy, Nginx, rate limits, and provider bounds all on. The
protocol, the caps, and the targets are unchanged and are in
[../v0.1.0-alpha.1/live-benchmark.md](../v0.1.0-alpha.1/live-benchmark.md).
The alpha's result is the before.

Status: **run on 2026-09-24, every target met.** The sanitized JSON is
`live-benchmark-results.json` beside this page. It holds no answer text,
password, or token.

## Running it

```bash
BENCH_PASSWORD=... ./.venv/bin/python scripts/loadtest/live_benchmark.py \
  --url https://sourcebook.duckdns.org \
  --deployed-sha 231e65224efa3ecf688af0f89b8d4d0ce924d153 \
  --client-location "operator laptop, home network" --label "v0.2.0 beta" \
  --out docs/releases/v0.2.0/live-benchmark-results.json --yes
```

The caps are the alpha's defaults: 8 requests at most, a burst of 3, stop
after 2 errors, 2 seconds between sequential requests.

## Results

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-09-24 21:49, run id `657f00d0` |
| Deployed commit | `231e65224efa3ecf688af0f89b8d4d0ce924d153`, read from `refs/deployed/main` and `HEAD` on the host just before the run |
| Operator | Taylor Shahan, from macOS on a home network, script run by Claude Code |
| Requests | 7 of the 8 allowed: 5 generated, 1 cached, 1 refused. No rate limiting, no errors, no path mismatches. Estimated cost $0.05 |

| Target | Agreed | Alpha, `4352966` | Beta |
| --- | --- | --- | --- |
| Generated time to first token, p50 | ≤ 4.0s | 1.21s, pass | 1.21s, pass |
| Generated total, max | ≤ 30.0s | 4.69s, pass | 4.35s, pass |
| Cached time to first token, max | ≤ 1.5s | 0.04s, pass | 0.04s, pass |
| Refused total, max | ≤ 3.0s | 0.31s, pass | 0.08s, pass |
| Error rate | 0.0 | 0.00, pass | 0.00, pass |

| Step | Path | Time to first token | Complete | Sources | Match |
| --- | --- | ---: | ---: | ---: | ---: |
| uncached answer | generated | 4.11s | 4.35s | 2 | 75% |
| cached repeat | cached | 0.04s | 0.04s | 2 | 75% |
| follow-up | generated | 2.88s | 3.57s | 2 | 77% |
| refusal | refused | 0.07s | 0.08s | 0 | 59% |
| burst 1 | generated | 1.09s | 1.44s | 3 | 75% |
| burst 2 | generated | 1.13s | 1.50s | 2 | 74% |
| burst 3 | generated | 1.21s | 1.48s | 3 | 78% |

The refused path now includes the coverage judge from PR #253 whenever the
cosine gate clears, so a refusal of that kind makes one utility-model call
that the alpha's refusals did not. The refusal step asks "What is the boiling
point of mercury at sea level?". It scored 59% against the 0.62 threshold, the
same as in the alpha's browser pass, so it was refused at the cosine gate and
the judge did not run. This run therefore does not time a judge refusal; the
browser pass refused one at 79% but did not time it.

The uncached answer's 4.11s time to first token is close to the alpha's
4.17s for the same step; both are the first generation after the cache probe.
Seven requests are far too few for percentiles, and a single run says nothing
about variance or load.
