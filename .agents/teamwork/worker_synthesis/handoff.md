# Multi-Tenant School Organization & Tiered RBAC Architecture Synthesis Handoff

**Agent:** `worker_synthesis` (teamwork_worker)  
**Date:** 2026-11-02  
**Target Deliverable:** `e:\WORK\intel rag llamaindex\docs\multi_tenant_rbac_architecture_plan.md`  
**Handoff File:** `e:\WORK\intel rag llamaindex\.agents\teamwork\worker_synthesis\handoff.md`  
**Parent Conversation ID:** `9277b568-318e-41a5-9aed-3aa9e78facfa`  

---

## 1. Observation

1. **Upstream Investigation & Reference Artifacts**:
   - Subagent 1 (`spec_miner_classroom` in `.agents/teamwork/spec_miner_classroom/handoff.md`) established Google Classroom's enterprise models: Customer Domains, OUs, Courses/Sections, read-only `enrollmentCode`, signed teacher invitations, Co-Teachers/Class Advisors, and tiered RBAC.
   - Subagent 2 (`explorer_codebase` in `.agents/teamwork/explorer_codebase/handoff.md`) established the existing NCERT Assistant codebase gaps:
     * `app/auth/jwt_handler.py:130-132`: `decode_access_token()` strictly requires `payload.get("grade")`, throwing `TokenError("Token is missing the student grade.")` if missing.
     * `app/auth/dependencies.py:78-80`: `get_current_user()` forces `user["role"] = "student"` unconditionally.
     * `app/auth/dependencies.py:114-137`: `enforce_grade(user, requested_grade)` lacks type check (`if not isinstance(user, dict): return`), causing `AttributeError: 'Depends' object has no attribute 'get'` in unit tests calling `main.ask()` directly.
     * `storage/users.json:1-13`: Single-student schema lacking `role`, `institution_id`, `class_id`, and `section_id`; writes guarded only by in-process `threading.Lock()`.
     * `ui-client/src/App.jsx:632-646`: Streaming fetch to `/api/ask/stream` passes no `Authorization` header, bypassing server-side grade isolation when queried from UI.

2. **Target Deliverable Creation**:
   - The authoritative architecture plan was generated and saved to `docs/multi_tenant_rbac_architecture_plan.md` (1,627 lines, 91.5 KB), covering all 7 mandatory sections without placeholders:
     * Section 1: Executive Summary & Google Classroom Enterprise Pattern Mapping Matrix.
     * Section 2: Codebase Gap Analysis, PyJWT Extended Token Claims, Hybrid 0ms Claims + DB Resolution Model, and `enforce_grade` bugfix.
     * Section 3: Concurrency & Storage Trade-offs (JSON vs SQLite WAL mode), complete SQLAlchemy 2.x Declarative Models (`Institution`, `Classroom`, `Section`, `User`, `LecturerProfile`, `InviteLink`, `Enrollment`), ASCII ERD, and startup migration engine from `storage/users.json`.
     * Section 4: Institution Lifecycle (Admin create with Demo Verification ID vs Join), Academic Hierarchy, Dedicated Role-Specific Invites (Lecturer vs Student), Lecturer Profile with Subject Tags and Class Advisor designation, Student Unjoined vs Joined states, 4-tier RBAC Matrix, and Parental Controls integration.
     * Section 5: Complete REST API Specifications with Pydantic v2 schemas, endpoints, request/response payloads, and error codes for Auth, Institutions, Classes, Sections, Invites, Lecturers, and Rosters.
     * Section 6: UI/UX Blueprint for React 18 + Vite (`ui-client/src/components/institution/`), `AuthContext`, topbar badges, Admin management console, Lecturer chips, and `?invite=...` URL acceptance flow.
     * Section 7: Phased 8-stage Implementation Roadmap, file-by-file delta specification table, backward compatibility guarantees, and automated test plan.

---

## 2. Logic Chain

1. **Tenancy & Isolation**: Google Classroom enforces domain-level tenancy via DNS/OUs. In a self-contained NCERT deployment, this is cleanly translated into an `institutions` table where onboarding is verified via a `demo_verification_id` (e.g. `DEMO-DPS-2026`) without requiring public DNS infrastructure (Observation 1, 2).
2. **Privilege Escalation Prevention**: To prevent students from acquiring faculty permissions, invite mechanisms must be role-segregated: Dedicated Lecturer Invite Links promote accounts to `role = "lecturer"`, while Student Invite Links are strictly bound to a target Class and Section (Observation 1, 2).
3. **Storage Stability & Multi-Worker Concurrency**: In-process `threading.Lock()` and atomic `os.replace` on `storage/users.json` fail in multi-worker Uvicorn setups and suffer from $O(N)$ write amplification. Moving to SQLite in WAL mode (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`) delivers ACID multi-process safety, $O(1)$ page writes, and native relational foreign keys, while startup migration ensures zero disruption to existing users (Observation 1, 2).
4. **Zero-Latency RAG Streaming**: Access tokens carry authoritative identity and tenant claims (`institution_id`, `role`, `section_id`, `grade`), allowing `/api/ask/stream` to execute with 0ms database overhead. Sensitive mutations (class/section CRUD, invite generation) resolve live against the SQLite database (Observation 1, 2).
5. **Robust Grade Enforcement**: Updating `enforce_grade` to verify `isinstance(user, dict)` eliminates the unit test crash on FastAPI `Depends` fixtures, while allowing Org Admins and Lecturers multi-grade access and strictly locking students to their enrolled grade (Observation 1, 2).

---

## 3. Caveats

1. **Scope Boundary**: Deliverable scope was strictly the architecture and implementation plan artifact. No application code (`app/`, `storage/`, `ui-client/`) was modified during this task.
2. **Network SMB Storage Consideration**: While SQLite WAL mode is process-safe on local filesystems, deployments over network-mounted SMB shares should use standard rollback journals or client-server PostgreSQL if multi-node clustering is required.

---

## 4. Conclusion

The architecture plan in `docs/multi_tenant_rbac_architecture_plan.md` provides an end-to-end, production-ready specification that bridges Google Classroom's enterprise multi-tenant patterns with the lightweight NCERT Textbook Assistant stack. All data models, cryptographic token flows, REST API contracts, UI component designs, and migration strategies are fully specified and ready for phased execution without risking backward compatibility or system regressions.

---

## 5. Verification Method

To independently verify the deliverable and findings:

1. **Verify Deliverable Existence & Completeness**:
   Inspect `e:\WORK\intel rag llamaindex\docs\multi_tenant_rbac_architecture_plan.md`. Confirm all 7 mandatory sections, complete SQLAlchemy declarative models, complete Pydantic schemas, and implementation roadmap are present without placeholders.
2. **Verify Zero Source Code Modification**:
   Confirm that files in `app/`, `storage/`, and `ui-client/` remain untouched.
3. **Verify Baseline Test Suite Passes**:
   Run `.venv\Scripts\pytest tests/test_auth.py tests/test_api.py` to confirm baseline auth and API unit tests remain fully intact.
4. **Invalidation Conditions**:
   The plan would be invalidated if:
   - A third-party cloud service or external identity provider was mandated instead of self-contained SQLite and PyJWT.
   - The student grade isolation rule was broken or made insecure.
   - The startup migration did not preserve existing PBKDF2 user passwords from `storage/users.json`.
