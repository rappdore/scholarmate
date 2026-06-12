# ScholarMate Codebase Audit — June 2026

Scope: application code only (backend Python + frontend TypeScript). Docker/Electron packaging config and CI were out of scope, though several findings touch the Electron *runtime* because app code breaks under it.

Produced by six parallel audit passes (knowledge-feature inventory, backend services, backend routers/models, frontend components, frontend hooks/services/state, architecture). Findings that appear in multiple passes are merged; each was verified against the code, with `file:line` references. Originally written before any changes; per-finding status markers below track remediation.

Finding IDs (`K-`, `C-`, `B-`, `F-`, `A-`, `X-`) are for review discussion.

---

## STATUS DASHBOARD (last updated 2026-06-12, after the A-1 frontend + A-2 tail session)

**✅ Done (commits on main):**
- **K** — knowledge/concepts feature removed (`38fa2fd`)
- **C-3** — tsc errors fixed, build restored, typecheck gated in pre-commit; includes F-2, F-12, F-17–F-20 (`273002e`)
- **C-1** — single-source-of-truth schema, fresh-install fixed, no migration framework per owner decision (`aa1b1bf`)
- **C-2 + B-14** — path-traversal containment + legacy/dead routes removed (`b007792`)
- **Bug burn-down** — B-1..B-13, B-15, F-1..F-10, F-14, F-16, all with regression tests; backend suite 155→270, frontend 20→48 (`2c17ca9`)
- **C-5 + A-4** — single config module (`config.ts`: HTTP+WS base, `VITE_API_URL` override) + one shared axios client and one `streamSSE` helper (`http.ts`); HashRouter; dev proxy deleted; frontend suite 48→68
- **C-6** — SettingsContext lazy hydration, regression tests
- **A-3** — pydantic-settings `Settings` + lifespan-scoped `ServiceRegistry`; all 11 routers on `Depends`; zero import-time side effects; backend suite 270→281
- **C-4** — sync-work endpoints converted to `def` (threadpool-offloaded); parse/DB work in the remaining async endpoints wrapped in `asyncio.to_thread`; backend suite 281→289
- **A-1 backend (DB layer + services), 7 slices** (`9503157`..`7d4ff0c`, 2026-06-12): one `documents` registry (typed `DocumentRecord`, type-filtered `get_by_id`); `document_progress` with `PdfPosition|EpubPosition` union; `document_notes` with anchor union; `document_sessions` (units_read + time_spent_seconds; PDF `average_time_per_page` derived); highlights as two anchor-specific tables behind one `HighlightsService` (owner decision — anchors structurally differ); 1,073-line `DatabaseService` facade deleted, routers on typed services via `Depends`. **Wire shapes unchanged — frontend untouched.** One-time migration executed on the live DB (backup at `data/reading_progress.db.bak-pre-unified-*`; 6 orphan rows for previously-deleted books dropped); all 10 legacy tables gone. Deliberate semantics fix: incoming non-NULL `nav_metadata` now replaces stored value (old COALESCE order made word-count extraction unable to persist). Suite 289→253 (≈90 twin-table tests superseded by unified-service tests).
- **A-2** — twin services were the `dict[str, Any]` hotspot; all unified services are fully typed end-to-end. mypy burned to **0 errors** (`007dd0e`, 2026-06-12) and **gated in pre-commit**. The latent TTS websocket bug found during the typing pass (`current_task = None` on completion without `break` → `None.done()` AttributeError → spurious error frame + socket close after every playback) is **fixed with regression tests** (`f4b52fa`; tests carry pytest-timeout marks because the regression manifests as a client-side hang).
- **A-1 frontend remainder** — DONE 2026-06-12 (commits `a46f001`, `a236376`, `149ba31`, `1f4a5d2`):
  - **F-13** — one canonical color model (`HIGHLIGHT_COLORS` in `types/highlights.ts`: 8 named colors + hex + label). In-app code uses names; the PDF API boundary converts name↔hex (wire + existing rows stay hex), EPUB wire/CSS stay name-keyed. EPUB gained purple/red/cyan CSS classes in all three themes; the lossy PDF→EPUB color fallback is gone. Legacy hex `defaultHighlightColor` in saved settings normalizes on load.
  - **F-11** — `EPUBHighlight` is now the snake_case API record only; `EPUBTextRange` remains the camelCase DOM-range type. Dead helpers/types deleted.
  - **Highlights contexts** — one generic `createHighlightsStore` (load-on-document-change with stale-response guard, optimistic create/delete/recolor) behind both contexts; public hook APIs unchanged.
  - **Stats** — shared `calculateReadingStreak` (the streak twins were byte-identical) + `useAsyncData` fetch hook (cancellation/loading/error scaffolding); aggregate semantics stay per-format (pages vs words, owner decision).
  - **`documentApi`** — type-agnostic dispatch for list/status-counts/status-update/delete/thumbnail/cache-refresh/note-read+delete; Library and NotesPanel branch-free for those ops. Bugs fixed en route: Library status/delete matched local state on id alone (PDF/EPUB id collision); PDFViewer/HighlightsPanel/NotesPanel treated document id 0 as "no document".
  - Frontend suite 68→96 tests.
- **`/documents/{id}` route unification** — DECIDED 2026-06-12 (owner): not doing it. Backend keeps per-format routes; frontend unification happened client-side in `documentApi`.

- **eslint** — burned 65→0 and gated in pre-commit at `--max-warnings 0` (`0307506`). Wire shapes got real interfaces; each exhaustive-deps site individually fixed or disabled-with-reason.

**⬜ Open — next up:**
- **A-5 / A-6 / A-7** — chat dedup, component decomposition, EPUB parse caching

**❓ Decisions still needed (see open questions at end):** F-15 (DualChat Stop: wire or delete), TabbedRightPanel mounting, plaintext LLM api_key (accept-and-document?). Resolved 2026-06-12: highlights = two tables behind one service; migrations = none, one-time scripts only; statistics = unified storage, format semantics in consumers.

### Pickup notes for the next session

Done through step 10 (A-1 complete both sides, A-2 complete, mypy + eslint gated, TTS websocket bug fixed). Remaining: A-5 (chat dedup — `markdownComponents` ×4, `useChatStream`), A-6 (component decomposition — EPUBViewer 1,651 lines), A-7 (EPUB parse caching). Open decisions: F-15 (DualChat Stop), TabbedRightPanel mounting, plaintext api_key.

New frontend landmarks: `types/highlights.ts` (canonical color model), `contexts/createHighlightsStore.tsx` (generic store factory), `hooks/useAsyncData.ts`, `utils/readingStreak.ts`, `services/documentApi.ts` (type dispatch for format-agnostic ops).

<details><summary>Original A-1 frontend pickup notes (historical)</summary>

State of the world: the backend data layer is fully unified (commits `9503157`..`645ebbd`); the frontend was deliberately left untouched because every wire shape was preserved. The app works end-to-end right now — the remaining work is dedup/typing, not repair.

Where things live after the backend refactor:
- Models: `backend/app/models/documents.py` — `DocumentType`, `DocumentRecord`, `Pdf/EpubDocumentUpsert`, `BookStatus` (moved here; re-exported from `pdf_responses`), `Pdf/EpubPosition`, `DocumentProgress`, `Pdf/EpubNoteAnchor`, `NoteRecord`, `NotesSummary`, `PdfHighlightRecord`, `HighlightsSummary`, `ReadingSessionRecord`, `SessionsPage`.
- Services: `documents_repository.py`, `progress_service.py`, `notes_service.py`, `sessions_service.py`, `highlights_service.py` (one class, two tables) — all typed, all mypy-clean, each owns its DDL. `DatabaseService` facade and all eight twin services are gone.
- Tables: `documents`, `document_progress`, `document_notes`, `document_sessions`, `document_highlights_pdf`, `document_highlights_epub`, `llm_configurations`. Nothing else.
- Migration: `backend/scripts/migrate_to_unified_documents.py` ran 2026-06-12 (disposable now); backup at `backend/data/reading_progress.db.bak-pre-unified-*`.

Concrete next steps, in suggested order:
1. **F-11** — split `frontend/src/utils/epubHighlights.ts` `EPUBHighlight` into an API model (snake_case, mirrors backend `EPUBHighlight`) and a DOM-range type; convert at the fetch boundary.
2. **F-13** — one canonical highlight color model (hex enum in `types/highlights.ts` vs name union in `utils/epubHighlights.ts`; PDFViewer's hardcoded palette at `PDFViewer.tsx:827-836`).
3. **A-1 frontend dedup** — one `documentApi` parameterized by `DocumentType`; merge `HighlightsContext`/`EPUBHighlightsContext`, `useStatistics`/`useEpubStatistics` (the two stats endpoints now differ only in field names `pages_read`+`average_time_per_page` vs `words_read`+`time_spent_seconds`); ~54 `documentType` branch sites are the cleanup target.
4. **`/documents/{id}` route unification** — optional, decide first: backend duality is gone, so the only payoff is fewer routes; it forces frontend churn in the same change.
5. **A-2 tail** — mypy 65 errors: `ollama_service` (22), `routers/tts` (9), `services/epub/` (~20), misc (rest). Gate mypy in pre-commit when ≈0. Then eslint burn-down + gate (45 errors/27 warnings at last count).

Gotchas for whoever picks this up:
- Document ids changed during migration (old per-format id spaces overlapped). Anything cached client-side (localStorage reader positions keyed by id?) was not migrated — filenames are the stable key. Verify `SimpleResizablePanels`/reader localStorage keys if odd behavior appears.
- PDF wire field `average_time_per_page` is now *derived* (`time_spent_seconds / units_read`) — values can differ in the last decimal place from what the old table stored.
- EPUB `nav_metadata` semantics changed deliberately: a non-NULL incoming value now replaces the stored one (word-count extraction persists); `None` still never erases. Test pins this in `test_progress_service.py`.
- Backend suite is 253 tests (≈90 twin-table tests were superseded, 60 unified-service tests added). All flat under `backend/tests/`.

</details>

---

## K. Knowledge/concepts feature removal — ✅ DONE (commit 38fa2fd, 2026-06-12)

Confirmed self-contained. Flashcards exist *only* inside this feature (models, `knowledge_database.py`, tests) and go with it. EPUB concept navigation was already a silent no-op (`Reader.tsx` sets a `currentNavId` that `EPUBViewer` never receives as a prop), further evidence nothing depends on this.

**K-1. Delete outright — backend**
- `backend/app/services/knowledge/` (entire directory)
- `backend/app/routers/knowledge.py`
- `backend/app/models/knowledge_models.py` (includes all Flashcard models)
- `backend/tests/test_knowledge/` (entire directory; no other test imports knowledge code)

**K-2. Delete outright — frontend**
- `frontend/src/components/ConceptsPanel.tsx`
- `frontend/src/components/graph/` (entire directory)
- `frontend/src/pages/GraphPage.tsx`
- `frontend/src/hooks/useKnowledge.ts`, `frontend/src/hooks/useGraph.ts`
- `frontend/src/services/knowledgeApi.ts`
- `frontend/src/types/knowledge.ts`, `frontend/src/types/graph.ts`
- `frontend/src/utils/graphUtils.ts`

**K-3. Partial edits**
- `backend/main.py:16` (import), `backend/main.py:93` (`include_router`)
- `frontend/src/App.tsx:6, 24` (GraphPage import + `/graph/:bookId` route; nothing else links to `/graph`)
- `frontend/src/components/TabbedRightPanel.tsx:7, 10, 24, 33, 47, 60, 146-157` (import, `Concept` type, `'concepts'` tab, `onConceptNavigate` prop, panel render)
- `frontend/src/pages/Reader.tsx:15, 210-225, 317` (type import, `handleConceptNavigate`, prop — the `setCurrentNavId`/`setCurrentPage` setters are shared, remove only the callback)

**K-4. Dependencies to drop** (each verified to have no other import site)
- `backend/pyproject.toml`: `chromadb`, `sentence-transformers` (then `uv sync`; `networkx` is transitive only and drops out automatically; torch stays via kokoro/TTS — expected)
- `frontend/package.json`: `d3`, `@types/d3` (then `npm install`). Keep `recharts`/`regression` — statistics feature, coincidental name matches.

**K-5. Data artifacts (local disk only; `backend/data/` is gitignored)**
- `backend/data/knowledge.db`, `backend/data/chroma_data/`. Keep `reading_progress.db`.

Post-removal check: `uv sync && uv run pytest`, `npm install && npm run build` (build will still fail until C-3 is fixed — run `npx tsc -b` and confirm no *new* errors instead).

---

## C. Critical issues

**C-1. Fresh database is broken: schema drift after migration system deletion** — ✅ DONE (2026-06-12). Per owner decision, no migration framework: each table's CREATE TABLE in its owning service is now the complete, single source of truth (documents/llm-config services gained `_init_table`; the facade's duplicate drifted DDL was deleted; all import-time ALTER/backfill blocks removed). Fresh-DB regression tests added (`backend/tests/test_fresh_database_schema.py`). Orphaned `quiz_*`/`schema_migrations` tables dropped from the live DB (backup at `data/reading_progress.db.bak-pre-c1`). Original finding: `backend/app/services/reading_progress_service.py:46-53` vs `:162, 202, 350`
The old `migration_service.py` was deleted (commit `0c273aa`), but the `reading_progress` CREATE TABLE doesn't include `status`, `status_updated_at`, `manually_set` — columns the INSERT/UPDATE/SELECT code references. On a fresh DB every PDF status operation fails, and silently, because `BaseDatabaseService` swallows exceptions (B-2). The live DB works only because the deleted migration once added the columns. Related debris: orphaned `schema_migrations` and `quiz_sessions`/`quiz_questions`/`quiz_answers` tables in the live DB with zero corresponding code; schema is declared twice (each service's `_init_table` *and* `DatabaseService._init_database`) and the copies have drifted; filename→id backfill UPDATEs run at import time on every startup and are tagged "safe to remove after ~March 2026" (it is June 2026).
**Fix:** reinstate a real migration mechanism (ordered SQL scripts or Alembic), make each table's DDL exist in exactly one place, fix the `reading_progress` DDL, drop the import-time backfills, and clean the orphaned tables. *(Effort: M — and a prerequisite for the A-1 unification.)*

**C-2. Path traversal in all filename-based file access** — ✅ DONE together with B-14 (2026-06-12): containment checks (`resolve()` + `is_relative_to`) added to both `get_pdf_path`/`get_epub_path` with regression tests (`backend/tests/test_path_containment.py`); legacy `filename` body fields removed from all five AI endpoints (ids now required); `/pdf/{filename}/file` converted to id-based; dead endpoints removed: `GET /ai/{filename}/context/{page_num}`, `GET /notes/chat/{pdf_filename}`, `GET /highlights/{pdf_filename}` (+`/page/{n}`), `GET /epub-highlights/id/{id}`; EPUB session update is PUT-only; dead client methods removed (`getPageContext`, `getEPUBFile`, `getEPUBChapterProgress`). Original finding: `backend/app/services/pdf_service.py:40-52`, `backend/app/services/epub_service.py:62-78`; reachable via `GET /pdf/{filename}/file` (`routers/pdf.py:393-409`), `GET /ai/{filename}/context/{page_num}` (`routers/ai.py:590`), and the legacy `filename` body fields on all five AI endpoints (`routers/ai.py:102, 317, 400, 500, 679`)
`get_pdf_path()` does `self.pdf_dir / filename` with only a suffix check; the EPUB variant URL-decodes *first*, so double-encoded `..%252F` traversal works. Two audit passes found this independently. The legacy `filename` body fields are never sent by the frontend (verified across all clients), so they are pure attack surface.
**Fix:** containment check (`resolve()` + `is_relative_to(base)`) in both services; delete the legacy filename body fields and make `pdf_id`/`epub_id` required (see B-14 dead-endpoint list); convert `/pdf/{filename}/file` to id-based. *(S)*

**C-3. `npm run build` fails; no type/lint gate anywhere** — `frontend/package.json:12` — ✅ DONE except eslint (2026-06-12): all tsc errors fixed, build restored, `typecheck` script added and gated in pre-commit; dead files F-17/F-18/F-19 deleted; F-2 null guard and F-12 stream-event type fixed along the way. Remaining: eslint has 47 errors — burn down during the bug-fix pass, then gate it; mypy gating tracked under A-2.
`tsc -b` reports ~18 real errors; Vite (dev and electron-forge) only transpiles, pre-commit runs only prettier/ruff/pytest/vitest (no tsc, no eslint, no mypy despite CLAUDE.md requiring mypy), and there is no CI. Error clusters:
- `DualChatInterface.tsx` — stale yield type in `dualChatService.ts:30-38` missing the `type`/`metadata`/`done` fields the backend actually sends (F-12), React 19 `RefObject<T | null>` mismatches, and a *genuine* null crash (F-2)
- `useHighlights.ts:27` — dead file, delete (F-19)
- `useStatistics.ts:86` (`string` vs `BookStatus`), `Reader.tsx:71` (wrong annotation vs `api.ts:79` return type), `HighlightsPanel.tsx:197` (two incompatible `HighlightColor` types, F-13), unused props (TS6133)
**Fix:** repair the ~18 errors (most are small), add `"typecheck": "tsc -b --noEmit"` and wire tsc + eslint (+ mypy backend-side, once A-4 shrinks the count) into pre-commit. *(S/M)*

**C-4. Event-loop blocking in async paths** — ✅ DONE (2026-06-12): every endpoint doing only sync work (all of pdf/epub/notes/highlights/statistics/llm-config routers, plus `/`, `/health`, and the two chat-stop endpoints) converted to plain `def` so FastAPI runs it on its threadpool; the genuinely-async paths (`ai.py` analyze/chat/dual-chat, llm-config test) now run their blocking work — id→filename resolution, `pdfplumber` page extraction, full EPUB parse + chat-context assembly, LLM-config SQLite reads — via `asyncio.to_thread` (new `_load_epub_chat_context` helper in `ai.py`; `DualChatService._get_document_context`/`_get_llm_config` delegate to sync bodies through `to_thread`). All SQLite services open a fresh connection per call, so cross-thread use is safe. Regression tests in `backend/tests/test_async_offloading.py`: an allowlist test pins which endpoints may stay `async def`, and thread-recording tests assert the offloads actually leave the event loop. TTS was already offloaded (`generate_audio_async`). Original finding: `backend/app/services/dual_chat_service.py:318-365`, `routers/ai.py:417, 520`, plus every sync SQLite call from `async def` endpoints
`pdfplumber` full-document parsing, `epub.read_epub()` (full ZIP+XML parse), and all `BaseDatabaseService` SQLite calls run synchronously on the event loop (FastAPI only thread-offloads sync `def` endpoints, and these are all `async def`). One chat request on a large book freezes all concurrent requests including in-flight SSE streams.
**Fix:** `await asyncio.to_thread(...)` around parse/DB calls (pattern already exists in `tts_service.generate_audio_async`), or make endpoints sync `def` where they don't stream. *(M)*

**C-5. Packaged Electron app is broken by app-code assumptions** — ✅ DONE (2026-06-12): `services/config.ts` is now the single config module (HTTP + WS base URLs, `VITE_API_URL` build-time override, default `http://127.0.0.1:8000`); all URL builders route through it (useStatistics, PDFViewer session update + react-pdf `file=`, ttsService WS, llmConfig); `main.tsx` switched to HashRouter; the Vite `/api` dev proxy was deleted (dev now uses the same absolute-URL + CORS path as Electron — backend already allows `localhost:5173` and `null` origins). Bonus fix found en route: `useEpubSessionTracking`'s `sendBeacon` flush always POSTs but the endpoint is PUT-only since C-2 — replaced with `fetch(..., {method:'PUT', keepalive:true})`. Original finding: — multiple files
- `useStatistics.ts:42-46` uses bare `axios.get('/api/...')` (dev-proxy-only); `PDFViewer.tsx:202` hardcodes `fetch('/api/reading-statistics/session/update')` — both 404 under `file://`. Note: PDFViewer's `file=` URL for react-pdf is also `/api/...`-relative (left that way deliberately during C-2).
- `ttsService.ts:38-43` builds `ws://${window.location.hostname}:8000` → `ws://:8000` under `file://`
- `main.tsx:12` uses `BrowserRouter`; under `loadFile` the pathname is the file path, no route matches → likely blank window (`vite.config.ts` sets `base: './'` for exactly this case but the router wasn't switched)
- Root cause: backend URL resolution is fragmented across 4 strategies/3 defaults (`services/config.ts`, `api/llmConfig.ts:16`, `ttsService.ts`, dev proxy)
**Fix:** one config module exporting HTTP + WS base URLs with a `VITE_API_URL` override; route everything through it; switch to `HashRouter` (or conditionally in Electron). *(S/M)*

**C-6. SettingsContext wipes saved settings** — ✅ DONE (2026-06-12): lazy `useState(loadSettings)` initializer, load effect deleted; regression tests in `tests/contexts/SettingsContext.test.tsx` (StrictMode hydration, no default-overwrite, corrupt-JSON fallback). Original finding: `frontend/src/contexts/SettingsContext.tsx:64-79`
Hydration happens in an effect while a save effect writes `defaultSettings` to localStorage before hydration flushes. Under `<StrictMode>` (on, `main.tsx:11`) user settings reset to defaults on every dev reload; in prod there's a loss window.
**Fix:** lazy `useState(() => loadFromLocalStorage())`, delete the load effect (or gate first save behind a hydrated ref). *(S)*

---

## B. Backend bugs

> ✅ **Bug burn-down completed 2026-06-12** (parallel agents, all fixes verified): B-1..B-13 and B-15 below are fixed with regression tests (~130 new backend tests; suite now 270). Remaining open from B-15: none. F-side: F-1..F-10, F-14, F-16 fixed (+28 frontend tests, suite now 48). Still open: F-11 (EPUBHighlight type split — folded into A-2 typed-models work), F-13 remainder (single color model — folded into A-1), F-15 (DualChat Stop button — awaiting wire-vs-delete decision, open question 3).

**B-1. 404s swallowed into 500s in notes router** — `routers/notes.py:108-121, 124-138, 141-158`: three handlers raise `HTTPException(404)` inside `try` with no `except HTTPException: raise` before the bare `except Exception` → "not found" returns 500. *(S)*

**B-2. `BaseDatabaseService` never closes connections and conflates errors with empty results** — `base_database_service.py:49-91`: `with conn:` manages only the transaction, not closure; every query opens a connection reclaimed only by GC, and SELECTs hold their implicit transaction open. `execute_query` returns `None` on *any* exception — callers can't distinguish "no rows" from "DB broken" (this is what hides C-1). `PDFDocumentsService`/`LLMConfigService` already have the correct close-in-`finally` pattern. *(S — high leverage)*

**B-3. Multiple independent service instances → cache incoherence; deletes leave stale state** — `routers/pdf.py:34`, `routers/ai.py:22-23`, `dual_chat_service.py:54` (3 `PDFService` instances post-knowledge-removal; 2 `EPUBService`): each builds its own in-memory cache and rescans/generates thumbnails at startup. `POST /pdf/refresh-cache` refreshes one of them. `DELETE /pdf/{pdf_id}` removes the file + progress/notes/highlights but neither evicts the cache entry nor deletes the `pdf_documents` row → deleted books keep appearing in `/pdf/list`. Also misses `reading_sessions` (orphaned rows); the purpose-built `delete_sessions_by_epub_id` and both `sync_from_filesystem` methods have zero callers. *(M — fold into A-3 DI work)*

**B-4. Cache refresh empties the live cache before rebuilding** — `pdf_cache.py:72`, `epub_cache.py:105`: `self._cache = {}` then a seconds-long rebuild; concurrent requests get `FileNotFoundError` for books that exist. Build into a local dict, swap atomically. *(S)*

**B-5. EPUB cache crashes app startup on NULL DB title/author** — `epub_cache.py:174-179` (vs the correct PDF version `pdf_cache.py:127-131`): `db_record.get("title", default)` never uses the default for a present-but-NULL column → `EPUBBasicMetadata(title=None)` ValidationError, uncaught in the DB-hit branch of `_build_cache` → `EPUBService.__init__` fails. Copy-paste drift. *(S)*

**B-6. Progress updates can null out `pdf_id`/`epub_id`** — `reading_progress_service.py:144-156`, `epub_progress_service.py:165-204, 413-419`: unconditional `SET pdf_id = ?` with a lookup result that's `None` on any failure, erasing a previously-correct id and breaking id-based stats. Use `COALESCE(?, pdf_id)`. *(S)*

**B-7. Invalid SQL: `OFFSET` without `LIMIT`** — `reading_statistics_service.py:193-199`, `epub_reading_statistics_service.py:254-260`: offset-only pagination generates a SQLite syntax error, swallowed into an empty result. Emit `LIMIT -1 OFFSET ?`. *(S)*

**B-8. Check-then-write races in progress upserts** — `reading_progress_service.py:138-175`, `epub_progress_service.py:153-238`: SELECT-then-INSERT-or-UPDATE; concurrent saves → swallowed PK violation → `False`. The codebase already uses `INSERT ... ON CONFLICT DO UPDATE` elsewhere; convert. *(S)*

**B-9. Reasoning-session store: misalignment + unbounded growth** — `ollama_service.py:29, 237-286, 399-449`: keyed by filename only, appended forever, paired against `chat_history[-10:]` by index — after 10 assistant messages the stored reasoning attaches to the wrong message; concurrent chats on the same file interleave. Key by conversation/request id, store reasoning with its message, evict on completion. *(M)*

**B-10. `RequestTrackingService` leaks entries; cleanup is dead code** — `request_tracking_service.py:40-41, 167-189`: `cleanup_old_requests` has zero callers; exceptions before first generator iteration leave entries forever. Register inside the generator's `try` and/or schedule periodic cleanup at startup. *(S)*

**B-11. New `AsyncOpenAI` client per dual-chat call, never closed** — `dual_chat_service.py:272-275`: leaks httpx pools/FDs. Cache per (base_url, api_key) or close in `finally`. *(S)*

**B-12. `delete_highlights_for_epub` returns `True` unconditionally; FK CASCADE is inert** — `epub_highlights_service.py:28-58, 231-240`: result discarded; also no connection runs `PRAGMA foreign_keys=ON`, so declared `ON DELETE CASCADE` never fires anywhere in the codebase. *(S)*

**B-13. `main.py` hygiene** — `main.py:38-57, 60-66`: middleware logs full request headers (Authorization/cookies) at INFO; catch-all returns `str(e)` to clients; `allow_origins=["*"]` + `allow_credentials=True` is an invalid combination (two passes flagged). Plus: `llm_configurations.api_key` stored plaintext (`database_service.py:287`) — acceptable for a local-first app, but worth an explicit decision. *(S)*

**B-14. Dead/broken endpoints and route mismatches** (cross-checked against all frontend clients)
- `GET /ai/{filename}/context/{page_num}` (`ai.py:590-626`) — unused; frontend's `aiService.getPageContext` calls a *different, nonexistent* path `/ai/pdf/{id}/context/{n}` (`api.ts:449`) → broken on both ends; also a traversal vector. Remove both or align id-based.
- `epubService.getEPUBFile` (`epubService.ts:75-79`) and `getEPUBChapterProgress` (`epubService.ts:148-156`) call routes that don't exist on the backend — dead client methods.
- `GET /epub-highlights/id/{highlight_id}` (`epub_highlights.py:65-71`) — no caller.
- `GET /notes/chat/{pdf_filename}` (`notes.py:108-121`), `GET /highlights/{pdf_filename}` and `.../page/{n}` (`highlights.py:183-224`) — legacy filename routes, no callers (frontend is id-based), and `/highlights/{pdf_filename}` can collide with `/highlights/stats/count`.
- `epub_reading_statistics.py:26` accepts POST+PUT where the PDF twin and the frontend use PUT only.
Remove the lot. *(S)*

**B-15. Misc backend bugs/cleanup**
- `epub_highlights.py:26-93`: zero exception handling on any handler — raw 500 stack leaks. *(S)*
- `pdf.py:206-242`: invalid status → 500 instead of 400 (EPUB twin validates correctly); type the field as the `BookStatus` enum. *(S)*
- Regex-based HTML sanitization in `epub_content_processor.py:233-306` is bypassable (unclosed `<script`, etc.); BS4 is already imported — parse and strip properly. *(S/M)*
- `tts_service.py:286-295`: "streaming" generator buffers the entire synthesis before yielding — first-byte latency = total time. Bridge the sync generator through an `asyncio.Queue`. *(M)*
- `print()` debugging in production paths: `ollama_service.py:231, 234, 277, 394, 397, 443`, `epub_image_service.py:257`, `pdf.py:266, 276`. *(S)*
- Dead code: `EPUBMetadataExtractor` (instantiated, never called), `tts_service` unused constants, `request_tracking._cleanup_interval`. *(S)*
- Twin drift trivia: PDF `get_status_counts` includes `"all"`, EPUB doesn't and can `KeyError` on unexpected status (`epub_progress_service.py:529-535`); `epub_reading_statistics.upsert_session` opens an extra connection just to log insert-vs-update; `tts` docstrings say default 1.0, `DEFAULT_SPEED = 1.5`. *(S)*

---

## F. Frontend bugs

**F-1. AIPanel streams have no cancellation → interleaved analysis text** — `AIPanel.tsx:125-193, 58-82`: page changes mid-stream leave the old stream appending into the new page's panel; two streams can interleave. AbortController per analysis, abort on re-trigger/cleanup. *(S)*

**F-2. DualChatInterface null crash** — `DualChatInterface.tsx:753, 796-798`: only `secondaryLLM` is guarded; the `llm-config-changed` listener can set `primaryLLM` to null (`:117`) → `primaryLLM.name` throws. Three of the tsc errors are this real bug. *(S)*

**F-3. ChatInterface hides errors after a partial stream** — `ChatInterface.tsx:404-417` writes error/abort text to `msg.text`, but render (`:658`) ignores `text` once `responseContent` is non-empty → silently truncated answers. DualChat does it correctly; port. *(S)*

**F-4. SSE error events swallowed in all stream clients** — `api.ts` (~580/590, ~674/684), `dualChatService.ts:84-95`: `if (data.error) throw` sits inside the `try` whose catch is for `JSON.parse` and only `console.error`s → backend errors never reach the UI. Wrap only `JSON.parse` in the try. *(S)*

**F-5. EPUBViewer out-of-order content loads** — `EPUBViewer.tsx:816-850` (also `:209-215`): no ordering guard; slow older chapter response overwrites newer; `currentNavId` set before the await so navId/content mismatch transiently. Request-sequence guard or AbortController. *(S)*

**F-6. `ttsService.stop()` permanent no-op after first use** — `ttsService.ts:187-215`: `cleanup()` is async-without-awaits, so `this.cleanupPromise = this.cleanup()` re-assigns *after* the body nulled it → every later `stop()` early-returns at `:191`. *(S)*

**F-7. No request cancellation in data hooks → wrong-document data** — `HighlightsContext.tsx:56-79`, `EPUBHighlightsContext.tsx:68-89`, `useStatistics.ts:30-110`, `useEpubStatistics.ts:44-82`: stale responses can overwrite newer ones; setState-after-unmount. Cancelled-flag or AbortController per effect. *(S)*

**F-8. Session tracking counts hidden/idle time; no periodic flush** — `useEpubSessionTracking.ts:120, 177`: wall-clock since mount; returning hours later books all hidden time as reading. Pause on `visibilitychange`, add low-frequency flush. *(M)*

**F-9. DST bug in streak calculation** — `statisticsCalculations.ts:86`, `epubStatisticsCalculations.ts:97`: `Date.now() - 86400000` is wrong on DST-transition days; use `subDays`. (Timezone handling is otherwise correct end-to-end.) *(S)*

**F-10. Misc component bugs** — un-cleaned 2s timers firing setState after unmount (`EPUBViewer.tsx:245, 261, 326, 673, 833, 972`, `HighlightsPanel.tsx:586`, `NotesPanel.tsx:100`); stale-closure `setNotes(notes.filter(...))` (`NotesPanel.tsx:113`); Library hover-menu keyed by ambiguous `doc.id` so a PDF and EPUB with the same id both open menus (`Library.tsx:411-421`); `localStorage` width parsed without NaN guard (`SimpleResizablePanels`). *(S each)*

**F-11. `EPUBHighlight` type lies about runtime shape** — `epubHighlights.ts:34-46`: type requires camelCase DOM-range fields, runtime objects from the API have only snake_case. Split API model from DOM-range type, convert at the boundary. *(M)*

**F-12. `dualChatService` yield type drifted from the SSE protocol** — `dualChatService.ts:30-38`: missing `type`/`metadata`/`done` — direct cause of the DualChat tsc cluster. Define a real `DualChatStreamEvent` mirroring the typed events `api.ts` already declares for single chat. *(S)*

**F-13. Two incompatible `HighlightColor` types** — `types/highlights.ts:35` (hex enum, PDF) vs `utils/epubHighlights.ts:48` (name union, EPUB); `HighlightsPanel.tsx:181-203` funnels one into the other (the `:197` tsc error; runtime EPUB would receive hex where names are expected). PDFViewer additionally hardcodes its own palette (`PDFViewer.tsx:827-836`). One canonical color model. *(S/M)*

**F-14. `extractChapterIdFromNavId` can produce `"foo_undefined"`** — `epubHighlights.ts:557-560`. *(S)*

**F-15. DualChat Stop machinery is dead — the feature is missing** — `DualChatInterface.tsx:95-97, 282, 313-314` + `dualChatService.stopDualChat` (`:119`, never called): plumbing 90% exists, no Stop button. Decide: wire it up or delete it. *(S)*

**F-16. Logging interceptors dump full request/response bodies unconditionally** — `api.ts:17-70`, prod included. Gate behind `import.meta.env.DEV`. *(S)*

**F-17–F-20. Dead frontend code** — `services/mockApi.ts` (no imports), `hooks/useHighlights.ts` (no imports, contains a build-breaking error; superseded by HighlightsContext), `components/ResizablePanels.tsx` (171 lines, only `SimpleResizablePanels` is used), unused types (`HighlightResponse`, `UpdateColorRequest`, `HighlightState`, `CreateHighlightData`, `SectionProgress`, `EpubSessionTrackingState`, `EpubSessionUpdateRequest`), unused imports (`api.ts:7-8`), unused props (`HighlightsPanel.selectedHighlightId/onHighlightSelect`, `NotesPanel.currentChapterId`, `StatisticsHeader.pdfId`). Delete all. *(S)*

---

## A. Architecture

**A-1. Unify the PDF/EPUB duality (the big one)** — ✅ DONE. Backend in 7 slices (2026-06-12, commits `9503157`..`7d4ff0c` + simplifier pass `645ebbd`); frontend remainder same day (`a46f001`..`1f4a5d2` — see dashboard).
Implemented largely as proposed below, with these deltas: highlights got **two tables behind one service** (owner decision, open question 1); locators are stored as nullable columns (not a JSON column) but parse into the proposed discriminated unions (`PdfPosition|EpubPosition`, `PdfNoteAnchor|EpubNoteAnchor`); sessions unified as `units_read` + `time_spent_seconds` with the PDF `average_time_per_page` derived; **router paths and wire shapes were kept stable** (the `/documents/{id}` route unification was deferred — optional now that the duality is gone below the routers); the AI `ContentProvider` interface was not needed. Data migrated via one-time script (now disposable); legacy tables dropped. Original proposal:
Measured duplication: `pdf_documents` vs `epub_documents` services **91%** similar; chat-notes pair **69%** (same lifecycle, same N+1, same stale TODOs); caches **69%**; statistics **62%**; 4 near-identical router pairs (~1,300 of ~2,300 router lines); `ai.py` duplicates chat/analyze/stop per format internally; frontend mirrors all of it (two contexts, two stats hooks, two stats pages, split API clients, **54** `documentType` branch sites). Drift between twins already caused real bugs (B-5, B-15 trivia, divergent `get_..._doc_or_404` copies). Addressing has already converged on integer ids at the API level — the duality survives mainly in the DB layer and legacy routes.

Proposed shape:
- One `documents` table (`id, doc_type CHECK('pdf','epub'), filename UNIQUE, title, author, ..., metadata_json`) replacing both registries.
- A discriminated-union **locator** type — `PdfLocator(page)` | `EpubLocator(nav_id, chapter_id, chapter_title, scroll_position)` — the only data-model concept that genuinely differs for notes/progress/sessions. Single `notes`/`reading_progress`/`reading_sessions` tables keyed by `document_id` with a typed locator column. Highlights: anchors differ structurally (coordinates vs XPath) — either an anchor union or two tables behind one service interface (decision point).
- One `NotesService` / `ProgressService` / `HighlightsService` / `StatisticsService` / `DocumentsRepository`; delete the 1,073-line `DatabaseService` delegation facade (its duplicate drifted DDL is part of C-1).
- Routers: `/documents/{id}/...` + `/notes`, `/highlights`, `/reading-statistics` by `document_id`; AI endpoints unify behind a `ContentProvider` interface.
- **Stays format-specific (genuinely different):** PDF text/metadata/thumbnail extraction; the entire `services/epub/` package; EPUB progress-percentage math; AI context-window assembly; statistics *semantics* (pages vs words — unify storage, keep computation separate).
- Frontend: one `documentApi` client, one notes/highlights/statistics hook parameterized by document type; viewers stay separate behind the common props contract `Reader.tsx` already uses.

Sequencing within A-1: documents table (M) → notes (M) → progress/status (M) → sessions (S) → highlights (M) → routers (M) → frontend client (M). **Requires C-1 (migrations) first.**

**A-2. Typed models instead of `dict[str, Any]`** — ✅ LARGELY DONE via A-1 (2026-06-12): the untyped EPUB twins were the hotspot and are gone; every unified service is typed end-to-end and mypy-clean. mypy overall 125→65 errors via A-1; the tail was burned to **0 and gated in pre-commit** on 2026-06-12 (`007dd0e`). Original finding:
134 occurrences in `backend/app/`; the EPUB side is systematically untyped end-to-end (`EPUBProgressService` — every method; `EPUBDocumentsService` returns raw dicts where its 91%-twin returns `PDFDocumentRecord`; chat-notes hand-built dicts; `epub.py` router has no `response_model` anywhere, with two hand-built progress dict shapes that can drift). mypy: **125 errors in 30 files** (hotspots: `ollama_service` 22, `epub_progress_service` 12, `routers/tts` 9). Start with `EPUBDocumentRecord` (template exists), then EPUB progress/notes models; add mypy to pre-commit once the count is near zero.

**A-3. Lifespan-scoped dependency injection + a settings module** — ✅ DONE (2026-06-12): `app/settings.py` (pydantic-settings, `SCHOLARMATE_` env prefix + `.env`, defaults for db_path/pdf_dir/epub_dir/thumbnails_dir/base_url) and `app/services/registry.py` (a `ServiceRegistry` dataclass built once in `main.py`'s FastAPI lifespan; `get_*` accessors for `Depends`; `init_services`/`reset_services` for tests). All module-level singletons deleted (`db_service`, `ollama_service`, `dual_chat_service`, `tts_service`, `request_tracking_service`, `instances.py`); all 11 routers converted to `Depends` with parameter names matching the old globals (bodies unchanged); router helpers (`get_epub_doc_or_404`, `_resolve_*_filename`) take the service explicitly. Circular-import workarounds replaced by constructor injection: `DualChatService(db_path, pdf_service)`, `OllamaService(db_path, request_tracking)`. Verified: importing `main` creates no files and runs no DDL; everything constructs in `init_services()`. Tests: `test_settings.py`, `test_registry.py` (+11; suite 281). Original finding:
Module-level singletons constructed at import time (DDL + backfills on import); 3 `PDFService` / 2 `EPUBService` independent instances (B-3); `EPUBDocumentsService` constructed in 5 routers; circular-import workarounds in the facade. No settings module: `"data/reading_progress.db"` hardcoded as default **23 times**; `pdfs`/`epubs`/`thumbnails`/`base_url` hardcoded; only env read in the backend is a PyTorch flag. One `pydantic-settings` `Settings` + FastAPI `Depends`/lifespan singletons fixes B-3 structurally.

**A-4. Frontend API client consolidation** — ✅ DONE with C-5 (2026-06-12): `services/http.ts` owns the one axios instance (dev-gated logging interceptors), `parseSSELine`, and a single `streamSSE` generator that replaced all five copy-pasted reader loops (analyze ×2, chat ×2, dual-chat); `highlightService` and `llmConfig.ts` converted from raw fetch to the shared client (404 semantics preserved); `epubService.ts`'s second axios instance deleted; `api.ts` 1,044→581 lines. Tests: `tests/services/http.test.ts` (streamSSE), `tests/services/config.test.ts`. Original finding:
`api.ts` (1,044 lines) mixes axios-with-interceptors and raw fetch for the same backend; `epubService.ts` is a second axios instance without interceptors; the SSE reader loop is copy-pasted five times. One shared client + one `streamSSE` helper; single config module (ties into C-5).

**A-5. Chat component dedup** *(M)*
`ChatInterface` (823) vs `DualChatInterface` (944): ~60-70% copy-paste (delimiter normalizer verbatim, LLM-config effect, save-note dialog, scroll, input, stream loop). `markdownComponents` exists in **4 copies** (~500 lines, already diverging — DualChat's dropped `h4-h6`/`table`). Extract `utils/markdown.tsx`, `useActiveLLM()`, `useChatStream()`, `SaveNoteDialog`, `MessageBubble`; DualChat becomes layout. Also fixes F-3/F-5-class drift permanently.

**A-6. Component size / structure** *(M, opportunistic)*
`EPUBViewer.tsx` **1,580 lines** (≥4 extractable hooks: progress, navigation, TTS, selection-menu), `PDFViewer.tsx` 864 (self-contained `useReadingSessionStats` block at `:78-239`), `SettingsModal.tsx` 746, `HighlightsPanel.tsx` 689. `NotesPanel` has its note-card JSX pasted twice verbatim (`:335-444` vs `:474-588`) — extract `NoteCard`. Reader→TabbedRightPanel drills 12 props into every panel — a `ReaderContext` (document identity + position) removes ~8 props per panel signature. Inline SVG icons repeated across 5+ files — tiny `components/icons.tsx`. TabbedRightPanel mounts all panels permanently behind CSS (every tab fetches on reader open) — intentional state preservation, but document or revisit.

**A-7. Whole-book EPUB re-parse on every request** *(M)*
`epub_service.py:116-182`, `epub_chat_context_service.py:228-271`: every content/nav/style/image call does `epub.read_epub()` from scratch and rebuilds the nav index; one new-chat message triggers three full rebuilds. Small LRU of parsed books + memoized nav index, mtime-invalidated. Related N+1s: per-document title queries in all three notes-count methods and per-PDF `get_by_filename` in `/pdf/list` (one window-function query each).

---

## X. Testing & tooling gaps

- **Backend tests:** 6 files, all EPUB-side, flat layout (violates the repo's own mirrored-structure rule). **Zero tests** for: all 13 routers (incl. `ai.py`'s 725 lines of SSE/cancellation logic), the entire PDF service side, both statistics services, `llm_config_service`, `ollama_service`, `dual_chat_service`, `tts_service`, `request_tracking_service`. C-1 would have been caught by a single fresh-temp-DB test. Priority order for new tests: `reading_progress_service` (fresh DB), routers via `TestClient` smoke tests, `ollama_service` stream parsing, `llm_config_service`.
- **Frontend tests:** vitest is configured and wired into pre-commit, but exactly **one** test file exists (`bookStatus.test.ts`). Highest-value additions: statistics calculations (F-9), SSE parsing helpers (F-4, F-12), SettingsContext hydration (C-6).
- **Gates:** pre-commit runs prettier/ruff/pytest/vitest but **no tsc, no eslint, no mypy**; no CI exists. (See C-3.)

---

## Suggested sequencing

1. ✅ **K** — remove the knowledge feature (commit `38fa2fd`).
2. ✅ **C-3** — tsc errors fixed, typecheck gated in pre-commit, dead files F-17–F-20 deleted (`273002e`). eslint gating still pending (45 errors).
3. ✅ **C-1** — single-source-of-truth DDL per service, fresh-DB regression tests; no migration framework per owner decision (`aa1b1bf`).
4. ✅ **C-2 + B-14** — path containment + legacy filename routes/fields deleted (`b007792`).
5. ✅ **Bug burn-down** — B-1..B-13, B-15, F-1..F-10, F-14, F-16 with ~155 new regression tests (`2c17ca9`).
6. ✅ **C-5 + A-4 + C-6** — unified frontend config/client (`config.ts` + `http.ts`), HashRouter, dev proxy removed, SettingsContext hydration fixed; +20 frontend tests (suite 68).
7. ✅ **A-3** — pydantic-settings + lifespan service registry; routers on `Depends`; import-time side effects eliminated; +11 backend tests (suite 281).
8. ✅ **C-4** — sync endpoints to `def` (threadpool), `asyncio.to_thread` for blocking work in async paths; +8 backend tests (suite 289).
9. ✅ **A-1 + A-2 backend** — document-unification refactor in 7 tested slices + live-DB migration (`9503157`..`7d4ff0c`); unified services fully typed, facade deleted, wire shapes preserved. Backend suite 253.
10. ✅ **A-1 frontend remainder + A-2 tail** — F-11, F-13, generic highlights store, shared streak/`useAsyncData`, `documentApi`, mypy 0 + gated (`007dd0e`..`1f4a5d2`, 2026-06-12). Frontend suite 96, backend 253.
11. ⬜ **A-5 / A-6 / A-7** — dedup and decomposition, opportunistically or after unification settles. eslint burn-down + gate in progress.

## Open questions for review

1. ~~**Highlights storage under A-1**~~ — ✅ RESOLVED (owner, 2026-06-12): two tables behind one `HighlightsService` interface; anchors are genuinely structurally different (page+rect vs XPath range), a union column would just be a JSON blob.
2. ~~**Migrations**~~ — ✅ RESOLVED (owner, 2026-06-12): neither. No migration framework, ever — single-user app; schema changes must be backwards compatible, and genuinely breaking moves get a one-time disposable script (pattern: `scripts/migrate_to_unified_documents.py` — backup → copy with remap → drop legacy).
3. **DualChat Stop (F-15):** wire up the missing Stop button (plumbing exists) or delete the dead machinery?
4. **Security posture:** ~~traversal and CORS~~ (fixed in C-2/B-13). Remaining: `llm_configurations.api_key` stored plaintext — accept-and-document for a local-first app, or encrypt at rest?
5. ~~**Statistics unification**~~ — ✅ RESOLVED (owner, 2026-06-12): unified storage (`document_sessions`: `units_read` + `time_spent_seconds`) confirmed by schema inspection — both old tables held only counters, no positions; pages-vs-words semantics stay in consumers.
6. **TabbedRightPanel mounts all panels permanently** (state preservation vs eager fetching) — keep or lazy-mount?
