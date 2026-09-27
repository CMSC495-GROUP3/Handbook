# Sourcebook v0.2.0

The second tagged version of Sourcebook, released as a prerelease for the
CMSC 495 Unit 6 beta. It is a class demo, not a production system, and the
sections below say plainly what it does, what is broken, and what nobody has
measured yet.

Tagged commit: `383cea5a5c2154fa4d7688e642d94299191a88a1`. The evidence behind every claim here is in
[handoff.md](handoff.md), which is the page to read if you are grading this.

## What it does

Sourcebook answers employee policy questions from a fixed corpus of company
documents and cites the document behind every answer. When the corpus does not
cover a question, it says so and offers to hand the question to Human
Resources rather than guessing.

A question goes through retrieval against a vector index, then a grounding
gate that compares the best passage score against a threshold. When the score
clears it, a coverage judge checks that the passages actually answer the
question. If either says no, there is no answer generation and the user gets a
refusal card with a button to ask Human Resources. Otherwise the answer
streams back with the policies it drew on and a match score.

## What changed since the alpha

- **The refusal card follows the model's own decline.** In the alpha, an
  uncovered question near an HR topic, or a prompt injection, cleared the
  gate and got a prose decline with unrelated source chips instead of the
  refusal card (#192). A follow-up could do the same (#189). The coverage
  judge (PR #253) and gating on the question as asked (PR #245) fix both.
- **Human Resources has a page.** HR Requests lists open and resolved
  escalations with the question and context, resolves and reopens them, and
  retries webhook delivery (PRs #250, #263, #264).
- **A busy provider says so.** Saturation answers HTTP 503 with a retryable
  error and `Retry-After` instead of a generic failure, and the web app offers
  one Retry that resends the same question (PRs #247, #254).
- **A knowledge-gap report** over the query log (PR #171).
- **A unique index on passage identity**, migrated on the demo site (PR #176).
- **Phone fixes** to the drawer and the source pane (PRs #234, #242, #240).
- **Web tests** with Vitest and React Testing Library, run in CI with an 80%
  floor (PR #252).
- **Documentation** for installation, the API, CI/CD, and quality evidence
  (PRs #233, #221, #228, #232).

## Getting access

**The demo site** runs at <https://sourcebook.duckdns.org> on a single instance
and stays up while the course runs. It needs a password. The team supplies the
reviewer password through the course channel, never through this repository.

**Without any credential**, the whole app runs locally in about two minutes
with a fake model and an in-memory database:

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
make setup && make stub     # then, in a second terminal
make web
```

**Setup and usage** are in [docs/install.md](../../install.md) and the
[README](../../../README.md).

## Known defects

| Issue | What a user would see | Impact | Mitigation |
| --- | --- | --- | --- |
| [#266](https://github.com/CMSC495-GROUP3/Sourcebook/issues/266) | on a phone, Back can reopen the request or policy just left, and focus falls to the top of the page when the panes switch | confusing navigation for keyboard and screen-reader users | use the "All requests" link, or a desktop window where both panes show |
| [#142](https://github.com/CMSC495-GROUP3/Sourcebook/issues/142) | assigning and deleting a project at the same moment can race | a conversation can point at a deleted project; the list treats it as ungrouped | unlikely at demo volume with one operator |
| [#269](https://github.com/CMSC495-GROUP3/Sourcebook/issues/269) | a question the coverage judge refuses shows "Strong match" and its score under "No matching policy", and says nothing indexed came close | the user may doubt a correct refusal | the refusal and the Ask Human Resources button are right; ignore the badge |
| Vague questions on covered topics | "Can I expense this trip?" is refused where the alpha answered in general terms | the user gets the refusal card instead of a pointer to the travel policy | ask a more specific question, or use Ask Human Resources |

## What this beta does not establish

- **Answer quality is measured on twenty questions.** The smoke-tier result
  for this commit is in [live-evaluation.md](live-evaluation.md). The full
  tier has not been run against it, and none of it says anything about a real
  corpus. Do not read a green workflow badge as evidence of answer quality.
- **The 10,000-user requirement is not verified.** The throughput figures in
  `docs/load-testing.md` are synthetic, with the model and database faked.
  The deployed system has not been load-tested.
- **Accessibility and web performance have not been measured.**
- **The corpus is fictional.** Sourcebook has never run against a real
  company's policies.
- **One deployment, one instance, no failover.** There is no backup schedule
  and no restore drill.

## Reproducing this exact version

The demo host follows `main`, so it moves past this tag. The tag does not.

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
git checkout v0.2.0
make setup && make stub
```

Showing the demo site at the tagged version is the by-hand procedure in the
[alpha handoff](../v0.1.0-alpha.1/handoff.md#the-tag-and-reproducing-this-version-later).
