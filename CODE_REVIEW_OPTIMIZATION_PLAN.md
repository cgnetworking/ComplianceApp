The standalone `IMPLEMENTATION_PLAN`, `TECHNICAL_SPECIFICATION`, `PROJECT_REQUEST`, and `PROJECT_RULES` documents are not present in this repo. This review is inferred from the current codebase and [DEPLOYMENT.md](/Users/coreygeorge/Documents/ISO27001/DEPLOYMENT.md:1). I also could not run `python manage.py check` because Django is not installed in this workspace.

1. `[High]` Mapping uploads can persist unsanitized HTML that is rendered directly into the policy viewer. `contentHtml` from mapping JSON is trusted in [portal/services.py](/Users/coreygeorge/Documents/ISO27001/portal/services.py:236), accepted by [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:309), and injected with `innerHTML` in [webapp/js/policies.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/policies.js:794). That creates a stored HTML/XSS path that bypasses the stricter uploaded-policy flow.
2. `[High]` Risk register writes are destructive full-table replacements, so stale clients can delete unrelated records. The client submits the whole register in [webapp/js/risks.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/risks.js:529), the view treats it as the full source of truth in [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:340), and the service deletes anything not present in [portal/services.py](/Users/coreygeorge/Documents/ISO27001/portal/services.py:1030).
3. `[High]` A single processing failure can terminate the assessment worker loop. `process_zero_trust_run()` re-raises some failures in [portal/assessment_services.py](/Users/coreygeorge/Documents/ISO27001/portal/assessment_services.py:682), and the worker command does not catch them in [portal/management/commands/run_assessment_worker.py](/Users/coreygeorge/Documents/ISO27001/portal/management/commands/run_assessment_worker.py:39).
4. `[High]` Stored assessment reports execute inside an unsandboxed same-origin iframe, backed by a permissive report CSP. The iframe is rendered in [webapp/js/assessments.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/assessments.js:393), and the report response explicitly allows inline/eval script in [portal/assessment_views.py](/Users/coreygeorge/Documents/ISO27001/portal/assessment_views.py:157).
5. `[Medium]` Several JSON endpoints return `500` instead of `400` on malformed bodies because `parse_json_body()` exceptions are not handled consistently. The parser is defined in [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:216), but callers like [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:341) and [portal/assessment_views.py](/Users/coreygeorge/Documents/ISO27001/portal/assessment_views.py:57) do not consistently catch those errors.
6. `[Medium]` Review and control saves are fire-and-forget, so the UI can show changes as completed even when persistence fails. Local state is mutated immediately in [webapp/js/shared.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/shared.js:595), while the actual saves swallow failures in [webapp/js/shared.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/shared.js:873).

<analysis>
Here is my detailed review of the current codebase:
1. Code Organization & Structure: the app is functional but tightly coupled. One Django app owns page views, JSON APIs, persistence, and the assessment worker. A single bootstrap endpoint loads most state for every page, and nearly every page template repeats the same shell markup. There is also duplicated content-rendering logic in Python and JavaScript.
2. Code Quality & Best Practices: the backend has useful normalization helpers and reasonable model indexing, but error handling is inconsistent, shared-state writes are last-write-wins snapshots, and some trust boundaries are too broad for a shared portal. The repo also has no automated test suite in place to protect these flows.
3. UI/UX: the visual language is coherent and responsive, but accessibility is incomplete. The sidebar search lacks a usable label, some row-selection patterns are click-only, and review/control saves do not give reliable persistence feedback. Hard-coded workspace copy also makes the UI feel more prototype-like than production-ready.
</analysis>

# Optimization Plan

## Reliability
1. Step 1: Normalize JSON request handling.
Files: [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:216), [portal/assessment_views.py](/Users/coreygeorge/Documents/ISO27001/portal/assessment_views.py:23)
Task: introduce a shared JSON parsing/validation wrapper and use it across every JSON endpoint so malformed bodies always become stable `400` responses.
Dependencies: None.
Success Criteria: invalid JSON on assessment, risk, checklist, mapping, review, and control endpoints returns `400` with a consistent `detail` payload.
User Instructions: None.

2. Step 2: Replace destructive risk-register snapshots with record-level mutations.
Files: [portal/urls.py](/Users/coreygeorge/Documents/ISO27001/portal/urls.py:45), [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:340), [portal/services.py](/Users/coreygeorge/Documents/ISO27001/portal/services.py:1030), [webapp/js/risks.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/risks.js:529)
Task: move the risk API to create/update/delete operations by `external_id` instead of whole-register replacement.
Dependencies: Step 1.
Success Criteria: editing one risk never deletes unrelated rows, and two users can edit different risks without clobbering each other.
User Instructions: None.

3. Step 3: Make review/control saves acknowledged and failure-visible.
Files: [webapp/js/shared.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/shared.js:595), [webapp/js/reviews.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/reviews.js:1), [webapp/js/controls.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/controls.js:598), [webapp/js/review_tasks.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/review_tasks.js:100)
Task: await persistence, surface failure states in the UI, and resync local state when the server rejects or misses a write.
Dependencies: Step 1.
Success Criteria: failed writes are visible to the user and the page never silently shows stale "saved" state.
User Instructions: None.

## Security
4. Step 4: Sanitize every HTML source with the same allow-list sanitizer.
Files: [requirements.txt](/Users/coreygeorge/Documents/ISO27001/requirements.txt:1), [portal/services.py](/Users/coreygeorge/Documents/ISO27001/portal/services.py:236), [webapp/js/policies.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/policies.js:682), [DEPLOYMENT.md](/Users/coreygeorge/Documents/ISO27001/DEPLOYMENT.md:5)
Task: replace regex-based and unsanitized HTML handling with a single backend allow-list sanitizer for uploaded policies and mapping JSON documents.
Dependencies: None.
Success Criteria: disallowed tags, event handlers, and dangerous URLs are stripped regardless of whether content came from policy upload or mapping upload.
User Instructions: install the new sanitizer dependency.

5. Step 5: Make the assessment worker exception-safe.
Files: [portal/management/commands/run_assessment_worker.py](/Users/coreygeorge/Documents/ISO27001/portal/management/commands/run_assessment_worker.py:32), [portal/assessment_services.py](/Users/coreygeorge/Documents/ISO27001/portal/assessment_services.py:643)
Task: catch per-run failures in the worker loop, log them clearly, and continue polling instead of exiting the daemon.
Dependencies: None.
Success Criteria: missing `pwsh`, module issues, or unexpected run failures mark the run failed but do not stop the worker service.
User Instructions: None.

6. Step 6: Isolate report rendering from the portal origin.
Files: [webapp/js/assessments.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/assessments.js:393), [portal/assessment_views.py](/Users/coreygeorge/Documents/ISO27001/portal/assessment_views.py:150)
Task: add iframe sandboxing and tighten report-serving headers/CSP so report code cannot interact with the main portal context.
Dependencies: Step 5 recommended.
Success Criteria: stored reports remain viewable, but cannot reach `window.parent`, portal cookies, or same-origin portal APIs by default.
User Instructions: None.

## Structure, UI, and Verification
7. Step 7: Split the bootstrap payload and lazy-load heavy data.
Files: [portal/urls.py](/Users/coreygeorge/Documents/ISO27001/portal/urls.py:7), [portal/views.py](/Users/coreygeorge/Documents/ISO27001/portal/views.py:227), [portal/services.py](/Users/coreygeorge/Documents/ISO27001/portal/services.py:846), [webapp/js/runtime.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/runtime.js:178), [webapp/js/policies.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/policies.js:303), [webapp/js/vendors.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/vendors.js:1), [webapp/js/assessments.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/assessments.js:126)
Task: stop loading full policy HTML and every secondary dataset on every page; fetch only the data each page actually needs.
Dependencies: Step 1.
Success Criteria: home, controls, and reports render without downloading full policy bodies, vendor queues, and assessment detail.
User Instructions: None.

8. Step 8: Improve accessibility and extract shared page chrome.
Files: [templates/portal/_sidebar.html](/Users/coreygeorge/Documents/ISO27001/templates/portal/_sidebar.html:1), [templates/portal/index.html](/Users/coreygeorge/Documents/ISO27001/templates/portal/index.html:11), [templates/portal/controls.html](/Users/coreygeorge/Documents/ISO27001/templates/portal/controls.html:57), [templates/portal/risks.html](/Users/coreygeorge/Documents/ISO27001/templates/portal/risks.html:53), [webapp/js/shared.js](/Users/coreygeorge/Documents/ISO27001/webapp/js/shared.js:133), [webapp/styles.css](/Users/coreygeorge/Documents/ISO27001/webapp/styles.css:139)
Task: give the search input an accessible label, replace click-only table-row selection with keyboard-reachable controls, add consistent focus-visible states, and move repeated shell/header markup into a base template.
Dependencies: None.
Success Criteria: keyboard-only navigation works on shared controls, search is announced correctly to screen readers, and page shell markup exists in one place.
User Instructions: manual QA on desktop and mobile.

9. Step 9: Add regression tests and fail-closed production settings.
Files: `portal/tests/test_api_validation.py`, `portal/tests/test_risks.py`, `portal/tests/test_policies.py`, `portal/tests/test_assessments.py`, [portal_backend/settings.py](/Users/coreygeorge/Documents/ISO27001/portal_backend/settings.py:68), [DEPLOYMENT.md](/Users/coreygeorge/Documents/ISO27001/DEPLOYMENT.md:48)
Task: add tests for the critical API/security paths and change settings defaults so production does not come up with `DEBUG=True` or an unsafe fallback secret.
Dependencies: Steps 1-8.
Success Criteria: the highest-risk paths are covered by automated tests and production configuration fails closed when required env vars are missing.
User Instructions: install dependencies, then run `python manage.py test`.

Logical next step: start with Steps 1 and 2. They remove the most immediate correctness risks with the smallest surface-area change.
