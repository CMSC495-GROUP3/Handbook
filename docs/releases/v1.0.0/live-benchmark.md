# Final performance benchmark against the real services

The same bounded workload as the alpha and beta, against the deployed pilot
with OpenAI, Atlas, Caddy, Nginx, rate limits, and provider bounds all on. The
protocol, the caps, and the targets are unchanged and are in
[../v0.1.0-alpha.1/live-benchmark.md](../v0.1.0-alpha.1/live-benchmark.md).
The alpha and beta results are the before.

This is a bounded check that the deployed path works for one user and a burst
of three. Load against the deployed system is a separate measurement,
[#212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212).

Status: **Done on the candidate.** Run `e6615d05` on 2026-09-27 against the
pilot running `7d3c779`. All five targets pass. The raw output is
[live-benchmark-results.json](live-benchmark-results.json); it holds timings
and synthetic session labels, no answer text and no credential.

## Running it

Run `scripts/loadtest/live_benchmark.py` with the alpha's defaults (8 requests
at most, a burst of 3, stop after 2 errors), then save the sanitized output as
`live-benchmark-results.json` beside this page and fill the tables below.
Record the deployed commit from `HEAD` and `refs/deployed/main` on the host.

## Results

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-09-27 14:16 |
| Deployed commit | `7d3c779` in `HEAD` and `refs/deployed/main` on the host; API container started 14:10 UTC |
| Operator | Claude, from Taylor's session, signed in with the HR password |
| Requests | 7: one uncached answer, a cached repeat, a follow-up, a refusal, and a burst of 3. No rate limiting, no errors, about $0.05 |

| Target | Agreed | Alpha, `4352966` | Beta, `231e652` | Final |
| --- | --- | --- | --- | --- |
| Generated time to first token, p50 | ≤ 4.0s | 1.21s, pass | 1.21s, pass | 1.18s, pass |
| Generated total, max | ≤ 30.0s | 4.69s, pass | 4.35s, pass | 3.30s, pass |
| Cached time to first token, max | ≤ 1.5s | 0.04s, pass | 0.04s, pass | 0.10s, pass |
| Refused total, max | ≤ 3.0s | 0.31s, pass | 0.08s, pass | 0.05s, pass |
| Error rate | 0.0 | 0.00, pass | 0.00, pass | 0.00, pass |

| Step | Path | Time to first token | Complete | Sources |
| --- | --- | ---: | ---: | ---: |
| uncached answer | generated | 3.12s | 3.30s | 2 |
| cached repeat | cached | 0.10s | 0.10s | 2 |
| follow-up | generated | 1.97s | 2.41s | 2 |
| refusal | refused | 0.05s | 0.05s | 0 |
| burst 1 | generated | 1.18s | 1.83s | 3 |
| burst 2 | generated | 1.14s | 1.62s | 2 |
| burst 3 | generated | 1.18s | 1.58s | 3 |

Seven requests are far too few for percentiles; the p50 is the middle of five
generated answers. The first uncached answer took 3.12s to its first token,
slower than the burst, and still inside the 4.0s target for a single request.
