# Load-test harness

`server.py` runs the app with its external services stubbed and `run.py` drives
it. The measurements and the reasoning behind `THREADPOOL_TOKENS` are in
[docs/load-testing.md](../../docs/load-testing.md).

`live_benchmark.py` and `pilot_load.py` run against the deployed pilot with the
real model, capped; `host_stats.sh` samples the host while they do. The pilot
load protocol and results are in
[docs/load-testing-pilot.md](../../docs/load-testing-pilot.md).

`report_timing.py` seeds a throwaway MongoDB with one popular question and
times the What People Ask pipelines against it (issue #291). Results are in
the last section of [docs/load-testing.md](../../docs/load-testing.md).
