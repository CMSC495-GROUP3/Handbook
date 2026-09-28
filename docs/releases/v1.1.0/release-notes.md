# Sourcebook v1.1.0

A minor release after [`v1.0.0`](../v1.0.0/release-notes.md), tagged the same
week. It changes one page, What People Ask, so that it can serve the question
volume the project planned for. Everything else since `v1.0.0` is
documentation. Sourcebook is a CMSC 495 capstone project, built for a
fictional company, and the demo site is a class demo.

Release [`v1.1.0`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.0).
The commit it names, the checks run on it, and why the `v1.0.0` measurements
still apply are in [handoff.md](handoff.md).

## What changed since v1.0.0

- **What People Ask reads from a daily rollup and a five-minute snapshot.**
  Each question asked now also updates one count document per question and
  UTC day. A background thread in the API recomputes the page's 7, 30, and
  90-day windows every 5 minutes, and the page reads the stored result. On a
  local MongoDB 7 seeded with 7 million asks a day for 90 days, the page
  reads its snapshot in 1 ms, and a full refresh of all three windows took
  8.4 s at 50,000 distinct questions a day and 56.2 s at 200,000. At `v1.0.0`
  a 90-day window at that volume missed the page's 5-second limit (#291,
  PR #308).
- **The report's counts are normally up to five minutes old, and up to 15
  after a deploy.** A question asked now shows up on What People Ask at the
  next refresh, not on the next page load. Past 15 minutes the page computes
  its counts live. The [user guide](../../user-guide.md) covers the refresh
  (PR #309).
- **Conversation counts can come out lower than before, never higher.** A
  conversation counts once, on the day it first asked a question. If that day
  falls before the window, a later ask inside the window adds an ask but not a
  conversation. Lower is the safe direction for the manager's view, which
  hides any question asked in fewer than three conversations. Asks stay exact
  (PR #308).
- **Fixes from an independent review of the refresh** (PR #313):
  - A missing covering index falls back to a slower query instead of
    returning a server error.
  - Two API workers can no longer refresh the snapshots at the same time.
  - Rerunning an interrupted backfill no longer counts an ask twice.
- **The docs are reorganized by reader.** The README went from 1,157 lines to
  about 300 and opens with a table of where each reader starts. Install,
  deploy, and design rationale moved to [docs/install.md](../../install.md) and
  the new [docs/architecture.md](../../architecture.md) (PR #311).
- **The docs describe the project as a capstone demo.** "Pilot" is now "demo
  site" or "demo host" throughout the Markdown, and
  `docs/load-testing-pilot.md` is now
  [docs/load-testing-demo.md](../../load-testing-demo.md). Links to the old
  file name from outside the repository no longer work (PR #312).
- **The `v1.0.0` evidence sheet has no Pending rows left.** Review events,
  auto-deploys since the alpha, and host uptime are filled from files in the
  evidence folder (#217, PR #310).
- **Lighthouse scores for the sign-in, chat, and document pages, in both
  themes at mobile and desktop width, are in
  [quality.md](../../quality.md#lighthouse-scores)** (#214, PR #292).

## Upgrading

Only a host that ran `v1.0.0` or earlier needs this. Rows logged before the
rollup existed are missing from What People Ask until a one-time backfill
records them. It is safe to rerun:

```bash
docker compose exec -T api python -m sourcebook.rag.query_log_rollup --backfill < /dev/null
```

`REPORT_REFRESH_SECONDS` (default 300) sets how often the snapshots refresh.
`0` turns the thread off, and every page load computes live. See
[docs/install.md](../../install.md#query-log-report-and-rollup-backfill).

## Getting access

Unchanged from `v1.0.0`. The demo site runs at
<https://sourcebook.duckdns.org>, and the team supplies the reviewer and HR
passwords through the course channel. Without any credential, the whole app
runs locally with a fake model and an in-memory database:

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
make setup && make stub     # then, in a second terminal
make web
```

## Known defects

The three from [`v1.0.0`](../v1.0.0/release-notes.md#known-defects) still
apply: vague questions on covered topics get the refusal card, conversations
belong to a browser rather than a person, and What People Ask misses some
paraphrases. This release adds none.

## What this release does not establish

- **What People Ask on Atlas.** The timings above come from a local MongoDB
  container on a laptop. Seeding the same volume would write about 30 GB,
  which does not belong in the demo site's cluster, so #291 dropped that
  criterion. The slowest read with the least headroom is the conversation-id
  lookup, which took 4.4 s once on a cold cache at 200,000 questions a day.
- **Anything new about answers.** The chat, retrieval, grounding gate, and
  prompts are unchanged, so this release repeats no evaluation, benchmark, or
  load run. The `v1.0.0` figures and their limits still stand, as
  [handoff.md](handoff.md#what-carries-over-from-v100) explains.

## Reproducing this exact version

The demo host follows `main`, so it moves past this tag. The tag does not.

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
git checkout v1.1.0
make setup && make stub
```
