# Multi-Tenant School Organization & Tiered RBAC Architecture Plan
## NCERT Textbook Assistant Enterprise Specification & Implementation Blueprint

**Document Version:** 1.0.0  
**Status:** Approved for Implementation  
**Target System:** NCERT Textbook Assistant (`FastAPI`, `SQLite/SQLAlchemy`, `PyJWT`, `React 18 + Vite`)  
**Authority Reference:** `ORIGINAL_REQUEST.md`  
**Authors:** Architecture & Synthesis Core Team (`worker_synthesis`, `spec_miner_classroom`, `explorer_codebase`)  
**Date:** 2026-11-02  

---

## Table of Contents

1. [Executive Summary & Architecture Vision](#1-executive-summary--architecture-vision)
   - 1.1 [System Vision & Objectives](#11-system-vision--objectives)
   - 1.2 [Architectural Philosophy](#12-architectural-philosophy)
   - 1.3 [Google Classroom Enterprise Pattern Mapping Matrix](#13-google-classroom-enterprise-pattern-mapping-matrix)
   - 1.4 [System Architecture Overview](#14-system-architecture-overview)
2. [Codebase Gap Analysis & PyJWT Extension](#2-codebase-gap-analysis--pyjwt-extension)
   - 2.1 [Audit of Existing Authentication Subsystem](#21-audit-of-existing-authentication-subsystem)
   - 2.2 [PyJWT Extended Token Claims Schema](#22-pyjwt-extended-token-claims-schema)
   - 2.3 [Hybrid Claims + DB Session Resolution Model](#23-hybrid-claims--db-session-resolution-model)
   - 2.4 [FastAPI Parameter Bugfix for `enforce_grade`](#24-fastapi-parameter-bugfix-for-enforce_grade)
   - 2.5 [Role-Based Grade Enforcement Matrix](#25-role-based-grade-enforcement-matrix)
3. [Backend Storage Strategy: Flat JSON vs. SQLite + SQLAlchemy](#3-backend-storage-strategy-flat-json-vs-sqlite--sqlalchemy)
   - 3.1 [In-Depth Technical Trade-Off Evaluation](#31-in-depth-technical-trade-off-evaluation)
   - 3.2 [SQLite Engine & WAL Mode Configuration](#32-sqlite-engine--wal-mode-configuration)
   - 3.3 [Complete SQLAlchemy Declarative Models](#33-complete-sqlalchemy-declarative-models)
   - 3.4 [Entity-Relationship Diagram (ERD)](#34-entity-relationship-diagram-erd)
   - 3.5 [Automated Startup Migration from `storage/users.json`](#35-automated-startup-migration-from-storageusersjson)
4. [Institution Lifecycle & Multi-Tier RBAC Architecture](#4-institution-lifecycle--multi-tier-rbac-architecture)
   - 4.1 [Institution Onboarding & Admin Lifecycle](#41-institution-onboarding--admin-lifecycle)
   - 4.2 [Academic Hierarchy: Classes & Sections](#42-academic-hierarchy-classes--sections)
   - 4.3 [Role-Specific Invite Link Mechanics](#43-role-specific-invite-link-mechanics)
   - 4.4 [Lecturer Profile, Subject Tags & Class Advisor Designation](#44-lecturer-profile-subject-tags--class-advisor-designation)
   - 4.5 [Student Lifecycle: Unjoined vs. Joined States](#45-student-lifecycle-unjoined-vs-joined-states)
   - 4.6 [Complete 4-Tier RBAC Authorization Matrix](#46-complete-4-tier-rbac-authorization-matrix)
   - 4.7 [Integration with Parental Controls & Audit Logging](#47-integration-with-parental-controls--audit-logging)
5. [Complete REST API Specifications](#5-complete-rest-api-specifications)
   - 5.1 [Core Pydantic Data Contracts](#51-core-pydantic-data-contracts)
   - 5.2 [Authentication & Identity Endpoints](#52-authentication--identity-endpoints)
   - 5.3 [Institution Lifecycle Endpoints](#53-institution-lifecycle-endpoints)
   - 5.4 [Class & Section Management Endpoints](#54-class--section-management-endpoints)
   - 5.5 [Role-Specific Invite Mechanics Endpoints](#55-role-specific-invite-mechanics-endpoints)
   - 5.6 [Lecturer Profile & Advisor Assignment Endpoints](#56-lecturer-profile--advisor-assignment-endpoints)
   - 5.7 [Section Roster & Multi-Tenant Audit Endpoints](#57-section-roster--multi-tenant-audit-endpoints)
6. [UI/UX Blueprint (React 18 + Vite)](#6-uiux-blueprint-react-18--vite)
   - 6.1 [Component Architecture & Hierarchy](#61-component-architecture--hierarchy)
   - 6.2 [Global Authentication & Institution Context](#62-global-authentication--institution-context)
   - 6.3 [Student Topbar & Sidebar Profile States](#63-student-topbar--sidebar-profile-states)
   - 6.4 [Admin Onboarding & Management Console](#64-admin-onboarding--management-console)
   - 6.5 [Lecturer Subject Tagging & Advisor Badge](#65-lecturer-subject-tagging--advisor-badge)
   - 6.6 [Invite URL Detection & Acceptance Flow (`?invite=...`)](#66-invite-url-detection--acceptance-flow-invite)
   - 6.7 [Visual Styling & Glassmorphic Component Spec](#67-visual-styling--glassmorphic-component-spec)
7. [Phased Implementation Roadmap & Backward Compatibility](#7-phased-implementation-roadmap--backward-compatibility)
   - 7.1 [Implementation Phases (1 through 8)](#71-implementation-phases-1-through-8)
   - 7.2 [File-by-File Delta Specification Table](#72-file-by-file-delta-specification-table)
   - 7.3 [Backward Compatibility Guarantees](#73-backward-compatibility-guarantees)
   - 7.4 [Comprehensive Automated Test Plan](#74-comprehensive-automated-test-plan)

---

## 1. Executive Summary & Architecture Vision

### 1.1 System Vision & Objectives

The NCERT Textbook Assistant originated as a specialized, single-tenant AI study companion, assisting individual K-12 students with textbook-grounded Q&A across NCERT Class 10 and Class 5 curricula. It features streaming generation, guardrails against inappropriate under-18 content, and parental PIN-protected controls.

This architecture plan elevates the NCERT Textbook Assistant to an enterprise-grade, multi-tenant educational platform modeled after **Google Classroom** and **Google Workspace for Education**. The system introduces structured institutional boundaries, hierarchical academic structuring (Classes and Sections), dedicated role-specific invitation links for Lecturers and Students, specialized Lecturer capabilities (Subject Tags and Class Advisor designations), and a tiered Role-Based Access Control (**Org Admin** $\rightarrow$ **Lecturer** $\rightarrow$ **Student** $\rightarrow$ **Guardian**) model.

Crucially, this transformation maintains 100% backward compatibility: existing independent self-study students, parental controls, and offline development capabilities remain fully operational without service disruption.

### 1.2 Architectural Philosophy

1. **Lightweight & Self-Contained:** Avoid heavy distributed dependencies (e.g. Kubernetes, Apache Kafka, external identity providers, or enterprise LDAP servers). The system must run flawlessly in a local Python virtual environment, lightweight container, or single-node edge server.
2. **ACID Relational Integrity with Zero Overhead:** Transition from concurrent flat-file JSON mutations to **SQLite** operating in Write-Ahead Logging (**WAL**) mode with **SQLAlchemy 2.x ORM**. This provides thread- and multi-worker safety, fast indexed queries, foreign-key constraints, and eliminates disk write amplification.
3. **Stateless High-Throughput / Stateful Sensitive Mutation Hybrid:** High-frequency, low-latency streaming endpoints (`/api/ask/stream`) execute with zero database query latency by relying on cryptographically verified PyJWT claims. Administrative mutations (class creation, invite generation, role promotion) perform live database session validation.
4. **Non-Breaking Backward Compatibility:** Existing single-student accounts stored in `storage/users.json` are migrated seamlessly into SQLite on server startup, preserving existing PBKDF2 password hashes, student grades, and chat records.

---

### 1.3 Google Classroom Enterprise Pattern Mapping Matrix

Google Classroom and Google Workspace for Education represent the industry standard for cloud-native academic coordination. The table below demonstrates how Google Classroom's enterprise abstractions are mapped directly into the NCERT Textbook Assistant stack:

| Google Classroom Enterprise Architecture | NCERT Textbook Assistant Lightweight Stack | Architectural Translation & Design Rationale |
| :--- | :--- | :--- |
| **Google Workspace Customer Domain** (`customerId`, DNS domain isolation) | **`institutions` Table** (`id`, `name`, `demo_verification_id`, `is_active`) | Isolates academic institutions into distinct tenants. Onboarding is validated via a lightweight Demo Verification ID rather than public DNS TXT verification. |
| **Organizational Units (OUs)** (`/Staff/Teachers`, `/Students/Grade10`) | **User Role Enums & Claims** (`org_admin`, `lecturer`, `student`, `guardian`) | Users inherit explicit capabilities based on role hierarchy. Org Admins govern the institution, Lecturers oversee subjects and sections, and Students are locked to their enrolled curriculum. |
| **Course Resource Model** (`/v1/courses`, `name`, `section`, `room`) | **`classes` & `sections` Relational Tables** | Normalizes courses into a two-level Indian school academic model: `Classroom` (Grade 1 to 12) $\rightarrow$ `Section` (Section A, B, C...). |
| **Student Join Code** (`enrollmentCode`, `cjc` URL parameter) | **Student Alphanumeric Invite Link** (`/join?invite=stu_...`) | Reusable, time-bounded, and max-usage capped token that automatically enrolls an authenticated student into an explicit Class and Section. |
| **Teacher Dedicated Invitations** (`/v1/invitations`, `role=TEACHER`) | **Cryptographically Signed Lecturer Invite Link** (`/join?invite=lec_...`) | Dedicated invitation token that promotes the recipient to the `lecturer` role upon redemption. Public self-registration as a Lecturer is strictly prohibited. |
| **Primary Teacher (`ownerId`)** | **Section "Class Advisor" Assignment** | Designates exactly one lead faculty member (Class Teacher / Homeroom Advisor) per section, granting pastoral and roster oversight. |
| **Co-Teachers & Subject Specialists** (`courses.teachers`) | **`lecturer_profiles` & Subject Tags** (`subject_tags: ["Science", "Math"]`) | Permits faculty to instruct multiple subjects across multiple classes without granting course destruction rights. |
| **Course Roster** (`courses.students`) | **`enrollments` Junction Table** (`user_id`, `section_id`, `enrolled_at`) | Many-to-many relationship tracking active student cohort memberships and admission timestamps. |
| **Guardian Summaries** (`courses.guardians`) | **Parental Controls & PIN Portal** (`app/parental/`, `storage/parental_config.json`) | Retains PIN-protected parental oversight while augmenting safety event logs with student, class, and institution IDs. |
| **Grade Level Boundary** | **FastAPI Middleware `enforce_grade`** | Restricts students strictly to their enrolled grade textbooks, while allowing Org Admins and Lecturers multi-grade pedagogical access. |

---

### 1.4 System Architecture Overview

```
                                      ┌─────────────────────────────────────────────────────────┐
                                      │              React 18 + Vite Web Client                 │
                                      │  - Student Topbar Badge ("Join" vs. "Delhi Public")     │
                                      │  - Admin Onboarding & Class/Section Hierarchy Console   │
                                      │  - Lecturer Subject Tagging & Advisor Badge             │
                                      │  - URL Invite Detection (?invite=...)                   │
                                      └────────────────────────────┬────────────────────────────┘
                                                                   │ HTTP / Streaming SSE
                                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                   FastAPI Application                                                  │
│                                                                                                                        │
│  ┌──────────────────────────┐  ┌───────────────────────────────┐  ┌─────────────────────────────────────────────────┐  │
│  │   Auth & JWT Subsystem   │  │  Institution & Academic Core  │  │             RBAC & Grade Enforcement            │  │
│  │ - Login / Refresh        │  │ - Institution Lifecycle       │  │ - require_role("org_admin", "lecturer")         │  │
│  │ - Extended Token Claims  │  │ - Class & Section CRUD        │  │ - enforce_grade (role bypass vs student lock)   │  │
│  │ - PBKDF2 Password Hash   │  │ - Role-Specific Invites       │  │ - FastAPI Depends parameter bugfix              │  │
│  └─────────────┬────────────┘  └───────────────┬───────────────┘  └────────────────────────┬────────────────────────┘  │
└────────────────┼───────────────────────────────┼───────────────────────────────────────────┼───────────────────────────┘
                 │                               │                                           │
                 ▼                               ▼                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                              Storage & Persistence Layer                                               │
│                                                                                                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       ┌──────────────────────────────────────┐   │
│   │               SQLite Database (WAL Mode Enabled)                │       │     Parental Controls & Flat Logs    │   │
│   │ - institutions      - classes         - sections                │       │ - storage/parental_config.json       │   │
│   │ - users             - invite_links    - lecturer_profiles       │       │ - storage/safety_events.jsonl        │   │
│   │ - enrollments       - SQLAlchemy 2.x Declarative Base           │       │ - storage/student_chat_history.jsonl │   │
│   └─────────────────────────────────────────────────────────────────┘       └──────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Codebase Gap Analysis & PyJWT Extension

### 2.1 Audit of Existing Authentication Subsystem

A forensic audit of the existing codebase revealed several architectural bottlenecks that prevent multi-tenant school onboarding without strategic refactoring:

1. **Mandatory Student Grade Claim in Token Decoding (`app/auth/jwt_handler.py:126-133`):**
   ```python
   # Existing code in app/auth/jwt_handler.py
   if not payload.get("grade"):
       raise TokenError("Token is missing the student grade.")
   ```
   *Impact:* Any non-grade entity (e.g. an Org Admin or a Lecturer teaching multiple grades) cannot authenticate, because their tokens have `grade = None`, immediately triggering a 401 `TokenError`.

2. **Hardcoded Student Role Injection (`app/auth/dependencies.py:78-80`):**
   ```python
   # Existing code in app/auth/dependencies.py
   user["grade"] = payload.get("grade")
   user["role"] = "student"
   user["is_parent"] = False
   ```
   *Impact:* Regardless of user credentials, every authenticated user is forced into the `"student"` role, making administrative access impossible.

3. **Single-Role Student Registration (`app/auth/schemas.py:12-17` & `app/auth/routes.py:38-51`):**
   `RegisterRequest` mandates `grade: int = Field(ge=1, le=12)`. There is no mechanism for an Org Admin to register, nor any mechanism to accept an invite token as a Lecturer.

4. **FastAPI Parameter Bug in `enforce_grade` (`app/auth/dependencies.py:114-137`):**
   In `app/main.py:199`, routes declare `user: dict | None = Depends(get_optional_user)`. When `main.ask()` or `main.ask_stream()` is called directly in Python tests (such as `tests/test_parental.py`), the default argument passed for `user` is the `fastapi.params.Depends` object rather than `None`. Calling `user.get("is_parent")` triggers:
   `AttributeError: 'Depends' object has no attribute 'get'`.
   An explicit type check (`if user is None or not isinstance(user, dict): return`) is mandatory.

5. **Missing Authorization Header in Frontend Query Stream (`ui-client/src/App.jsx:632-646`):**
   The chat streaming fetch call `/api/ask/stream` only provides `Content-Type: application/json` and omits `Authorization: Bearer <token>`. The backend receives `user = None`, inadvertently allowing anonymous access to bypass server-side grade restriction.

---

### 2.2 PyJWT Extended Token Claims Schema

To support multi-tenancy, institutional scoping, and tiered roles without breaking existing clients, the access token payload is extended with structured optional claims:

#### Extended Token Claim Definition

```json
{
  "sub": "usr_c83d19a2e5",
  "username": "dr_anita_sharma",
  "role": "lecturer",
  "institution_id": "inst_dps_rkpuram_01",
  "institution_name": "Delhi Public School, R.K. Puram",
  "class_id": "cls_grade10_dps",
  "section_id": "sec_10a_dps",
  "grade": 10,
  "subject_tags": ["Science", "Physics"],
  "type": "access",
  "iat": 1730541600,
  "exp": 1730545200,
  "jti": "acc_7b29e01f84ac"
}
```

#### Token Claims Field Specifications

| Claim Key | Type | Mandatory? | Description & Constraints |
| :--- | :--- | :---: | :--- |
| `sub` | `str` | **Yes** | Authoritative user ID (`usr_...`). |
| `username` | `str` | **Yes** | Alphanumeric username for display and logging. |
| `role` | `str` | **Yes** | One of: `"org_admin"`, `"lecturer"`, `"student"`. Defaults to `"student"` if absent for legacy tokens. |
| `institution_id` | `str \| null` | No | ID of the joined school (`inst_...`). `null` for independent self-study students. |
| `institution_name`| `str \| null` | No | Cached display name of the school (avoids DB lookups for topbar rendering). |
| `class_id` | `str \| null` | No | ID of the enrolled class (`cls_...`). Null for Admins and non-advised Lecturers. |
| `section_id` | `str \| null` | No | ID of the enrolled section (`sec_...`). Null for Admins and unassigned Lecturers. |
| `grade` | `int \| null` | No | Primary NCERT Grade (1-12). Mandatory for Students; `null` for Admins and multi-grade Lecturers. |
| `subject_tags` | `list[str] \| null`| No | Array of subjects taught (e.g. `["Science", "Mathematics"]`). Specific to Lecturers. |
| `type` | `str` | **Yes** | Must equal `"access"` or `"refresh"`. |
| `iat` | `int` | **Yes** | Issued-at UTC UNIX timestamp. |
| `exp` | `int` | **Yes** | Expiration UTC UNIX timestamp (defaults to 60 minutes for access tokens). |
| `jti` | `str` | **Yes** | Unique token nonce for replay prevention (`acc_...`). |

---

### 2.3 Hybrid Claims + DB Session Resolution Model

A fundamental dilemma in distributed systems is choosing between purely stateless JWT claims and purely stateful database lookups. 

```
                                  INCOMING HTTP REQUEST
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │   Extract Bearer Access Token   │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │  Verify PyJWT Signature & Expiry│
                           └────────────────┬────────────────┘
                                            │
                ┌───────────────────────────┴───────────────────────────┐
                ▼                                                       ▼
      [ Read / Streaming Query ]                              [ Administrative / State Mutation ]
      - /api/ask                                              - /api/institutions/classes
      - /api/ask/stream                                       - /api/institutions/invites
      - /api/subjects                                         - /api/institutions/sections/.../advisor
                │                                                       │
                ▼                                                       ▼
  ┌──────────────────────────┐                                ┌──────────────────────────┐
  │ Trust Claims in JWT:     │                                │ Query SQLite Database:   │
  │ - user_id, role, grade   │                                │ - Verify user is_active  │
  │ - institution_id         │                                │ - Verify org_admin rights│
  │ Latency: 0.00ms          │                                │ Latency: < 0.8ms         │
  └──────────────────────────┘                                └──────────────────────────┘
```

1. **Streaming Performance (0ms DB Latency):**
   High-frequency Q&A queries (`/api/ask/stream`) and catalog lookups (`/api/subjects`) read claims directly from the cryptographically verified JWT payload. The SQLite database is never queried during the streaming loop, guaranteeing zero token-resolution latency and zero thread contention.
2. **Administrative Security (Live DB Validation):**
   Mutating operations (e.g. creating sections, deleting classes, issuing invite tokens, assigning class advisors) verify the user against the SQLite database using an active session dependency (`get_db_user`). If an administrator has revoked a user's rights, the change takes effect immediately for state-altering operations.
3. **Context Synchronization on Enrollment:**
   When a student or lecturer accepts an invite (`POST /api/invites/accept`), the backend updates the database record and returns a fresh access/refresh token pair encoding the new `institution_id`, `role`, and `section_id`. The client immediately swaps its stored token, propagating the new institutional context instantaneously.

---

### 2.4 FastAPI Parameter Bugfix for `enforce_grade`

To resolve unit test crashes when endpoints are invoked directly in Python tests, `enforce_grade` is updated with a strict dictionary type check:

```python
# app/auth/dependencies.py

def enforce_grade(user: dict | None, requested_grade: int) -> None:
    """
    Enforce grade-level access boundaries across tiered roles.
    
    Rules:
    1. If user is None or not a dict (e.g. FastAPI Depends instance in tests), pass.
    2. Parents (is_parent=True) have guardian oversight across all grades.
    3. Org Admins (role='org_admin') have administrative oversight across all grades.
    4. Lecturers (role='lecturer') have multi-grade access for curriculum review.
    5. Students (role='student') are strictly locked to their enrolled grade.
    """
    # Guard against None, anonymous access, and raw FastAPI Depends default fixtures
    if user is None or not isinstance(user, dict):
        return

    # Guardian / Parental bypass
    if user.get("is_parent"):
        return

    user_role = user.get("role", "student")

    # Faculty & Administration bypass
    if user_role in ("org_admin", "lecturer"):
        return

    # Strict Student Grade Enforcement
    student_grade = user.get("grade")
    if student_grade is not None and int(student_grade) != int(requested_grade):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access denied: You are authorized for Class {student_grade} textbooks only. "
                f"You cannot access Class {requested_grade} content."
            ),
        )
```

---

### 2.5 Role-Based Grade Enforcement Matrix

| Requester Role | Attached Token Grade | Requested Textbook Grade | Access Decision | Detail / Explanation |
| :--- | :---: | :---: | :---: | :--- |
| **Anonymous** | None | Class 10 | **Allowed** | Anonymous access allows open textbook queries in demo/self-study mode. |
| **Student (Grade 10)** | 10 | Class 10 | **Allowed** | Enrolled grade matches requested grade. |
| **Student (Grade 10)** | 10 | Class 5 | **403 Forbidden** | Strict NCERT curriculum isolation blocks out-of-grade access. |
| **Student (Grade 5)** | 5 | Class 10 | **403 Forbidden** | Strict NCERT curriculum isolation blocks out-of-grade access. |
| **Lecturer (Science)** | None | Class 10 | **Allowed** | Faculty can access any grade matching their curriculum. |
| **Lecturer (Science)** | None | Class 5 | **Allowed** | Multi-grade faculty access permitted. |
| **Org Admin** | None | Class 10 | **Allowed** | Full institutional oversight. |
| **Parent / Guardian** | Linked (10) | Any | **Allowed** | Parental supervision bypasses grade locks for safety audits. |

---

## 3. Backend Storage Strategy: Flat JSON vs. SQLite + SQLAlchemy

### 3.1 In-Depth Technical Trade-Off Evaluation

The current repository stores user records in `storage/users.json` using an in-memory `threading.Lock()` and atomic file overwrite (`os.replace`). While adequate for single-user prototyping, this mechanism represents a critical architectural vulnerability for a multi-tenant platform.

```
+--------------------------+------------------------------------+---------------------------------------+
| Architectural Dimension  | Flat-File JSON (Current)           | SQLite + WAL Mode (Proposed)          |
+--------------------------+------------------------------------+---------------------------------------+
| Multi-Worker Safety      | FAILS: threading.Lock is purely    | EXCELLENT: SQLite coordinates locks   |
|                          | in-process; multiple Uvicorn       | across multiple OS processes via      |
|                          | workers corrupt the file.          | filesystem byte-range lock primitives.|
+--------------------------+------------------------------------+---------------------------------------+
| Windows File Locking     | HIGH RISK: os.replace() fails with | ZERO RISK: WAL mode readers never     |
|                          | WinError 32 if another process     | block writers, and writers never      |
|                          | has an open read handle on the file| block readers.                        |
+--------------------------+------------------------------------+---------------------------------------+
| Relational Integrity     | NONE: Requires manual loops to     | NATIVE: Declarative Foreign Keys,     |
|                          | join users, classes, and sections. | cascading deletes, and unique indexes.|
+--------------------------+------------------------------------+---------------------------------------+
| Disk I/O & Write Scale   | O(N) Write Amplification: Modifying| O(1) Page Writes: SQLite appends 4KB  |
|                          | 1 user rewrites the entire file.   | dirty pages to the WAL log.           |
+--------------------------+------------------------------------+---------------------------------------+
| ACID Compliance          | Partial: Crash during serialization| FULL: Complete Atomic Commit & Rollback|
|                          | leaves orphaned .tmp files.        | guarantees zero database corruption.  |
+--------------------------+------------------------------------+---------------------------------------+
| Zero-Config Footprint    | Pure Python standard library.      | Built into Python (`sqlite3`); zero   |
|                          |                                    | daemon setup; 100% self-contained.    |
+--------------------------+------------------------------------+---------------------------------------+
```

**Architectural Decision:** Select **SQLite** operating in **Write-Ahead Logging (WAL)** mode managed via **SQLAlchemy 2.x**. This architecture provides enterprise-grade concurrency and relational stability without introducing external database servers.

---

### 3.2 SQLite Engine & WAL Mode Configuration

The SQLite database file is located at `storage/ncert_assistant.db`. To ensure maximum read concurrency across multiple asynchronous workers, the database engine is configured with high-performance pragmas upon every connection:

```python
# app/db/engine.py
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_FILE = Path(__file__).resolve().parent.parent.parent / "storage" / "ncert_assistant.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Engine with check_same_thread=False for FastAPI concurrency
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    echo=False,
)

# Apply performance and integrity pragmas upon connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")        # Non-blocking concurrent reads/writes
    cursor.execute("PRAGMA synchronous = NORMAL;")      # Fast writes with power-loss safety
    cursor.execute("PRAGMA foreign_keys = ON;")         # Strict relational integrity enforcement
    cursor.execute("PRAGMA busy_timeout = 5000;")       # Wait up to 5s during lock contention
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency yielding a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### 3.3 Complete SQLAlchemy Declarative Models

The complete entity model resides in `app/db/models.py`. It establishes strict relational constraints, cascading rules, and indexes across all multi-tenant entities:

```python
# app/db/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.engine import Base

def generate_uuid(prefix: str = "") -> str:
    """Generate a clean URL-safe prefixed identifier."""
    token = uuid.uuid4().hex[:12]
    return f"{prefix}_{token}" if prefix else token

class Institution(Base):
    __tablename__ = "institutions"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("inst"))
    name = Column(String(150), nullable=False, index=True)
    demo_verification_id = Column(String(64), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    classes = relationship("Classroom", back_populates="institution", cascade="all, delete-orphan")
    users = relationship("User", back_populates="institution")
    invite_links = relationship("InviteLink", back_populates="institution", cascade="all, delete-orphan")


class Classroom(Base):
    __tablename__ = "classes"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("cls"))
    institution_id = Column(String(32), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    grade = Column(Integer, nullable=False)  # 1 to 12
    display_name = Column(String(60), nullable=False)  # e.g. "Class 10"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("institution_id", "grade", name="uq_institution_grade"),
    )

    # Relationships
    institution = relationship("Institution", back_populates="classes")
    sections = relationship("Section", back_populates="classroom", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("sec"))
    class_id = Column(String(32), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    section_name = Column(String(20), nullable=False)  # e.g. "Section A"
    room = Column(String(50), nullable=True)  # e.g. "Room 302"
    class_advisor_id = Column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("class_id", "section_name", name="uq_class_section_name"),
    )

    # Relationships
    classroom = relationship("Classroom", back_populates="sections")
    class_advisor = relationship("User", foreign_keys=[class_advisor_id], back_populates="advised_section")
    enrollments = relationship("Enrollment", back_populates="section", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("usr"))
    username = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(128), nullable=False)
    password_salt = Column(String(64), nullable=False)
    role = Column(String(20), default="student", nullable=False, index=True)  # org_admin | lecturer | student
    
    institution_id = Column(String(32), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True)
    grade = Column(Integer, nullable=True)  # Mandatory for students (1-12); null for admins
    class_id = Column(String(32), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    section_id = Column(String(32), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="users")
    lecturer_profile = relationship("LecturerProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    advised_section = relationship("Section", back_populates="class_advisor", uselist=False)
    enrollments = relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")


class LecturerProfile(Base):
    __tablename__ = "lecturer_profiles"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("lec"))
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    subject_tags = Column(Text, default="[]", nullable=False)  # JSON-encoded array: ["Science", "Physics"]
    department = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="lecturer_profile")


class InviteLink(Base):
    __tablename__ = "invite_links"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("inv"))
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hash of plaintext token
    token_preview = Column(String(12), nullable=False)  # e.g. "lec_9a8f..."
    institution_id = Column(String(32), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role = Column(String(20), nullable=False)  # "lecturer" | "student"
    
    class_id = Column(String(32), ForeignKey("classes.id", ondelete="CASCADE"), nullable=True)
    section_id = Column(String(32), ForeignKey("sections.id", ondelete="CASCADE"), nullable=True)
    created_by_user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    expires_at = Column(DateTime, nullable=False)
    max_uses = Column(Integer, default=50, nullable=False)
    uses_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="invite_links")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("enr"))
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String(32), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active | withdrawn

    __table_args__ = (
        UniqueConstraint("user_id", "section_id", name="uq_user_section_enrollment"),
    )

    # Relationships
    user = relationship("User", back_populates="enrollments")
    section = relationship("Section", back_populates="enrollments")
```

---

### 3.4 Entity-Relationship Diagram (ERD)

```
┌─────────────────────────────────┐
│          institutions           │
├─────────────────────────────────┤
│ id: VARCHAR(32) [PK]            │
│ name: VARCHAR(150)              │
│ demo_verification_id: VARCHAR   │
│ is_active: BOOLEAN              │
│ created_at / updated_at         │
└───────────────┬─────────────────┘
                │ 1
                │
                ├─────────────────────────────────────────┐
                │ *                                       │ *
┌───────────────▼─────────────────┐       ┌───────────────▼─────────────────┐
│             classes             │       │          invite_links           │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ id: VARCHAR(32) [PK]            │       │ id: VARCHAR(32) [PK]            │
│ institution_id: VARCHAR(32)[FK] │       │ token_hash: VARCHAR(64) [UQ]    │
│ grade: INTEGER (1-12)           │       │ institution_id: VARCHAR(32)[FK] │
│ display_name: VARCHAR(60)       │       │ target_role: VARCHAR(20)        │
└───────────────┬─────────────────┘       │ class_id: VARCHAR(32) [FK, NULL]│
                │ 1                       │ section_id: VARCHAR(32)[FK, NULL│
                │                         │ max_uses / uses_count / expires │
                │ *                       └─────────────────────────────────┘
┌───────────────▼─────────────────┐
│            sections             │
├─────────────────────────────────┤
│ id: VARCHAR(32) [PK]            │
│ class_id: VARCHAR(32) [FK]      │
│ section_name: VARCHAR(20)       │
│ room: VARCHAR(50) [NULL]        │
│ class_advisor_id: VARCHAR [FK]  ├───────────────────────┐
└───────────────┬─────────────────┘                       │ 0..1 (Advisor)
                │ 1                                       │
                │                                         │
                │ *                                       │ 1
┌───────────────▼─────────────────┐       ┌───────────────▼─────────────────┐
│           enrollments           │       │              users              │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ id: VARCHAR(32) [PK]            │       │ id: VARCHAR(32) [PK]            │
│ user_id: VARCHAR(32) [FK]       ├───────┤ username: VARCHAR(50) [UQ]      │
│ section_id: VARCHAR(32) [FK]    │ *   1 │ role: VARCHAR(20)               │
│ enrolled_at: DATETIME           │       │ institution_id: VARCHAR(32)[FK] │
└─────────────────────────────────┘       │ grade: INTEGER [NULL]           │
                                          │ password_hash / password_salt   │
                                          └───────────────┬─────────────────┘
                                                          │ 1
                                                          │
                                                          │ 0..1 (Lecturer)
                                          ┌───────────────▼─────────────────┐
                                          │        lecturer_profiles        │
                                          ├─────────────────────────────────┤
                                          │ id: VARCHAR(32) [PK]            │
                                          │ user_id: VARCHAR(32) [FK, UQ]   │
                                          │ subject_tags: TEXT (JSON)       │
                                          │ department: VARCHAR(100)        │
                                          │ bio: TEXT [NULL]                │
                                          └─────────────────────────────────┘
```

---

### 3.5 Automated Startup Migration from `storage/users.json`

To guarantee seamless backward compatibility, the system implements an idempotent startup migration in `app/db/migration.py`, called during FastAPI's lifespan initialization in `app/main.py`:

```python
# app/db/migration.py
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.engine import Base, engine, SessionLocal
from app.db.models import User

logger = logging.getLogger("ncert.migration")
USERS_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "storage" / "users.json"

def run_startup_migrations():
    """
    1. Ensures all SQLite tables are created.
    2. Idempotently imports existing users from storage/users.json if the database is unpopulated.
    3. Preserves identical PBKDF2 password hashes, salts, grades, and identifiers.
    """
    # 1. Create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    logger.info("SQLite database schema initialized.")

    if not USERS_JSON_PATH.exists():
        logger.info("No legacy users.json file found; skipping import.")
        return

    db: Session = SessionLocal()
    try:
        existing_db_count = db.query(User).count()
        if existing_db_count > 0:
            logger.info("Users table already populated (%d records); skipping legacy import.", existing_db_count)
            return

        raw_data = USERS_JSON_PATH.read_text(encoding="utf-8").strip()
        if not raw_data:
            return

        legacy_users = json.loads(raw_data)
        logger.info("Migrating %d users from storage/users.json to SQLite...", len(legacy_users))

        for u in legacy_users:
            new_user = User(
                id=u.get("id"),
                username=u.get("username"),
                full_name=u.get("full_name"),
                password_hash=u.get("password_hash"),
                password_salt=u.get("password_salt"),
                role="student",  # All legacy accounts default to Student
                institution_id=None,  # Unjoined self-study student
                grade=u.get("grade", 10),
                is_active=u.get("is_active", True),
                created_at=datetime.fromisoformat(u.get("created_at")) if u.get("created_at") else datetime.now(timezone.utc),
                updated_at=datetime.fromisoformat(u.get("updated_at")) if u.get("updated_at") else datetime.now(timezone.utc),
            )
            db.add(new_user)

        db.commit()
        logger.info("Successfully imported %d legacy users into SQLite.", len(legacy_users))
        
        # Create a backup marker
        backup_path = USERS_JSON_PATH.with_suffix(".json.migrated_bak")
        if not backup_path.exists():
            USERS_JSON_PATH.rename(backup_path)
            logger.info("Archived storage/users.json to %s", backup_path.name)

    except Exception as e:
        db.rollback()
        logger.error("Failed to migrate legacy users.json: %s", e, exc_info=True)
    finally:
        db.close()
```

---

## 4. Institution Lifecycle & Multi-Tier RBAC Architecture

### 4.1 Institution Onboarding & Admin Lifecycle

An institution represents the primary tenant boundary. Org Admins possess complete authority over their institution's academic hierarchy, invite links, and roster management.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Admin Onboarding Flow                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                     [ Authenticated as Org Admin ]
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
      [ "Create an Institution" ]             [ "Join an Institution" ]
                  │                                   │
                  ├──────────────────────┐            └───────────────┐
                  ▼                      ▼                            ▼
       Inputs: Name & Demo ID    Validates against allowlist   Inputs: Admin Access Code
                  │                      │                            │
                  └──────────┬───────────┘                            │
                             │                                        │
                             ▼                                        ▼
                  Creates Institution Record            Binds Admin to Existing School
                  Binds User as Org Admin               Returns Refreshed JWT Token
```

#### Demo Verification ID Mechanism
In enterprise production (Google Workspace for Education), institutions prove domain ownership through DNS TXT records. In the NCERT Assistant architecture, onboarding utilizes **Demo Verification IDs**:
- When calling `POST /api/institutions`, the administrator provides:
  - `name`: e.g. `"Delhi Public School, R.K. Puram"`
  - `demo_verification_id`: e.g. `"DEMO-DPS-2026"` or `"NCERT-VERIFIED-991"`
- Verification Logic:
  1. The ID must match an allowed institution registry or follow an authoritative cryptographic format: `DEMO-[SCHOOL_CODE]-[YEAR]`.
  2. The system guarantees uniqueness (`UniqueConstraint` on `demo_verification_id`). If already claimed, returns HTTP 409 Conflict.
  3. Upon verification, the user account is assigned `role = "org_admin"`, `institution_id = institution.id`, and receives a refreshed JWT.

---

### 4.2 Academic Hierarchy: Classes & Sections

To mirror the Indian school system (NCERT/CBSE) and Google Classroom's Course model:
1. **Classroom (Grade):** Represents an educational standard (Grades 1 through 12).
   - An institution has exactly one `Classroom` per grade level (e.g., Class 10).
2. **Section (Cohort):** Represents a distinct division of students within that grade (e.g., Section A, Section B, Section C).
   - Each section has an optional `room` descriptor (e.g. "Room 302").
   - Each section is assigned at most **one Class Advisor**.

---

### 4.3 Role-Specific Invite Link Mechanics

To eliminate privilege escalation risks (where a student might inadvertently or maliciously obtain faculty permissions), the system enforces **strict role segregation** across two dedicated invite types:

```
                               ┌────────────────────────────────┐
                               │     Org Admin Generates Link   │
                               └───────────────┬────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
         [ Dedicated Lecturer Invite ]                   [ Dedicated Student Invite ]
         - Target Role: "lecturer"                       - Target Role: "student"
         - Not bound to specific class                   - Explicitly bound to Class & Section
         - Multi-use (e.g. 20 faculty)                   - Multi-use (e.g. 50 students)
         - Generates URL:                                - Generates URL:
           /join?invite=lec_8f91a2...                      /join?invite=stu_3b4c10...
```

#### Cryptographic Security & Lifecycle Properties
1. **Token Generation:** Plaintext tokens are constructed as `lec_<secrets.token_urlsafe(24)>` or `stu_<secrets.token_urlsafe(24)>`.
2. **Storage:** The raw plaintext token is sent only once to the client upon creation. The database stores a SHA-256 hash (`token_hash`) to prevent token leakage in database dumps.
3. **Usage Limits & Expiration:** Links carry an expiration timestamp (`expires_at`, defaulting to 14 days) and a maximum redemption limit (`max_uses`, defaulting to 50).
4. **Redemption Flow (`POST /api/invites/accept`):**
   - The user submits `token`.
   - The system checks: `is_active == True`, `expires_at > now()`, and `uses_count < max_uses`.
   - If `target_role == "lecturer"`: The user is promoted to `role = "lecturer"`, attached to `institution_id`, and initialized with an empty `LecturerProfile`.
   - If `target_role == "student"`: The user is attached to `institution_id`, assigned `grade = class.grade`, enrolled in `section_id`, and a record is created in `enrollments`.
   - `uses_count` is incremented by 1 atomically.
   - Refreshed access/refresh tokens are returned.

---

### 4.4 Lecturer Profile, Subject Tags & Class Advisor Designation

Faculty members require granular subject-matter authorization and cohort supervision capabilities:

1. **Subject Tags:**
   - A lecturer profile maintains an array of subjects taught: `["Science", "Physics", "Chemistry"]`.
   - When querying curriculum Q&A or listing subjects (`/api/subjects`), lecturers can inspect any textbook matching their assigned subject tags across all relevant grades.
2. **Class Advisor Designation (Homeroom Teacher):**
   - In NCERT schools, each section (e.g., Class 10-A) is assigned one **Class Advisor**.
   - The Class Advisor has pastoral responsibility over that cohort.
   - *Constraint:* Exactly one Class Advisor per section at any time (`unique=True` on `sections.class_advisor_id`).
   - *Privileges of Class Advisor:*
     * Generate student invite links for their advised section.
     * View the full student roster of their section.
     * Review parental and safety audit alerts triggered by students within their section.

---

### 4.5 Student Lifecycle: Unjoined vs. Joined States

```
+-----------------------------------+-----------------------------------+-----------------------------------+
| Feature / State                   | Unjoined Student (Self-Study)     | Joined Institutional Student      |
+-----------------------------------+-----------------------------------+-----------------------------------+
| UI Topbar Display                 | Pill Button:                      | School Badge:                     |
|                                   | [ 🏫 Join your Institution ]      | [ 🏛️ Delhi Public School · 10-A ] |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Sidebar User Card                 | "Class 10 (Self-Study)"           | "Class 10-A"                      |
|                                   | Subtitle: "Not connected"         | Subtitle: "Advisor: Dr. Sharma"   |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Textbook Q&A Access               | Enrolled Class 10 textbooks only  | Enrolled Class 10 textbooks only  |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Roster & Classmates               | Disabled                          | View section peers                |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Institutional Safety Logging      | Local single-user log             | Scoped with institution_id and    |
|                                   |                                   | section_id for advisor oversight  |
+-----------------------------------+-----------------------------------+-----------------------------------+
```

---

### 4.6 Complete 4-Tier RBAC Authorization Matrix

| Action / Resource | Org Admin | Class Advisor | Subject Lecturer | Student | Guardian (Parent) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Create Institution** | ✅ (Verified Demo ID)| ❌ | ❌ | ❌ | ❌ |
| **Delete / Archive Institution** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Create Class & Section** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Assign Class Advisor** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Generate Lecturer Invite Link** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Generate Student Invite Link** | ✅ | ✅ (Own Section) | ❌ | ❌ | ❌ |
| **Update Own Subject Tags** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **View Section Student Roster** | ✅ (All Sections) | ✅ (Advised Section)| ✅ (Taught Sections)| Section Peers | Linked Child Only |
| **Ask Assistant (Curriculum Q&A)** | All Grades | All Grades / Subjects| Assigned Subjects | **Enrolled Grade Only**| Oversight Only |
| **Access Safety Event Logs** | Full School Audit | Advised Section Logs| ❌ | ❌ | **Linked Child Only**|
| **Parental PIN & Safe Toggles** | ❌ | ❌ | ❌ | ❌ | ✅ (PIN Protected)|

---

### 4.7 Integration with Parental Controls & Audit Logging

The multi-tenant architecture integrates seamlessly with the existing parental subsystem (`app/parental/`):
1. **Safety Event Augmentation:**
   `log_safety_event()` in `app/safety/` is extended to capture tenant metadata:
   ```json
   {
     "event_id": "evt_20261102_9f81ab",
     "timestamp": "2026-11-02T10:15:30Z",
     "user_id": "usr_c83d19a2e5",
     "username": "rahul_10",
     "institution_id": "inst_dps_rkpuram_01",
     "class_id": "cls_grade10_dps",
     "section_id": "sec_10a_dps",
     "student_grade": 10,
     "category": "cyberbullying",
     "query_text": "...",
     "safety_status": "blocked"
   }
   ```
2. **Scoped Safety Review:**
   - Org Admins review safety trends across the entire school via `GET /api/institutions/safety-events`.
   - Class Advisors view safety events scoped exclusively to their section.
   - Parents retain private, PIN-authenticated oversight over their individual child's chat history.

---

## 5. Complete REST API Specifications

### 5.1 Core Pydantic Data Contracts

All endpoints utilize Pydantic v2 schemas located in `app/institution/schemas.py`:

```python
# app/institution/schemas.py
from datetime import datetime
from pydantic import BaseModel, Field

# ── Auth & Onboarding ──
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    role: str = Field(default="student", pattern=r"^(student|org_admin)$")
    grade: int | None = Field(default=None, ge=1, le=12)

class InstitutionCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    demo_verification_id: str = Field(min_length=4, max_length=64)

class InstitutionJoinRequest(BaseModel):
    admin_access_code: str = Field(min_length=6, max_length=64)

class InstitutionResponse(BaseModel):
    id: str
    name: str
    demo_verification_id: str
    is_active: bool
    created_at: datetime

# ── Classes & Sections ──
class ClassCreateRequest(BaseModel):
    grade: int = Field(ge=1, le=12)
    display_name: str | None = Field(default=None, max_length=60)

class SectionCreateRequest(BaseModel):
    section_name: str = Field(min_length=1, max_length=20)
    room: str | None = Field(default=None, max_length=50)

class SectionResponse(BaseModel):
    id: str
    class_id: str
    section_name: str
    room: str | None
    class_advisor_id: str | None
    class_advisor_name: str | None = None
    student_count: int = 0

class ClassResponse(BaseModel):
    id: str
    institution_id: str
    grade: int
    display_name: str
    sections: list[SectionResponse] = []

# ── Invites ──
class InviteCreateRequest(BaseModel):
    target_role: str = Field(pattern=r"^(lecturer|student)$")
    class_id: str | None = None
    section_id: str | None = None
    max_uses: int = Field(default=50, ge=1, le=1000)
    expires_days: int = Field(default=14, ge=1, le=90)

class InviteResponse(BaseModel):
    id: str
    invite_url: str
    token_preview: str
    target_role: str
    class_id: str | None
    section_id: str | None
    max_uses: int
    uses_count: int
    expires_at: datetime
    is_active: bool

class InviteValidateResponse(BaseModel):
    is_valid: bool
    institution_name: str
    target_role: str
    grade: int | None
    section_name: str | None

class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)

# ── Lecturer Profiles ──
class LecturerProfileUpdateRequest(BaseModel):
    subject_tags: list[str] = Field(default_factory=list)
    department: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=500)

class LecturerResponse(BaseModel):
    user_id: str
    username: str
    full_name: str | None
    subject_tags: list[str]
    department: str | None
    bio: str | None
    is_class_advisor: bool
    advised_section: str | None = None

class ClassAdvisorAssignRequest(BaseModel):
    lecturer_id: str
```

---

### 5.2 Authentication & Identity Endpoints

#### 1. `POST /api/auth/register`
- **Description:** Registers a new user account. Supports public self-registration for `student` and `org_admin`. Lecturers must be onboarded via invite links.
- **Headers:** `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "username": "dr_kapoor",
    "password": "SecretPassword123!",
    "full_name": "Dr. Ramesh Kapoor",
    "role": "org_admin"
  }
  ```
- **Responses:**
  - `201 Created`: Returns JWT `TokenResponse` and user object.
  - `400 Bad Request`: Username already taken or validation error.

#### 2. `POST /api/auth/login`
- **Description:** Authenticates user via PBKDF2 hash verification and returns JWT access/refresh token pair.
- **Request Body:** `{"username": "dr_kapoor", "password": "SecretPassword123!"}`
- **Responses:**
  - `200 OK`: `{"access_token": "...", "refresh_token": "...", "token_type": "bearer", "user": {...}}`
  - `401 Unauthorized`: Invalid credentials.

#### 3. `GET /api/auth/me`
- **Description:** Returns the authenticated user's current identity and institutional context.
- **Headers:** `Authorization: Bearer <token>`
- **Response 200 OK:**
  ```json
  {
    "id": "usr_78a1bc4f",
    "username": "dr_kapoor",
    "full_name": "Dr. Ramesh Kapoor",
    "role": "org_admin",
    "institution_id": "inst_dps_01",
    "institution_name": "Delhi Public School",
    "grade": null,
    "class_id": null,
    "section_id": null
  }
  ```

---

### 5.3 Institution Lifecycle Endpoints

#### 1. `POST /api/institutions`
- **Auth:** Bearer Token (`role == "org_admin"`)
- **Description:** Provisions a new institution verified via Demo Verification ID.
- **Request Body:**
  ```json
  {
    "name": "Delhi Public School, R.K. Puram",
    "demo_verification_id": "DEMO-DPS-2026"
  }
  ```
- **Responses:**
  - `201 Created`: Returns `InstitutionResponse`.
  - `409 Conflict`: Demo Verification ID already claimed.
  - `403 Forbidden`: User does not hold `org_admin` role.

#### 2. `GET /api/institutions/current`
- **Auth:** Bearer Token (Any institutional member)
- **Response 200 OK:**
  ```json
  {
    "id": "inst_dps_01",
    "name": "Delhi Public School, R.K. Puram",
    "demo_verification_id": "DEMO-DPS-2026",
    "is_active": true,
    "total_students": 240,
    "total_lecturers": 18,
    "total_classes": 4
  }
  ```

---

### 5.4 Class & Section Management Endpoints

#### 1. `GET /api/institutions/classes`
- **Auth:** Bearer Token (Any institutional member)
- **Response 200 OK:** Returns array of `ClassResponse` objects with nested sections and advisor info.

#### 2. `POST /api/institutions/classes`
- **Auth:** Bearer Token (`role == "org_admin"`)
- **Request Body:** `{"grade": 10, "display_name": "Class 10"}`
- **Responses:**
  - `201 Created`: Returns created class record.
  - `409 Conflict`: Class for this grade already exists in this institution.

#### 3. `POST /api/institutions/classes/{class_id}/sections`
- **Auth:** Bearer Token (`role == "org_admin"`)
- **Request Body:** `{"section_name": "A", "room": "Room 302"}`
- **Responses:**
  - `201 Created`: Returns created section record.
  - `409 Conflict`: Section with this name already exists in this class.

#### 4. `DELETE /api/institutions/sections/{section_id}`
- **Auth:** Bearer Token (`role == "org_admin"`)
- **Response 204 No Content**: Deletes section and cascades enrollments.

---

### 5.5 Role-Specific Invite Mechanics Endpoints

#### 1. `POST /api/institutions/invites`
- **Auth:** Bearer Token (`org_admin` or Class Advisor for student invites)
- **Request Body (Lecturer Invite):**
  ```json
  {
    "target_role": "lecturer",
    "max_uses": 25,
    "expires_days": 14
  }
  ```
- **Request Body (Student Invite):**
  ```json
  {
    "target_role": "student",
    "class_id": "cls_10",
    "section_id": "sec_10a",
    "max_uses": 60,
    "expires_days": 30
  }
  ```
- **Response 201 Created:**
  ```json
  {
    "id": "inv_89ab12cd",
    "invite_url": "https://ncert.app/join?invite=lec_e82f7a91b2c3d4e5",
    "token_preview": "lec_e82f7...",
    "target_role": "lecturer",
    "class_id": null,
    "section_id": null,
    "max_uses": 25,
    "uses_count": 0,
    "expires_at": "2026-11-16T10:00:00Z",
    "is_active": true
  }
  ```

#### 2. `POST /api/invites/validate`
- **Auth:** Public
- **Description:** Allows clients to inspect invite details before redemption.
- **Request Body:** `{"token": "lec_e82f7a91b2c3d4e5"}`
- **Response 200 OK:**
  ```json
  {
    "is_valid": true,
    "institution_name": "Delhi Public School, R.K. Puram",
    "target_role": "lecturer",
    "grade": null,
    "section_name": null
  }
  ```

#### 3. `POST /api/invites/accept`
- **Auth:** Bearer Token (Any authenticated user)
- **Request Body:** `{"token": "stu_3b4c10..."}`
- **Responses:**
  - `200 OK`: Returns refreshed `TokenResponse` carrying updated claims (`institution_id`, `role`, `section_id`).
  - `400 Bad Request`: Token usage limit reached or token inactive.
  - `410 Gone`: Token expired.
  - `409 Conflict`: User already enrolled in this section.

---

### 5.6 Lecturer Profile & Advisor Assignment Endpoints

#### 1. `PUT /api/institutions/lecturers/me/profile`
- **Auth:** Bearer Token (`role == "lecturer"`)
- **Request Body:**
  ```json
  {
    "subject_tags": ["Science", "Physics", "Chemistry"],
    "department": "Science Department",
    "bio": "Senior Physics Lecturer with 12 years of CBSE curriculum experience."
  }
  ```
- **Response 200 OK:** Returns updated `LecturerResponse`.

#### 2. `PUT /api/institutions/sections/{section_id}/advisor`
- **Auth:** Bearer Token (`role == "org_admin"`)
- **Request Body:** `{"lecturer_id": "usr_teach_sharma"}`
- **Responses:**
  - `200 OK`: Assigns teacher as Class Advisor.
  - `409 Conflict`: Lecturer is already Class Advisor for another section.

---

### 5.7 Section Roster & Multi-Tenant Audit Endpoints

#### 1. `GET /api/institutions/sections/{section_id}/roster`
- **Auth:** Bearer Token (`org_admin`, Section Advisor, or enrolled Student)
- **Response 200 OK:**
  ```json
  {
    "section_id": "sec_10a",
    "section_name": "Section A",
    "grade": 10,
    "advisor": {
      "user_id": "usr_teach_sharma",
      "full_name": "Dr. Anita Sharma"
    },
    "students": [
      {
        "user_id": "usr_stu_01",
        "username": "rahul_10",
        "full_name": "Rahul Verma",
        "enrolled_at": "2026-11-02T03:15:48Z"
      }
    ]
  }
  ```

#### 2. `GET /api/institutions/safety-events`
- **Auth:** Bearer Token (`org_admin` or Class Advisor)
- **Response 200 OK:** Returns audit logs filtered by the user's institution and advised section.

---

## 6. UI/UX Blueprint (React 18 + Vite)

### 6.1 Component Architecture & Hierarchy

All institution and RBAC components reside in a dedicated directory: `ui-client/src/components/institution/`.

```
ui-client/src/
├── App.jsx                        # Core layout & routing state
├── App.css                        # Global layout rules
├── components/
│   ├── parental/                  # Existing PIN & Guardian components
│   └── institution/               # New Multi-Tenant & RBAC Components
│       ├── InstitutionNavButton.jsx       # Topbar badge / "Join" CTA
│       ├── InstitutionOnboardingModal.jsx # Admin Create/Join modal
│       ├── AdminManagementModal.jsx       # Class/Section CRUD & Roster
│       ├── InviteLinkGeneratorModal.jsx   # Dedicated Lecturer & Student links
│       ├── LecturerProfileModal.jsx       # Subject tags & Advisor badge
│       ├── InviteAcceptModal.jsx          # URL (?invite=...) join flow
│       └── institution.css                # Frosted-glass Gemini styling
```

---

### 6.2 Global Authentication & Institution Context

To eliminate hardcoded student profiles (`studentUser` fallback in `App.jsx`) and pass Bearer tokens to `/api/ask/stream`, an `AuthContext` provides centralized state:

```javascript
// ui-client/src/context/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem('access_token'));
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem('student_user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const saveAuth = (newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('access_token', newToken);
    localStorage.setItem('student_user', JSON.stringify(newUser));
  };

  const clearAuth = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('access_token');
    localStorage.removeItem('student_user');
  };

  return (
    <AuthContext.Provider value={{ token, user, saveAuth, clearAuth, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
```

#### Passing Bearer Token in `/api/ask/stream`
In `ui-client/src/App.jsx:632`:
```javascript
const headers = { 'Content-Type': 'application/json' };
if (token) {
  headers['Authorization'] = `Bearer ${token}`;
}

const res = await fetch('/api/ask/stream', {
  method: 'POST',
  headers,
  body: JSON.stringify(payload),
});
```

---

### 6.3 Student Topbar & Sidebar Profile States

#### 1. Topbar Navigation (`InstitutionNavButton.jsx`)
- **Unjoined Student (`!user?.institution_id`):**
  Renders a vibrant call-to-action button in the topbar:
  ```html
  <button className="gemini-institution-pill unjoined" onClick={() => setJoinModalOpen(true)}>
    <span className="inst-icon">🏫</span>
    <span className="inst-label">Join your Institution</span>
  </button>
  ```
- **Joined Student (`user?.institution_id`):**
  Renders an institutional badge:
  ```html
  <div className="gemini-institution-pill joined">
    <span className="inst-icon">🏛️</span>
    <span className="inst-name">{user.institution_name}</span>
    <span className="inst-divider">·</span>
    <span className="inst-cohort">Class {user.grade}-{user.section_name || 'A'}</span>
  </div>
  ```
- **Org Admin:**
  Renders an administrative badge opening the management console:
  ```html
  <button className="gemini-institution-pill admin" onClick={() => setAdminModalOpen(true)}>
    <span className="inst-icon">⚙️</span>
    <span className="inst-name">{user.institution_name || 'Institution Admin'}</span>
  </button>
  ```

#### 2. Sidebar Profile Card (`App.jsx:1054`)
The user profile footer displays:
- Student Name (`user.full_name || user.username`)
- Role / Grade Badge (`Class 10-A` or `Faculty · Science`)
- Subtitle: Advisor name if joined, or `"Independent Self-Study"` if unjoined.

---

### 6.4 Admin Onboarding & Management Console

The Admin Console (`AdminManagementModal.jsx`) provides a four-tabbed glassmorphic interface:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 🏛️ Delhi Public School — Administration Console                        │
├────────────────────────────────────────────────────────────────────────┤
│ [ Overview ]   [ Academic Structure ]   [ Invite Links ]   [ Rosters ] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Academic Structure:                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 📘 Class 10 (Secondary)                        [ + Add Section ] │  │
│  │   ├── Section A (Room 302) · Advisor: Dr. Anita Sharma [Edit]    │  │
│  │   └── Section B (Room 304) · Advisor: Prof. M. Verma   [Edit]    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 📘 Class 5 (Primary)                           [ + Add Section ] │  │
│  │   └── Section A (Room 101) · Advisor: Unassigned       [Assign]  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  [ + Add New Class Standard ]                                          │
└────────────────────────────────────────────────────────────────────────┘
```

#### Invite Link Generator Tab (`InviteLinkGeneratorModal.jsx`)
Features two dedicated cards:
1. **Lecturer Invite Card:**
   - One-click "Generate Faculty Link".
   - Generates `/join?invite=lec_...`.
   - Copy to clipboard button with auto-check animation.
2. **Student Invite Card:**
   - Dropdown selects target Class (e.g. Class 10) and Section (e.g. Section A).
   - Generates `/join?invite=stu_...`.
   - Max uses counter and expiration dropdown.

---

### 6.5 Lecturer Subject Tagging & Advisor Badge

Faculty members can access `LecturerProfileModal.jsx` from their sidebar:
1. **Interactive Subject Chips:**
   Multi-select chips for NCERT disciplines: `[ Science ]`, `[ Mathematics ]`, `[ English ]`, `[ Social Science ]`, `[ Hindi ]`.
2. **Advisor Status Pill:**
   If assigned to a section, displays:
   `⭐ Class Advisor for Class 10, Section A`.

---

### 6.6 Invite URL Detection & Acceptance Flow (`?invite=...`)

In `ui-client/src/App.jsx`, a `useEffect` hook monitors the window query string on startup:

```javascript
useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const inviteToken = params.get('invite');
  if (inviteToken) {
    // Validate token against /api/invites/validate
    fetch('/api/invites/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: inviteToken }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.is_valid) {
          setPendingInvite({ token: inviteToken, ...data });
          setInviteModalOpen(true);
        }
      });
  }
}, []);
```

- If authenticated: The modal displays: *"Join {data.institution_name} as {data.target_role}?"* Clicking **Accept** issues `POST /api/invites/accept` and refreshes user context without page reload.
- If unauthenticated: The modal presents options to **Sign In** or **Register**, preserving the invite token in memory.

---

### 6.7 Visual Styling & Glassmorphic Component Spec

Styling adheres strictly to the existing Gemini frosted-glass visual theme in `ui-client/src/App.css` and `parental.css`:

```css
/* ui-client/src/components/institution/institution.css */
.gemini-institution-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  cursor: pointer;
}

.gemini-institution-pill.unjoined {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15));
  border-color: rgba(168, 85, 247, 0.35);
  color: #c084fc;
}

.gemini-institution-pill:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.25);
  transform: translateY(-1px);
}
```

---

## 7. Phased Implementation Roadmap & Backward Compatibility

### 7.1 Implementation Phases (1 through 8)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Phased Implementation Roadmap                        │
├────────────────────────────────────────────────────────────────────────┤
│  Phase 1: Database Engine & Relational Models (app/db/)                │
│  Phase 2: Auth Enhancement & Extended PyJWT Claims (app/auth/)         │
│  Phase 3: Institution & Academic Core Services (app/institution/)      │
│  Phase 4: Role-Specific Invite System & Mechanics                      │
│  Phase 5: Lecturer Profiles & Advisor Subsystem                        │
│  Phase 6: Core App & RAG Integration (app/main.py, enforce_grade)      │
│  Phase 7: Frontend UI/UX Components & State (ui-client/)               │
│  Phase 8: Comprehensive Verification & Automated Test Suite            │
└────────────────────────────────────────────────────────────────────────┘
```

#### Detailed Phase Execution Plan

1. **Phase 1: Database Engine & Relational Models (`app/db/`)**
   - Create `app/db/__init__.py`, `app/db/engine.py`, `app/db/models.py`.
   - Implement `app/db/migration.py` with idempotent `run_startup_migrations()` to seed SQLite from `storage/users.json`.
   - Wire SQLite WAL pragmas to ensure multi-worker safety.

2. **Phase 2: Auth Enhancement & Extended PyJWT Claims (`app/auth/`)**
   - Refactor `app/auth/jwt_handler.py` to support optional `grade`, `role`, `institution_id`, `class_id`, and `section_id`.
   - Update `decode_access_token()` to allow `grade = None` for non-student roles.
   - Refactor `app/auth/dependencies.py` with role checkers (`require_role`) and the `enforce_grade` bugfix.
   - Extend `app/auth/schemas.py` and `routes.py` to allow `org_admin` registration.

3. **Phase 3: Institution & Academic Core Services (`app/institution/`)**
   - Create `app/institution/models.py`, `schemas.py`, `service.py`, `routes.py`.
   - Implement Institution CRUD: `POST /api/institutions`, `GET /api/institutions/current`.
   - Implement Class and Section CRUD: `GET /api/institutions/classes`, `POST /api/institutions/classes`, `POST /api/institutions/classes/{id}/sections`.

4. **Phase 4: Role-Specific Invite System & Mechanics**
   - Implement invite generation in `app/institution/service.py`: dedicated Lecturer vs Student link generation.
   - Implement token validation (`POST /api/invites/validate`) and redemption (`POST /api/invites/accept`).
   - Add SHA-256 token hashing, expiration checks, and atomic usage counters.

5. **Phase 5: Lecturer Profiles & Advisor Subsystem**
   - Implement `PUT /api/institutions/lecturers/me/profile` for subject tags and department info.
   - Implement `PUT /api/institutions/sections/{id}/advisor` for assigning Class Advisors.
   - Extend `/api/subjects` in `app/main.py` to allow lecturers to view subjects matching their subject tags.

6. **Phase 6: Core App & RAG Integration (`app/main.py`)**
   - Mount `institution_router` in `app/main.py` under prefix `/api/institutions`.
   - Incorporate `run_startup_migrations()` into FastAPI `lifespan`.
   - Augment `log_safety_event()` and `make_turn_record()` with `institution_id`, `class_id`, and `section_id`.

7. **Phase 7: Frontend UI/UX Components & State (`ui-client/`)**
   - Implement `AuthContext` to centralize token and user state.
   - Add `Authorization: Bearer <token>` to `/api/ask/stream`.
   - Build `ui-client/src/components/institution/`: `InstitutionNavButton.jsx`, `InstitutionOnboardingModal.jsx`, `AdminManagementModal.jsx`, `LecturerProfileModal.jsx`, `InviteAcceptModal.jsx`.
   - Style components with frosted-glass CSS matching Gemini themes.

8. **Phase 8: Comprehensive Verification & Automated Test Suite**
   - Create `tests/test_multi_tenant.py` verifying full institution lifecycle, class/section creation, and invite link redemption.
   - Create `tests/test_institution_rbac.py` verifying tiered RBAC permissions and grade enforcement.
   - Re-run existing test suites (`test_auth.py`, `test_api.py`, `test_parental.py`) to confirm zero regressions.

---

### 7.2 File-by-File Delta Specification Table

| Target File | Action | Purpose & Design Decisions |
| :--- | :---: | :--- |
| `app/db/__init__.py` | **Create** | Exports `Base`, `engine`, `get_db`. |
| `app/db/engine.py` | **Create** | SQLite engine with WAL mode pragmas and `SessionLocal`. |
| `app/db/models.py` | **Create** | Declarative SQLAlchemy models: `Institution`, `Classroom`, `Section`, `User`, `LecturerProfile`, `InviteLink`, `Enrollment`. |
| `app/db/migration.py` | **Create** | Idempotent migration engine importing `storage/users.json` into SQLite on startup. |
| `app/auth/jwt_handler.py` | **Modify** | Extend payload with `role`, `institution_id`, `section_id`; make `grade` optional. |
| `app/auth/dependencies.py` | **Modify** | Fix `isinstance(user, dict)` parameter bug; add `require_role`; update `enforce_grade` for faculty bypass. |
| `app/auth/schemas.py` | **Modify** | Allow `role` and optional `grade` in `RegisterRequest`. |
| `app/auth/routes.py` | **Modify** | Allow `org_admin` registration; verify credentials via SQLite. |
| `app/institution/__init__.py` | **Create** | Package initializer for institution module. |
| `app/institution/schemas.py` | **Create** | Pydantic v2 schemas for institutions, classes, sections, invites, and lecturers. |
| `app/institution/service.py` | **Create** | Business logic for onboarding, class/section CRUD, invite generation, and redemption. |
| `app/institution/routes.py` | **Create** | FastAPI router exposing all `/api/institutions` and `/api/invites` routes. |
| `app/main.py` | **Modify** | Mount `institution_router`; invoke `run_startup_migrations()` in lifespan; augment safety turn logs. |
| `ui-client/src/context/AuthContext.jsx` | **Create** | Centralized React auth state managing JWT token and user profile. |
| `ui-client/src/components/institution/InstitutionNavButton.jsx` | **Create** | Topbar badge rendering school name or "Join your Institution" CTA. |
| `ui-client/src/components/institution/InstitutionOnboardingModal.jsx` | **Create** | Admin modal to create institution with Demo ID or join via admin key. |
| `ui-client/src/components/institution/AdminManagementModal.jsx` | **Create** | Comprehensive Admin console for class/section hierarchy, advisor assignment, and invites. |
| `ui-client/src/components/institution/LecturerProfileModal.jsx` | **Create** | Modal for faculty to update subject tags and view Class Advisor status. |
| `ui-client/src/components/institution/InviteAcceptModal.jsx` | **Create** | Modal handling `?invite=...` parameter and completing enrollment. |
| `ui-client/src/components/institution/institution.css` | **Create** | Glassmorphic styles matching existing Gemini theme. |
| `ui-client/src/App.jsx` | **Modify** | Integrate `AuthContext`, mount institution components, and include Bearer token in `/api/ask/stream`. |
| `tests/test_multi_tenant.py` | **Create** | Automated test suite for multi-tenant lifecycle, classes, sections, and invites. |

---

### 7.3 Backward Compatibility Guarantees

1. **Existing Student Accounts:**
   The startup migration in `app/db/migration.py` reads `storage/users.json` and inserts existing records into SQLite. Existing PBKDF2 salts and hashes are preserved exactly; students can log in immediately with their existing passwords.
2. **Self-Study Unjoined Mode:**
   Students without an institutional affiliation (`institution_id = None`) continue to have full access to NCERT textbook Q&A for their enrolled grade. The system does not force users to join an institution to use the core assistant.
3. **Parental Controls & PIN Protection:**
   The parental controls subsystem (`app/parental/`) continues reading and writing to `storage/parental_config.json`. Parental PIN authentication remains fully independent and unaffected by school membership.
4. **Offline & Edge Capability:**
   SQLite is embedded in Python's standard library. No Docker daemon, external database process, or cloud connectivity is required.
5. **Existing Unit Test Preservation:**
   Because `app/auth/models.py` and `app/auth/routes.py` retain compatible signatures, existing unit tests (`tests/test_auth.py`, `tests/test_api.py`) continue passing with 100% success rate.

---

### 7.4 Comprehensive Automated Test Plan

To guarantee system stability, the automated test suite will execute the following validation matrix:

```python
# Test Verification Suite Outline (tests/test_multi_tenant.py)

def test_startup_migration_from_users_json():
    """Verify legacy storage/users.json is imported into SQLite with role='student'."""

def test_admin_registration_without_grade():
    """Verify Org Admin can register with grade=None and receive valid JWT."""

def test_create_institution_with_demo_id():
    """Verify Org Admin can provision an institution using a valid Demo Verification ID."""

def test_duplicate_demo_id_rejected():
    """Verify duplicate Demo Verification ID raises HTTP 409 Conflict."""

def test_class_and_section_creation_hierarchy():
    """Verify Admin can create Class 10 and Section A under their institution."""

def test_dedicated_lecturer_invite_link_generation():
    """Verify Admin can generate a dedicated Lecturer invite link."""

def test_dedicated_student_invite_link_generation():
    """Verify Admin can generate a dedicated Student invite link bound to Class 10-A."""

def test_lecturer_invite_acceptance_flow():
    """Verify redeeming Lecturer invite promotes user to 'lecturer' role."""

def test_student_invite_acceptance_flow():
    """Verify redeeming Student invite enrolls user in Section A and updates JWT."""

def test_lecturer_subject_tagging():
    """Verify Lecturer can update subject tags (e.g. Science, Physics)."""

def test_class_advisor_assignment():
    """Verify Admin can assign Lecturer as Class Advisor for Section A."""

def test_advisor_collision_rejected():
    """Verify assigning a second advisor to Section A raises HTTP 409 Conflict."""

def test_student_grade_isolation_enforced():
    """Verify Class 10 student is forbidden (403) from accessing Class 5 textbooks."""

def test_lecturer_multi_grade_access_allowed():
    """Verify Lecturer can query Class 10 and Class 5 textbooks for authorized subjects."""

def test_enforce_grade_fastapi_depends_fixture_safety():
    """Verify enforce_grade does not crash with AttributeError when user is Depends instance."""
```

---

## 8. Conclusion & Sign-Off

This document provides the complete, authoritative architecture and detailed implementation plan for integrating Google Classroom-style multi-tenant school organizations and tiered RBAC into the NCERT Textbook Assistant.

By combining:
- **SQLite in WAL mode** with **SQLAlchemy 2.x** for process-safe concurrency and relational integrity,
- An **extended PyJWT schema** supporting hybrid zero-latency streaming and live DB administrative resolution,
- **Dedicated role-specific invite links** eliminating privilege escalation risks,
- Rich **Lecturer Profiles** with subject tagging and Class Advisor designations, and
- A modular **React 18 + Vite** client architecture with frosted-glass styling,

the NCERT Textbook Assistant achieves enterprise-ready educational collaboration while preserving complete backward compatibility with existing single-student and parental workflows.
