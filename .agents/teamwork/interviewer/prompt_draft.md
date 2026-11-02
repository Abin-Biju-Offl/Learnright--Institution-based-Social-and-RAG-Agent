Teamwork task:
1. One subagent to analyse current Google Classroom core features and implementation patterns (Organizations, Courses/Classrooms, Invite Codes, Assignments/Coursework, Roster management, and Tiered RBAC: Org Admin -> Teacher -> Student).
2. Second subagent to analyse what is already available in our current codebase (app/auth, storage, app/main.py, ui-client) and identify gaps.
3. Final agent to synthesize output from both subagents and formulate a lightweight, stable, production-ready architecture and detailed implementation plan artifact for this multi-tenant school organization and multi-tier RBAC system.

Synthesize Google Classroom patterns and the NCERT Textbook Assistant codebase into a lightweight, stable, production-ready architecture and detailed implementation plan artifact for institution lifecycle, class/section structuring, role-specific invite links (Lecturers and Students), lecturer profiles with subject tags and class advisor roles, and student enrollment integrated with existing PyJWT auth.

Working directory: E:\WORK\intel rag llamaindex
Integrity mode: development

## Requirements

### R1. Current Codebase & Auth Gap Analysis
Analyze the existing NCERT Textbook Assistant codebase (`app/auth`, `storage/users.json`, `storage/parental_config.json`, `app/main.py`, and `ui-client`) to evaluate how to extend the existing PyJWT authentication system to support:
- Initial user authorization as Student or Admin, with Lecturer as an invited role.
- Tenant/institution context attachment in JWT claims or session resolution.
- UI integration points in `ui-client` (Vite + React) for student headers/sidebars, institution onboarding, and admin management.

### R2. Institution Lifecycle & Multi-Tier RBAC Architecture
Design the data models, storage strategy, and authorization middleware for the target flows:
- Admin Flow:
  - Option to "Create an Institution" requiring Institution Name and Demo Verification ID (verification/registration code), OR "Join an Institution".
  - Class and Section creation (e.g., Class 10, Section A) under an institution.
  - Generation of role-specific invite links: one dedicated link for Lecturers and one for Students.
- Lecturer Profile & Capabilities:
  - Subject tags for subjects taught (e.g., Science, English).
  - "Class Advisor" designation (the lecturer assigned in charge of a specific class/section).
- Student Flow:
  - Display "Join your Institution" action if not yet associated with an institution.
  - Display the `<Institution Name>` in header/sidebar profile once joined.
- Authorization & Permissions:
  - Tiered RBAC enforcing operations across Org Admin, Lecturer, and Student roles, integrated with existing grade claims (`enforce_grade`) and parental controls.

### R3. Production-Ready Architecture & Implementation Plan Artifact
Synthesize findings into a comprehensive architecture and implementation plan markdown artifact covering:
- Storage Strategy: Evaluate trade-offs between flat-file JSON and lightweight relational storage (e.g., SQLite / SQLAlchemy), selecting and defining the optimal production-ready schema for institutions, classes, sections, users, roles, invites, and lecturer profiles.
- API Contracts: Full endpoint specifications (HTTP methods, path routes, request/response models, error handling) for institution creation/joining, class/section management, invite generation/acceptance, and lecturer profile tagging.
- UI/UX Blueprint: Component and state design for `ui-client` handling Admin dashboards, invite workflows, Lecturer tags, and Student header displays.
- Phased Implementation Roadmap: Concrete step-by-step phases, file-level modifications/creations across `app/` and `ui-client/`, backward compatibility guarantees for existing users, and migration steps. Deliverable scope is strictly the architecture and implementation plan artifact; no codebase modifications are to be made in this task.

## Acceptance Criteria

### Core Workflow & RBAC Specification
- [ ] The architecture details the complete Admin flow: Create Institution (with Name and Demo Verification ID), Join Institution, and creation of Classes and Sections (e.g., Class 10, Section A).
- [ ] The plan specifies role-specific invite link mechanics for Lecturers and Students, including link generation, token validation, and role assignment.
- [ ] Lecturer profiles explicitly model subject tags (e.g., Science, English) and Class Advisor assignments for classes/sections.
- [ ] The Student flow is documented for both unjoined state ("Join your Institution" prompt) and joined state (displaying Institution Name in header/sidebar).
- [ ] An authorization matrix maps Org Admin, Lecturer, and Student permissions against all institution, class/section, and tutor resources, integrated with the existing PyJWT token flow.

### Architecture Artifact & Implementation Roadmap
- [ ] The plan evaluates and selects the backend storage approach (SQLite vs. JSON files) with explicit entity schemas and relationship diagrams for Institutions, Classes, Sections, Users, Roles, Invites, and Lecturer metadata.
- [ ] Complete API contracts (paths, HTTP methods, payload schemas, response codes) are documented for all Admin, Lecturer, and Student endpoints.
- [ ] A phased, file-by-file implementation plan details changes across `app/`, `storage/`, and `ui-client/` with backward compatibility for existing grade-based tutor queries and parental controls.
- [ ] The deliverable is provided as a standalone architecture and implementation plan markdown artifact without unrequested code edits made to the codebase.
