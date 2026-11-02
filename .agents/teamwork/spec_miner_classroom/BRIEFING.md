# BRIEFING — 2026-11-02T08:56:00Z

## Mission
Analyze current Google Classroom core features, data models, and implementation patterns, and provide an architectural translation for the NCERT Textbook Assistant multi-tenant school organization and multi-tier RBAC system.

## 🔒 My Identity
- Archetype: teamwork_spec_miner (SPECIFICATION MINER)
- Roles: Specification Mining, Enterprise Architecture Analysis, Domain Modeling
- Working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\
- Original parent: 9277b568-318e-41a5-9aed-3aa9e78facfa
- Milestone: Phase 1 Specification Mining & Pattern Analysis

## 🔒 Key Constraints
- Read-only on application codebase; do NOT implement anything or modify app source code.
- Write only inside working directory `e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\`.
- Thoroughly investigate and document Google Classroom core features, data models, API schemas, and implementation patterns.
- Produce authoritative 5-component handoff report (`handoff.md`).
- Notify orchestrator via `send_message` with summary and path.

## Current Parent
- Conversation ID: 9277b568-318e-41a5-9aed-3aa9e78facfa
- Updated: 2026-11-02T08:56:00Z

## Task Summary
- **What to analyze**: Google Classroom core features (Tenancy/OUs, Courses/Sections, Invites/Tokens, Rosters, RBAC) and translate to NCERT Textbook Assistant (FastAPI, SQLite, PyJWT, Vite+React).
- **Success criteria**: Detailed, exhaustive analysis covering all 6 focus areas with explicit schema definitions, data flow diagrams, edge cases, permission matrices, and lightweight translation recommendations.
- **Interface contracts**: e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md
- **Code layout**: N/A (analysis only, deliverables in `.agents/teamwork/spec_miner_classroom/`)

## Key Decisions Made
- Analyzed Google Classroom API v1 resources: `courses`, `invitations`, `courseState`, `enrollmentCode`, and Google Workspace OUs.
- Formulated translation to NCERT Assistant: SQLite / SQLAlchemy schema (`institutions`, `classes`, `sections`, `invitations`, `lecturer_profiles`, `users`, `enrollments`).
- Mapped role-specific invite link mechanics: separate Lecturer signed token vs Student join code/link to prevent privilege escalation.
- Designed 100% backward-compatible PyJWT token extension (`role`, `institution_id`, `section_id`, `subject_tags`) preserving existing `enforce_grade` for students.

## Artifact Index
- `DISPATCH.md` — Task definition and incoming dispatch prompts
- `BRIEFING.md` — Persistent situational memory
- `progress.md` — Liveness heartbeat and milestone tracking
- `handoff.md` — Complete specification mining deliverable report (22 features, 12 edge cases, full 5-component report)

## Loaded Skills
- None specified by dispatch.
