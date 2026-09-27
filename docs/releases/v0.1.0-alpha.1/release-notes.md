# Sourcebook v0.1.0-alpha.1

The first tagged version of Sourcebook, released as a prerelease for the
CMSC 495 Unit 5 alpha. It is a class demo, not a production system, and the
sections below say plainly what it does, what is broken, and what nobody has
measured yet.

Tagged commit: `d7199f57e3eb600e646d4202de43c97f2c5cc770`. The evidence behind every claim here is
in [handoff.md](handoff.md), which is the page to read if you are grading this.

## What it does

Sourcebook answers employee policy questions from a fixed corpus of company
documents and cites the document behind every answer. When the corpus does not
cover a question, it says so and offers to hand the question to Human
Resources rather than guessing.

A question goes through retrieval against a vector index, then a grounding
gate that compares the best passage score against a threshold. Below the
threshold there is no model call at all and the user gets a refusal card.
Above it the answer streams back with the policies it drew on and a match
score.

## What is in this release

- Streaming answers with cited sources and a retrieval score.
- A grounding gate that refuses instead of guessing, and refuses without
  paying for a model call.
- Escalation to Human Resources, with an optional webhook, delivery status on
  each record, and a bounded retry endpoint. An escalation names the stored
  turn by id, so one filed after a failed generation reaches the question the
  user clicked (#84, fixed in PR #188).
- Conversation history, grouped into projects.
- A Policy Library that renders whole documents, so a citation can be read in
  full.
- Shared-password sign-in, with a second password so a reviewer's can be
  handed out and rotated without touching the team's.
- Rate limits on chat, login, and reindex, a bounded pool of concurrent
  provider calls, and a provider timeout, so a slow model cannot take the site
  down.
- An answer cache, and an embedding cache, both with expiry.
- A query log, one row per request, for later analysis of content gaps.
- Docker Compose behind Caddy, with automatic redeploy when `main` moves.

## Getting access

**The demo site** runs at <https://sourcebook.duckdns.org> on a single instance
and stays up while the course runs. It needs a password. The team supplies the
reviewer password through the course channel, never through this repository,
so nothing here has to be rotated after grading.

**Without any credential**, the whole app runs locally in about two minutes
with a fake model and an in-memory database:

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
make setup && make stub     # then, in a second terminal
make web
```

That needs no accounts, no API key, and no network. It is the fastest way to
see the refusal path, escalation, and the Policy Library without asking anyone
for anything.

**Setup and usage** are in the [README](../../../README.md), which walks one
question through retrieval, the gate, and streaming.
[CONTRIBUTING.md](../../../CONTRIBUTING.md) covers running against real services,
the checks, and the things that bite.

## Known defects

Each of these is open, reproducible, and has a mitigation a demo-site user or
operator can apply today.

| Issue | What a user would see | Impact | Mitigation |
| --- | --- | --- | --- |
| [#189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189) | an uncovered question asked as a follow-up is answered with a decline that cites unrelated policies, instead of the refusal card | the citations mislead, and the user loses the refusal card's route to a person | ask an uncovered question in a new conversation, where the gate scores it correctly |
| [#192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192) | an uncovered question on an HR-adjacent topic, or a prompt injection, is answered with a sentence saying the policies do not cover it, under a score badge and unrelated source chips, instead of the refusal card | the answer is safe, but the one-click route to a person is missing and the chips mislead | "Not what you needed?" under the answer still files the escalation. Found by the live evaluation on 2026-09-11 |
| [#118](https://github.com/CMSC495-GROUP3/Sourcebook/issues/118) | provider saturation reads as a generic error | the user does not know the request is worth retrying | `OPENAI_MAX_CONCURRENT_REQUESTS` bounds the damage; retry by hand |
| [#142](https://github.com/CMSC495-GROUP3/Sourcebook/issues/142) | assigning and deleting a project at the same moment can race | a conversation can end up pointing at a project that no longer exists; the list view treats it as ungrouped | unlikely at demo volume with one operator |
| [#158](https://github.com/CMSC495-GROUP3/Sourcebook/issues/158) | nothing at the database level prevents duplicate passage identities | a repeated ingestion could duplicate passages and skew retrieval | ingestion upserts by `(source, chunk_index)`. [PR #176](https://github.com/CMSC495-GROUP3/Sourcebook/pull/176) adds the constraint and is held for a maintenance window |
| [#159](https://github.com/CMSC495-GROUP3/Sourcebook/issues/159) | Human Resources has no in-app queue | the handler works from the API or a webhook-fed channel instead of a screen | `GET /api/escalations?status=open` and `PATCH` to resolve |
| [#160](https://github.com/CMSC495-GROUP3/Sourcebook/issues/160) | no weekly knowledge-gap report | content gaps have to be read out of the query log by hand | the log is populated and queryable; the report is drafted in [PR #171](https://github.com/CMSC495-GROUP3/Sourcebook/pull/171) |

## Technical debt

- The passage index migration in PR #176 needs a database snapshot and a
  maintenance window, because it deletes duplicates and the application
  refuses to start against the old index. It is deliberately not in this
  release.
- `CustomerDataProvider` is specified in the design document and not written.
  The plan is a simulated provider behind the contract, which would show the
  contract holds rather than that Sourcebook can read a real customer system.
- The web bundle is a single chunk over 500 KB. It is fine for a class demo and
  wants code splitting before anything larger.

## What this alpha does not establish

- **Answer quality is measured on twenty questions, once.** The smoke-tier
  evaluation in [live-evaluation.md](live-evaluation.md) ran on 2026-09-11
  with the real provider and index, on this prompt and on the one before
  PR #138. Retrieval and citation scored 100% of 12 answerable cases on both;
  the grounding gate stopped none of the five uncovered or injection cases on
  either, which is #192. The clarification judgements are one reader's. The
  full tier has not been run, and none of it says anything about a real
  corpus. Do not read a green workflow badge as evidence of answer quality.
- **The 10,000-user requirement is not verified.** The throughput figures in
  `docs/load-testing.md` are synthetic, with the model, the database,
  and retrieval faked and the limiter off. The real-service run in
  [live-benchmark.md](live-benchmark.md) is seven requests, which says the
  deployed path works for one user and a burst of three on one day and nothing
  about capacity.
- **The corpus is fictional.** Sourcebook has never run against a real
  company's policies. The retrieval threshold, the refusal rate, and citation
  accuracy would all need revisiting before anyone relied on it.
- **One deployment, one instance, no failover.** There is no backup schedule
  and no restore drill.

## Reproducing this exact version

The demo host follows `main`, so it moves past this tag. The tag does not.

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
git checkout v0.1.0-alpha.1
make setup && make stub
```

With a `.env` holding real credentials, `docker compose up --build` at that
checkout runs the full stack instead. The commit deployed on the demo site at any
moment is `refs/deployed/main` on the host; the README's "Automatic deploys"
section explains it. The demo site is expected to move past the tag. Showing it at
the tagged version is a by-hand procedure, written in
[handoff.md](handoff.md): stop the auto-deploy timer, check out the tag on the
host, build and start the stack with Compose, record the date, then re-enable
the timer. `scripts/deploy.sh` does not do this; it only triggers the
auto-deploy, which deploys `main`.
