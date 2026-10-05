# Sourcebook v1.1.1

A patch release after [`v1.1.0`](../v1.1.0/release-notes.md). It adds no
feature. It fixes how What People Ask recovers from a deploy and updates the
dependencies, including the OpenAI client that every answer goes through.
Sourcebook is a CMSC 495 capstone project, built for a fictional company, and
the demo site is a class demo.

Release [`v1.1.1`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v1.1.1).
The commit it names and the checks run on it are in [handoff.md](handoff.md).

## What changed since v1.1.0

- **What People Ask stays under five minutes old across a deploy.** At
  `v1.1.0` the new API waited out the old one's refresh lease, so the counts
  could reach 15 minutes old after a deploy. Now an API that shuts down
  between refreshes releases the lease, and its replacement refreshes as it
  starts. On the demo host the first refresh came six seconds after start. A
  deploy that lands during a refresh still waits, up to 12 minutes (PR #315).
- **The OpenAI client moved from 3.15.0 to 3.23.0.** Both live evaluation
  tiers ran again on the release code and match `v1.0.0` on every metric:
  100% on the 20-case smoke tier, and 47 of 49 answerable cases plus every
  unsupported and prompt-injection case on the 59-case full tier. See
  [live-evaluation.md](live-evaluation.md) (PR #319).
- **Other API dependencies moved too.** fastapi 0.142.2, which brings in
  opentelemetry-api 1.45.0; pyjwt 2.15.1, which fixes PYSEC-2026-4141;
  pymongo 4.18.2; uvicorn 0.54.0; python-dotenv 1.2.4 (PR #319).
- **The web app picks up lucide-react 1.49.0.** vite 8.3.2 and newer
  eslint, vitest, and jsdom build and test it (PR #318).
- **No known vulnerabilities in either dependency tree.** urllib3 2.8.0 and
  brace-expansion 5.0.12 clear the last advisories, in the ingestion and
  development tools; neither ships in the API image (PR #321).

## Upgrading

Rebuild the images. `docker compose up -d --build` installs the new locks; no
setting, index, or backfill changed. A host that skipped `v1.1.0` still needs
that release's [backfill](../v1.1.0/release-notes.md#upgrading).

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

- **Latency on the new OpenAI client.** The live evaluation scores answers
  but does not time them, and the [live benchmark](../v1.0.0/live-benchmark.md)
  did not run again.
- **What People Ask on Atlas**, as in [`v1.1.0`](../v1.1.0/release-notes.md#what-this-release-does-not-establish).

## Reproducing this exact version

The demo host follows `main`, so it moves past this tag. The tag does not.

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
git checkout v1.1.1
make setup && make stub
```
