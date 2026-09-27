# Load-test harness

`server.py` runs the app with its external services stubbed and `run.py` drives
it. The measurements and the reasoning behind `THREADPOOL_TOKENS` are in
[docs/load-testing.md](../../docs/load-testing.md).

`live_benchmark.py` and `pilot_load.py` run against the deployed demo site with the
real model, capped; `host_stats.sh` samples the host while they do. The demo site
load protocol and results are in
[docs/load-testing-demo.md](../../docs/load-testing-demo.md).

`report_timing.py` seeds a throwaway MongoDB with one popular question and
times the What People Ask pipelines that grouped raw `query_logs` rows (issue
#291, PR #296). `rollup_timing.py` seeds the per-day rollup that replaced them
at 7M asks a day, and times the background refresh and the route's snapshot
reads (PR #308). Results for both are in the "Report aggregation at planned
volume" section of [docs/load-testing.md](../../docs/load-testing.md).
