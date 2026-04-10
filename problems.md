# Active Review Findings for `origin/main..HEAD`

Reviewed range: `origin/main..HEAD`

Scope: committed changes only; unrelated uncommitted worktree changes were ignored.

Status legend: Open | Deferred

---

## 1. ✅ High: tab re-attach can duplicate already-rendered turns

Files:
- `ui/web/frontend/src/main.ts`

Details:
- `lastRenderedContextOffset` was only updated after initial `/history` load and `visibilitychange` backfill; live SSE delivery never advanced it. On re-focus, `getHistory(id, staleOffset)` returned turns already rendered.

Resolution:
- SSE callback in `attachSession()` now reads `(event as any)._ctx` (embedded in every event payload) and advances `lastRenderedContextOffset = Math.max(last, _ctx)`. `visibilitychange` fetch now always starts from the true last-rendered offset.

---

## 2. ✅ Medium: panel can show or write stale task/config state across session switches

Files:
- `ui/web/frontend/src/main.ts`
- `ui/web/frontend/src/components/panel.ts`

Details:
- `attachSession()` did not clear `store.taskCards` / `store.currentParams` before switching, so the panel briefly showed the previous session's data. Async refresh/save callbacks in panel.ts lacked stale-session guards.

Resolution:
- `attachSession()` now sets `store.taskCards = []` and `store.currentParams = null` (with `emit`) immediately at the start, before any `await`.
- `showTaskEditor` callback, `btn-refresh-tasks` handler, and `showConfigEditor` save callback all check `store.currentSessionId !== sessionId` after their awaits and bail if stale.

---

## 3. ✅ Medium: persistent sessions never show persistent tone in the sidebar

Files:
- `ui/web/sessions.py`

Details:
- `sessionTone()` in `types.ts` read `sess.persistent`, but `sessions.py` never set that field — only `session_type` was returned.

Resolution:
- Added `"persistent": params.get("session_type") == "persistent"` to the session info dict in `sessions.py`. The `Session` interface already declared `persistent: boolean`; now the backend actually populates it.

---

## 4. Open Medium: committed pytest suite is red after the web/runtime changes

Files:
- `tests/porter_system/test_runtime_v1_3_77_ipc.py`
- `tests/porter_system/test_session_engine_v1_3_77_session_engine.py`
- `tests/porter_system/test_porter_system_v1_3_77_runner_helpers.py`

Details:
- `pytest tests/porter_system -q` fails with 3 errors.
- `test_session_engine_*:58` asserts default heartbeat interval `600.0`; current default is `7200.0`.
- `test_runtime_*:41` asserts `agent` events have no `id`; they now carry `id = f"turn:{ts}"`.
- These are test-suite drift issues, not regressions in production behaviour.

Not fixed:
- Test updates are owned by a dedicated person; not touched here per project policy.

---

## 5. Deferred Medium: markdown rendering is a stored XSS sink

Files:
- `ui/web/frontend/src/markdown.ts`
- `ui/web/frontend/src/components/chat.ts`

Details:
- `renderMarkdown()` returns raw `marked.parse(text)` and multiple message render paths assign that result to `innerHTML` without sanitization.

Deferred:
- Real risk, but currently lower urgency for a local/personal-use tool. Proper fix is to sanitize rendered HTML before insertion.

---

## 6. Deferred Medium: HUD still adds avoidable file-scan and subprocess overhead

Files:
- `ui/web/app.py`
- `ui/web/frontend/src/main.ts`

Details:
- Every 10s HUD poll still resolves git state via subprocess and scans `context.jsonl` backwards to recover the latest turn usage.

Deferred:
- Acceptable for now on a single-user local tool, but still worth moving to cached or event-driven data if HUD polling becomes more frequent.

---

## 7. Deferred Medium: streaming markdown still re-parses and replaces the full DOM on every chunk

Files:
- `ui/web/frontend/src/components/chat.ts`

Details:
- Each `partial_text` chunk re-runs `renderMarkdown()` on the full accumulated text and replaces `body.innerHTML`.

Deferred:
- This is mostly a performance/jank concern on long generations rather than a correctness bug. A plain-text streaming path with final markdown render would be safer.
