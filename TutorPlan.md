ScholarMate Tutor Workspace — Implementation Plan (UI‑First)

Overview
- Goal: Add a dedicated Tutor Workspace that asks conceptual questions based on the book and user progress, evaluates freeform answers, provides hints/follow‑ups, and saves all Q&A data.
- Strategy: Build UI first with mock data and a typed client API, then wire to backend endpoints. Keep Reader navigation and progress independent from Tutor sessions.
- Entry points: From Library (Start/Resume Tutor) and from Reader (Practice this section) routing to a standalone page.

User Experience
- Page route: `/tutor/:filename/:sessionId?` with optional `scope`, `mode`, `difficulty` query params.
- Header: book info, scope selector (Current section, Up to here, Custom), difficulty control, mode toggle (Practice/Assessment), session controls (Start/End/Resume), and a quick link to open the same location in Reader.
- Main layout: two-pane workspace (left: Document Context Viewer; right: Tutor Conversation). Optional history drawer.
- Flow per question: Ask → (optional Hint) → Answer (with LaTeX preview) → Evaluate (score/verdict, rubric hits/misses) → (optional Follow‑up) → Next.
- History: Timeline of questions/answers/feedback per session with filters (concept, difficulty, verdict). Click an item to jump the Document Context Viewer to the relevant location.

Navigation & Routing
- Add route `TutorPage` at `/tutor/:filename/:sessionId?`.
- Accept navigation from:
  - Library card actions: “Start Tutor” (no sessionId), “Resume Tutor” (existing sessionId).
  - Reader CTA: “Practice this section” with an encoded scope (PDF: page/page range; EPUB: nav_id/anchor).
- Deep links: Allow direct access to a given sessionId; the Tutor page fetches the session and resumes.

UI Layout & Components
- Responsive layout prioritizing sufficient space for math answers and feedback.
- Left panel (Document Context Viewer):
  - Shows the precise doc location associated with the current question (PDF single page; EPUB chapter/anchor).
  - Read‑only by default; controls: zoom, fit, jump to location, open in Reader.
- Right panel (Tutor Conversation):
  - Conversation list of Question → Answer → Feedback blocks.
  - Active composer: multiline answer textarea with LaTeX preview; actions: Submit, Hint, Explain, Skip, Follow‑up.
  - Feedback panel: verdict (Correct/Partial/Incorrect), score, rubric hits/misses, suggested next steps.
- History drawer (right side or bottom sheet on small screens):
  - Filters for concept/difficulty/verdict.
  - Click to load that Q&A and reposition Document Context Viewer.

Planned File/Folder Structure (Frontend)
- `frontend/src/pages/Tutor/TutorPage.tsx`
- `frontend/src/components/tutor/TutorHeader.tsx`
- `frontend/src/components/tutor/DocumentContextViewer.tsx`
- `frontend/src/components/tutor/TutorConversation.tsx`
- `frontend/src/components/tutor/QuestionCard.tsx`
- `frontend/src/components/tutor/AnswerEditor.tsx`
- `frontend/src/components/tutor/FeedbackPanel.tsx`
- `frontend/src/components/tutor/HistoryDrawer.tsx`
- `frontend/src/components/tutor/SessionSummary.tsx`
- `frontend/src/contexts/TutorSessionContext.tsx`
- `frontend/src/services/tutorApi.ts` (typed client; mockable)
- `frontend/src/mocks/tutorFixtures.ts` (mock data for UI‑first)

UI State Management
- Context: `TutorSessionContext` to hold session state, current question, history, loading flags, and actions.
- Reducer actions (examples):
  - `INIT_SESSION`, `RESUME_SESSION`, `END_SESSION`
  - `LOAD_NEXT_QUESTION_REQUEST/SUCCESS/FAILURE`
  - `SUBMIT_ANSWER_REQUEST/SUCCESS/FAILURE`
  - `REQUEST_HINT_REQUEST/SUCCESS/FAILURE`
  - `REQUEST_FOLLOWUP_REQUEST/SUCCESS/FAILURE`
  - `SELECT_HISTORY_ITEM`, `SET_SCOPE`, `SET_DIFFICULTY`, `SET_MODE`
- Persisted client state: ephemeral in memory (no local storage) during UI‑first; real persistence via backend once wired.

Key TypeScript Types (UI contracts)
```ts
export type DocType = 'pdf' | 'epub';

export interface DocLocationPDF {
  type: 'pdf';
  page: number;          // 1-based
  bbox?: [number, number, number, number]; // optional highlight box
}

export interface DocLocationEPUB {
  type: 'epub';
  navId: string;         // chapter id
  anchor?: string;       // css selector or fragment id for location
}

export type DocLocation = DocLocationPDF | DocLocationEPUB;

export type TutorMode = 'practice' | 'assessment';

export interface TutorSession {
  id: string;
  filename: string;
  docType: DocType;
  scope: {
    kind: 'current' | 'up_to_here' | 'custom';
    pdfRange?: { startPage: number; endPage: number };
    epubRange?: { startNavId: string; endNavId: string };
  };
  mode: TutorMode;
  difficulty: 1 | 2 | 3 | 4 | 5;
  status: 'active' | 'completed' | 'paused';
  createdAt: string;
  endedAt?: string;
}

export interface TutorQuestion {
  id: string;
  sessionId: string;
  text: string;          // UTF-8 with optional $...$ or $$...$$
  questionType: 'concept' | 'definition' | 'compare' | 'intuition' | 'derivation' | 'counterexample';
  difficulty: 1 | 2 | 3 | 4 | 5;
  conceptKey?: string;   // normalized label for coverage tracking
  docLocation: DocLocation;
  rubric: string[];      // concise key points expected in a good answer
  createdAt: string;
}

export interface TutorEvaluation {
  verdict: 'correct' | 'partial' | 'incorrect';
  score: number;         // 0–1
  hits: string[];        // rubric points met
  misses: string[];      // rubric points missed
  incorrectClaims?: string[]; // specific mistakes
  feedback: string;      // short, actionable feedback
  followUpQuestion?: string;  // optional targeted follow-up
}

export interface TutorAnswer {
  id: string;
  questionId: string;
  userAnswer: string;    // text with LaTeX segments allowed
  evaluation: TutorEvaluation;
  isCorrect: boolean;
  createdAt: string;
}
```

Component Responsibilities
- `TutorPage`: Route controller. Parses params, bootstraps or resumes session, orchestrates layout and data fetching, owns History Drawer visibility.
- `TutorHeader`: Book info, scope/mode/difficulty controls, Start/End/Resume buttons, “Open in Reader”. Emits events to context.
- `DocumentContextViewer`:
  - Wraps `PDFViewer`/`EPUBViewer` in read‑only mode.
  - Receives `docLocation` and ensures the correct page/chapter/anchor is shown.
  - Provides zoom controls and a “jump to location” action.
- `TutorConversation`:
  - Renders a list of blocks (QuestionCard, AnswerEditor/AnswerView, FeedbackPanel).
  - Manages scrolling to the current active block; shows skeletons while loading.
- `QuestionCard`: Displays question text, concept label/difficulty, quick actions (Hint/Explain/Skip).
- `AnswerEditor`:
  - Multiline text input with LaTeX preview (KaTeX). Toggle preview and keyboard shortcut (Ctrl/Cmd+Enter to submit).
  - Shows “Need a nudge?” (hint) and “Explain” options.
- `FeedbackPanel`: Displays verdict, score, rubric hits/misses, incorrect claims, suggested next steps, and optional follow‑up question.
- `HistoryDrawer`: Timeline of past Q&A. Filters by concept/difficulty/verdict. Clicking loads that item and updates DocumentContextViewer.
- `SessionSummary`: When ending a session, shows correctness by concept and suggested topics to revisit.

Math Input & Rendering
- Use KaTeX for fast client-side math rendering in QuestionCard, Answer preview, and Feedback.
- Input guidelines: `$...$` for inline, `$$...$$` for display math; provide a short helper tooltip with examples.
- Preserve raw text in answers; render preview on demand.

Loading & Error States (UI)
- Skeleton loaders for question fetch and evaluation steps.
- Toasts for transient errors (network, evaluation parsing). Inline retry buttons for idempotent actions (Get next, Evaluate again).
- Defensive JSON parsing for model outputs in mock/real mode; show minimal fallback feedback if parsing fails.

Mock‑First Development
- `tutorApi` exposes async functions returning Promises; during UI‑first these resolve from `tutorFixtures`.
- Fixtures include realistic question/rubric/evaluation examples across math topics and doc types.
- Add a “Mock Mode” toggle in header (developer only), or auto‑enable when backend is not reachable.

Minimal Client API (UI‑first stub)
```ts
// tutorApi.ts (mock signatures; resolve fixtures during UI‑first)
startSession(args: { filename: string; docType: DocType; scope: TutorSession['scope']; mode: TutorMode; difficulty: TutorSession['difficulty']; }): Promise<{ session: TutorSession; question?: TutorQuestion }>;
getNextQuestion(args: { sessionId: string; focus?: { conceptKey?: string; difficulty?: number } }): Promise<TutorQuestion>;
evaluateAnswer(args: { sessionId: string; questionId: string; userAnswer: string; }): Promise<{ answer: TutorAnswer }>;
getHint(args: { sessionId: string; questionId: string; }): Promise<{ hint: string }>;
getSessionHistory(args: { sessionId: string; }): Promise<Array<{ question: TutorQuestion; answer?: TutorAnswer }>>;
endSession(args: { sessionId: string; }): Promise<{ summary: { byConcept: Array<{ conceptKey: string; correct: number; total: number }> } }>;
```

Document Context Integration (UI)
- PDF: Render a single page via existing `PDFViewer` component with props to lock pagination and disable editing/highlighting. Accept `page` and optional `bbox` to draw a translucent overlay.
- EPUB: Render the chapter (`navId`) and scroll to `anchor` if present; hide navigation controls; read‑only.
- Provide a link “Open in Reader at this location” that routes back to Reader with precise docLocation params.

Accessibility & Keyboard
- Focus management: Move focus to AnswerEditor when a new question arrives; restore focus after evaluation.
- Keyboard: Enter (with modifier) submits; ESC closes History Drawer; `[` `]` lowers/raises difficulty slider.
- ARIA labels for math preview, verdict, and rubric items.

Styling Conventions
- Tailwind utility classes consistent with existing project; adhere to dark theme readability.
- Color hints: green (correct), amber (partial), red (incorrect); neutral for rubric points.

Backend Contracts (to drive later wiring)

HTTP Endpoints (JSON, with optional SSE for streaming)
- POST `/quiz/session/start`
  - Request: `{ filename, doc_type: 'pdf'|'epub', scope, mode: 'practice'|'assessment', difficulty: 1..5 }`
  - Response: `{ session: TutorSession, question?: TutorQuestion }`

- POST `/quiz/question/next`
  - Request: `{ session_id, focus?: { concept_key?, difficulty? } }`
  - Response: `{ question: TutorQuestion }`

- POST `/quiz/answer`
  - Request: `{ session_id, question_id, user_answer }`
  - Response: `{ answer: TutorAnswer }`

- POST `/quiz/hint`
  - Request: `{ session_id, question_id }`
  - Response: `{ hint: string }`

- GET `/quiz/session/{id}/history`
  - Response: `{ items: Array<{ question: TutorQuestion, answer?: TutorAnswer }> }`

- PUT `/quiz/session/{id}/end`
  - Response: `{ summary: { by_concept: Array<{ concept_key, correct, total }> } }`

Streaming Variants (optional MVP-1)
- SSE `/quiz/question/stream` for progressive question generation (rarely needed; default to non‑stream).
- SSE `/quiz/evaluate/stream` to stream evaluation feedback as it’s produced.

Backend Data Model (SQLite)
- `quiz_sessions`:
  - `id` (PK, text/uuid), `filename` (text), `doc_type` (text), `scope_json` (text), `mode` (text), `difficulty` (int), `status` (text),
    `started_at` (datetime), `ended_at` (datetime null)
- `quiz_questions`:
  - `id` (PK), `session_id` (FK), `question_text` (text), `question_type` (text), `difficulty` (int), `concept_key` (text null),
    `doc_location_json` (text), `rubric_json` (text), `created_at` (datetime)
- `quiz_answers`:
  - `id` (PK), `question_id` (FK), `user_answer_text` (text), `evaluation_json` (text), `feedback_text` (text),
    `is_correct` (int bool), `created_at` (datetime)
- Indexes:
  - `quiz_questions(session_id)`, `quiz_answers(question_id)`, `quiz_sessions(filename, status)`

Backend Service Architecture
- New `tutor` (or `quiz`) service module encapsulating:
  - Session management: start/end/resume, scope parsing, state.
  - Question generation: uses PDF/EPUB services to extract context from the specified scope; feeds to AI prompt.
  - Evaluation: compares user answer against rubric via AI; enforces grounding to provided context.
  - Persistence: saves sessions, questions, answers.
  - History & summary: aggregates by concept and difficulty.
- Reuse existing services:
  - `PDFService`: page text extraction + optional bbox mapping; thumbnail not required.
  - `EPUBService`: chapter HTML and anchors; CSS sanitized; images optional.
  - `AIService` (Ollama/qwen3:30b): add prompt templates for question generation and evaluation. Support streaming.

AI Prompting & Guardrails
- Context assembly: extract relevant text for the current scope (PDF pages or EPUB chapter), capped by token budget. If scope is “up_to_here”, summarize earlier segments and include the full current section.
- Question generation prompt: produce one conceptual question with a concise rubric and `concept_key`.
- Evaluation prompt: given question, rubric, and user answer, return JSON with `verdict`, `score`, `hits`, `misses`, `incorrect_claims`, `feedback`, and `follow_up_question`.
- Guardrails: “Only use provided book context. If insufficient, ask for clarification or reference the needed section.”
- Determinism: lower temperature for evaluation, moderate for question generation; add JSON schema examples for reliability.

Doc Location Encoding
- PDF: `{ type: 'pdf', page: 12, bbox?: [x1,y1,x2,y2] }` using the same coordinate system as `PDFViewer`.
- EPUB: `{ type: 'epub', navId: 'ch05', anchor: '#thm-2.3' }` consistent with `EPUBViewer` navigation IDs.

Validation & Error Handling (Backend)
- Strict JSON parsing with schema validation; retry with constrained prompt if parsing fails.
- Timeouts and cancellation tokens for long generations; return partial results if streaming.
- Idempotency: `question/next` should avoid duplicates by concept within a session unless explicitly requested.

Performance Considerations
- Cache per-section concept candidates to accelerate subsequent questions.
- For large scopes, summarize prior content; include only the current section’s full text.
- Stream evaluation feedback for responsiveness if parsing latency is noticeable.

Security & Privacy
- Entirely local (Ollama); no external calls.
- Sanitize HTML from EPUB before prompts; strip images unless essential.
- Escape/strip LaTeX when sending to model to avoid prompt injection via math environment.

Testing Strategy
- Frontend
  - Component tests: AnswerEditor (math preview), FeedbackPanel rendering for all verdicts, DocumentContextViewer positioning.
  - Integration tests: Start → Ask → Answer → Evaluate loop in mock mode.
  - Routing tests: deep link to an existing session; “Open in Reader” navigates with docLocation.
- Backend
  - Unit tests: scope parsing, DB CRUD for sessions/questions/answers, question selection logic.
  - AI stubs: deterministic fake model to verify rubric adherence and JSON structure.
  - API tests: happy paths and error paths (invalid sessionId, missing scope, parse failures).

Acceptance Criteria
- Start a Tutor session from Library or Reader with chosen scope; receive a grounded question tied to a doc location.
- Submit a freeform answer with optional LaTeX; get structured evaluation (verdict, score, hits/misses) and brief feedback.
- Optional: request a hint or follow‑up; UI updates without blocking the main flow.
- All Q&A persisted; History shows items and repositions the Document Context Viewer.
- Ending a session shows a summary by concept; resuming works across app restarts.

Implementation Steps (Sequenced)

Phase 1 — UI Scaffolding (Mock Mode)
1) Routing
   - Add `TutorPage` route at `/tutor/:filename/:sessionId?`.
   - Add link targets in Library cards and Reader CTA (no backend calls yet).

2) Context & Types
   - Create `TutorSessionContext` with types above and reducer skeleton.
   - Provide actions: init/resume/end, next question, submit answer, hint, follow‑up.

3) Header
   - Implement `TutorHeader` with filename display, scope selector, difficulty slider, mode toggle, Start/End buttons, and “Open in Reader”.
   - Wire to context; keep Start disabled until required fields selected.

4) Document Context Viewer
   - Implement wrapper that accepts `DocLocation` and renders PDF/EPUB via existing viewers in read‑only mode. Provide zoom and “jump to location”.

5) Conversation & Composer
   - Implement `TutorConversation`, `QuestionCard`, `AnswerEditor`, and `FeedbackPanel` with mock data flow.
   - Add LaTeX preview using KaTeX and a small formatting helper tooltip.

6) History Drawer
   - Implement `HistoryDrawer` reading from context; enable filters and click‑to‑jump.

7) Mock API & Fixtures
   - Implement `tutorApi` functions returning fixtures from `tutorFixtures` with artificial delays to simulate network.
   - Seed fixtures for 2–3 math topics (e.g., limits, linear algebra basics) including doc locations for PDF and EPUB.

Deliverable: Fully navigable Tutor UI with realistic mock flow, independent of backend.

Phase 2 — Backend Infrastructure
8) DB Migration
   - Add tables `quiz_sessions`, `quiz_questions`, `quiz_answers` with indexes.
   - Expose migrations via existing migration system; add seed smoke tests.

9) API Endpoints
   - Implement endpoints as per contracts. Use Pydantic models for request/response.
   - Add OpenAPI docs and examples for each route.

10) Tutor Service
    - Implement session lifecycle, question generation (context extraction + AI prompt), evaluation (AI + rubric matching), and persistence.
    - Add guardrails for grounding; retries for JSON parsing failures.

11) Context Extraction
    - Hook into PDF/EPUB services to build scope text; add summarization for long scopes.
    - Define doc_location mapping helpers for consistent encoding.

12) Streaming (optional in MVP)
    - Add SSE endpoints for evaluation streaming; fall back to non‑streaming if disabled.

Deliverable: Backend API returns real questions and evaluations, persisted in SQLite.

Phase 3 — Wiring & Integration
13) Swap Mock API
    - Update `tutorApi` to call FastAPI endpoints; keep a feature flag to toggle mock mode.

14) Session Resume & History
    - Connect History Drawer to `/quiz/session/{id}/history`.
    - Ensure Document Context Viewer jumps to historical `docLocation`.

15) Reader Bridge
    - Implement “Open in Reader” linking with docLocation params; verify round‑trip flow from Reader “Practice this section”.

16) QA & Polishing
    - Validate math rendering performance and dark theme readability.
    - Add empty/skeleton states, timeouts, and error retries.
    - Finalize acceptance criteria checks.

Nice‑to‑Haves (Post‑MVP)
- Spaced repetition queue derived from incorrect/partial answers.
- Concept map extraction per chapter with coverage visualization.
- Timed assessment mode with exportable rubric results.
- Attach feedback to notes/highlights; “Revisit this concept” shortcuts.

Developer Notes
- Keep UI and API contracts in sync: update this plan if contracts change.
- Favor small, composable components; avoid coupling Tutor state with Reader state.
- Ensure testability by keeping `tutorApi` injectable (mock vs. real).

Next Action (when implementation starts)
- Begin Phase 1 Step 1: add Tutor route and scaffold `TutorPage` with header and empty panes, then iterate through components using mock API.
