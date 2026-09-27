# Installing Sourcebook

## You may not need to install anything

Sourcebook is running right now at <https://sourcebook.duckdns.org>. It is
the real application against the real model, corpus, and vector index, and it
is the fastest way to see what the project does: sign in, ask a question about
the sample policies, open the cited document, ask something the policies do
not cover, and watch it refuse and offer to hand the question to a person.
Sign in with the shared password, which the team gives out on request rather
than publishing. The instance is not kept up around the clock, so a connection
timeout means it is switched off at the moment, not that it is broken. If you
are a reviewer or a grader, start there. Everything below is for running your
own copy.

## Three ways to run your own

There are three ways to run this project, and which one you want depends on
what you are trying to find out. If you want to see the application, sign in,
ask a question, and watch it refuse one, the stub route gets you there in
about ten minutes with nothing but Python and Node. If you want to judge how
well it retrieves and answers, you need the real services, which means an
OpenAI key, a MongoDB Atlas cluster, and an S3 bucket. If you are putting it
on a host for other people to use, the deployment route is the real-services
route plus one variable and a systemd timer.

This page is the entry point for all three, and it holds every procedure in
full, so there is one place for each to go stale. Why the system is built the
way it is lives in [architecture.md](architecture.md).

| Route | Answers the question | Needs a paid account |
| --- | --- | --- |
| [The stub](#the-stub) | what does it look like and how does it behave | no |
| [Real services](#real-services) | how good are the answers | yes |
| [Deployment](#deployment) | how do I run it for a team | yes |

Whichever route you take, `.env`, API keys, bcrypt hashes, and real policy
documents never go into git. `.gitignore` covers `.env`. The rest is on you.

## The stub

This is the real application, with the model and the database swapped out
from the outside. Nothing in the application code knows it is running against
fakes, and that is the point. What you see is the actual UI, the actual API,
and the actual refusal and escalation paths, with canned content behind them.

You need Python 3.11 or newer, Node 22 or newer, and `make`. Docker is not
involved.

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
make setup    # creates .venv, installs Python and Node dependencies
make stub     # terminal 1: the API on :8000 with a fake model and in-memory Mongo
make web      # terminal 2: the React app on :5173, proxying /api to :8000
```

Open <http://localhost:5173> and sign in with the password `dev`. Sign in
with `manager` instead to see the What People Ask page as a manager does, or
with `hr` to see it unfiltered along with HR Requests. `make stub` hashes all
three passwords when it starts, so `make stub DEV_PASSWORD=something
DEV_MANAGER_PASSWORD=boss DEV_HR_PASSWORD=other` changes them, and it launches `scripts/loadtest/server.py`, which patches the fakes in
around the real app.

Every answer in this mode is the same canned paragraph about PTO, and the
suggested follow-ups are canned too. Retrieval scores are fixed rather than
computed, so either every question answers or every question refuses. The
default is to answer. `make stub REFUSE=1` flips it, and that is how you see
the refusal card and the button that hands the question to a person.
`make stub REFUSE=judge` keeps the scores above the threshold and has the
coverage judge refuse instead, which shows the card for a question the
policies touch on but do not answer.
Conversations and escalations live in memory and are gone when you stop the
API. Because the scores are made up, this mode tells you nothing about answer
quality, and `SIMILARITY_THRESHOLD` should never be tuned against it.

The in-memory Mongo stub also deliberately does not implement MongoDB sessions
or transactions. Project assignment and deletion therefore use the sequential
fallback in stub mode. A passing stub test suite must not be interpreted as
evidence of atomic cross-collection referential integrity; that behavior is
verified separately against a transaction-capable MongoDB deployment.

The same commands appear in the README's [Quick start](../README.md#quick-start)
and in CONTRIBUTING under [Ten minutes to a running app](../CONTRIBUTING.md#ten-minutes-to-a-running-app),
which also explains what the stub is for during development.

On native Windows the Makefile does the right thing on its own. It notices
`OS=Windows_NT`, looks for the virtualenv tools in `.venv\Scripts` instead of
`.venv/bin`, and starts Python with `py -3`. The one thing to carry in your
head is that any command in the docs written as `.venv/bin/python` is
`.venv\Scripts\python.exe` on your machine. Git Bash sets the same variable,
so it behaves the same way. The team has run the stub route on macOS and
Linux; nobody has yet walked it end to end on Windows, so if you do and hit a
snag, open an issue with the command and the output.

## Real services

Take this route when the question is about retrieval quality, ingestion, or
the provider. Before you start you need an OpenAI API key, a MongoDB Atlas
deployment with Vector Search enabled, an S3 bucket, and AWS credentials that
can read and write it. Docker is needed only if you want to run the full
Compose stack rather than the dev servers.

### Configure

Copy the example file and fill it in with an editor:

```bash
cp .env.example .env
```

The API refuses to start until `JWT_SECRET_KEY`, `MONGODB_URI`, and
`APP_PASSWORD_HASH` are set. The comments in `.env.example` say what each
value is for. Generate the JWT signing secret with:

```bash
openssl rand -hex 32
```

Create a virtual environment and generate the shared password hash:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
python -c "import bcrypt; print(bcrypt.hashpw(b'replace-this-password', bcrypt.gensalt()).decode())"
```

Store only the hash in `APP_PASSWORD_HASH`. A bcrypt hash contains `$`, which
most shells interpret, so paste it with a text editor rather than `echo`.

#### More passwords

To hand out a second password without sharing the first, for a reviewer or a
grader, generate its hash the same way and put it in `APP_PASSWORD_HASH_2`.
Either password logs in; every configured hash is checked at startup and a
malformed one stops the server from booting. Leave the second unset to accept
only the shared password (plus the HR and manager ones below, if set).

Three things to know before handing one out. Every configured password opens
the employee routes, so the deployment is only as strong as the weakest one;
do not make the second one short because it is temporary. Each successful
login logs which variable matched and puts that name in the token's `cred`
claim, which is how to tell a reviewer's session from the team's afterwards.
Changing or unsetting a hash signs out everyone who logged in with it: each
session is bound to a fingerprint of that hash, so the next request with the
old token fails. Rotating `JWT_SECRET_KEY` is no longer needed just to revoke
one password's sessions; sessions from the other passwords keep working.

Two more passwords open pages the shared one cannot. Both are generated the
same way, and a session opened with either can do everything the shared
password can as well.

- **`HR_PASSWORD_HASH`**, for Human Resources. It is the only password that
  opens the HR Requests queue (`GET /api/escalations`, and `GET`, `PATCH`,
  and retry-delivery on `/api/escalations/{escalation_id}`) and the only one
  that can call `POST /api/documents/reindex`, which drops every cached
  answer. It opens the What People Ask report too, with every question
  listed.
- **`MANAGER_PASSWORD_HASH`**, for managers and supervisors. It opens the What
  People Ask report (`GET /api/reports/gaps`) and nothing else beyond the employee routes, so a manager
  can see what their people keep asking and cover it in training and
  orientation. A manager's report lists only questions asked in at least
  `MANAGER_MIN_CONVERSATIONS` separate conversations (default 3). A question
  typed once can point at the person who typed it, and a manager, unlike HR,
  is not the confidential channel. The totals at the top still count every
  question.

Every other valid token gets 403 on those routes, and the web app hides their
links unless the stored token's `cred` claim names the right variable. Leave a
variable unset and nobody can use its pages. Use passwords different from the
shared one: login checks `APP_PASSWORD_HASH` first, so an HR or manager hash of
the shared password never matches. Login then checks `HR_PASSWORD_HASH`,
`MANAGER_PASSWORD_HASH`, and `APP_PASSWORD_HASH_2`, in that order, so the same
hash in two of them gives the wider access. The course deployment sets
`MANAGER_PASSWORD_HASH` to the same hash as `APP_PASSWORD_HASH_2`, so the
grader's password opens What People Ask, and gives HR a password of its own.
A token keeps the `cred` it was issued with, so after that change anyone
signed in with the grader's password signs out and back in once to see the
page, and a session opened with the old HR password stops working once
`HR_PASSWORD_HASH` changes.

Leave `HR_PASSWORD_HASH` unset and nobody can open HR Requests, while
employees can still escalate from the chat.

#### Conversations and passwords

Conversations are separate from the passwords. Each browser keeps a random id
and sends it at login, and a session sees only the conversations and projects
filed under that id, whichever password opened it. Signing out keeps them;
clearing the browser's site data or switching browsers starts an empty
history. Conversations stored before this existed have no owner and stop
appearing for anyone. Every token issued before it is rejected, so everyone
signs in once more after the upgrade. The ownerless records stay in Mongo
until you remove them; see
[Removing ownerless conversations](#removing-ownerless-conversations).

Escalation records are kept. HR Requests reads only those, and each one
copies the question and answer it was filed from. The README's
[Known limitations](../README.md#known-limitations) has what browser-owned
conversations mean for privacy.

#### Every variable

Every variable `.env.example` sets or mentions is listed below, once, with
what it is for and where its value comes from. The comments in
`.env.example` and the defaults in `sourcebook/rag/config.py` and
`sourcebook/rag/llm.py` are the authority on values. The code reads a few
more names than these, all with defaults, and nothing in a normal install
needs them.

The API will not boot without these three.

| Name | What it is for | Where it comes from |
| --- | --- | --- |
| `JWT_SECRET_KEY` | signs login tokens | `openssl rand -hex 32` |
| `MONGODB_URI` | the Atlas connection string | the Atlas cluster's Connect dialog |
| `APP_PASSWORD_HASH` | bcrypt hash of the shared login password | generated locally, see Configure |

These are needed to answer questions and to ingest documents.

| Name | What it is for | Where it comes from |
| --- | --- | --- |
| `LLM_PROVIDER` | which `LLMProvider` in `sourcebook/rag/llm.py` to use | `openai` is the only one that ships |
| `OPENAI_API_KEY` | provider credentials | OpenAI |
| `MONGODB_DB` | the database name inside the cluster | your choice; the example suggests `policy_assistant` |
| `S3_BUCKET_NAME` | where the raw policy documents live | AWS |
| `AWS_ACCESS_KEY_ID` | S3 access | an AWS IAM user or role |
| `AWS_SECRET_ACCESS_KEY` | S3 secret | the same IAM user or role |
| `AWS_REGION` | the bucket's region | AWS; the example uses `us-east-1` |

These shape how the product presents itself and where escalations go. All
are optional.

| Name | What it is for | Where it comes from |
| --- | --- | --- |
| `APP_PASSWORD_HASH_2` | a second accepted password | generated like the first |
| `HR_PASSWORD_HASH` | the Human Resources password; the only one that opens HR Requests, and it opens What People Ask too | generated like the first, with a different password |
| `MANAGER_PASSWORD_HASH` | the manager and supervisor password; opens What People Ask, filtered to questions asked in several conversations | generated like the first, with a different password; the course deployment reuses `APP_PASSWORD_HASH_2` |
| `SITE_ADDRESS` | the public hostname Caddy serves and gets a certificate for | your DNS; leave unset for local Compose |
| `APP_ENV` | environment label; `production` makes the fake provider refuse to start | you |
| `APP_NAME` | the product name; change it in `web/src/config.ts` and `web/index.html` too | you |
| `CORS_ORIGINS` | comma-separated origins allowed during local development | you |
| `ESCALATION_CONTACT` | who the UI says a question is handed to | you |
| `ESCALATION_WEBHOOK_URL` | a JSON webhook that receives each escalation; a Slack or Teams incoming webhook works as-is | your chat tool, or empty to only store escalations |
| `ESCALATION_WEBHOOK_TIMEOUT_SECONDS` | HTTP timeout on that webhook | you |
| `ESCALATION_WEBHOOK_MAX_ATTEMPTS` | the first attempt plus retries before further retries are rejected | you |
| `ESCALATION_WEBHOOK_LEASE_SECONDS` | how long one worker holds an escalation while sending; must exceed the timeout | you |

These tune the provider, retrieval, and capacity. Leave them unset unless
you are deliberately changing a default, and read the file that owns the
default first.

| Name | What it is for |
| --- | --- |
| `OPENAI_ANSWER_MODEL` | the model that writes grounded answers |
| `OPENAI_UTILITY_MODEL` | the model for query rewrites and follow-up suggestions |
| `OPENAI_EMBEDDING_MODEL` | embeddings for ingestion and queries; changing it changes the vector dimensions, so the Atlas index has to change with it |
| `OPENAI_TIMEOUT_SECONDS` | idle time allowed between streamed chunks |
| `OPENAI_MAX_RETRIES` | SDK retries per call |
| `OPENAI_STREAM_DEADLINE_SECONDS` | wall-clock limit on a stream that keeps trickling |
| `OPENAI_MAX_CONCURRENT_REQUESTS` | how many provider calls may be in flight |
| `OPENAI_CAPACITY_WAIT_SECONDS` | how long a request waits for one of those slots |
| `REPORT_PROVIDER_TIMEOUT_SECONDS` | how long each What People Ask provider call may take, with no retry, before the page falls back to coarser grouping |
| `MONGO_MAX_POOL_SIZE` | connections per process; the arithmetic against the Atlas cap is in `sourcebook/rag/mongo.py` |
| `SIMILARITY_THRESHOLD` | refuse when the best passage scores below this; tune it from `query_logs`, never from the stub |
| `RETRIEVAL_K` | how many passages the model sees |
| `CHUNK_SIZE` | characters per passage at ingestion |
| `CHUNK_OVERLAP` | characters shared between neighbouring passages |
| `THREADPOOL_TOKENS` | the chat streaming thread pool; the measured curve is in [load-testing.md](load-testing.md) |
| `LOGIN_THREADPOOL_TOKENS` | a separate pool so sign-in still works when chat is saturated |
| `CHAT_RATE_LIMIT` | per-address limit on chat requests |
| `REINDEX_RATE_LIMIT` | per-address limit on reindex requests |
| `MANAGER_MIN_CONVERSATIONS` | fewest conversations a question needs before a manager sees it on What People Ask (default 3) |
| `REPORT_REFRESH_SECONDS` | seconds between background refreshes of What People Ask's 7, 30, and 90-day windows, so its counts are up to this old; 0 computes every load live (default 300) |

Two names in the file belong to the fake provider and mean nothing on a
real-services host: `FAKE_STREAM_DELAY_MS` and `FAKE_UTILITY_DELAY_MS` slow
the stub down so streaming looks realistic. `make stub` sets
`FAKE_PASSAGE_SCORE` and `FAKE_DB_LATENCY_MS` itself. Compose sets
`FORWARDED_ALLOW_IPS` in `docker-compose.yml`, so do not add it to `.env`,
and the deploy script's `AUTO_DEPLOY_MAX_FAILURES` is read from the host
environment, not from `.env`.

### Load the corpus

`data/sample-policies/` holds 42 fictional HR documents for demonstration.
Replace them with real ones and the same commands apply.

```bash
python -m sourcebook.rag.seed_documents     # upload data/sample-policies/ to S3
python -m sourcebook.rag.embed_documents    # chunk, embed, store in Atlas
```

Re-ingestion keeps the current corpus available while the replacement is
prepared. Every document is parsed and embedded first, one batch per document;
if any of that fails, the live collection and the corpus version are left as
they were. Then the new passages are upserted in place by `(source,
chunk_index)`, and only after they are all written does ingestion remove
sources and chunks that are no longer present in S3 and bump the corpus
version. The live `passages` collection is never emptied, and the Atlas
collection and its Vector Search index are never renamed or recreated. The
one caveat: while the upsert loop runs, a document whose chunk boundaries
moved can briefly have an old chunk and its overlapping replacement side by
side, so retrieval for a few seconds may surface both. That is consistent
enough to answer from, which is what #89 asked for. The reading copy of each
document in `document_bodies` follows the same discipline: upserted by source
after the passages, stale sources removed only at the end.

After upgrading to a version that stores reading copies, run the embed command
once more. Until then the library shows a document as its passages with a
notice: `POST /api/documents/reindex` only rebuilds the index from passages
and cannot recover a body, because chunks overlap.

In Atlas, create a Vector Search index named `vector_index` on the `passages`
collection:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    }
  ]
}
```

Create it in the Atlas UI or CLI. A search index is not a regular index and the
driver cannot create it, so this is the step people forget. `ensure_indexes()`
in `sourcebook/api/db.py` creates every other index at API startup.

#### Document format

Plain UTF-8 text with a short header block, a blank line, then the body:

```text
Title: Paid Time Off (PTO) Policy
Category: Time Off & Leave
Owner: Human Resources
Effective: 2026-01-01

## Overview
...
```

Only `Title` is required. Missing fields degrade to `null`, and an absent title
falls back to a readable form of the filename.

### Run

For day-to-day work, start the API with hot reload and the web app beside it.
The API is at <http://localhost:8000>, its interactive docs at
<http://localhost:8000/docs>, and the UI at <http://localhost:5173>.

```bash
.venv/bin/uvicorn sourcebook.api.main:app --reload    # terminal 1
make web                                              # terminal 2
```

To see what a deploy will actually run, bring up the Compose stack instead.
`make compose` builds the images and starts Caddy in front of Nginx in front
of the API. The app is at <http://localhost> and the health route at
<http://localhost/api/health>. Compose does not publish the API port, and
with `SITE_ADDRESS` unset Caddy serves plain HTTP.

### Verify transactional project integrity

The normal stub test suite cannot verify atomic project assignment or deletion
because FakeMongo intentionally has no MongoDB sessions or transactions. The
transaction regression tests are therefore opt-in and require a real
transaction-capable MongoDB deployment.

Set `MONGODB_TX_TEST_URI` and `MONGODB_TX_TEST_DB` to a test Atlas deployment
or other replica-set/sharded MongoDB database, then run:

```bash
MONGODB_TX_TEST_URI='<test connection string>' \
MONGODB_TX_TEST_DB='<test database name>' \
.venv/bin/python -m pytest -q tests/test_project_transaction_integration.py
```

Do not commit the connection string. The tests create uniquely named temporary
collections and remove them afterward. They verify that a concurrent assignment
cannot survive deletion of its project and that a failed delete+unassign
transaction rolls back both operations. The test fails rather than silently
falling back if the configured real MongoDB deployment does not support
transactions.

## Deployment

The demo site runs on a single EC2 instance at <https://sourcebook.duckdns.org>.
DuckDNS provides the name for free and Caddy fetches the certificate, so the
instance needs no manual TLS setup. The stack is the same Compose file used
locally, plus one variable in `.env`.

1. Give the instance an Elastic IP. A stopped and restarted instance otherwise
   gets a new public address and the DNS record goes stale.
2. In the DuckDNS dashboard, point the subdomain at that address.
3. Security group inbound rules: 80 and 443 from anywhere, 22 from your own
   address. Leave 3000 and 8000 closed; nothing listens on them.
4. On the instance, install Docker, clone the repository into
   `/home/ubuntu/CMSC495-CAP`, and write `.env` as in [Configure](#configure) with one
   extra line:

   ```bash
   git clone https://github.com/CMSC495-GROUP3/Sourcebook.git /home/ubuntu/CMSC495-CAP
   cd /home/ubuntu/CMSC495-CAP
   ```

   ```dotenv
   SITE_ADDRESS=sourcebook.duckdns.org
   ```

5. Start the stack:

   ```bash
   docker compose up -d --build
   ```

   The DNS name must already resolve to the instance. Caddy answers the Let's
   Encrypt HTTP challenge on port 80 on the first request. If the challenge
   fails it retries with backoff, and `docker compose logs caddy` shows why.

6. Turn on automatic deploys. The checkout must already be at
   `/home/ubuntu/CMSC495-CAP` (step 4); that is where the unit file points:

   ```bash
   sudo cp scripts/systemd/auto-deploy.* /etc/systemd/system/
   sudo cp scripts/systemd/docker-prune.* /etc/systemd/system/
   sudo systemctl enable --now auto-deploy.timer docker-prune.timer
   ```

   The deploy timer fires as soon as it is enabled. `docker-prune.timer`
   runs a weekly `docker builder prune -f --keep-storage 300M` so the build
   cache cannot fill the root volume between rebuilds. `auto_deploy.sh`
   also prunes when root free space drops under 1 GiB before a rebuild.
   The demo host's root volume was grown to 16 GB on 2026-09-05 (issue
   #79), so a rebuild no longer competes with the build cache for space. If
   `df -h /` ever shows under about 1 GB free again, run
   `docker builder prune -f` by hand before a deploy that rebuilds both
   images, and see [Root disk](#root-disk).

7. Load the corpus. Ingestion runs from a shell on the host, not from a
   container: it needs the ingest dependencies and reads the same `.env`.

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements/ingest.txt
   .venv/bin/python -m sourcebook.rag.seed_documents    # first time: upload data/sample-policies/ to S3
   .venv/bin/python -m sourcebook.rag.embed_documents
   ```

   Run the embed command again whenever the documents in S3 change, and once
   after deploying a version that stores document bodies; until then the
   library shows each document as its passages with a notice. `.venv/` is
   ignored by git, so it does not disturb the auto-deploy's clean-checkout
   check.

### Automatic deploys

From then on the host polls upstream `main` every two minutes and rebuilds
only what changed, gated on `/api/health`.
[ci-cd.md § From merge to the demo containers](ci-cd.md#from-merge-to-the-demo-containers)
walks each tick: which paths rebuild which service, the health gate, and the
failure cap. `sudo journalctl -u auto-deploy.service` shows what the last run
did. Run the script by hand as `ubuntu`, not under `sudo`; it refuses to run on
a checkout that is not on `main` or that has local edits, untracked files
included.

To force a full redeploy of both images on the next tick (for example after
deleting a bad image by hand), drop the success marker:

```bash
git update-ref -d refs/deployed/main
```

The script only reacts to git. After editing `.env` on the instance, recreate
the affected service yourself with `docker compose up -d <service>`.

`scripts/deploy.sh` runs the same script now, over SSH, for when two minutes
is too long to wait:

```bash
EC2_HOST=ubuntu@sourcebook.duckdns.org SSH_KEY_PATH=~/.ssh/key.pem ./scripts/deploy.sh
```

`SSH_KEY_PATH` must point at the instance's private key. If `~/.ssh/config`
already names the key for the host, a wrong path only prints a warning and ssh
uses the configured key, but pass the real path so the script fails loudly when
the key is missing.

### Upgrading an existing install

Hosts that already run the older auto-deploy timer need a one-time handoff
before the first tick that executes the retry-aware script. Without a seeded
`refs/deployed/main`, that tick diffs against the empty tree, rebuilds both
images with `--pull`, and recreates Caddy: a slow, avoidable rebuild that
failed outright while the root disk was near full (issue #79).

1. Confirm the checkout is clean under the new rule (untracked files count):

   ```bash
   cd /home/ubuntu/CMSC495-CAP && git status --porcelain --untracked-files=all
   ```

   Must print nothing. If it lists files, delete them or add them to
   `.gitignore` in a separate PR first.

2. Seed the deployed ref to the commit whose images are currently running
   *before* the new retry logic is active on the host (while the old script is
   still what the timer runs, immediately before merging the retry change):

   ```bash
   git update-ref refs/deployed/main "$(git rev-parse HEAD)"
   ```

3. Verify the ref before the first new deploy tick:

   ```bash
   git rev-parse refs/deployed/main
   ```

   It must match the running checkout (`git rev-parse HEAD`). After the upgrade
   lands, watch two ticks of `sudo journalctl -u auto-deploy.service -f`; a
   later idle tick should log `nothing to rebuild` and exit 0.

### Certificates and the public address

Certificates persist in the `caddy_data` volume across restarts and deploys.
With an Elastic IP the DuckDNS record never needs to change, so no update
client runs on the instance.

To change the public address on a running instance, point the new DuckDNS
name at the Elastic IP first, then edit `SITE_ADDRESS` in `.env` and run
`docker compose up -d caddy`. Compose sees the changed variable and recreates
only Caddy, which requests a certificate for the new name as it starts. The
old name stops answering at once, so tell anyone using it before the switch.

### Checking a deploy

The script ends with `docker compose ps`. Three more checks confirm the stack is
serving and that client addresses reach the API the way the trust chain intends
(see [architecture.md](architecture.md#client-identity-across-the-proxies)).

1. The site answers over TLS and the health route returns 200:

   ```bash
   curl -sI https://sourcebook.duckdns.org/ | grep -i strict-transport
   curl -s -o /dev/null -w '%{http_code}\n' https://sourcebook.duckdns.org/api/health
   ```

2. Both Compose networks sit inside either `172.16.0.0/12` or
   `192.168.0.0/16` (the two ranges Nginx and Uvicorn trust), and the API
   container carries the trust variable:

   ```bash
   ssh ubuntu@sourcebook.duckdns.org '
     docker network inspect cmsc495-cap_edge cmsc495-cap_app \
       --format "{{.Name}} {{range .IPAM.Config}}{{.Subnet}}{{end}}"
     docker inspect cmsc495-cap-api-1 \
       --format "{{range .Config.Env}}{{println .}}{{end}}" | grep FORWARDED'
   ```

   A subnet outside both trusted ranges indicates a custom Docker
   `default-address-pools` configuration. Clients share a rate-limit
   bucket until the configured pool and trust list agree.

3. The API log shows the external client, not a container address. Send one
   request with a forged header, then read the log:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 198.18.0.1' \
     -H 'Content-Type: application/json' --data '{"password":"wrong"}' \
     https://sourcebook.duckdns.org/api/auth/login
   ssh ubuntu@sourcebook.duckdns.org 'docker logs cmsc495-cap-api-1 --tail 5'
   ```

   The request returns 401 and the "Failed login attempt from" line carries
   your public address. If it carries 198.18.0.1, the forged header got
   through and the proxy configuration has regressed.

## Maintenance on the host

### Root disk

The demo host launched with a ~7 GB root volume. Docker images are about
500 MB and one full rebuild leaves ~1 GB of build cache, which was enough to
make the next rebuild fail for lack of space (issue #79). The volume was grown
to 16 GB on 2026-09-05, which left about 8 GB free after a warm rebuild, and
`docker-prune.timer` is enabled so the cache cannot creep into that headroom.
The pre-build prune in `auto_deploy.sh` stays as a backstop.

To grow the volume again, change its size in the AWS console (gp3 resizes
online), then on the instance:

```bash
lsblk
sudo growpart /dev/xvda 1
sudo resize2fs /dev/xvda1
df -h /
```

Device names come from `lsblk`. The demo host shows `/dev/xvda`; Nitro
instance types show `/dev/nvme0n1` and `nvme0n1p1` instead. `growpart` prints
`NOCHANGE` when the partition already fills the volume, which means the volume
itself has not been grown yet.

### Query log report and rollup backfill

For score histograms or an exact window, run the read-only report on the
host. The cluster's IP access list admits that host, so anywhere else waits out
`--timeout` (default 10 s) and then fails in a way that looks like a config
typo.

    python -m sourcebook.rag.query_log_reports --since 2026-08-01

`--until` defaults to now. Optional `--top` and `--min-repeat` bound the ranked
lists. `query_logs` rows expire after 90 days (`QUERY_LOG_TTL_SECONDS`), so a
window that ends earlier than that prints an empty report rather than an error.

What People Ask reads per-day counts rather than the rows
([architecture.md](architecture.md#learning-from-the-query-log)). Rows logged
before those counts existed need a one-time backfill after the deploy that
adds them. Rerunning it skips rows it has already recorded. A run
interrupted between recording a row and marking it counts that one ask twice
on the next run, so let it finish:

    python -m sourcebook.rag.query_log_rollup --backfill

On the demo host, run both inside the API container so they read the app's
settings: `docker compose exec -T api python -m ... < /dev/null`.

### Removing ownerless conversations

Conversations and projects stored before each browser had an owner id stay in
Mongo, and nothing in the app can reach or delete them. They still hold the
questions people typed, so remove them once the upgrade has settled. The
script counts them and changes nothing until it is given `--delete`:

```bash
.venv/bin/python -m scripts.purge_ownerless_conversations
.venv/bin/python -m scripts.purge_ownerless_conversations --delete
```

## Where to go next

- [evaluation.md](evaluation.md): measure what the system does with the real
  services.
- [ci-cd.md](ci-cd.md): the workflows, the deploy pipeline, and the release
  procedure.
- [user-guide.md](user-guide.md): what employees, managers, and Human
  Resources see.
- [architecture.md](architecture.md): why it is built this way.
