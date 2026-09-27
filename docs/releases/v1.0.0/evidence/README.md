# Evidence, Unit 8 final

Screenshots and data behind [../handoff.md](../handoff.md). The corpus is the
fictional Meridian Systems sample, so no real policy appears. No password,
token, or session id may be visible in any image.

| File | What it holds | State |
| --- | --- | --- |
| [numbers.md](numbers.md) | the shared figures for the position papers ([#217](https://github.com/CMSC495-GROUP3/Sourcebook/issues/217)) | Pending rows filled after the freeze |
| [coverage.md](coverage.md) | Python and web coverage for the candidate ([#210](https://github.com/CMSC495-GROUP3/Sourcebook/issues/210)) | Pending |
| End-to-end pass screenshots | the 22 files below, from the pass in [../handoff.md](../handoff.md#end-to-end-pass-by-hand) | Done on `7d3c779` |
| CI/CD screenshots | green CI, Security, and auto-deploy runs on the candidate ([#207](https://github.com/CMSC495-GROUP3/Sourcebook/issues/207)) | Pending |

## End-to-end pass screenshots

Taken on 2026-09-27 against the pilot running `7d3c779`, in Google Chrome
153.0.8010.53 at 1440x1000, and 390x844 for `22`. On the two What People Ask
captures the question text is blurred, since a question can identify who
asked. The HR Requests captures show only test questions from this pass and
earlier ones.

| File | What it shows |
| --- | --- |
| `01-wrong-password.png` | a wrong password rejected with "Incorrect password." |
| `02-signed-in-hr.png` | the chat page after signing in with the HR password, with HR Requests and What People Ask in the sidebar |
| `03-answer-with-sources.png` | a covered question answered at "Strong match · 75%" with two source chips |
| `04-cited-source-open.png` | the cited policy open in the source pane |
| `05-follow-up.png` | a follow-up answered against the conversation history |
| `06-after-reload.png` | the conversation restored after a reload |
| `07-uncovered-follow-up.png` | an uncovered question asked as a follow-up, refused with the Ask Human Resources button (#189) |
| `08-refusal.png` | the same question refused in a new conversation |
| `09-pet-insurance-refusal.png` | `unanswerable_01` refused by the coverage judge, with no "Strong match" badge (#192, #269) |
| `10-escalation-form.png` | the escalation form with a note typed |
| `11-escalation-confirmed.png` | "Sent to Human Resources" with reference 48d08505 |
| `12-escalate-again.png` | the same message after a reload, still marked sent, with no second button |
| `13-hr-requests-open.png` | the request at the top of the HR Requests open list, with its detail and note |
| `14-hr-request-resolved.png` | the request in the Resolved list with its resolution note |
| `15-hr-request-reopened.png` | the request back in the open list after Reopen request |
| `16-what-people-ask-hr.png` | What People Ask for HR, 30 days: 15 of 87 questions unanswered; question text blurred |
| `17-history-after-sign-in.png` | the same browser after signing out and in again, with its conversations still listed (#299) |
| `18-other-browser-link.png` | a second browser opening the first browser's conversation link: an empty sidebar and the "isn't available in this browser" notice (#299) |
| `19-what-people-ask-reviewer.png` | What People Ask for the reviewer password: no HR Requests link, the 3-conversation line, question text blurred (#302) |
| `20-reviewer-escalations-403.png` | `/escalations` with the reviewer password: the page is for Human Resources |
| `21-employee-gaps-403.png` | `/gaps` with the employee password: the page is for managers and Human Resources |
| `22-phone-request-open.png` | HR Requests at 390px with a request opened from the keyboard (#266) |
