# API (for client authors)

This page is the client walkthrough. The machine-readable contract is
[openapi.json](openapi.json). Regenerate it with `make openapi`; CI fails if the
committed file is stale. The live console is `/docs` while the API is running
(`make stub` on :8000, password `dev`, or `hr` for the HR routes). Setup and
the things that bite are in
[CONTRIBUTING.md](../CONTRIBUTING.md).

Send `Authorization: Bearer <access_token>` on every route except
`/api/auth/login`, `/api/health`, and `/api/config`. History is stored on the
server: the client sends a question and a `session_id`, never a `chat_history`
array.

Ids, timestamps, tokens, and `corpus_version` change on every request. The
bodies below were taken from one stub run so the shapes are real.

## Rate limits and the error envelope

Errors use FastAPI's envelope: `{"detail": ...}`. `detail` is a string for
application errors and a list of `{loc, msg, type, ...}` objects for
validation (HTTP 422). A rate-limit response is HTTP 429 with
`{"error": "Rate limit exceeded: N per 1 minute"}`.

Limits are per remote address per API worker (slowapi's default store is
in-process). Defaults:

| Route | Limit |
| --- | --- |
| `POST /api/auth/login` | 10/minute |
| `POST /api/chat`, `POST /api/chat/stream` | `CHAT_RATE_LIMIT` (default 30/minute) |
| `POST /api/escalations`, `POST /api/escalations/{escalation_id}/retry-delivery` | 5/minute |
| `POST /api/documents/reindex` | `REINDEX_RATE_LIMIT` (default 2/minute) |
| `GET /api/reports/gaps` | 30/minute |

Missing bearer → `{"detail": "Not authenticated"}`. Bad or rotated token →
`{"detail": "Invalid or expired token."}`. Wrong password →
`{"detail": "Incorrect password."}`. A valid token that was not issued for the
HR password, on an HR-only route → HTTP 403,
`{"detail": "Human Resources sign-in required."}`. On the coverage report, a
token from neither the manager nor the HR password → HTTP 403,
`{"detail": "Manager or Human Resources sign-in required."}`.

## HR-only routes

Login accepts up to four passwords. The token's `cred` claim names the
variable whose hash matched: `APP_PASSWORD_HASH`, `APP_PASSWORD_HASH_2`,
`HR_PASSWORD_HASH`, or `MANAGER_PASSWORD_HASH`. Every signed-in route takes
any of them except these five, which take only an `HR_PASSWORD_HASH` session:

- `GET /api/escalations`
- `GET /api/escalations/{escalation_id}`
- `PATCH /api/escalations/{escalation_id}`
- `POST /api/escalations/{escalation_id}/retry-delivery`
- `POST /api/documents/reindex`

and `GET /api/reports/gaps`, which takes an `HR_PASSWORD_HASH` or a
`MANAGER_PASSWORD_HASH` session and filters what a manager sees (see
[Coverage report](#coverage-report)).

`POST /api/escalations` is not one of them; employees file escalations from
the chat. When `HR_PASSWORD_HASH` is unset, the five HR-only routes answer 403
to everyone, and when both it and `MANAGER_PASSWORD_HASH` are unset, so does
the report. The web app decodes the token's payload to decide which links to
show, but the server check above is the only gate.

## Owners

Conversations and projects belong to the browser that created them. The
token's `sub` claim is an owner id, 32 lowercase hex digits; the web app keeps
one in local storage and sends it as `client_id` at login, so signing out and
back in on the same browser keeps its history. A client that sends no
`client_id` gets a fresh owner id at every login. Every conversation, project,
and chat route, and filing an escalation, sees only the caller's own records;
someone else's session id or project id answers 404, the same as one that does
not exist. HR sessions are no exception. Records stored before owners existed
match no one; `scripts/purge_ownerless_conversations.py` deletes them (see
[install.md](install.md#removing-ownerless-conversations)). A token without an owner id in `sub`, which is every token issued
before this change, gets 401.

Both chat routes answer HTTP 503 when the model provider is at its
concurrency limit (`OPENAI_MAX_CONCURRENT_REQUESTS`, waited on for
`OPENAI_CAPACITY_WAIT_SECONDS`). The body is
`{"error": "<message>", "retryable": true}` and a `Retry-After` header says
how many seconds to wait. Nothing is stored or logged for that turn, so a
retry is a fresh question. This is distinct from a generation failure, which
is not retryable and keeps the shapes below.

## Sign in

`POST /api/auth/login`

```http
POST /api/auth/login
Content-Type: application/json

{"password": "dev", "client_id": "5f0c3a9e1b7d4c2a8e6f0b1d3c5a7e9f"}
```

`client_id` is optional; see [Owners](#owners).

```json
{
  "access_token": "<access_token>",
  "token_type": "bearer"
}
```

The live body is a JWT that lasts 24 hours; the example is a placeholder so
the committed page does not look like a leaked token. Rotating the password
hash revokes sessions bound to it. Paste a live token into `/docs` → Authorize
to call the rest of the console.

## Ask (SSE)

The UI uses `POST /api/chat/stream`. `POST /api/chat` is the same grounding
rule as a single JSON body, kept for tests and scripts.

`question` is 1–5000 characters. `session_id` is optional; when present it must
match `^[A-Za-z0-9_-]+$` (max 64). A newline in `session_id` is rejected.

### Stream

`POST /api/chat/stream` — `text/event-stream`. Each event is `data: <json>\n\n`.

```http
POST /api/chat/stream
Authorization: Bearer <access_token>
Content-Type: application/json

{"question": "Can I carry unused days?", "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b"}
```

The stub streams one chunk per word of the fake answer, then `done`, then
`follow_ups`:

```
data: {"chunk": "Based"}

data: {"chunk": " on"}

data: {"chunk": " the"}

…
data: {"done": true, "message_id": "75fa3bcb15324c9cae08d61b9adcbc23", "sources": ["Paid Time Off (PTO) Policy"], "confidence": 75, "refused": false}

data: {"follow_ups": ["How do I request time off?", "What happens to unused days when I leave?", "Do company holidays count against my balance?"]}
```

Every event type:

| Event | Payload |
| --- | --- |
| token | `{"chunk": "<text>"}` |
| finished | `{"done": true, "message_id": "<32 hex>", "sources": ["…"], "confidence": 75, "refused": false}` |
| finished from cache | same as finished, plus `"cached": true` |
| refused | `{"done": true, "message_id": "…", "sources": [], "confidence": <int>, "refused": true, "refusal_reason": "no_match"}` after one `chunk` that is the refusal text. `refusal_reason` is `no_match` when retrieval similarity missed the threshold and `not_covered` when it cleared but the coverage judge refused. A cached refusal carries it too, and one cached before the field existed sends `null` |
| suggestions | `{"follow_ups": ["…", "…", "…"]}` — omitted on refusal; may be skipped if the client hangs up after `done` |
| generation failure | `{"error": "An error occurred while generating the response."}` |
| provider busy after a token | `{"error": "<message>", "retryable": true}`; before the first token the whole response is the HTTP 503 above instead |

`message_id` names the assistant turn for escalation. Do not use list position.

### Non-streaming

`POST /api/chat`

```http
POST /api/chat
Authorization: Bearer <access_token>
Content-Type: application/json

{"question": "How much PTO do I get?", "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b"}
```

```json
{
  "answer": "Based on the policy documents provided, full-time employees accrue 15 days of paid time off per year for the first two years of service, rising to 20 days from year three and 25 days from year six. Accrual begins on your first day and there is no waiting period before you may use it. You may carry a maximum of 10 unused days into the following calendar year; anything above that is forfeited on December 31. This is drawn from the Paid Time Off (PTO) Policy, effective 2026-01-01. For absences longer than five consecutive business days you will also need approval from Human Resources.",
  "sources": ["Paid Time Off (PTO) Policy"],
  "confidence": 75,
  "follow_ups": [
    "How do I request time off?",
    "What happens to unused days when I leave?",
    "Do company holidays count against my balance?"
  ],
  "refused": false,
  "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b",
  "message_id": "11f49d3989164c59be28882a2f9ce9fd"
}
```

A refusal returns `refused: true`, empty `sources` / `follow_ups`, and the
fixed refusal text (it names Human Resources; see `REFUSAL_MESSAGE` in
`sourcebook/rag/config.py`). `refusal_reason` is `no_match` or `not_covered`
as in the stream, and `null` on an answer. The stored assistant turn keeps the
same field, so a reloaded conversation shows the same refusal card. `message_id` is null when the request had no
session. A saturated provider returns the HTTP 503 described under the error
envelope rather than a 200 with an error answer.

## Follow-up in a session

Create a session, then send the next question with the same `session_id`. The
server loads prior turns and may rewrite the retrieval query. There is no
client-supplied history field and no free-text "follow-ups" route — suggested
questions are just new `question` values.

`POST /api/conversations` then the stream above is the usual order. To reopen:

`GET /api/conversations/{session_id}`

```http
GET /api/conversations/7059759c-1f55-4812-852c-06a11bb5cc4b
Authorization: Bearer <access_token>
```

```json
{
  "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b",
  "title": "PTO questions",
  "project_id": "1d91575f-a1d3-4bed-87db-3afe9af7cf60",
  "messages": [],
  "created_at": "2026-09-12T01:03:57.702699+00:00",
  "updated_at": "2026-09-12T01:03:57.702699+00:00"
}
```

After chat, `messages` holds the user turn and the assistant turn (with
`message_id`, `sources`, `confidence`, `refused`, `follow_ups`).

## Escalate

`POST /api/escalations` copies the question from the stored conversation. Send
`message_id` from `done` (or `message_index` only for turns persisted before
ids existed). `reason` is `refused` or `unhelpful`.

```http
POST /api/escalations
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b",
  "message_id": "11f49d3989164c59be28882a2f9ce9fd",
  "reason": "unhelpful",
  "note": "Need the carry-over rule in writing."
}
```

```json
{
  "escalation_id": "da78161d307f40868c3b92db5e04223d",
  "status": "open",
  "reason": "unhelpful",
  "contact": "Human Resources",
  "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b",
  "message_index": 1,
  "message_id": "11f49d3989164c59be28882a2f9ce9fd",
  "question": "How much PTO do I get?",
  "answer_excerpt": "Based on the policy documents provided, full-time employees accrue 15 days of paid time off per year for the first two years of service, rising to 20 days from year three and 25 days from year six. Accrual begins on your first day and there is no waiting period before you may use it. You may carry a maximum of 10 unused days into the following calendar year; anything above that is forfeited on December 31. This is drawn from the Paid Time Off (PTO) Policy, effective 2026-01-01. For absences longer than five consecutive business days you will also need approval from Human Resources.",
  "refused": false,
  "confidence": 75,
  "sources": ["Paid Time Off (PTO) Policy"],
  "note": "Need the carry-over rule in writing.",
  "resolution": null,
  "created_at": "2026-09-12T01:04:16.973759+00:00",
  "updated_at": "2026-09-12T01:04:16.973759+00:00",
  "resolved_at": null,
  "delivery_status": "not_configured",
  "delivery_attempts": 0,
  "delivery_last_attempt_at": null,
  "delivery_claimed_at": null,
  "delivery_retryable": false
}
```

Escalating the same message twice returns the first record. Create never waits
on the webhook.

`delivery_status` and `delivery_retryable` are computed for each response, not
stored:

| `delivery_status` | Meaning |
| --- | --- |
| `not_configured` | No `ESCALATION_WEBHOOK_URL` is set and nothing was ever sent. The stub returns this |
| `pending` | A webhook is configured and a send is queued, in flight, or not yet attempted |
| `delivered` | The webhook accepted the last attempt |
| `failed` | The last attempt failed |

`delivery_retryable` is true only when `POST .../retry-delivery` would send
now: a webhook is configured, attempts are under
`ESCALATION_WEBHOOK_MAX_ATTEMPTS`, and no live claim holds the record.

### Webhook delivery

Records land in the `escalations` collection with status `open`. If
`ESCALATION_WEBHOOK_URL` is set, each one is also posted there in a background
task after the response is sent. The payload has a
top-level `text` field, so a Slack or Teams incoming webhook renders it with no
adapter. Each attempt updates non-secret delivery fields on the record
(`pending` / `delivered` / `failed`, attempt count, last-attempt time). Delivery
is best effort and logged on failure; the webhook URL is never stored, logged,
or returned. The record is already stored, and a webhook outage must not turn a
successful hand-off into an error. Failed deliveries can be retried with
`POST /api/escalations/{id}/retry-delivery` up to
`ESCALATION_WEBHOOK_MAX_ATTEMPTS`, with an atomic claim so concurrent retries
cannot double-send. Claims older than `ESCALATION_WEBHOOK_LEASE_SECONDS`
(default 30) can be recovered after a worker interruption. The lease must be
greater than `ESCALATION_WEBHOOK_TIMEOUT_SECONDS`; invalid configuration fails
at startup. Records created before delivery tracking can be claimed as legacy
work. Delivery is at-least-once: a receiver that accepts a request immediately before the worker
dies may see the same escalation again, so consumers should deduplicate by
`escalation_id`.

Because `not_configured` and `delivery_retryable` are computed rather than
stored, setting `ESCALATION_WEBHOOK_URL` later turns records that were never
attempted back into `pending`, and the HR Requests page can send them.

## Human Resources queue and resolve

Every route in this section needs an HR session; see
[HR-only routes](#hr-only-routes).

`GET /api/escalations?status=open` — newest first. Optional `session_id`,
`limit` 1–200 (default 50).

```http
GET /api/escalations?status=open
Authorization: Bearer <hr_access_token>
```

```json
{
  "items": [
    {
      "escalation_id": "da78161d307f40868c3b92db5e04223d",
      "status": "open",
      "reason": "unhelpful",
      "contact": "Human Resources",
      "session_id": "7059759c-1f55-4812-852c-06a11bb5cc4b",
      "message_index": 1,
      "message_id": "11f49d3989164c59be28882a2f9ce9fd",
      "question": "How much PTO do I get?",
      "answer_excerpt": "Based on the policy documents provided, full-time employees accrue 15 days of paid time off per year for the first two years of service, rising to 20 days from year three and 25 days from year six. Accrual begins on your first day and there is no waiting period before you may use it. You may carry a maximum of 10 unused days into the following calendar year; anything above that is forfeited on December 31. This is drawn from the Paid Time Off (PTO) Policy, effective 2026-01-01. For absences longer than five consecutive business days you will also need approval from Human Resources.",
      "refused": false,
      "confidence": 75,
      "sources": ["Paid Time Off (PTO) Policy"],
      "note": "Need the carry-over rule in writing.",
      "resolution": null,
      "created_at": "2026-09-12T01:04:16.973759+00:00",
      "updated_at": "2026-09-12T01:04:16.973759+00:00",
      "resolved_at": null,
      "delivery_status": "not_configured",
      "delivery_attempts": 0,
      "delivery_last_attempt_at": null,
      "delivery_claimed_at": null,
      "delivery_retryable": false
    }
  ],
  "total": 1
}
```

`GET /api/escalations/{escalation_id}` returns that same record as an object.

`PATCH /api/escalations/{escalation_id}`

```http
PATCH /api/escalations/da78161d307f40868c3b92db5e04223d
Authorization: Bearer <hr_access_token>
Content-Type: application/json

{"status": "resolved", "resolution": "Pointed them at the PTO policy carry-over section."}
```

```json
{"status": "resolved", "resolution": "Pointed them at the PTO policy carry-over section.", "resolved_at": "2026-09-12T01:04:16.985959+00:00"}
```

(The live body is the full record with `status`, `resolution`, and `resolved_at`
updated.)

`POST /api/escalations/{escalation_id}/retry-delivery` re-sends a failed
webhook. With no webhook configured the stub returns:

```json
{"detail": "Webhook delivery is not configured."}
```

## Coverage report

Every chat request writes one `query_logs` row (question hash, scores, refused,
sources, cache hit, latency). How that log is used is in
[architecture.md § Learning from the query log](architecture.md#learning-from-the-query-log).

`GET /api/reports/gaps` ranks that log for the What People Ask page. It needs
a manager or HR session ([HR-only routes](#hr-only-routes)). `days`
(1–90, default 30) sets the window in whole UTC days, today included, so
`since` is a UTC midnight; `top` (1–100, default 20)
caps each list. A window longer than the log's TTL is shortened to it, and
`days` in the response is the one used. The counts come from a per-question,
per-day rollup kept as each ask is logged, not from the raw rows (#291).

The page's windows, 7, 30, and 90 days, are read from snapshots that the API
refreshes in the background every `REPORT_REFRESH_SECONDS` (default 300), so
their counts are normally up to that old and never more than three intervals. `until` in the response is when the
snapshot was taken, and `since` is the UTC midnight its window starts at. Any
other `days`, or a window whose snapshot is missing or more than three
intervals old, is computed when it is asked for.

- `gaps`: refused questions, most asks first. Every refusal is a gap, even one
  person's, so this list ranks on asks.
- `faq`: questions asked in at least two conversations, most conversations
  first, with how many of the asks were refused.

On a manager's session the route first drops every wording asked in fewer
than `MANAGER_MIN_CONVERSATIONS` conversations (default 3), then groups what is
left, so no question text a manager sees, row or other wording, was typed in
fewer conversations than that. `min_conversations` in the response is that
number, or `null` on an HR session, which sees every wording. `total` and
`refused` count every row either way.

Each row carries `count` (every ask, including one person asking again) and
`conversations` (distinct `session_id` values). A conversation is not a
person, but it is the closest the log gets. A conversation is counted on the
day of its first ask of that question, so one that first asked before the
window and asked again inside it adds an ask but not a conversation. The count
can be lower than the raw log's, never higher, which keeps a manager's
`min_conversations` filter on the safe side. Near-identical wordings share a
row; see [Grouping by meaning](#grouping-by-meaning) below.

`question` is the logged condensed question, or the truncated raw one, or
`null` when neither was logged. No session ids are returned, but the question
text comes from what the employee typed (the condensed rewrite when there is
one), which is why the route is limited to manager and HR sessions and a
manager's view drops rare wordings. It is the one place HR or a manager sees
questions across browsers.

Each query stops after five seconds. A snapshot read never comes near that. A
window computed when asked can: a 90-day one at the planned volume does. A
report that runs longer returns HTTP
503 with `{"detail": "This report took too long. Try a shorter window."}`.
One that passes MongoDB's per-stage memory limit returns 503 with
`{"detail": "This report needs too much memory. Try a shorter window."}`. The
rollup's `$group` holds only sums, so it should not hit that limit; see
[load testing](load-testing.md).

### Grouping by meaning

Both lists merge near-identical wordings of one question into one row (#287). The log's
`question_hash` groups identical text. The route then merges hash groups whose
question embeddings are within `QUESTION_GROUP_THRESHOLD` cosine, default 0.91.
Each wording joins the most asked group it is close to, compared with that
group's first wording only, so a chain of near neighbours cannot drift into one
row. `question` is the most asked wording. `count`, `refused`, and
`conversations` cover every wording in the row, and a conversation that used
two wordings counts once. `other_wordings` lists up to five more, most asked
first, and `other_wording_count` says how many there are in all.

Only the top 200 hash groups per list are grouped: refused wordings by asks,
all wordings by conversations. Their vectors come from `embedding_cache`,
where retrieval stored them. That cache keeps 30 days, so on a 90-day window
the older wordings are embedded in one provider call. Those vectors are kept
in a bounded in-process memo (5,000 entries, off when `CACHE_ENABLED=0`) and never written to Mongo, so a
repeat load makes no provider call and the route writes nothing.
If that call fails, `grouping` is `"exact"` and every wording has its own row.

Cosine cannot tell a paraphrase from a near neighbour, so pairs scoring from
`QUESTION_JUDGE_FLOOR` (default 0.7) up to the threshold go to the utility
model (#293). It gets both wordings as untrusted data and must reply
`{"same": [2, 5]}`, the numbers of the pairs that are one question. A pair
merges only when it is listed. All of a load's new pairs go in one call, at most
`QUESTION_JUDGE_MAX_PAIRS` (default 50), closest first; pairs past the cap
stay apart on that load and are judged on a later one. `unjudged` counts the
band pairs a load left without a verdict, past the cap or in a failed call,
and the page asks for a reload while it is above 0. With `CACHE_ENABLED=0`
every load judges the same closest pairs, so it is 0 there. Verdicts are memoized
per process (20,000 entries, off when `CACHE_ENABLED=0`) and never stored, so
a repeat load with nothing new makes no call. At 50 pairs the call is about
2,000 input tokens and 200 output tokens, under $0.001 on `gpt-4o-mini`. If it
fails or the reply does not parse, no pair below the threshold merges on that
load, not even one confirmed earlier, and `grouping` is `"cosine"`. `QUESTION_JUDGE_MAX_PAIRS=0` turns the check off and also reports
`"cosine"`.

The embed call and the judge call each get `REPORT_PROVIDER_TIMEOUT_SECONDS`
(default 8) with no retry, instead of the chat's 30 seconds plus a retry, so
a stalled provider costs a load about 16 seconds at most before it falls back
(#300).

| `grouping` | Rows merge when |
| --- | --- |
| `meaning` | cosine clears the threshold, or clears the floor and the model says they are one question |
| `cosine` | cosine clears the threshold |
| `exact` | the text is identical after normalization |

Merging two different questions ("How does PTO accrue?" and "Does unused PTO
carry over?") hides a gap behind a covered neighbour, which is worse than
splitting one question into two rows. On 120 labelled pairs the closest two
different questions are one word apart ("HSA" and "FSA", a sick employee and a
sick child) and score up to 0.907, so 0.91 merges none of them, but cosine
alone merges only 3 of 60 paraphrases: a missing question mark and a change
of case. The model check brings paraphrases merged to 16 to 18 of 60. The
measurements are in [evaluation.md](evaluation.md#question-grouping-threshold).

```http
GET /api/reports/gaps?days=30
Authorization: Bearer <hr_access_token>
```

```json
{
  "since": "2026-08-28T00:00:00+00:00",
  "until": "2026-09-26T14:00:00+00:00",
  "days": 30,
  "grouping": "meaning",
  "unjudged": 0,
  "min_conversations": null,
  "total": 412,
  "refused": 37,
  "gaps": [
    {
      "question_hash": "5c1e…",
      "question": "Does the company pay for pet insurance?",
      "count": 6,
      "conversations": 5,
      "other_wordings": [{"question": "Is pet insurance a benefit?", "count": 2}],
      "other_wording_count": 1
    }
  ],
  "faq": [
    {
      "question_hash": "a07b…",
      "question": "How much PTO do I get?",
      "count": 19,
      "conversations": 16,
      "other_wordings": [{"question": "How many vacation days do I have?", "count": 4}],
      "other_wording_count": 1,
      "refused": 0
    }
  ]
}
```

The terminal version with score histograms is
`python -m sourcebook.rag.query_log_reports`; see its module docstring.

## Health and config

`GET /api/health`

```json
{"status": "ok"}
```

`GET /api/config`

```json
{"app_name": "Sourcebook", "similarity_threshold": 0.62}
```

## Conversations

`GET /api/conversations` — sidebar rows, no `messages`. Unresolved
`project_id` values are returned as `null`.

```json
[
  {
    "session_id": "320b424b-a3a0-4686-941d-860aa8552c82",
    "title": "PTO questions",
    "project_id": "1d91575f-a1d3-4bed-87db-3afe9af7cf60",
    "updated_at": "2026-09-12T01:03:57.702699+00:00"
  }
]
```

`POST /api/conversations`

```http
POST /api/conversations
{"title": "PTO questions", "project_id": "1d91575f-a1d3-4bed-87db-3afe9af7cf60"}
```

```json
{
  "session_id": "320b424b-a3a0-4686-941d-860aa8552c82",
  "title": "PTO questions",
  "project_id": "1d91575f-a1d3-4bed-87db-3afe9af7cf60",
  "messages": [],
  "created_at": "2026-09-12T01:03:57.702699+00:00",
  "updated_at": "2026-09-12T01:03:57.702699+00:00"
}
```

`PATCH /api/conversations/{session_id}` with `{"title": "PTO follow-up"}` or
`{"project_id": null}` to unassign → `{"ok": true}`.

`DELETE /api/conversations/{session_id}` → `{"ok": true}`.

Unknown session or project → `{"detail": "Conversation not found."}` or
`{"detail": "Project not found."}`.

## Documents

`GET /api/documents` — `q` (title substring), `category`, `limit` (default 50,
max 200), `skip`.

```json
{
  "items": [
    {
      "source": "documents/pto-policy.md",
      "doc_id": "pto-policy",
      "title": "Paid Time Off (PTO) Policy",
      "category": "Time Off & Leave",
      "owner": "Human Resources",
      "effective_date": "2026-01-01",
      "passage_count": 1,
      "preview": "Full-time employees accrue 15 days of PTO per year."
    }
  ],
  "total": 1
}
```

`GET /api/documents/categories` → `["Time Off & Leave"]`.

`GET /api/documents/body?source=documents/pto-policy.md`

```json
{
  "source": "documents/pto-policy.md",
  "body": "## Overview\n\nFull-time employees accrue 15 days of paid time off per year."
}
```

`GET /api/documents/passages?source=documents/pto-policy.md` → the ordered
passage strings retrieval sees.

`POST /api/documents/reindex` rebuilds the library and bumps the corpus
version (that is what invalidates the answer cache). It takes only an HR
session, because every cached answer goes with it:

```json
{"ok": true, "documents": 1, "corpus_version": "f971481377004fb3a3fce267dc5facd3"}
```

## Projects

`GET /api/projects`

```json
[
  {
    "project_id": "1d91575f-a1d3-4bed-87db-3afe9af7cf60",
    "name": "Onboarding",
    "created_at": "2026-09-12T01:03:57.697874+00:00"
  }
]
```

`POST /api/projects` with `{"name": "Onboarding"}` returns one of those
objects. `DELETE /api/projects/{project_id}` unassigns its conversations and
returns `{"ok": true}`.
