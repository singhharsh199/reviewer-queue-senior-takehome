# Submission

## Summary of changes
We implemented a production-grade, state-safe reviewer queue system by fixing backend validation gaps and implementing a highly intuitive, premium user experience. Specifically, we:
- Corrected backend state machine constraints (e.g. claim vs action rules, terminal block).
- Enforced reviewer ownership checks to block unauthorized actions.
- Coded the exact urgency sorting algorithm required.
- Refactored the UI to use a Tab-based layout separating claimable items, personal tasks, colleague tasks, and history.
- Implemented real-time search/filtering.
- Upgraded the styling to a premium slate-indigo theme featuring color-coded risk levels, priority tags, and a chronological case timeline.

## Bugs fixed
1. **Active Queue Pollution**: The active queue previously only excluded `approved` items. We fixed this to exclude all terminal states (`approved`, `rejected`, `escalated`).
2. **Incorrect Sorting**: The queue was sorted by submission date descending (newer first). We corrected this to prioritize high risk levels first, priority customers second, and older items third (ascending submission date).
3. **Invalid Workflow Transitions**: Claims were allowed on terminal items, and approvals/rejections/escalations were allowed on unassigned items. We added strict status validations to block these.
4. **Lack of Owner Validation**: Any reviewer could approve/reject/escalate items assigned to other users. We added checks ensuring only the assigned reviewer can execute these actions.

## Product/UX decisions
1. **Interactive Tabs (To Claim, My Tasks, Others, Done)**: Rather than displaying all tasks in a single list, this separation makes it clear what a reviewer should do next ("To Claim"), what they are responsible for ("My Tasks"), what colleagues are working on ("Others"), and historical context ("Done").
2. **Context-Aware Banners & Lockouts**:
   - If a task is unassigned, only a prominent "Claim Task" button is shown.
   - If owned by me, the "Approve/Reject/Escalate" actions are enabled.
   - If owned by a colleague, a locked banner explains who owns it, protecting work.
   - If terminal, a decision summary banner is shown, and all actions are cleanly hidden.
3. **Seamless State Transitions**: When claiming an item from "To Claim", the app automatically switches focus to "My Tasks" and selects it. Similarly, finalizing a decision navigates the user to "Done".
4. **Activity Timeline**: We added an interactive timeline to the details panel displaying when the item was created, who claimed it, and who made the final decision.

## Tests added
We added `backend/tests/test_workflow.py` containing five comprehensive pytest suites:
- `test_active_queue_sorting_and_exclusion`: Validates that terminal items are excluded and active items are sorted precisely by the risk > customer > date priority rule.
- `test_claim_unassigned_item_success`: Verifies claim status transitions.
- `test_claim_already_claimed_or_terminal_fails`: Confirms 400 errors are returned when attempting to claim in-review or terminal items.
- `test_approve_reject_escalate_transitions`: Asserts that actions on unassigned tasks fail, and checks that only the assigned reviewer can successfully finalize a case.
- `test_terminal_items_reject_all_actions`: Ensures all actions on terminal items fail with 400.

## Known gaps
1. **Hardcoded User Identity**: The reviewer is hardcoded as `alex` for testing, which would be replaced with real JWT/session auth in production.
2. **Timeline Source**: The timeline logs are computed programmatically from the item's current state. A production version would query a database-backed audit log.

## Files changed and why
- **[main.py](file:///Users/singhharsh199/workspace/PAIR/reviewer-queue-senior-takehome/backend/app/main.py)**: Added urgency sorting algorithm, refined endpoints to exclude all terminal states, and enforced state machine transitions/reviewer checks.
- **[test_workflow.py](file:///Users/singhharsh199/workspace/PAIR/reviewer-queue-senior-takehome/backend/tests/test_workflow.py) [NEW]**: Implemented robust backend tests covering sorting and workflow state transitions.
- **[api.ts](file:///Users/singhharsh199/workspace/PAIR/reviewer-queue-senior-takehome/frontend/src/api.ts)**: Supported passing `activeOnly` parameter to `/review-items`.
- **[App.vue](file:///Users/singhharsh199/workspace/PAIR/reviewer-queue-senior-takehome/frontend/src/App.vue)**: Built the new tabbed layout, search engine, ownership locks, and visual timeline.
- **[styles.css](file:///Users/singhharsh199/workspace/PAIR/reviewer-queue-senior-takehome/frontend/src/styles.css)**: Implemented premium design palette, cards, independent scrolls, and responsive overrides.

## AI assistance used
Antigravity (built by Google DeepMind) was used to construct the implementation plan, refine the backend sorting keys, build out the Vue and CSS UI revamp, and structure the workflow unit test suite. All code was verified via compile checks and test passes.
