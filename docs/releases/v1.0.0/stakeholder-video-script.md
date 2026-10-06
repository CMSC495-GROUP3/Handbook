# Stakeholder video script (v1.0.0)

**Status:** Recorded and published at <https://youtu.be/ywaTO12U8Ls>.
This page is the script the team recorded from.

**Issue:** [#216](https://github.com/CMSC495-GROUP3/Sourcebook/issues/216)
(part of [#201](https://github.com/CMSC495-GROUP3/Sourcebook/issues/201) step 5).

**Audience:** Technical stakeholders (course graders, peer reviewers, and HR /
engineering partners who need a grounded walkthrough).

**Runtime target:** 10–15 minutes. Timestamps below are a rehearsal plan; trim
or stretch per segment after the day-before demo rehearsal.

**Record after:** Annotated tag `v1.0.0` exists and the demo host shows that
submitted commit. Until then, keep every live answer and metric claim marked
**pending final live run**.

**Folder note:** This file lives under `docs/releases/v1.0.0/` to match the
portfolio scaffold in [pull request #230](https://github.com/CMSC495-GROUP3/Sourcebook/pull/230).
Sibling release pages (`portfolio.md`, `handoff.md`, `release-notes.md`,
`evidence/`) and Lane 4 measurement pages (for example `numbers.md`) are owned
elsewhere. This pull request adds only the stakeholder video package files.

## Pending deliverables (do not invent)

| Deliverable | State |
| --- | --- |
| Final recording (1080p MP4) | **Pending** |
| Unlisted YouTube (or hosted) URL | **Pending** |
| Deployed SHA shown in the demo | **Pending** — capture from the demo site after `v1.0.0` |
| Final screenshots for the video package | **Pending** — publish via the evidence workflow after the live pass |
| Live demo answers / citation text | **Pending** — do not paste final answers here before the live run |
| Refusal card on `unanswerable_01` | **Pending host verification** — [#253](https://github.com/CMSC495-GROUP3/Sourcebook/pull/253) (coverage gate) is on `main`; the refusal card and Ask Human Resources button appear for that question only after that behavior is **deployed** to the demo host and confirmed in the day-before rehearsal. Alpha evidence in `docs/releases/v0.1.0-alpha.1/live-evaluation.md` showed a prose decline with source chips instead. |
| Follow-up wording after PTO | **Pending rehearsal** — prefer a suggested-follow-up chip under the PTO answer; otherwise a short PTO-contextual typed question (see demo table). Confirm final wording against the PTO policy during rehearsal. |
| Link from README, release notes, and `portfolio.md` | **Pending** — follow-up after upload |

## Speakers (roles until living names are assigned)

Issue [#216](https://github.com/CMSC495-GROUP3/Sourcebook/issues/216) asks for a
speaker per segment. Living on-camera names are **not yet assigned**, so this
script uses role labels only. Do not invent assignments from the README Team
table. Put the agreed names on the opening slide before recording.

| Role label | Segments on camera |
| --- | --- |
| **Architecture narrator** | Problem, architecture, RAG / grounding, CI/CD |
| **Demo operator** | Live browser demo (sign-in through escalation) |
| **Quality narrator** | Quality / evaluation evidence and value proposition |
| **HR handler** | Optional third person for the HR queue segment (may be the architecture narrator or demo operator) |

Opening slide: assigned team names, course, product name **Sourcebook**, and
"recorded against tag `v1.0.0` @ `<SHA pending>`".

## Demo questions (evaluation dataset + contextual follow-up)

Grounded and refusal prompts come from `evaluation/questions.json` (smoke
tier, 20 cases). **Do not claim the live model's final wording in this
script.** At recording time, read the on-screen answer and confirm it matches
the expected outcome class (`answer`, `refuse`, or follow-up grounded in the
same sources).

| Demo beat | Prompt source | Question / action | Expected outcome class | Expected sources / behavior (label only) |
| --- | --- | --- | --- | --- |
| Grounded answer | Eval `answerable_01` | How many PTO days do full time employees with two years of service receive each year? | `answer` | Cite Paid Time Off (PTO) Policy; label expects 15 days |
| Citation / source open | same turn | — | `answer` | Open the cited document from the sources UI |
| Follow-up | UI chip **or** typed PTO continue | Prefer: click a **suggested follow-up** shown under the PTO answer. Fallback typed question (only if chips are missing or off-topic): "How far in advance must I request three or more days off?" | `answer` (PTO-grounded) | Must continue the PTO conversation — not parental leave. Confirm wording and expected answer against the PTO policy at rehearsal. |
| Uncovered refusal | Eval `unanswerable_01` | Does Meridian reimburse employee pet insurance? | `refuse` **only if deployed** | Declines via refusal card when the [#253](https://github.com/CMSC495-GROUP3/Sourcebook/pull/253) coverage-gate behavior is on the demo host; otherwise stop the take (see pending table). |
| Escalation | after refusal | Use **Ask Human Resources** on the refusal card | escalation filed | Show confirmation; leave queue handling to the HR segment |

Optional spare grounded question if the first retrieval looks weak on rehearsal:
`answerable_03` — "What company match do I receive if I contribute five percent
to my 401(k)?" (`answer`, 401(k) Retirement Savings Plan).

Stakeholder camera time stays on the uncovered-refusal path above. Other smoke
rows that exercise hostile instruction overrides are out of scope for this
recording package.

## Timestamped script

Total planned: **~13:00** (fits 10–15).

### 0:00–0:20 — Title (Architecture narrator)

> "This is Sourcebook, our retrieval-augmented policy assistant for Unit 8.
> We are recording against tag `v1.0.0` at commit `<SHA pending>`. Speakers
> today: `<assigned names>`."

### 0:20–1:50 — Problem statement (~1.5 min) (Architecture narrator)

**Source:** README "The problem".

Talking points:

- Employees spend time searching scattered policy and onboarding documents;
  HR answers the same questions repeatedly.
- The documents usually contain the answer; discovery is the expensive part.
- Goal: plain-language search over the corpus with an answer **and** a source
  the reader can check, rather than trusting memory or an uncited summary.

Say explicitly: we refuse when evidence is too weak — honesty is a product
requirement, not a slide slogan.

### 1:50–3:50 — Solution / architecture (~2 min) (Architecture narrator)

**Source:** README architecture diagram and Compose table.

Talking points:

- Three Compose services on one EC2 host: `caddy` (TLS edge), `web` (React +
  Nginx), `api` (FastAPI RAG pipeline). OpenAI, MongoDB Atlas, and S3 sit
  outside Compose.
- Request path in one sentence: browser to Caddy to Nginx to API to Atlas
  Vector Search to grounding gate to model (or refuse) to SSE stream back to
  the UI.
- Honesty measures to name on camera: server-side conversation history (no
  client-supplied chat history), cosine score vs `SIMILARITY_THRESHOLD` plus
  the fail-closed coverage judge when cosine clears, citations on every
  answered turn, escalation when the corpus cannot help.

Optional visual: freeze the README mermaid diagram or a printed slide of the
three containers — see the shot list.

### 3:50–7:50 — AI demonstration (~4 min) (Demo operator)

**Source:** browser pass pattern from the release handoff; questions from the
table above. Demo: `https://sourcebook.duckdns.org` (or the tagged host once
frozen).

| Clock | Action | Spoken cue |
| --- | --- | --- |
| 3:50 | Sign in | "Shared demo credential — no secrets on the recording." |
| 4:10 | Ask `answerable_01` | "Smoke-tier eval id `answerable_01`. We expect a grounded answer with a PTO citation — exact wording pending this live run." |
| 4:40 | Point at sources + match | "Citation and retrieval match are part of the response, not a separate doc hunt." |
| 5:00 | Open cited source | "Same turn: open the cited policy so a stakeholder can verify the paragraph." |
| 5:30 | Follow-up | "Continuing the PTO turn: either a suggested follow-up chip under this answer, or a short advance-notice question from the same policy — final wording confirmed in rehearsal." |
| 6:10 | Ask `unanswerable_01` | "Uncovered question from the eval set. We expect the refusal card only if the coverage-gate build is on this host — verified in rehearsal." |
| 6:40 | Show refusal card | "Refuse rather than guess." |
| 7:00 | Escalate | "Ask Human Resources from the same screen; confirmation should appear." |
| 7:30 | Pause on confirmation | "Escalation id stays on screen for the HR segment." |

**Hard rule:** If the live run disagrees with the expected outcome class, stop
the take, note the discrepancy, and do not narrate a fabricated "correct"
answer over a wrong UI state. If `unanswerable_01` returns a prose decline with
source chips instead of the refusal card, stop — that is the pre-#253 host
behavior documented in the alpha live-evaluation note.

### 7:50–9:20 — Escalation and HR handling (~1.5 min) (Demo operator + HR handler)

Talking points:

- Employee path: refusal or unhelpful answer to escalation record (+ optional
  webhook).
- Sign in with the **HR password** before this segment and keep it out of
  frame. HR Requests needs it
  ([#295](https://github.com/CMSC495-GROUP3/Sourcebook/pull/295)). A session
  opened with the shared or reviewer password shows no HR Requests link; on
  the demo site the reviewer password is the manager one
  ([#302](https://github.com/CMSC495-GROUP3/Sourcebook/pull/302)).
- Handler path: open **HR Requests** (`/escalations`) as shipped on current
  `main` (two-pane queue from [#264](https://github.com/CMSC495-GROUP3/Sourcebook/pull/264)).
  Confirm the tagged deploy still exposes that page at rehearsal. Mark resolved
  after a human answer.
- Last 30 seconds: open **What People Ask** (`/gaps`,
  [#286](https://github.com/CMSC495-GROUP3/Sourcebook/pull/286),
  [#288](https://github.com/CMSC495-GROUP3/Sourcebook/pull/288)). It ranks the
  questions the corpus did not answer and the ones asked most, over 7, 30, or
  90 days, with rewordings of one question on one row. Say that managers can
  sign in to this page alone with their own password, and that their view
  leaves out any wording asked in fewer than three conversations. Read
  whatever rows the demo site's query log shows; do not seed or describe rows
  that are not on screen.
- Say what the alpha / final notes still limit: do not claim a full Slack/Teams
  operator console unless that UI is actually on the tagged build.

### 9:20–11:50 — Technical implementation (~2.5–3 min) (Architecture narrator)

**Sources:** README (RAG vs fine-tuning, grounding, `LLMProvider`),
`docs/ci-cd.md`.

Talking points:

- **Why RAG, not fine-tuning:** citations and stale-policy risk. New documents
  ingest without retraining.
- **Grounding gate:** cosine score vs `SIMILARITY_THRESHOLD`; when that clears,
  a fail-closed coverage judge must also say the passages answer the question.
  Below either bar means no policy answer with citations; decline instead.
- **Server-side history:** history loaded by `session_id` from MongoDB; the
  client cannot supply forged conversation turns or forged sources.
- **`LLMProvider`:** one interface; OpenAI for the demo site, fake provider for
  stub/tests; swap is a configuration choice, not a rewrite.
- **CI/CD:** name the workflow family honestly (code CI, security, pull request
  checks, evaluation instrumentation, deploy path / `auto_deploy`). Point at
  `docs/ci-cd.md` rather than inventing run URLs. Final green runs for the
  tagged SHA are **pending** until captured after tag.

### 11:50–13:20 — Performance, reliability, quality / eval (~1.5–2.5 min) (Quality narrator)

**Source:** `docs/quality.md`, evaluation README, release measurement pages
when Lane 4 / freeze fills them.

Talking points:

- Smoke tier: 20 labeled cases in `evaluation/questions.json`; full tier is
  larger and is not required to be re-run on camera.
- Metrics to mention by **name** only until final numbers exist: citation
  correctness, unsupported refusal handling, coverage / gate behavior.
- Load / benchmark: point at documented targets and the last committed
  measurement pages; **do not recite invented final percentages**.
- Gate fix narrative: describe the engineering intent (refuse when unsupported)
  and point reviewers to quality docs plus open issue tracking for any remaining
  live-eval blockers — without claiming PASS for a run that has not been
  re-executed on the tagged SHA.

### 13:20–14:20 — Value proposition (~1 min) (Quality narrator)

**Sources:** README, `docs/user-guide.md` (when present on the tag; not yet on
current `main`).

Talking points:

- **Employees:** faster answers with sources they can open.
- **HR:** fewer repeat tickets; escalations arrive with question context.
- **Policy owners and managers:** What People Ask shows where the corpus is
  silent and what people keep asking, so a policy owner knows what to write
  next and a manager knows what to cover in onboarding (point back at the
  page shown in the HR segment; do not over-claim).

Close: "Video URL and README link land after upload. MP4 retained for the
submission form. End of stakeholder pass."

## Rehearsal checklist

- [ ] Day-before rehearsal on the demo site (or tagged host)
- [ ] Confirm deployed SHA matches the intended tag
- [ ] Confirm `unanswerable_01` shows the refusal card (not alpha prose+chips)
- [ ] Confirm PTO follow-up chip or typed fallback against the PTO policy
- [ ] Confirm the HR password opens HR Requests and What People Ask on the
      host, and that What People Ask has rows for the 30-day window
- [ ] Assign living names to the four role labels; put them on the opening slide
- [ ] Run the five demo beats; record expected outcome class only
- [ ] 1080p, one take per segment, cut together
- [ ] Export MP4; upload unlisted; names in the description
- [ ] Link from README, `v1.0.0` release notes, and `portfolio.md`

## Related files

- Shot list: [stakeholder-video-shot-list.md](stakeholder-video-shot-list.md)
- Issue: <https://github.com/CMSC495-GROUP3/Sourcebook/issues/216>
- Portfolio map: <https://github.com/CMSC495-GROUP3/Sourcebook/issues/201>
