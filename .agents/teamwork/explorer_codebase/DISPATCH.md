# Dispatch: Codebase & Auth Gap Analysis

## Context
Working Directory: `e:\WORK\intel rag llamaindex\.agents\teamwork\explorer_codebase\`
Authority Document: `e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md`

## Assignment
You are `explorer_codebase` (teamwork_explorer). Your objective is to thoroughly explore the current NCERT Textbook Assistant codebase and produce a detailed gap analysis for extending the system to support a multi-tenant school organization and multi-tier RBAC system.

## Investigation Scope
1. **Authentication Subsystem (`app/auth/`)**:
   - Inspect existing authentication implementation, token generation, PyJWT usage, claims structure, secret keys, password hashing, and token verification dependencies (`get_current_user`, etc.).
   - Evaluate how to extend JWT claims or session resolution to support tenant context (`institution_id`, `institution_name`, `role`, `class_id`, `section_id`, `permissions`).
2. **User Storage & State (`storage/users.json`, etc.)**:
   - Inspect current user schemas, fields (`username`, `password_hash`, `grade`, `role`), and storage mechanism in `storage/users.json`.
   - Inspect `storage/parental_config.json`, `app/parental/`, and how user IDs / sessions interact with parental controls and chat history.
   - Analyze the concurrency and scalability limitations of flat-file JSON and assess the feasibility of migrating to SQLite + SQLAlchemy while maintaining backward compatibility.
3. **Application Routing & Middleware (`app/main.py`)**:
   - Inspect FastAPI app setup, existing routers, middleware (including `enforce_grade`), protected endpoints, and chat/RAG endpoints.
   - Identify where RBAC middleware should intercept requests to enforce Org Admin, Lecturer, and Student scopes.
4. **Frontend Architecture (`ui-client/`)**:
   - Inspect `ui-client/src/` structure, routing (React Router or state-based), auth context/store (e.g. token storage in localStorage, user profile state), login/signup forms, header/sidebar components, and grade selector.
   - Identify precise UI integration points for:
     - Student header/sidebar: Showing `<Institution Name>` or "Join your Institution" action.
     - Admin onboarding modal / page: "Create an Institution" (Name + Demo Verification ID) vs "Join an Institution".
     - Admin dashboard: Class & Section creation, generation of dedicated Lecturer and Student invite links.
     - Lecturer profile & settings: Subject tags and Class Advisor indicators.
     - Invite link acceptance handler in frontend (e.g., `/join?token=...` or modal).
5. **Backward Compatibility & Risks**:
   - Existing users without institution assignment (independent self-study students).
   - Interaction with existing grade restriction (`enforce_grade`) and parental controls.

## Deliverable
Write your complete report with verified file paths, code snippets, and structured gap analysis to:
`e:\WORK\intel rag llamaindex\.agents\teamwork\explorer_codebase\handoff.md`
Notify the orchestrator via `send_message` upon completion.


## 2026-11-02T08:55:56Z
Task: Conduct a thorough Codebase and Auth Gap Analysis across the NCERT Textbook Assistant codebase:
1. Examine app/auth/ (token creation, validation, password hashing, PyJWT usage, claims structure, user authentication dependencies).
2. Examine storage/users.json, storage/parental_config.json, app/parental/ (user data schemas, roles, fields, concurrency limitations of flat JSON, feasibility of SQLite/SQLAlchemy migration).
3. Examine app/main.py (FastAPI application setup, router mounting, existing middleware like enforce_grade, protected endpoints, tutor/query routes).
4. Examine ui-client/ (Vite + React structure in ui-client/src/, router, auth store/context, token handling, header/sidebar navigation, student grade selector, parental controls modal).
5. Identify specific gap points and integration blueprints for:
   - PyJWT claim extension (institution_id, role, class_id, section_id) vs session resolution.
   - Initial registration: Student or Admin initially, with Lecturer as invited role.
   - Admin flow in UI: "Create an Institution" (with Name and Demo Verification ID) vs "Join an Institution", Class & Section CRUD, generating dedicated Lecturer and Student invite links.
   - Student flow in UI: "Join your Institution" prompt when unjoined, displaying <Institution Name> in header/sidebar when joined.
   - Lecturer profile: Subject tags (e.g. Science, English) and Class Advisor assignment per section.
   - Tiered RBAC middleware enforcing Org Admin -> Lecturer -> Student permissions while maintaining backward compatibility with existing grade enforcement and parental controls.
