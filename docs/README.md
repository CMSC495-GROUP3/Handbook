# Documentation

Narrative docs live here. New to the project? Start with
[install.md](install.md). The [README](../README.md) explains what the system
is and why, [CONTRIBUTING.md](../CONTRIBUTING.md) covers changing it, and
[SECURITY.md](../SECURITY.md) covers reporting a vulnerability.

| Page | Covers |
| --- | --- |
| [install.md](install.md) | the live site, the offline stub, real services with every `.env` variable, deployment |
| [user-guide.md](user-guide.md) | using the app: asking, checking sources, escalating, and the HR Requests page |
| [api.md](api.md) | every HTTP route, with a stub request and response |
| [openapi.json](openapi.json) | the committed OpenAPI document; `make openapi` regenerates it, CI fails if it drifts |
| [design.md](design.md) | the paper-and-ink design system for `web/` |
| [evaluation.md](evaluation.md) | the labeled question sets in `evaluation/` and how to run the live evaluation |
| [load-testing.md](load-testing.md) | throughput measurements from `scripts/loadtest/` and the `THREADPOOL_TOKENS` decision |
| [load-testing-pilot.md](load-testing-pilot.md) | the concurrent load run against the deployed pilot with the real model, and how to repeat it |
| [ci-cd.md](ci-cd.md) | the five workflows, the merge-to-deploy path on the pilot host, and the `v1.0.0` tag procedure |
| [quality.md](quality.md) | code review, coverage, and performance evidence, each number tied to a file, PR, or run |

## Releases

Each release folder holds the handoff that names the verified commit, the
release notes used as the GitHub release body, the measurements taken against
the deployed system, and the evidence behind them.

| Release | Handoff | Notes | Measured |
| --- | --- | --- | --- |
| [v0.2.0](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.2.0) | [handoff](releases/v0.2.0/handoff.md) | [release notes](releases/v0.2.0/release-notes.md) | [benchmark](releases/v0.2.0/live-benchmark.md), [evaluation](releases/v0.2.0/live-evaluation.md) |
| [v0.1.0-alpha.1](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.1.0-alpha.1) | [handoff](releases/v0.1.0-alpha.1/handoff.md) | [release notes](releases/v0.1.0-alpha.1/release-notes.md) | [benchmark](releases/v0.1.0-alpha.1/live-benchmark.md), [evaluation](releases/v0.1.0-alpha.1/live-evaluation.md) |

## Conventions

- Lowercase kebab-case file names. `README.md` is used only as a folder index.
- Release material goes under `releases/<tag>/`, with screenshots and logs in
  its `evidence/` folder, numbered in the order the steps ran.
- Brand source images live in `../assets/brand/`; the served copies are in
  `web/public/`.
