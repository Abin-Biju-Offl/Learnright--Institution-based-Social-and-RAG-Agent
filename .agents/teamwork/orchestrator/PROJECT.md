# Project: Multi-Tenant School Organization & Tiered RBAC Architecture

## Architecture
Synthesize Google Classroom patterns and the NCERT Textbook Assistant codebase into a lightweight, stable, production-ready architecture and detailed implementation plan artifact for:
- **Multi-Tenant Institution Lifecycle**: Institution registration (with Name and Demo Verification ID), joining, and hierarchy.
- **Academic Structuring**: Class and Section hierarchy (e.g. Class 10, Section A).
- **Role-Specific Invite Mechanics**: Cryptographically secure, role-specific invite tokens/links for Lecturers vs Students with automated role and class assignment.
- **Lecturer Profiles**: Subject tags (e.g. Science, Mathematics, English) and Class Advisor assignments.
- **Student Enrollment & Identity**: Unjoined state onboarding ("Join your Institution") and joined state profile/header badge (`<Institution Name>`).
- **Tiered RBAC & Authorization Middleware**: Org Admin $\rightarrow$ Lecturer $\rightarrow$ Student hierarchy, integrated with existing PyJWT token claims, grade enforcement (`enforce_grade`), and parental controls.
- **Storage Strategy**: Trade-off evaluation between flat-file JSON and relational storage (SQLite + SQLAlchemy), defining formal schemas, indices, and relationships.
- **UI/UX Blueprint**: Component hierarchy and state management in `ui-client` (Vite + React).
- **Phased Implementation Roadmap**: File-level delta, migrations, and backward compatibility.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Google Classroom Pattern Analysis | Organizations, Courses/Classrooms, Invite Codes, Assignments/Coursework, Roster management, Tiered RBAC | M1 (Track A) | ORIGINAL_REQUEST §1 |
| 2 | Codebase & Auth Gap Analysis | Existing auth (`app/auth`), storage, `app/main.py`, `ui-client`, PyJWT claim structure, tenant context | M1 (Track B) | ORIGINAL_REQUEST §R1 |
| 3 | Backend Storage Architecture | SQLite/SQLAlchemy schema for Institutions, Classes, Sections, Users, Roles, Invites, Lecturer profiles | M2 | ORIGINAL_REQUEST §R3 |
| 4 | Admin Flow & Institution Lifecycle | Create Institution (with Name & Demo Verification ID), Join Institution, Class & Section CRUD | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Role-Specific Invite Links | Dedicated Lecturer and Student invite links, token validation, expiration, and enrollment handlers | M2 | ORIGINAL_REQUEST §R2 |
| 6 | Lecturer Profiles & Capabilities | Subject tags (e.g. Science, English) and Class Advisor assignments per section | M2 | ORIGINAL_REQUEST §R2 |
| 7 | Student Flow & Header Badging | Unjoined prompt ("Join your Institution") and joined header/sidebar display of `<Institution Name>` | M2 | ORIGINAL_REQUEST §R2 |
| 8 | Tiered RBAC & Authorization Matrix | Complete permission matrix across Org Admin, Lecturer, Student with PyJWT and parental control integration | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Complete REST API Specifications | Paths, HTTP methods, Pydantic schemas, status codes, error handling for all institution/class/invite routes | M2 | ORIGINAL_REQUEST §R3 |
| 10 | UI/UX Blueprint & State Design | React components, routing, modal states, header badges, admin dashboard, invite acceptance workflows | M2 | ORIGINAL_REQUEST §R3 |
| 11 | Phased Implementation Roadmap | Step-by-step file-level changes, migrations, backward compatibility guarantees for existing users | M2 | ORIGINAL_REQUEST §R3 |
| 12 | Architecture Plan Artifact Review | Independent review verifying complete coverage of all acceptance criteria | M3 | ORIGINAL_REQUEST Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status | Key Outputs |
|---|------|-------|-------------|--------|-------------|
| M1-A | Google Classroom Patterns Investigation | Subagent 1 (`spec_miner_classroom`): Analyze Google Classroom patterns, data entities, invite tokens, rosters, and RBAC | none | DONE | `spec_miner_classroom/handoff.md` (435 lines) |
| M1-B | Codebase & Auth Gap Analysis | Subagent 2 (`explorer_codebase`): Inspect `app/auth/`, `storage/`, `app/main.py`, `ui-client/` and document integration points | none | DONE | `explorer_codebase/handoff.md` (623 lines) |
| M2 | Architecture & Implementation Plan Synthesis | Subagent 3 (`worker_synthesis`): Author production-ready architecture and implementation plan artifact in `docs/multi_tenant_rbac_architecture_plan.md` | M1-A, M1-B | DONE | `docs/multi_tenant_rbac_architecture_plan.md` (1,627 lines, 91.5 KB) |
| M3 | Plan Review & Verification | Subagent 4 (`reviewer_plan`): Review artifact against all acceptance criteria and provide verification verdict | M2 | DONE | `reviewer_plan/handoff.md` (APPROVE verdict, 9/9 criteria met) |
| M4 | Final Reporting | Top-level Orchestrator synthesizes findings and reports to Parent Sentinel | M3 | DONE | Final handoff report to caller |

## Interface Contracts & Deliverables
### Target Deliverable
- File: `e:\WORK\intel rag llamaindex\docs\multi_tenant_rbac_architecture_plan.md`
- Status: APPROVED
- Scope: Purely architecture, data models, API contracts, UI blueprint, and phased implementation plan. Zero source code modifications made.
