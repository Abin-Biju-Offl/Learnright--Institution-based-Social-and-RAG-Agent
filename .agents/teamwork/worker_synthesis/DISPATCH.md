# Dispatch: Architecture & Implementation Plan Synthesis

## Context
Working Directory: `e:\WORK\intel rag llamaindex\.agents\teamwork\worker_synthesis\`
Authority Document: `e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md`
Subagent 1 Findings: `e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\handoff.md`
Subagent 2 Findings: `e:\WORK\intel rag llamaindex\.agents\teamwork\explorer_codebase\handoff.md`

## Assignment
You are `worker_synthesis` (teamwork_worker). Your objective is to synthesize the Google Classroom reference architecture findings from Subagent 1 and the codebase/auth gap analysis from Subagent 2 into a comprehensive, production-ready architecture and detailed implementation plan artifact.

## Deliverable Target
Save the complete architecture and implementation plan artifact to:
`e:\WORK\intel rag llamaindex\docs\multi_tenant_rbac_architecture_plan.md`
(Also write your handoff summary to `e:\WORK\intel rag llamaindex\.agents\teamwork\worker_synthesis\handoff.md`).

## Strict Scope Constraint
Deliverable scope is STRICTLY the architecture and implementation plan artifact in `docs/multi_tenant_rbac_architecture_plan.md`. Do NOT modify existing application source code (`app/`, `storage/`, `ui-client/`).

## Mandatory Sections to Cover in the Artifact
1. **Executive Summary & System Vision**: Core goals, architectural philosophy, multi-tenancy model, mapping Google Classroom enterprise patterns to a lightweight FastAPI + SQLite + PyJWT + React stack.
2. **Current Codebase Gap Analysis & PyJWT Extension**:
   - Assessment of `app/auth/`, `storage/users.json`, `app/main.py`, `ui-client/`.
   - Token claim extension (`sub`, `role`, `institution_id`, `institution_name`, `class_id`, `section_id`, optional `grade`).
   - Hybrid JWT Claim + DB Session Resolution architecture (0ms latency for streaming tutor queries, live DB check for administrative operations).
   - Fix for `enforce_grade` bug when `user` is FastAPI `Depends` instance.
3. **Backend Storage Strategy: Flat JSON vs. SQLite / SQLAlchemy**:
   - In-depth technical trade-off evaluation (multi-worker concurrency, ACID, write amplification, relational queries).
   - Selection of SQLite + WAL mode (`PRAGMA journal_mode=WAL`) and SQLAlchemy ORM.
   - Complete declarative schemas and entity-relationship diagrams (ERD) for:
     * `institutions` (id, name, demo_verification_id, is_active, created_at, updated_at)
     * `classes` (id, institution_id, grade, display_name, created_at)
     * `sections` (id, class_id, section_name, room, class_advisor_id, created_at)
     * `users` (id, username, full_name, password_hash, password_salt, role, institution_id, grade, section_id, is_active, created_at, updated_at)
     * `lecturer_profiles` (id, user_id, subject_tags JSON array, created_at, updated_at)
     * `invite_links` (id, token_hash, institution_id, target_role, class_id, section_id, created_by_user_id, expires_at, max_uses, uses_count, is_active, created_at)
     * `enrollments` / roster mapping
   - Automated backward-compatible migration plan from `storage/users.json` to SQLite on server startup.
4. **Institution Lifecycle & Multi-Tier RBAC Architecture**:
   - **Admin Flow**:
     * Option to "Create an Institution" (requiring Institution Name and Demo Verification ID), OR "Join an Institution".
     * Class & Section creation (e.g., Class 10, Section A).
     * Generation of dedicated role-specific invite links: one dedicated link for Lecturers and one for Students.
   - **Lecturer Profile & Capabilities**:
     * Subject tags (e.g. Science, Mathematics, English).
     * "Class Advisor" designation (the lecturer assigned in charge of a specific class/section).
     * Multi-grade subject access for authorized subjects vs student strict grade isolation.
   - **Student Flow**:
     * Display "Join your Institution" action if not yet associated with an institution.
     * Display `<Institution Name>` in header/sidebar profile once joined.
     * Acceptance of student invite link -> auto-enrollment in institution, class, and section.
   - **Authorization & Permissions**:
     * Tiered RBAC matrix (Org Admin -> Lecturer -> Student -> Guardian).
     * Integration with existing PyJWT token flow, `enforce_grade`, and parental controls.
5. **Complete REST API Contracts**:
   - Full endpoint specifications (paths, HTTP methods, request headers, request bodies, response models, status codes, error codes):
     * Auth & Onboarding: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me`
     * Institution Lifecycle: `POST /api/institutions`, `POST /api/institutions/join`, `GET /api/institutions/current`
     * Class & Section Management: `GET /api/institutions/classes`, `POST /api/institutions/classes`, `POST /api/institutions/classes/{class_id}/sections`, `DELETE /api/institutions/sections/{section_id}`
     * Invite Link Mechanics: `POST /api/institutions/invites`, `GET /api/institutions/invites`, `POST /api/invites/validate`, `POST /api/invites/accept`, `DELETE /api/institutions/invites/{invite_id}`
     * Lecturer Profiles & Assignments: `GET /api/institutions/lecturers`, `PUT /api/institutions/lecturers/{lecturer_id}/profile`, `PUT /api/institutions/sections/{section_id}/advisor`
     * Student Enrollment & Roster: `GET /api/institutions/sections/{section_id}/roster`
6. **UI/UX Blueprint (`ui-client` React 18 + Vite)**:
   - Component hierarchy, state management, modal workflows.
   - Student Header / Topbar: `<Institution Name>` badge or "Join your Institution" button.
   - Student Sidebar Profile: Displaying student name, grade, section, and institution.
   - Admin Onboarding & Dashboard: Create vs Join Institution modal, Class/Section CRUD manager, Dedicated Invite Link generation modal with copyable links and QR preview.
   - Lecturer Profile Component: Subject tag selector pills, Class Advisor badge.
   - URL Invite Acceptance Workflow: Handling `?invite=TOKEN` on web client load.
   - Seamless integration with existing Gemini-styled frosted-glass theme.
7. **Phased Implementation Roadmap & Backward Compatibility**:
   - Phase 1: Database Layer & Migration (`app/db/`, models, engine, startup migration).
   - Phase 2: Auth & Token Enhancement (`app/auth/`, extended claims, optional grade, RBAC dependencies).
   - Phase 3: Institution & Academic Hierarchy Services (`app/institution/`).
   - Phase 4: Invite System & Enrollment Flow (`app/institution/invites.py`).
   - Phase 5: Lecturer Profile & Subject Tagging (`app/institution/lecturers.py`).
   - Phase 6: Core App & RAG Integration (`app/main.py`, `enforce_grade` fix, subject authorization).
   - Phase 7: Frontend UI/UX (`ui-client/src/components/institution/`, `App.jsx`, modals, header/sidebar).
   - Phase 8: Verification & Automated Test Suite.
   - File-by-file delta table (files to create, files to modify, changes required).
   - Detailed Backward Compatibility Guarantees: existing single-student accounts, existing parental PIN auth, existing grade enforcement, and offline development.

## Quality Standards
Ensure extreme thoroughness, production-grade precision, complete code blocks for schemas and contracts, and zero placeholders.


## 2026-11-02T09:09:08Z
[Message] sender=9277b568-318e-41a5-9aed-3aa9e78facfa priority=MESSAGE_PRIORITY_HIGH
Target Deliverable:
Save the comprehensive, production-ready architecture and detailed implementation plan artifact to:
e:\WORK\intel rag llamaindex\docs\multi_tenant_rbac_architecture_plan.md
(Also write your handoff summary to e:\WORK\intel rag llamaindex\.agents\teamwork\worker_synthesis\handoff.md).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Strict Constraint:
Deliverable scope is STRICTLY the architecture and implementation plan artifact in docs/multi_tenant_rbac_architecture_plan.md. Do NOT modify existing application source code (app/, storage/, ui-client/).

Mandatory Sections to cover in docs/multi_tenant_rbac_architecture_plan.md:
1. Executive Summary & Architecture Vision (Google Classroom patterns mapped to lightweight NCERT stack)
2. Codebase Gap Analysis & PyJWT Extension (Token claims: role, institution_id, class_id, section_id, optional grade; hybrid claims + DB session resolution; enforce_grade bugfix)
3. Backend Storage Strategy: JSON vs SQLite + SQLAlchemy (Concurrency trade-offs, WAL mode, complete declarative schemas & ERD for institutions, classes, sections, users, lecturer_profiles, invite_links, enrollments; startup migration from users.json)
4. Institution Lifecycle & Multi-Tier RBAC Architecture:
   - Admin Flow: Create Institution (with Name and Demo Verification ID) vs Join Institution, Class/Section creation (e.g. Class 10, Section A), dedicated Lecturer and Student invite links.
   - Lecturer Profile: Subject tags (e.g. Science, English), Class Advisor designation for section.
   - Student Flow: "Join your Institution" prompt if unjoined, <Institution Name> in header/sidebar if joined.
   - RBAC Matrix: Org Admin -> Lecturer -> Student -> Guardian, integrated with PyJWT and parental controls.
5. Complete REST API Specifications (Pydantic models, paths, methods, request/response bodies, status codes, error handling for auth, institution, class/section, invites, lecturers, rosters).
6. UI/UX Blueprint (React 18 + Vite components, state management, student header/sidebar badges, admin onboarding & management modals, lecturer tags, invite URL handling ?invite=...).
7. Phased Implementation Roadmap & Backward Compatibility (Phases 1-8, file-by-file delta table, migration strategy, backward compatibility guarantees).
