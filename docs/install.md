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

This page is the entry point for all three. Where the [README](../README.md)
already has a procedure worked out in detail, this page says what the step is
for and links to it rather than copying it, so there is one place for each
procedure to go stale.

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
with `hr` instead to see the HR Requests and What People Ask pages, which only
the Human Resources password opens. `make stub` hashes both passwords when it
starts, so `make stub DEV_PASSWORD=something DEV_HR_PASSWORD=other` changes
them, and it launches `scripts/loadtest/server.py`, which patches the fakes in
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
`APP_PASSWORD_HASH` are set. The README's [Configure](../README.md#1-configure)
section shows how to generate the first and the third, including why a bcrypt
hash has to be pasted rather than echoed. It also explains what a second
password in `APP_PASSWORD_HASH_2` does and does not give you. Read that before
handing one to a reviewer.

Set `HR_PASSWORD_HASH` too if anyone will work escalations or read the
coverage report in the web app. It is the Human Resources password, generated
the same way and different from `APP_PASSWORD_HASH`. It may be the same hash
as `APP_PASSWORD_HASH_2`, which makes the second password the HR one; the
course deployment does this for the grader. Only a session opened with it
can use the HR Requests queue (`GET /api/escalations`, and `GET`, `PATCH`,
and retry-delivery on `/api/escalations/{escalation_id}`) and What People Ask
(`GET /api/reports/gaps`); every other valid token gets 403 there, and the sidebar hides both links from it. With it
unset, nobody can open either page, and employees can still escalate from the
chat. It does not scope conversations: any password still lists and opens
every conversation. The README's
[Known limitations](../README.md#known-limitations) says why.

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
| `HR_PASSWORD_HASH` | the Human Resources password; the only one that opens HR Requests and What People Ask | generated like the first, with a different password |
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
| `MONGO_MAX_POOL_SIZE` | connections per process; the arithmetic against the Atlas cap is in `sourcebook/rag/mongo.py` |
| `SIMILARITY_THRESHOLD` | refuse when the best passage scores below this; tune it from `query_logs`, never from the stub |
| `RETRIEVAL_K` | how many passages the model sees |
| `CHUNK_SIZE` | characters per passage at ingestion |
| `CHUNK_OVERLAP` | characters shared between neighbouring passages |
| `THREADPOOL_TOKENS` | the chat streaming thread pool; the measured curve is in [load-testing.md](load-testing.md) |
| `LOGIN_THREADPOOL_TOKENS` | a separate pool so sign-in still works when chat is saturated |
| `CHAT_RATE_LIMIT` | per-address limit on chat requests |
| `REINDEX_RATE_LIMIT` | per-address limit on reindex requests |

Two names in the file belong to the fake provider and mean nothing on a
real-services host: `FAKE_STREAM_DELAY_MS` and `FAKE_UTILITY_DELAY_MS` slow
the stub down so streaming looks realistic. `make stub` sets
`FAKE_PASSAGE_SCORE` and `FAKE_DB_LATENCY_MS` itself. Compose sets
`FORWARDED_ALLOW_IPS` in `docker-compose.yml`, so do not add it to `.env`,
and the deploy script's `AUTO_DEPLOY_MAX_FAILURES` is read from the host
environment, not from `.env`.

### Load the corpus

The repository ships 42 fictional HR documents in `data/sample-policies/`.
Two commands upload them to S3 and then chunk, embed, and store them in
Atlas. After that you create a Vector Search index named `vector_index` in
the Atlas UI, because a search index is not a regular index and the driver
cannot create it. That is the step people forget. The commands, the index
JSON, and how re-ingestion keeps the old corpus live while the new one loads
are all in the README's [Load the corpus](../README.md#2-load-the-corpus)
section. CONTRIBUTING's [Running against the real services](../CONTRIBUTING.md#running-against-the-real-services)
is the same thing as a shorter checklist.

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

The pilot at <https://sourcebook.duckdns.org> is the same Compose file you
just ran locally, on one EC2 instance, with `SITE_ADDRESS` set so Caddy can
fetch a Let's Encrypt certificate, and a systemd timer that pulls `main`
every two minutes and rebuilds only what changed. The README's
[Deployment](../README.md#deployment) section is the procedure, in order,
with the Elastic IP, the DNS record, the security group, the clone path, the
timer units, the disk, and the post-deploy checks. Follow that page rather
than this summary when you are actually at the keyboard.

The shape of it is this:

1. Configure `.env` exactly as in [Real services](#real-services), then add
   `SITE_ADDRESS` with the public hostname. DNS has to resolve to the
   instance before the first request, because Caddy answers the certificate
   challenge on port 80 then. [Certificates and the public address](../README.md#certificates-and-the-public-address)
   covers renewals and changing the name later.
2. Start the stack with `docker compose up -d --build`. Only Caddy publishes
   ports, 80 and 443.
3. Install and enable the `auto-deploy` and `docker-prune` timers from
   `scripts/systemd/`. From then on the host follows `main` on its own.
   Which paths trigger which rebuilds, how the health probe gates a deploy,
   and the failure cap are in [Automatic deploys](../README.md#automatic-deploys).
4. Load the corpus from a shell on the host, since ingestion needs the
   ingest dependencies and the same `.env`.

A host that already ran the older timer needs a one-time seed of
`refs/deployed/main` before the retry-aware script's first tick, or that
tick rebuilds everything. [Upgrading an existing install](../README.md#upgrading-an-existing-install)
has the three commands and what to check afterwards.

Two habits keep a host healthy. The timer only reacts to git, so after
editing `.env` on the instance you recreate the affected service yourself
with `docker compose up -d <service>`. And when two minutes is too long to
wait for a deploy, `scripts/deploy.sh` runs the same script over SSH right
now. The README's [Checking a deploy](../README.md#checking-a-deploy)
section is the three checks that confirm the stack is serving and that
client addresses reach the API intact.

Once real services are up, [evaluation.md](evaluation.md) is how you measure
what the system actually does with them.
