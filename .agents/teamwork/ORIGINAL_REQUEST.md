# Original User Request

## Initial Request — 2026-10-31T11:54:33Z

Implement production-grade under-18 safety, content filtering against adult and inappropriate content, parental controls, and security safeguards for the NCERT Textbook Assistant. As requested: "think deeply list all the inappropriate question by one agent another agent should think about all parential features and one agent should think about security etc".

Integrity mode: development

## Requirements

### R1. Inappropriate Content Taxonomy & Filtering
The system must prevent the NCERT Textbook Assistant from answering or generating adult, sexual, violent, self-harm, hate speech, illegal acts, cyberbullying, or otherwise inappropriate content for users under 18. Queries falling under these categories must be refused with clear, age-appropriate explanations. External moderation APIs are permitted if needed.

### R2. Parental Controls and Features
Provide parental controls in the system, including a frontend UI in `ui-client/` protected by a parental PIN/credentials. Parents must be able to view student chat history, review flagged or blocked queries, and configure content filtering toggles/categories. Provide backend logging and endpoints to support parental monitoring and configuration persistence.

### R3. Security Safeguards
Protect the assistant against jailbreak attempts, prompt injection, system prompt exfiltration, and adversarial evasion attacks intended to bypass under-18 safety constraints. Safety rules must remain robust against adversarial framing, persona adoption, and role-playing bypasses.

### R4. Automated Verification Test Suite
Provide an automated test suite verifying content moderation refusal across inappropriate query categories, parental control operations (PIN protection, chat history access, and settings updates), and resilience against jailbreaks and prompt injections.

## Acceptance Criteria

### Content Moderation & Taxonomy
- [ ] Automated tests verify that inappropriate queries across taxonomy categories (adult/sexual content, violence, self-harm, hate speech, illegal acts, cyberbullying) are refused with age-appropriate responses and do not produce inappropriate content.
- [ ] Legitimate educational queries based on NCERT curriculum (such as Class 10 biology/science topics) are handled appropriately without being improperly blocked.

### Parental Controls & UI
- [ ] The parental controls UI is accessible and protected by a parental PIN or credentials.
- [ ] Student chat history and flagged/refused queries are logged and viewable in the parental interface.
- [ ] Category filtering preferences can be configured and persisted through the parental interface.

### Security Safeguards
- [ ] Automated tests verify that prompt injection attacks and jailbreak templates (e.g. "ignore previous instructions", persona-switching, prompt leakage attempts) fail to bypass under-18 restrictions or leak system prompts.

### Test Automation
- [ ] Running the automated test suite programmatically executes and passes all safety, parental API, and security test cases.


## Task Request — 2026-11-02T08:50:57Z

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
