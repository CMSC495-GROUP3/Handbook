# Coverage for the v1.0.0 candidate

Copied on 2026-09-27 from the candidate's green push-to-`main` CI run. That run
uploads two SHA-named artifacts, kept for 90 days
([#261](https://github.com/CMSC495-GROUP3/Sourcebook/pull/261),
[#275](https://github.com/CMSC495-GROUP3/Sourcebook/pull/275)):

- `python-coverage-<sha>`: `coverage.xml` and `coverage-table.md`
- `web-coverage-<sha>`: `coverage-table.md`, `coverage-summary.json`, and
  `coverage-final.json`

Each section below is that pack's `coverage-table.md`, pasted unchanged apart
from its heading. The
steps are in
[docs/quality.md](../../../quality.md#where-the-release-coverage-comes-from).
Web coverage is measured on the source files listed in `web/vitest.config.ts`,
not all of `web/src`. Say so wherever the figure is quoted.

| Field | Value |
| --- | --- |
| Candidate commit | [`7d3c779`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/7d3c7795c197c5be56b15aebc650576760fd75d1) |
| CI run | [36324854066](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854066), push to `main`, success |

## Python

93% of 2,426 statements. CI fails below 80%.

Measured on Python 3.12.

| Name                                   |    Stmts |     Miss |   Cover |
|--------------------------------------- | -------: | -------: | ------: |
| sourcebook/\_\_init\_\_.py             |        0 |        0 |    100% |
| sourcebook/api/\_\_init\_\_.py         |        0 |        0 |    100% |
| sourcebook/api/analytics.py            |       14 |        0 |    100% |
| sourcebook/api/db.py                   |       45 |        0 |    100% |
| sourcebook/api/limiter.py              |       17 |        0 |    100% |
| sourcebook/api/logutil.py              |       10 |        0 |    100% |
| sourcebook/api/main.py                 |       50 |        3 |     94% |
| sourcebook/api/notify.py               |       31 |        0 |    100% |
| sourcebook/api/routes/\_\_init\_\_.py  |        0 |        0 |    100% |
| sourcebook/api/routes/auth.py          |       88 |        3 |     97% |
| sourcebook/api/routes/chat.py          |      195 |        4 |     98% |
| sourcebook/api/routes/conversations.py |      107 |        2 |     98% |
| sourcebook/api/routes/deps.py          |       47 |        2 |     96% |
| sourcebook/api/routes/documents.py     |       76 |        0 |    100% |
| sourcebook/api/routes/escalations.py   |      174 |        8 |     95% |
| sourcebook/api/routes/projects.py      |       47 |        2 |     96% |
| sourcebook/api/routes/reports.py       |      155 |        1 |     99% |
| sourcebook/api/tokens.py               |       42 |        1 |     98% |
| sourcebook/rag/\_\_init\_\_.py         |        0 |        0 |    100% |
| sourcebook/rag/cache.py                |       65 |        2 |     97% |
| sourcebook/rag/config.py               |       51 |        2 |     96% |
| sourcebook/rag/documents.py            |       33 |        0 |    100% |
| sourcebook/rag/embed\_documents.py     |       72 |        3 |     96% |
| sourcebook/rag/evaluation.py           |      420 |       74 |     82% |
| sourcebook/rag/llm.py                  |      167 |       25 |     85% |
| sourcebook/rag/mongo.py                |       52 |        3 |     94% |
| sourcebook/rag/query\_log\_reports.py  |      172 |       11 |     94% |
| sourcebook/rag/question\_groups.py     |       82 |        0 |    100% |
| sourcebook/rag/question\_judge.py      |       27 |        0 |    100% |
| sourcebook/rag/rag\_chain.py           |      161 |       12 |     93% |
| sourcebook/rag/seed\_documents.py      |       26 |        1 |     96% |
| **TOTAL**                              | **2426** |  **159** | **93%** |

## Web

92.28% of statements, 87.29% of branches, 94% of functions, and 93.93% of
lines, on the files `web/vitest.config.ts` lists. CI fails below 80% on any
of the four.

| File | Statements | Branches | Functions | Lines |
|---|---:|---:|---:|---:|
| src/api/escalations.ts | 100% (17/17) | 100% (12/12) | 100% (5/5) | 100% (15/15) |
| src/components/Chat/EscalateButton.tsx | 100% (34/34) | 100% (25/25) | 100% (8/8) | 100% (28/28) |
| src/components/Chat/Message.tsx | 100% (22/22) | 94.11% (32/34) | 100% (10/10) | 100% (18/18) |
| src/components/Escalations/EscalationDetail.tsx | 90% (9/10) | 88.57% (31/35) | 80% (4/5) | 88.88% (8/9) |
| src/components/Escalations/EscalationListItem.tsx | 100% (3/3) | 100% (8/8) | 100% (2/2) | 100% (3/3) |
| src/components/Escalations/delivery.ts | 100% (7/7) | 100% (6/6) | 100% (2/2) | 100% (7/7) |
| src/components/Layout/ThemeToggle.tsx | 100% (5/5) | 100% (5/5) | 100% (1/1) | 100% (5/5) |
| src/hooks/useChat.ts | 94.76% (181/191) | 88.79% (103/116) | 100% (32/32) | 97.45% (153/157) |
| src/hooks/usePaneFocus.ts | 100% (42/42) | 82.14% (23/28) | 100% (7/7) | 100% (35/35) |
| src/lib/history.ts | 100% (2/2) | 100% (3/3) | 100% (1/1) | 100% (2/2) |
| src/lib/theme.ts | 97.14% (34/35) | 100% (14/14) | 100% (13/13) | 96.66% (29/30) |
| src/pages/DocumentLibraryPage.tsx | 65.88% (56/85) | 63.88% (46/72) | 61.9% (13/21) | 68% (51/75) |
| src/pages/EscalationsPage.tsx | 95.85% (162/169) | 90.57% (125/138) | 100% (43/43) | 98.61% (142/144) |
| **Total** | **92.28% (574/622)** | **87.29% (433/496)** | **94% (141/150)** | **93.93% (496/528)** |
