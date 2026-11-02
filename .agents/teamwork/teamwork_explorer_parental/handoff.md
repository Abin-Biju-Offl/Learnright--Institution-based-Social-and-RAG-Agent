# Handoff Report: Parental Controls, Monitoring, and Filtering Architecture

**Author**: Teamwork Explorer (`teamwork_explorer_parental`)  
**Target Recipient**: Teamwork Orchestrator (`f0cdbf9a-9067-430b-91fd-5b4abd94d12d`) & Peer Implementers  
**Type**: Hard Handoff (Investigation & Architecture Design Complete)  
**Date**: 2026-10-31  

---

## 1. Observation

1. **Frontend Architecture & Serving Pipeline (`ui-client/` and `app/main.py`)**:
   - `ui-client/package.json:15-24` defines React 18 (`react: ^18.3.1`, `react-dom: ^18.3.1`) and Vite 5 (`vite: ^5.4.11`).
   - `ui-client/vite.config.js:8-23` compiles assets directly into `../frontend/` without clearing previous static assets, and proxies `/api` and `/pdfs` to `http://127.0.0.1:8000`.
   - `app/main.py:230` mounts the compiled bundle at root: `app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")`.
   - `ui-client/src/App.jsx:98-114` stores chat history solely in browser `localStorage` using the key `ncert-tutor-sessions-v3`. There is zero server-side conversation history persistence for student sessions.
   - `ui-client/src/App.css:1656-1733` already implements Google Gemini dark frosted-glass modal styles (`.gemini-modal-overlay`, `.gemini-modal-card`, `.gemini-modal-header`, `.gemini-modal-title`, `.gemini-modal-close`, `.gemini-modal-body`) matching the visual aesthetic.

2. **Backend API & Ingress Handling (`app/main.py:79-208`)**:
   - `app/main.py:159-208` handles `POST /api/ask` and `POST /api/ask/stream`. Neither endpoint currently enforces parental restrictions, logs student conversation turns, or provides endpoints for parental authentication, history retrieval, or filtering preferences.
   - Telemetry in `app/metrics.py:14-48` and `storage/conversation_metrics.jsonl` records latency and token counts, but truncates questions (`question[:40]`) and omits full assistant answers and safety evaluation tags.
   - Thread-safe storage in `app/metrics.py:11` and `app/main.py:216` utilizes `threading.Lock()` (`metrics_lock`, `feedback_lock`) to append records to `.jsonl` files in `storage/`.

3. **Taxonomy & Safety Integration Contract (`teamwork_explorer_taxonomy`)**:
   - Peer explorer `teamwork_explorer_taxonomy` established a 7-category taxonomy (`adult_sexual`, `violence_gore`, `self_harm`, `hate_speech`, `illegal_acts_weapons_drugs`, `cyberbullying`, `other_inappropriate`) with curriculum whitelisting for NCERT Class 10 Biology (Chapter 7 Reproduction, Chapter 8 Heredity).
   - The safety pipeline will emit structured events to `storage/safety_events.jsonl`, which serves as the data foundation for parental alerts.

---

## 2. Logic Chain

1. **From Observation 1 to Server-Side History Requirement**:
   - Because `ui-client/src/App.jsx` currently retains chat conversations only in client-side `localStorage`, any student can clear browser history, use incognito mode, or switch browsers to conceal inappropriate inquiries from parents.
   - Therefore, a production-grade parental control system requires **server-side conversation turn logging** to `storage/student_chat_history.jsonl` upon completion of `POST /api/ask` and `POST /api/ask/stream`.

2. **From Observation 1 & 2 to Security & PIN Authentication**:
   - To prevent children from guessing PINs or tampering with configuration, PINs must be hashed using PBKDF2-HMAC-SHA256 (100,000 iterations, 16-byte random salt) stored in `storage/parental_config.json`.
   - To counteract local brute-force attempts, the backend must enforce progressive lockout (5 failed attempts = 5 min lockout; 8 fails = 15 min lockout) and issue temporary, expirable Bearer tokens (15-minute inactivity window).

3. **From Observation 2 & 3 to Parental Feature Endpoints**:
   - Guardians need dedicated REST endpoints to:
     a) Authenticate and manage PIN (`/api/parent/auth/*`)
     b) Audit complete student chat transcripts (`/api/parent/history`)
     c) Review and acknowledge flagged queries (`/api/parent/flagged`)
     d) Configure category toggles, strictness profiles, and custom blacklisted keywords (`/api/parent/settings`)
     e) View high-level study compliance and activity metrics (`/api/parent/overview`)

4. **From Observation 1 to UI/UX Seamless Integration**:
   - The React UI can reuse existing `.gemini-modal-*` CSS tokens and frosted glass aesthetics in `ui-client/` to introduce a `ParentalControlsNavButton` in the sidebar and an elegant 5-tab `ParentalPortalModal` (Overview, Chat History, Flagged Alerts, Content Filtering, Security & PIN).

---

## 3. Caveats

1. **Single-Parent Device Assumption**: The current architecture assumes a single parental administration entity per local installation. Multi-account role-based access control (e.g. distinct parent accounts per student) is deferred as out-of-scope for the single-user local deployment model.
2. **Local Storage Cleanup vs. Server History**: Clearing browser history in the UI only clears the student's local view (`localStorage`); it does not erase the server-side audit log in `storage/student_chat_history.jsonl`, which can only be archived or purged from within the authenticated Parental Portal.
3. **Helpline Localization**: Emergency crisis response banners (for `self_harm` flags) are tailored to Indian national helplines (Tele-MANAS `14416`, CHILDLINE `1098`, KIRAN `1800-599-0019`) reflecting the NCERT context.

---

## 4. Conclusion

1. **Comprehensive Architecture Delivered**: A complete architectural specification and implementation plan for Parental Controls, Features, API, and UI has been authored in `analysis.md`.
2. **Backend Architecture Specified**:
   - `app/parental/`: Modular package providing `auth.py` (PBKDF2 salted PIN hashing, rate-limiting lockout, session tokens), `storage.py` (atomic thread-safe JSON/JSONL management), `service.py`, `schemas.py`, and `routes.py` (`/api/parent/*`).
   - Logging pipeline: Dual persistence in `storage/student_chat_history.jsonl` (full turns) and `storage/safety_events.jsonl` (flagged query triage).
3. **Frontend UI Designed**:
   - Sleek Google Gemini-themed components in `ui-client/`: `ParentalNavButton` with unreviewed alert pill, `ParentalAuthModal` with on-screen numeric keypad & shake animation, and `ParentalPortalModal` with 5 dedicated functional tabs.
4. **Custom Filtering & Exceptions**:
   - Flexible presets (`Strict Elementary` vs `Curriculum Standard`), category toggles, custom keyword blacklist manager, and preserved NCERT Biology reproductive science access.

---

## 5. Verification Method

1. **Artifact Verification**:
   - Inspect `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_parental\analysis.md` for complete data models, endpoint contracts, UI layout wireframes, and security algorithms.
2. **Backend API & Security Verification**:
   - Once implemented by the engineering agent, run `.venv\Scripts\pytest tests/test_parental.py -v`.
   - Test cases must verify:
     - PIN setup & verification with salted PBKDF2 hashing.
     - 5-attempt brute-force lockout enforcing `HTTP 429`.
     - Student chat history logging and retrieval via `/api/parent/history`.
     - Flagged query logging and review status transition via `POST /api/parent/flagged/{id}/review`.
     - Category toggles & custom keyword blocking persistence via `/api/parent/settings`.
3. **Frontend Verification**:
   - Run `npm run build` in `ui-client/` to verify bundling into `frontend/`.
   - Access `http://localhost:8000` to verify PIN modal, lockout animations, tab switching, and responsiveness.
