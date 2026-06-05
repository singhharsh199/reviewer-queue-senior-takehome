# Submission

## Summary of changes

- Extracted the reviewer workflow into a pure `backend/app/workflow.py` module (transitions, terminal-state guard, queue filter, queue sort, allowed-actions lookup). The HTTP layer in `main.py` is now a thin shell over it.
- Fixed every workflow-correctness bug listed in the brief: claim now requires `unassigned`, terminal actions require `in_review`, all three terminal states block further actions, the active queue excludes all three terminals, and the queue is ordered by `risk_level → customer_tier → age` as specified.
- Frontend reads `allowed_actions` from the API and renders buttons accordingly, so invalid actions are visibly disabled with a tooltip instead of triggering an opaque 409.
- Added 37 backend tests covering transitions, queue ordering, the active filter, `allowed_actions`, and the HTTP→workflow mapping. The 2 original smoke tests still pass.

## Bugs fixed

| File:line (pre) | Bug | Fix |
|---|---|---|
| `backend/app/main.py:59` | Active queue only filtered `approved`; `rejected` and `escalated` leaked in. | `workflow.is_active()` excludes all three terminal statuses. |
| `backend/app/main.py:61` | Queue sorted by `submitted_at` desc — ignored urgency entirely. | `workflow.queue_sort_key()` orders by `(risk_rank, tier_rank, submitted_at asc)`. |
| `backend/app/main.py:75-77` | `claim` was allowed on `in_review` items, letting a second reviewer overwrite an existing assignment. | `workflow.apply_action` only allows `claim` from `unassigned`. |
| `backend/app/main.py:80-83` | `approve`/`reject`/`escalate` were allowed from `unassigned` and from `rejected`/`escalated`. Only `approved` was guarded. | All three terminal actions require `in_review`; terminal items reject every action with a specific message. |
| `backend/app/main.py:80-83` | A reviewer could close out another reviewer's claim. | Terminal actions require `reviewer == assigned_reviewer`; returns a clear error. |
| `frontend/src/api.ts:47` | Frontend swallowed the server's `detail` and showed a generic "Action failed". | `ApiError` carries the parsed `detail`; the banner displays it. |
| `frontend/src/App.vue` | All actions were always enabled regardless of status. | Buttons read `selectedItem.allowed_actions`; invalid actions are `disabled` with a `title` tooltip explaining why. |

## Product/UX decisions

**The deliberate UX improvement: server-driven contextual actions + visible urgency.**

Problem I saw: a reviewer hitting this app couldn't answer the questions in the brief. The queue was ordered by submission date, not urgency. All four action buttons were always enabled, so "what can I do on this item?" was answered by clicking and reading an opaque error. Status was a small grey label and risk/tier were buried in meta text.

What I changed and why:

1. **Risk pill + priority star in every queue row.** Now the top of the queue visibly reads "HIGH · ★ Priority" and the eye can find work without parsing dates.
2. **`allowed_actions` returned per item from the backend.** The frontend disables buttons that aren't valid for the current status and shows the reason in the tooltip. Single source of truth lives in `workflow.py`; the frontend doesn't replicate the state machine.
3. **"Mine" tag** on items assigned to the current reviewer, plus a left-border highlight in the queue. Answers "who owns this?" at a glance.
4. **Terminal note** under the action row when an item has no allowed actions, so the empty button strip isn't confusing.

**Tradeoff I made:** I chose to express `allowed_actions` server-side rather than recomputing it in the frontend. This costs one extra field in the GET response, but it keeps the rules in one place and means a future second client gets the same affordances for free. The alternative — duplicating the small lookup in TypeScript — invites the two implementations to drift.

**What I deliberately did not do in the timebox:** no major UI rewrite, no toast/snackbar library, no animations on item removal, no front-end test framework (vitest isn't in the project's dependencies and adding the toolchain would have cost time that I spent on backend test depth instead).

## Tests added

`backend/tests/test_workflow.py` (39 tests, all green):

Unit tests against `workflow.apply_action` / `is_active` / `queue_sort_key` / `allowed_actions`:
- `claim` succeeds from `unassigned` and records the reviewer.
- `claim` is rejected when status is `in_review` (state unchanged).
- Every action × every terminal status is rejected.
- A reviewer different from the assignee cannot close out the claim.
- `queue_sort_key` produces the exact specified order across a mixed fixture.

Thin HTTP integration tests via `TestClient`:
- `GET /review-items` excludes terminal items and returns the highest-urgency item first.
- Full happy path: claim → approve on an item returns 200 at each step with the right `status` and `allowed_actions`.

## Files changed and why

- `backend/app/workflow.py` (new) — single source of truth for transitions, terminal-state set, queue filter/sort, and `allowed_actions`. Kept free of FastAPI imports so it's trivially unit-testable.
- `backend/app/main.py` — reduced to HTTP wiring.
- `backend/tests/test_workflow.py` (new) — tests covering every transition + the queue rules.
- `frontend/src/api.ts` — added `allowed_actions` to the `ReviewItem` type; introduced `ApiError`.
- `frontend/src/App.vue` — render buttons from `allowed_actions` (disabled + tooltip when not allowed); risk pill, priority star, and "mine" tag in queue rows.
- `frontend/src/styles.css` — scoped CSS classes for pills and tags.
- `SUBMISSION.md` (new) — this file.
