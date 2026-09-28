# Documentation

Narrative docs live here, grouped by what you want to do. The
[README](../README.md) is the short version of what the system is and why, and
its [Start here](../README.md#start-here) table says what to read first.

## Use it

| Page | Covers |
| --- | --- |
| [user-guide.md](user-guide.md) | using the app: asking, checking sources, escalating, the HR Requests page, and What People Ask |

## Run it

| Page | Covers |
| --- | --- |
| [install.md](install.md) | the live site, the offline stub, real services with every `.env` variable, deployment, and maintenance on the host |
| [ci-cd.md](ci-cd.md) | the five workflows, the merge-to-deploy path on the demo host, and the tag and release procedure |

## Understand and judge it

| Page | Covers |
| --- | --- |
| [architecture.md](architecture.md) | how a question is answered, the four risks the design answers, the query log, and the limitations in full |
| [evaluation.md](evaluation.md) | the labeled question sets in `evaluation/` and how to run the live evaluation |
| [load-testing.md](load-testing.md) | throughput measurements from `scripts/loadtest/`, the `THREADPOOL_TOKENS` decision, and the What People Ask report at planned volume |
| [load-testing-demo.md](load-testing-demo.md) | the concurrent load run against the deployed demo site with the real model, and how to repeat it |
| [quality.md](quality.md) | code review, coverage, and performance evidence, each number tied to a file, PR, or run |
| [team.md](team.md) | each member's role, commits, pull requests, and reviews |

## Change it

| Page | Covers |
| --- | --- |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | checks, conventions, the repository layout, and the things that bite |
| [api.md](api.md) | every HTTP route, with a stub request and response |
| [openapi.json](openapi.json) | the committed OpenAPI document; `make openapi` regenerates it, CI fails if it drifts |
| [design.md](design.md) | the paper-and-ink design system for `web/` |
| [../SECURITY.md](../SECURITY.md) | reporting a vulnerability; what the Security workflow scans |

## Releases

Each release folder holds the handoff that names the verified commit, the
release notes used as the GitHub release body, the measurements taken against
the deployed system, and the evidence behind them.

| Release | Handoff | Notes | Measured |
| --- | --- | --- | --- |
| [v1.1.0](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.0) | [handoff](releases/v1.1.0/handoff.md) | [release notes](releases/v1.1.0/release-notes.md) | [What People Ask timing](load-testing.md#the-per-day-rollup); the rest carries over from v1.0.0 |
| [v1.0.0](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.0.0) | [handoff](releases/v1.0.0/handoff.md) | [release notes](releases/v1.0.0/release-notes.md), [portfolio](releases/v1.0.0/portfolio.md) | [benchmark](releases/v1.0.0/live-benchmark.md), [evaluation](releases/v1.0.0/live-evaluation.md), [load](load-testing-demo.md), [Lighthouse](releases/v1.0.0/evidence/lighthouse.md) |
| [v0.2.0](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.2.0) | [handoff](releases/v0.2.0/handoff.md) | [release notes](releases/v0.2.0/release-notes.md) | [benchmark](releases/v0.2.0/live-benchmark.md), [evaluation](releases/v0.2.0/live-evaluation.md) |
| [v0.1.0-alpha.1](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.1.0-alpha.1) | [handoff](releases/v0.1.0-alpha.1/handoff.md) | [release notes](releases/v0.1.0-alpha.1/release-notes.md) | [benchmark](releases/v0.1.0-alpha.1/live-benchmark.md), [evaluation](releases/v0.1.0-alpha.1/live-evaluation.md) |

## Conventions

- Lowercase kebab-case file names. `README.md` is used only as a folder index.
- Release material goes under `releases/<tag>/`, with screenshots and logs in
  its `evidence/` folder, numbered in the order the steps ran.
- Brand source images live in `../assets/brand/`; the served copies are in
  `web/public/`.
