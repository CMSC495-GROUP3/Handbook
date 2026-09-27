# Team and individual contributions

CMSC 495 Group 3. This page is the per-person record that the README [Team](../README.md#team) section summarizes.

Counts below are taken against `main` at
[`aacec66`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/aacec662bf50a58085242b72fa46c1f46f837358)
(the merge of #311, 2026-09-27). Commit counts come from that commit; pull
request and review counts are GitHub search totals taken at 2026-09-27 21:58
UTC. Everything merged between the `v1.0.0` candidate
[`7d3c779`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/7d3c7795c197c5be56b15aebc650576760fd75d1)
and `aacec66` is documentation, apart from #308, which moved What People Ask
onto a per-day rollup with background snapshots, and #311's edits to code
comments and message strings.

**The roster is projected to the end of the course, 2026-10-04.** It assumes
every pull request and issue open at the snapshot is finished by then: #292
and #312 merge with a merge commit, and issues #214 and #216 close. Cells that
change under that assumption carry a footnote, and
[Open work and the projection](#open-work-and-the-projection) gives the
counted value beside each one and what would change it.

Each member confirmed their own row on
[PR #231](https://github.com/CMSC495-GROUP3/Sourcebook/pull/231), except Gavin
and Dominick, who had not replied by the 27 September deadline. Their rows are
marked unconfirmed.

| How counted | Command or query |
| --- | --- |
| Author commits | `git log --no-merges --format='%an <%ae>'` on `aacec66`, grouped by person |
| Merged pull requests authored | `gh` search `repo:CMSC495-GROUP3/Sourcebook type:pr author:<login> is:merged` |
| Others' pull requests reviewed | `gh` search `repo:CMSC495-GROUP3/Sourcebook type:pr reviewed-by:<login> -author:<login>`. GitHub records a reply in a review thread on your own pull request as a review, so the `-author:` filter leaves those out. It counts other people's pull requests with at least one review, not review events |
| Open pull requests | `gh` search `repo:CMSC495-GROUP3/Sourcebook type:pr author:<login> is:open` |
| Issues assigned | `gh issue list --assignee <login> --state all` on this repository |

Several people commit under more than one Git name. Author commits are grouped by person: `t-shahan`, `Taylor`, `Taylor Shahan`, and `Claude` under **Taylor Shahan**; `Lokias` under **Chris**; `RoNUO` under **Rob**; `DanielTsang26` and `Daniel Tsang` under **Daniel Tsang**; `fudgepop01` under **Dominick**. `dependabot[bot]` is not grouped with anyone.

## Roster

| Member | GitHub | Role (Unit 5 pitch) | Author commits | Merged PRs authored | Others' PRs reviewed | Open PRs |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Taylor Shahan | [@t-shahan](https://github.com/t-shahan) | Lead Architect | 277 [^claude] [^projected] | 97 [^projected] | 59 | 0 [^projected] |
| Chris | [@threshi-art](https://github.com/threshi-art) | Integration Lead | 129 | 52 | 1 | 0 |
| Daniel Tsang | [@DanielTsang26](https://github.com/DanielTsang26) | Interface Designer | 4 | 1 | 1 | 0 |
| George Struder | [@Lazzy-dev](https://github.com/Lazzy-dev) | Administration (EC2, S3, Atlas), locks, MongoDB | 11 | 3 | 4 | 0 |
| Rob | [@RoNUO](https://github.com/RoNUO) | Corpus availability and passage index | 4 | 3 | 2 | 0 |
| Gavin (unconfirmed) | [@gavinwathen](https://github.com/gavinwathen) | React components, design and styling | 2 | 1 | 0 | 0 |
| Dominick (unconfirmed) | [@fudgepop01](https://github.com/fudgepop01) | React components, design and styling | 5 [^projected] | 1 [^projected] | 0 | 0 [^projected] |

`dependabot[bot]` has 20 author commits and 20 merged PRs on the same snapshot. It is not a team member.

Grouped this way, `aacec66` shows six people plus Dependabot; Dominick has no author commits on `main` yet. With #292 merged, all seven members have author commits on `main`.

## Open work and the projection

Open at 2026-09-27 21:58 UTC, and assumed finished by 2026-10-04:

| Item | Owner | State at the snapshot | Assumed by 2026-10-04 |
| --- | --- | --- | --- |
| [PR #292](https://github.com/CMSC495-GROUP3/Sourcebook/pull/292) `docs: add lighthouse metrics to quality.md` | Dominick ([@fudgepop01](https://github.com/fudgepop01)) | Five non-merge commits. Taylor requested changes on 2026-09-26; Dominick pushed two fixes after that review (`8dd650c`, `c63df06`). Conflicts with `main` | Merged |
| [PR #312](https://github.com/CMSC495-GROUP3/Sourcebook/pull/312) `docs: describe Sourcebook as the capstone it is, not a workplace tool` | Taylor ([@t-shahan](https://github.com/t-shahan)) | Three non-merge commits, this page's update among them | Merged |
| [Issue #214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214) Lighthouse per theme | Dominick and Taylor | Measured in [lighthouse.md](releases/v1.0.0/evidence/lighthouse.md); #292 is "Part of #214", so merging it does not close the issue | Closed |
| [Issue #216](https://github.com/CMSC495-GROUP3/Sourcebook/issues/216) the stakeholder video | Unassigned; the whole team records it | Script and shot list merged in [#262](https://github.com/CMSC495-GROUP3/Sourcebook/pull/262), updated in [#304](https://github.com/CMSC495-GROUP3/Sourcebook/pull/304) | Recorded, published, and closed |

No other branch on the repository carries commits that are not on `main`.

What the projection changes:

| Row and metric | Counted at `aacec66` | Projected for 2026-10-04 | Why |
| --- | ---: | ---: | --- |
| Taylor, author commits | 274 | 277 | #312's three non-merge commits land under `t-shahan`. The merge commit is not counted |
| Taylor, merged PRs authored | 96 | 97 | #312 |
| Taylor, open PRs | 1 | 0 | #312 leaves the open list |
| Dominick, author commits | 0 | 5 | #292's five non-merge commits (`8ff6bec`, `9ef947d`, `e77d288`, `8dd650c`, `c63df06`) land under `fudgepop01`. The two merges of `main` into the branch are not counted |
| Dominick, merged PRs authored | 0 | 1 | #292 |
| Dominick, open PRs | 1 | 0 | #292 leaves the open list |

Closing #214 and #216 changes no roster cell, since the roster does not count
closed issues. Reviews do not change either: Taylor's review of #292 is
already in Taylor's 59, and merging a pull request adds no review.

The projection changes if:

- #292 or #312 is squash-merged. Its author gains one commit, not five or
  three.
- Either pull request gains commits, for example to fix #292's conflict or to
  answer review. Each non-merge commit adds one; a merge of `main` into the
  branch adds none.
- Either is closed without merging. That row keeps its counted values.
- Publishing the video adds a pull request, for example to link the recording.
  Its author's row gains that pull request and its commits.

## Taylor Shahan

**Owns, per the README.** Module boundaries in `sourcebook/`, the split between the API and `web/`, the deployment shape, and the architecture diagrams.

**What `main` shows.** The largest author and review share. Representative merged work:

- Initial groundwork, [PR #1](https://github.com/CMSC495-GROUP3/Sourcebook/pull/1).
- Package and web layout, [PR #24](https://github.com/CMSC495-GROUP3/Sourcebook/pull/24); later package rename to `sourcebook`, [PR #199](https://github.com/CMSC495-GROUP3/Sourcebook/pull/199).
- Host auto-deploy, [PR #71](https://github.com/CMSC495-GROUP3/Sourcebook/pull/71).
- Open-book web redesign, [PR #161](https://github.com/CMSC495-GROUP3/Sourcebook/pull/161); whole-document library, [PR #167](https://github.com/CMSC495-GROUP3/Sourcebook/pull/167).
- Alpha measurement and release writing: [PR #186](https://github.com/CMSC495-GROUP3/Sourcebook/pull/186), [PR #190](https://github.com/CMSC495-GROUP3/Sourcebook/pull/190), [PR #191](https://github.com/CMSC495-GROUP3/Sourcebook/pull/191), [PR #198](https://github.com/CMSC495-GROUP3/Sourcebook/pull/198).
- httpx lock-outage fix, [PR #163](https://github.com/CMSC495-GROUP3/Sourcebook/pull/163); pip-compile `.in` / `.txt` names, [PR #178](https://github.com/CMSC495-GROUP3/Sourcebook/pull/178); Atlas evaluation access list, [PR #197](https://github.com/CMSC495-GROUP3/Sourcebook/pull/197).
- Follow-up grounding on the question as asked, [PR #245](https://github.com/CMSC495-GROUP3/Sourcebook/pull/245), which closed [issue #189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189).
- Finished and merged the HR escalation queue Gavin started, [PR #250](https://github.com/CMSC495-GROUP3/Sourcebook/pull/250).
- The What People Ask report: the page, [PR #286](https://github.com/CMSC495-GROUP3/Sourcebook/pull/286), grouping by meaning, [PR #288](https://github.com/CMSC495-GROUP3/Sourcebook/pull/288), and its caption, [PR #297](https://github.com/CMSC495-GROUP3/Sourcebook/pull/297); counting conversations at volume, [PR #296](https://github.com/CMSC495-GROUP3/Sourcebook/pull/296), and serving it from a per-day rollup and background snapshots at the planned 7M questions a day, [PR #308](https://github.com/CMSC495-GROUP3/Sourcebook/pull/308); the question judge, [PR #298](https://github.com/CMSC495-GROUP3/Sourcebook/pull/298), and its 0.91 threshold, [PR #303](https://github.com/CMSC495-GROUP3/Sourcebook/pull/303).
- The `v1.0.0` release folder, [PR #274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274), and its follow-ups through the tag and run write-back, [PR #304](https://github.com/CMSC495-GROUP3/Sourcebook/pull/304), [PR #305](https://github.com/CMSC495-GROUP3/Sourcebook/pull/305), [PR #306](https://github.com/CMSC495-GROUP3/Sourcebook/pull/306).
- Documentation after the tag: the team page refresh, [PR #307](https://github.com/CMSC495-GROUP3/Sourcebook/pull/307); the What People Ask docs follow-up, [PR #309](https://github.com/CMSC495-GROUP3/Sourcebook/pull/309); the last rows of the evidence sheet, [PR #310](https://github.com/CMSC495-GROUP3/Sourcebook/pull/310); the README reorganized by reader, with `docs/architecture.md`, [PR #311](https://github.com/CMSC495-GROUP3/Sourcebook/pull/311); and the capstone framing across the docs, [PR #312](https://github.com/CMSC495-GROUP3/Sourcebook/pull/312), projected.
- Access: the HR password, [PR #295](https://github.com/CMSC495-GROUP3/Sourcebook/pull/295); conversations scoped to the browser that started them, [PR #299](https://github.com/CMSC495-GROUP3/Sourcebook/pull/299); the manager password, [PR #302](https://github.com/CMSC495-GROUP3/Sourcebook/pull/302); and the review follow-ups for both, [PR #301](https://github.com/CMSC495-GROUP3/Sourcebook/pull/301).

The 61 `Claude`-authored commits at `aacec66` (among them the JWT `exp` work from [PR #154](https://github.com/CMSC495-GROUP3/Sourcebook/pull/154), facing-page icon fix [PR #202](https://github.com/CMSC495-GROUP3/Sourcebook/pull/202), lock-check follow-up on [PR #157](https://github.com/CMSC495-GROUP3/Sourcebook/pull/157), second-password and auto-deploy follow-ups, and review fixes on the What People Ask and access pull requests above) are counted with Taylor, as [issue #201](https://github.com/CMSC495-GROUP3/Sourcebook/issues/201) asked; Taylor directed that work and is accountable for it.

## Chris

**Owns, per the README.** Evaluation, verifying merged work as one system, and the evidence behind any release claim. Day-to-day integration.

**What `main` shows.** Second-largest author share. Git records these commits under the name `Lokias`. Representative merged work:

- Offline ingestion tests, [PR #2](https://github.com/CMSC495-GROUP3/Sourcebook/pull/2).
- Forwarded-client IP trust, [PR #54](https://github.com/CMSC495-GROUP3/Sourcebook/pull/54).
- Provider timeout and a separate login pool, [PR #112](https://github.com/CMSC495-GROUP3/Sourcebook/pull/112).
- Citation measurement split from retrieval, [PR #111](https://github.com/CMSC495-GROUP3/Sourcebook/pull/111); evaluation by category, [PR #140](https://github.com/CMSC495-GROUP3/Sourcebook/pull/140).
- Clarify-and-escalate prompt, [PR #138](https://github.com/CMSC495-GROUP3/Sourcebook/pull/138); lifecycle corpus, [PR #139](https://github.com/CMSC495-GROUP3/Sourcebook/pull/139).
- Empty-corpus library cleanup, [PR #132](https://github.com/CMSC495-GROUP3/Sourcebook/pull/132); prompt-injection hygiene for retrieved text, [PR #155](https://github.com/CMSC495-GROUP3/Sourcebook/pull/155).
- Query-log analysis reports, [PR #171](https://github.com/CMSC495-GROUP3/Sourcebook/pull/171) / [issue #160](https://github.com/CMSC495-GROUP3/Sourcebook/issues/160).
- The user guide, [PR #259](https://github.com/CMSC495-GROUP3/Sourcebook/pull/259), and this team record, [PR #231](https://github.com/CMSC495-GROUP3/Sourcebook/pull/231).
- The grounding-gate fix for [issue #192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192), [PR #253](https://github.com/CMSC495-GROUP3/Sourcebook/pull/253), merged on 2026-09-22.

[Issue #189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189) is closed; it was completed by Taylor's [PR #245](https://github.com/CMSC495-GROUP3/Sourcebook/pull/245), so it is not counted as Chris's merged authorship.

## Daniel Tsang

**Owns, per the README.** Endpoint shapes, streaming events, the `LLMProvider` interface, and stored record shapes. CODEOWNERS lists [@DanielTsang26](https://github.com/DanielTsang26) as a required reviewer on every path, with Taylor and George.

**What `main` shows.**

- `101df59` `Initial commit`.
- `c00b30c` facing-page topic-list alignment, the fix recorded on [issue #175](https://github.com/CMSC495-GROUP3/Sourcebook/issues/175).
- Merged: [PR #234](https://github.com/CMSC495-GROUP3/Sourcebook/pull/234) mobile drawer height (`h-screen` to `h-svh`; `5f96f1f`, `c2926c2`), committed under the name `DanielTsang26`.
- One review: [PR #170](https://github.com/CMSC495-GROUP3/Sourcebook/pull/170) (escalation contact rename).

Interface-contract work on `main` also appears in PRs Taylor or Chris authored; those PRs stay credited to their authors.

## George Struder

**Owns, per the README.** Administration, dependency locks, and the MongoDB deployment.

**What `main` shows.** Eleven author commits, including lock generation and the Linux lock refresh, the pip-compile CI check, escalation contact from config, the People Operations to Human Resources rename, the pydantic-core pin revert, and disabling the embedding cache in live evaluation. Merged PRs:

- [PR #157](https://github.com/CMSC495-GROUP3/Sourcebook/pull/157) lock the Python dependencies.
- [PR #170](https://github.com/CMSC495-GROUP3/Sourcebook/pull/170) escalation contact rename.
- [PR #244](https://github.com/CMSC495-GROUP3/Sourcebook/pull/244) disable embedding cache in the live evaluation workflow.

Reviews: [PR #173](https://github.com/CMSC495-GROUP3/Sourcebook/pull/173) (Dependabot Python group), [PR #197](https://github.com/CMSC495-GROUP3/Sourcebook/pull/197) (Atlas access-list admission), and [PR #219](https://github.com/CMSC495-GROUP3/Sourcebook/pull/219) (Atlas admin API access-list notes; [issue #218](https://github.com/CMSC495-GROUP3/Sourcebook/issues/218) is closed), and he approved [PR #253](https://github.com/CMSC495-GROUP3/Sourcebook/pull/253) before merging it.

**Infrastructure and configuration recorded in issues.** Most of George's operations work happened on the EC2 instance and in the Atlas and GitHub settings, so it shows up in issue comments rather than commits:

- Root disk on the EC2 instance: grew the EBS volume from 8 GB to 16 GB, extended the root partition, and enabled the weekly Docker prune timer ([issue #79](https://github.com/CMSC495-GROUP3/Sourcebook/issues/79#issuecomment-5553669326)).
- Verified the three auto-deploy paths on the instance from its deploy logs ([issue #80](https://github.com/CMSC495-GROUP3/Sourcebook/issues/80#issuecomment-5560512370)).
- Added the three evaluation secrets to the repository for [PR #197](https://github.com/CMSC495-GROUP3/Sourcebook/pull/197#issuecomment-5641222971).
- Confirmed that the runner's IP is added to and removed from the Atlas access list during an evaluation run, and checked the roles on the organization and project API keys ([issue #218](https://github.com/CMSC495-GROUP3/Sourcebook/issues/218#issuecomment-5657834042)).
- Reported that the read-only evaluation database user could not write the embedding cache ([issue #243](https://github.com/CMSC495-GROUP3/Sourcebook/issues/243)), then fixed it in [PR #244](https://github.com/CMSC495-GROUP3/Sourcebook/pull/244).
- Merged [PR #197](https://github.com/CMSC495-GROUP3/Sourcebook/pull/197), [PR #219](https://github.com/CMSC495-GROUP3/Sourcebook/pull/219), and [PR #253](https://github.com/CMSC495-GROUP3/Sourcebook/pull/253) into `main`.

George set up and administered the EC2 instance and the S3 storage ([comment on PR #231](https://github.com/CMSC495-GROUP3/Sourcebook/pull/231#issuecomment-5782718490)). The items above, including [issue #79](https://github.com/CMSC495-GROUP3/Sourcebook/issues/79) and [issue #80](https://github.com/CMSC495-GROUP3/Sourcebook/issues/80), are the parts of that work with a GitHub record.

## Rob

**Owns, per the README.** Corpus availability and the passage index.

**What `main` shows.**

- Merged: [PR #150](https://github.com/CMSC495-GROUP3/Sourcebook/pull/150) / [issue #89](https://github.com/CMSC495-GROUP3/Sourcebook/issues/89), keep the live corpus available during re-ingestion (`8e8c36e`).
- Merged: [PR #176](https://github.com/CMSC495-GROUP3/Sourcebook/pull/176) / [issue #158](https://github.com/CMSC495-GROUP3/Sourcebook/issues/158), unique `(source, chunk_index)` index (`a724d38`).
- Reviews: [PR #181](https://github.com/CMSC495-GROUP3/Sourcebook/pull/181) (requested the NaN rejection, then approved) and [PR #171](https://github.com/CMSC495-GROUP3/Sourcebook/pull/171).
- Merged: [PR #279](https://github.com/CMSC495-GROUP3/Sourcebook/pull/279) / [issue #142](https://github.com/CMSC495-GROUP3/Sourcebook/issues/142), transactions for project assignment and deletion (`d2ae7ba`, 2026-09-26).

## Gavin

Unconfirmed: Gavin had not confirmed this row by the 27 September deadline.

**Owns, per the README.** React components, design, and styling, with Dominick.

**What GitHub shows.** Gavin opened [PR #250](https://github.com/CMSC495-GROUP3/Sourcebook/pull/250) (`feat: add HR escalation queue`) and wrote the first version of the HR queue; Taylor finished it and merged it on 2026-09-22, resolving [issue #159](https://github.com/CMSC495-GROUP3/Sourcebook/issues/159). Gavin's two author commits on `main` are from it: `0b4c34f` (HR escalation queue) and `8fd1cf6` (escalation page lint fix). Zero reviews of others' pull requests. Assigned on the design and frontend issues [#41](https://github.com/CMSC495-GROUP3/Sourcebook/issues/41) through [#53](https://github.com/CMSC495-GROUP3/Sourcebook/issues/53), plus [#82](https://github.com/CMSC495-GROUP3/Sourcebook/issues/82), [#83](https://github.com/CMSC495-GROUP3/Sourcebook/issues/83), [#159](https://github.com/CMSC495-GROUP3/Sourcebook/issues/159), [#174](https://github.com/CMSC495-GROUP3/Sourcebook/issues/174), [#175](https://github.com/CMSC495-GROUP3/Sourcebook/issues/175), [#189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189), and [#192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192). All 20 of those issues are now closed. One issue comment, on [#41](https://github.com/CMSC495-GROUP3/Sourcebook/issues/41).

Assigned [#82](https://github.com/CMSC495-GROUP3/Sourcebook/issues/82) is ownership, not merged credit; the merged streaming-blank fix is [PR #126](https://github.com/CMSC495-GROUP3/Sourcebook/pull/126) (Taylor). The merged open-book implementation on `main` is [PR #161](https://github.com/CMSC495-GROUP3/Sourcebook/pull/161) (Taylor) and is credited to Taylor.

## Dominick

Unconfirmed: Dominick had not confirmed this row by the 27 September deadline.

**Owns, per the README.** React components, design, and styling, with Gavin.

**What GitHub shows.** At the snapshot: zero author commits, zero merged pull requests, and zero reviews of others' pull requests under `fudgepop01`. The roster row projects five author commits and one merged pull request, assuming #292 merges by 2026-10-04 (see [Open work and the projection](#open-work-and-the-projection)). Assigned on the same design and frontend cluster ([#41](https://github.com/CMSC495-GROUP3/Sourcebook/issues/41)–[#53](https://github.com/CMSC495-GROUP3/Sourcebook/issues/53), [#82](https://github.com/CMSC495-GROUP3/Sourcebook/issues/82), [#84](https://github.com/CMSC495-GROUP3/Sourcebook/issues/84), [#159](https://github.com/CMSC495-GROUP3/Sourcebook/issues/159), [#174](https://github.com/CMSC495-GROUP3/Sourcebook/issues/174), [#175](https://github.com/CMSC495-GROUP3/Sourcebook/issues/175)), plus [#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214) (Lighthouse accessibility and performance per theme, still open). Assigned [#175](https://github.com/CMSC495-GROUP3/Sourcebook/issues/175) is ownership, not merged authorship; the merged facing-page fix on `main` (`c00b30c`) is Daniel's commit and is recorded on his row. No author commits under Dominick's name appear on `main` at `aacec66`. He opened [PR #292](https://github.com/CMSC495-GROUP3/Sourcebook/pull/292) (`docs: add lighthouse metrics to quality.md`, for [#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)) on 2026-09-26; it has five non-merge commits. Taylor requested changes that evening; Dominick pushed two fixes afterward (trimming unrelated changes, and recording the live-site commit and time for each Lighthouse run). At the snapshot it is open, with Taylor's changes-requested review still standing, and it conflicts with `main`.

## Scope of this record

- Work that exists only in a fork, a classroom write-up, or a chat is not listed.
- Review counts are other people's pull requests GitHub marks `reviewed-by`, not every comment.
- Issue assignment is cited as ownership, not as authored work.

[^projected]: Projected for 2026-10-04, not yet counted. Assumes [PR #292](https://github.com/CMSC495-GROUP3/Sourcebook/pull/292) and [PR #312](https://github.com/CMSC495-GROUP3/Sourcebook/pull/312) merge with a merge commit and their commits at the snapshot. The counted values at `aacec66` are in [Open work and the projection](#open-work-and-the-projection).

[^claude]: This total includes 61 Claude-authored commits Taylor directed and accepted responsibility for.
