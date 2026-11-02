# Dispatch: Google Classroom Reference Architecture & Patterns Analysis

## Context
Working Directory: `e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\`
Authority Document: `e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md`

## Assignment
You are `spec_miner_classroom` (teamwork_spec_miner). Your objective is to thoroughly investigate and document Google Classroom core features, data models, and implementation patterns to serve as the foundational architectural reference for designing a lightweight, production-ready multi-tenant school organization and multi-tier RBAC system for the NCERT Textbook Assistant.

## Investigation Scope
1. **Organizations & Tenancy**:
   - Google Workspace / Domain tenancy model, Institution boundaries, Organizational Units (OUs).
   - Institution onboarding and verification mechanics (e.g. verification IDs, demo codes, domain verification).
2. **Courses, Classes & Sections**:
   - Course and Classroom entity structures, Class and Section divisions (e.g. Class 10, Section A).
   - Lifecycle states (Active, Archived, Provisioned).
   - Class metadata and hierarchy relationships.
3. **Invite Codes & Enrollment Links**:
   - Short alphanumeric join codes vs cryptographically signed invite URLs.
   - Role-specific invite links (dedicated Lecturer/Teacher link vs Student link).
   - Token parameters (expiration, usage limits, role binding, class/section binding, revokability).
   - Enrollment flow: anonymous click -> auth/account binding -> automatic role & section enrollment.
4. **Roster Management**:
   - Teachers, Co-teachers, Primary Teacher / Class Advisor designations.
   - Student rosters, enrollment records, parent/guardian links.
   - Role transitions, subject tagging (e.g. Science, Mathematics, English).
5. **Tiered RBAC & Permissions**:
   - Org Admin -> Teacher/Lecturer -> Student permission matrices.
   - Resource access boundaries (institution-level, class-level, section-level, personal).
   - Authorization middleware patterns.
6. **Architectural Translation for NCERT Assistant**:
   - Concrete recommendations on how to translate Google Classroom's heavy enterprise model into a clean, lightweight, stable model suitable for FastAPI + SQLite/JSON + PyJWT + React.

## Deliverable
Write your complete report to:
`e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\handoff.md`

## 2026-11-02T08:55:41Z
You are spec_miner_classroom (teamwork_spec_miner).
Your working directory is: e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\
Your dispatch task document is: e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\DISPATCH.md
The project authoritative request document is: e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md

Task: Analyze current Google Classroom core features, data models, and implementation patterns:
1. Organizations & Tenancy: Domain/Workspace tenancy, institution boundaries, organizational units (OUs), demo/verification ID mechanics.
2. Courses, Classrooms & Sections: Entity structure, Class & Section divisions (e.g. Class 10, Section A), lifecycle states (Active, Archived), metadata.
3. Invite Codes & Enrollment Links: Short join codes, enrollment invite URLs, role-specific invite tokens (dedicated Lecturer/Teacher link vs Student link), token validation, expiration, single/multi-use, enrollment flow.
4. Roster Management: Teachers, co-teachers, primary teacher / class advisor designation, student rosters, subject tags (e.g. Science, Mathematics, English).
5. Tiered RBAC: Org Admin -> Teacher/Lecturer -> Student permissions matrix, authorization boundaries.
6. Architectural Translation: Translating Google Classroom enterprise patterns into a lightweight, stable, production-ready design for NCERT Textbook Assistant (FastAPI, SQLite/SQLAlchemy, PyJWT, Vite+React).

Output: Write your complete, detailed analysis report to:
e:\WORK\intel rag llamaindex\.agents\teamwork\spec_miner_classroom\handoff.md
Update your progress.md periodically.
When finished, send a message to the orchestrator summarizing your findings and confirming that handoff.md is ready.
