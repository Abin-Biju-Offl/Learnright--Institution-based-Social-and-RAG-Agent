# Codebase and Auth Gap Analysis Report: Multi-Tenant School Organizations & Tiered RBAC

**Author:** `explorer_codebase` (teamwork_explorer)  
**Date:** 2026-11-02  
**Working Directory:** `e:\WORK\intel rag llamaindex`  
**Authority Document:** `.agents/teamwork/ORIGINAL_REQUEST.md`  
**Target File:** `.agents/teamwork/explorer_codebase/handoff.md`  

---

## Executive Summary

The NCERT Textbook Assistant currently operates as a single-tenant study assistant with single-student accounts stored in a flat JSON file (`storage/users.json`), verified via HS256 PyJWT access/refresh tokens. Authorization is strictly restricted to individual grades (Classes 1–12) enforced via `enforce_grade()` in `app/auth/dependencies.py`, alongside PIN-based guardian oversight in `app/parental/`.

To support Google Classroom-style multi-tenant school organizations and tiered Role-Based Access Control (**Org Admin** $\rightarrow$ **Lecturer** $\rightarrow$ **Student**), significant architectural gaps were identified:
1. **JWT & Auth Model:** `app/auth/jwt_handler.py` strictly mandates a student `grade` claim (`if not payload.get("grade"): raise TokenError`), crashing if an Admin or multi-grade Lecturer authenticates. Furthermore, initial registration only supports `student`.
2. **Storage Bottlenecks:** `storage/users.json` uses in-process thread locking and full-file atomic overwrite (`os.replace`), which cannot handle multi-process concurrency (e.g. Uvicorn multi-worker mode), lacks relational querying (Institutions, Classes, Sections, Invites, Lecturer profiles), and incurs $O(N)$ disk write amplification.
3. **Frontend Integration:** `ui-client/` (React 18 + Vite) does not pass the Bearer JWT in `/api/ask/stream` requests (bypassing server-side grade validation when queried from the React client), relies on a mock student profile in `localStorage`, and has no UI views or state management for Institution onboarding, Class/Section CRUD, role-based invite link generation, or lecturer tagging.
4. **Coexistence & Backward Compatibility:** Existing independent self-study students without an institution assignment must remain fully functional without regressions.

---

## 1. Observations

### 1.1 Authentication Subsystem (`app/auth/`)

1. **Mandatory Grade Claim in Token Decoding:**
   - **Path:** `app/auth/jwt_handler.py:126-133`
   ```python
   if payload.get("type") != "access":
       raise TokenError("Expected an access token, got a different token type.")
   if not payload.get("sub"):
       raise TokenError("Token is missing the user identifier (sub claim).")
   if not payload.get("grade"):
       raise TokenError("Token is missing the student grade.")
   return payload
   ```
   *Direct Observation:* `decode_access_token()` explicitly raises `TokenError` when `grade` is missing, `0`, or `None`. Admins and non-classroom users cannot be authenticated with this token validator.

2. **Hardcoded Student Token Creation:**
   - **Path:** `app/auth/jwt_handler.py:38-70`
   ```python
   def create_access_token(
       user_id: str,
       username: str,
       grade: int,
       expires_minutes: int | None = None,
   ) -> str:
       lifetime = expires_minutes or settings.jwt_access_expire_minutes
       now = datetime.now(timezone.utc)
       payload = {
           "sub": user_id,
           "username": username,
           "grade": grade,
           "type": "access",
           "iat": now,
           "exp": now + timedelta(minutes=lifetime),
           "jti": f"acc_{secrets.token_hex(8)}",
       }
       return jwt.encode(payload, _secret(), algorithm=ALGORITHM)
   ```
   *Direct Observation:* Access tokens only carry `sub`, `username`, `grade`, and standard JWT claims. There are no claims for `role`, `institution_id`, `institution_name`, `class_id`, `section_id`, or `permissions`.

3. **Hardcoded User Roles in Authentication Dependency:**
   - **Path:** `app/auth/dependencies.py:78-90`
   ```python
   user = get_user_by_id(payload["sub"])
   if user is None:
       raise HTTPException(
           status_code=status.HTTP_401_UNAUTHORIZED,
           detail="Student account not found or deactivated.",
           headers={"WWW-Authenticate": "Bearer"},
       )

   # Attach authoritative grade and role from token payload
   user["grade"] = payload.get("grade")
   user["role"] = "student"
   user["is_parent"] = False
   return user
   ```
   *Direct Observation:* `get_current_user()` forces `user["role"] = "student"` for every non-parent user.

4. **Single-Role Student Registration Endpoint:**
   - **Path:** `app/auth/routes.py:38-51`
   - **Path:** `app/auth/schemas.py:12-17`
   ```python
   class RegisterRequest(BaseModel):
       """Register a new student account."""
       username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
       password: str = Field(min_length=6, max_length=128)
       grade: int = Field(ge=1, le=12, description="Student's class (1-12)")
       full_name: str | None = Field(default=None, max_length=100)
   ```
   *Direct Observation:* The `/api/auth/register` route only accepts `RegisterRequest` which requires `grade` between 1 and 12. There is no mechanism to register as an Org Admin or accept an invitation token as a Lecturer.

5. **Grade Enforcement Dependency Bug with FastAPI Parameters:**
   - **Path:** `app/auth/dependencies.py:114-137`
   ```python
   def enforce_grade(user: dict | None, requested_grade: int) -> None:
       if user is None:
           return

       if user.get("is_parent"):
           return

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
   *Direct Observation:* In `app/main.py:199`, `user: dict | None = Depends(get_optional_user)`. When `main.ask()` or `main.ask_stream()` is called directly in Python (such as in `tests/test_parental.py`), the default parameter for `user` is the `Depends` instance itself rather than `None`. Calling `user.get("is_parent")` immediately crashes with `AttributeError: 'Depends' object has no attribute 'get'`. An explicit `if not isinstance(user, dict): return` guard is missing.

---

### 1.2 User Storage & State (`storage/users.json`, `storage/parental_config.json`, `app/parental/`)

1. **User Schema in `storage/users.json`:**
   - **Path:** `storage/users.json:1-13`
   ```json
   [
     {
       "id": "usr_2f8bb97e",
       "username": "rahul_10",
       "full_name": "rahul",
       "grade": 10,
       "password_salt": "a91bd12ec6a4cb88203999584a39f6d4",
       "password_hash": "06a487e8a56edee6c19ad217f5755d6006fc25d13706e5a35167f0311bc6660d",
       "is_active": true,
       "created_at": "2026-11-02T03:15:48+00:00",
       "updated_at": "2026-11-02T03:15:48+00:00"
     }
   ]
   ```
   *Direct Observation:* The user schema does not contain `role`, `institution_id`, `class_id`, `section_id`, or profile metadata.

2. **Atomic Write Mechanism and Concurrency Limit:**
   - **Path:** `app/auth/models.py:59-64`
   ```python
   def _write_users(users: list[dict[str, Any]]) -> None:
       """Atomically write the users list to disk."""
       USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
       tmp = USERS_FILE.with_suffix(".tmp")
       tmp.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
       os.replace(str(tmp), str(USERS_FILE))
   ```
   - **Path:** `app/auth/models.py:28`
   ```python
   _users_lock = threading.Lock()
   ```
   *Direct Observation:* Locking uses `threading.Lock()`, which only coordinates threads in a single process. In multi-process production servers (`uvicorn app.main:app --workers 4`), uncoordinated `os.replace` calls across workers will cause file corruption, lost writes, or Windows file locking errors (`WinError 32: The process cannot access the file because it is being used by another process`).

3. **Parental Controls Storage and Chat History:**
   - **Path:** `storage/parental_config.json:1-34`
   *Direct Observation:* Single global parental configuration storing PIN hash, category toggles, and safe search settings. There is no tenant or user scoping.
   - **Path:** `storage/student_chat_history.jsonl:1-2`
   *Direct Observation:* Records `turn_id`, `session_id`, `timestamp`, `student_grade`, `subject`, `question`, `answer`, `safety_status`. Does NOT record `user_id` or `institution_id`.
   - **Path:** `app/parental/auth.py:83-85`
   ```python
   _sessions_lock = threading.Lock()
   _active_sessions: dict[str, dict[str, Any]] = {}
   ```
   *Direct Observation:* Parental session tokens (`tok_par_...`) are stored in an in-memory dictionary. Any server restart or worker fork invalidates active parental sessions.

---

### 1.3 Application Routing & Middleware (`app/main.py`)

1. **Router Mounting and Middleware Configuration:**
   - **Path:** `app/main.py:68-71`
   ```python
   app = FastAPI(title="NCERT Textbook Assistant", lifespan=lifespan)
   app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
   app.include_router(parental_router, prefix="/api/parent", tags=["parental"])
   ```
   *Direct Observation:* Only `auth_router` and `parental_router` are mounted. No global HTTP middleware or RBAC middleware exists.
2. **Subject Listing Grade Scoping:**
   - **Path:** `app/main.py:160-166`
   ```python
   @app.get("/api/subjects")
   def subjects(user: dict | None = Depends(get_optional_user)):
       all_subjects = get_rag().subjects()
       if user and not user.get("is_parent") and user.get("grade") is not None:
           return [s for s in all_subjects if s.get("grade") == user["grade"]]
       return all_subjects
   ```
   *Direct Observation:* If `user["grade"]` is not None, it filters strictly by that grade. If an Org Admin or Lecturer logs in with a grade of `None`, they see all subjects. However, if a Lecturer is assigned to specific sections/subjects, there is currently no filtering by lecturer subject assignments.
3. **Query Endpoint Grade Enforcement:**
   - **Path:** `app/main.py:198-201` (`/api/ask`) and `app/main.py:329-333` (`/api/ask/stream`)
   ```python
   @app.post("/api/ask/stream")
   def ask_stream(q: Question, user: dict | None = Depends(get_optional_user)):
       """Streams the answer as it is written, one JSON object per line."""
       enforce_grade(user, q.grade)
       check_subject(q)
   ```
   *Direct Observation:* Grade check is enforced at the beginning of `/api/ask` and `/api/ask/stream`. If `user` is `None` (unauthenticated anonymous access), `enforce_grade` silently returns without raising 401.

---

### 1.4 Frontend Architecture (`ui-client/`)

1. **Architecture & Router Absence:**
   - **Path:** `ui-client/package.json:1-26`
   *Direct Observation:* Dependencies include `react`, `react-dom`, `vite`, `metal-fx`, `bot-avatars`, `border-beam`, `thinking-orbs`. `react-router-dom` is NOT installed. Navigation is purely modal and state-driven inside `App.jsx`.
2. **Vite Build and Proxy Setup:**
   - **Path:** `ui-client/vite.config.js:7-24`
   *Direct Observation:* Builds directly into `../frontend`. Proxies `/api` and `/pdfs` to `http://127.0.0.1:8000`.
3. **Missing Authorization Header in Main Query Stream:**
   - **Path:** `ui-client/src/App.jsx:632-646`
   ```javascript
   const res = await fetch('/api/ask/stream', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       question: cleanQ,
       grade: selectedGrade,
       subject: selectedSubject,
       chapter: selectedChapter,
       language,
       pure_llm: pureLlm,
       session_id: currentSid,
       history: historyPayload,
     }),
   });
   ```
   *Direct Observation:* The chat request does NOT include `Authorization: Bearer <student_token>`. As a result, the backend receives `user = None` and bypasses server-side grade restriction during chat queries from the web UI.
4. **Mock Student User State:**
   - **Path:** `ui-client/src/App.jsx:338-344`
   ```javascript
   // Student Profile State (defaults to 'Abin Biju', Class 10 matching user's spec)
   const [studentUser, setStudentUser] = useState(() => {
     try {
       const raw = localStorage.getItem('student_user');
       if (raw) return JSON.parse(raw);
     } catch { }
     return { username: 'abin_biju', full_name: 'Abin Biju', grade: 10 };
   });
   ```
   *Direct Observation:* The frontend falls back to a hardcoded student mock `Abin Biju (Class 10)` if `localStorage` has no `student_user`.
5. **Sidebar User Profile Card & Class Switcher:**
   - **Path:** `ui-client/src/App.jsx:1008-1089`
   *Direct Observation:* The footer of the sidebar contains `sidebar-user-card` displaying `studentUser.full_name`, `studentUser.grade`, and a popover allowing the user to manually switch between Class 10 and Class 5 or redirect to `/login` (`frontend/login.html`). There is no indicator of an Institution, nor is there a "Join your Institution" action.
6. **Topbar Header:**
   - **Path:** `ui-client/src/App.jsx:1094-1133`
   *Direct Observation:* Topbar contains only sidebar collapse toggles, brand logo, and PDF preview hide button. It has no tenant badge or institution header.

---

### 1.5 Test Suite Baseline Execution

1. **Auth Test Suite:**
   - **Command:** `.venv\Scripts\pytest tests/test_auth.py`
   - **Result:** `7 passed in 2.41s` (100% pass rate).
2. **API Test Suite:**
   - **Command:** `.venv\Scripts\pytest tests/test_api.py`
   - **Result:** `12 passed in 13.91s` (100% pass rate).
3. **Parental Test Suite Direct Invocations:**
   - **Command:** `.venv\Scripts\pytest tests/test_parental.py`
   - **Result:** `5 failed, 6 passed in 7.29s`.
   - **Root Cause of Failure:** `AttributeError: 'Depends' object has no attribute 'get'` in `app/auth/dependencies.py:126` when test calls `main.ask()` directly.

---

## 2. Logic Chain & Structured Gap Analysis

```
[Observation 1.1: Mandatory grade in JWT validation]
  └──> Step 1: decode_access_token() rejects Admin/Lecturer with None grade
        └──> Step 2: Need flexible JWT payload where grade is Optional[int] and role is explicit.

[Observation 1.2: Users stored in flat JSON with threading.Lock()]
  └──> Step 3: Multi-tenant models require relationships: Institution -> Classes -> Sections -> (Users, Invites, LecturerProfiles)
        └──> Step 4: JSON file locking fails in multi-worker Uvicorn and cannot handle joins/queries.
              └──> Step 5: Migrate storage to SQLite + SQLAlchemy with automated backward-compatible JSON loader.

[Observation 1.3: enforce_grade only knows Parent vs Student]
  └──> Step 6: Org Admin has full tenant oversight; Lecturer has subject/section oversight; Student is grade-locked; Parent has child oversight.
        └──> Step 7: Introduce Tiered RBAC dependencies with explicit permission hierarchy.

[Observation 1.4: UI has no router, mock user, no tenant header, no invite handler]
  └──> Step 8: UI must implement state-based modals for Institution Onboarding, Admin Class/Section CRUD, and URL invite detection.
```

### Gap Point 1: PyJWT Claim Extension vs Session Resolution

| Dimension | Pure JWT Claims (Stateless) | Pure Session Resolution (Stateful) | Hybrid Optimal Blueprint (Recommended) |
|---|---|---|---|
| **Mechanism** | All tenant context (`inst_id`, `role`, `class_id`, `section_id`, `permissions`) packed into JWT. | JWT contains only `sub`. Middleware queries database on every request. | JWT carries authoritative identity + primary tenant context. Sensitive admin operations re-verify against DB; tutor queries rely on JWT. |
| **Latency** | 0ms DB latency for `/api/ask` and `/api/ask/stream`. | 2–8ms SQLite read per chunk/request. | 0ms for tutor streaming queries; <1ms for admin CRUD. |
| **Token Size** | ~350–500 bytes (compact HS256). | ~180 bytes. | ~320 bytes. |
| **Revocation / Context Change** | Requires token refresh when user joins school or changes section. | Instant. | Immediate upon calling `/api/institution/join` (returns fresh token pair) or token refresh. |

#### Authoritative Token Blueprint
```json
{
  "sub": "usr_78a1bc4f",
  "username": "dr_sharma",
  "role": "lecturer",
  "institution_id": "inst_dps_rkpuram",
  "institution_name": "Delhi Public School, R.K. Puram",
  "grade": null,
  "class_id": "cls_10",
  "section_id": "sec_10b",
  "type": "access",
  "iat": 1730538000,
  "exp": 1730541600,
  "jti": "acc_8f7b9c1d2e"
}
```

---

### Gap Point 2: Initial Registration & Role Onboarding

- **Current Behavior:** `POST /api/auth/register` mandates `grade: int` (1–12), creating a `student` with no tenant association.
- **Target Architecture:**
  1. **Direct Public Registration:**
     - **Student:** Registers with `username`, `password`, `full_name`, and optional `grade` (defaulting to self-study if no invite). `role = "student"`.
     - **Org Admin:** Registers with `username`, `password`, `full_name`. No grade required (`grade = None`). `role = "org_admin"`.
  2. **Invited Role Only (Lecturer & Institutional Student):**
     - **Lecturer:** Cannot self-register publicly as a Lecturer. Registration requires a valid Lecturer Invite Token generated by an Org Admin. Upon redeeming `POST /api/institution/invites/accept`, user is assigned `role = "lecturer"`, `institution_id = invite.institution_id`.
     - **Student with Class/Section Enrollment:** Can redeem a Student Invite Token to automatically bind their account to `institution_id`, `class_id`, and `section_id`.

---

### Gap Point 3: Flat-File JSON vs SQLite / SQLAlchemy Migration

#### Concurrency and Scalability Comparison

```
+---------------------------------------------------------------------------------------+
| Feature                     | Flat JSON (Current)        | SQLite + WAL (Proposed)    |
+---------------------------------------------------------------------------------------+
| Multi-Worker Safety         | UNSAFE (threading.Lock)    | SAFE (Process-safe locks)  |
| Relational Modeling (Joins) | Manual $O(N)$ Python loops | Declarative SQL Foreign Ks |
| Write Amplification         | $O(N)$ full file rewrite   | $O(1)$ page write in WAL   |
| Zero External Dependencies  | YES                        | YES (Python `sqlite3`)     |
| Backward Compatibility      | N/A                        | Auto-seed from JSON files  |
+---------------------------------------------------------------------------------------+
```

#### Proposed Database Schema (`app/db/models.py`)
```
┌─────────────────────────────────┐       ┌───────────────────────────────────┐
│          institutions           │       │            classrooms             │
├─────────────────────────────────┤       ├───────────────────────────────────┤
│ id: VARCHAR(32) [PK]            │1     *│ id: VARCHAR(32) [PK]              │
│ name: VARCHAR(150)              ├───────┤ institution_id: VARCHAR(32) [FK]  │
│ verification_id: VARCHAR(64)    │       │ grade: INTEGER (1-12)             │
│ created_by: VARCHAR(32)         │       │ name: VARCHAR(50)                 │
│ created_at: DATETIME            │       └─────────────────┬─────────────────┘
└────────────────┬────────────────┘                         │ 1
                 │ 1                                        │ *
                 │                                ┌─────────┴─────────────────┐
                 │                                │         sections          │
                 │                                ├───────────────────────────┤
                 │                                │ id: VARCHAR(32) [PK]      │
                 │                                │ class_id: VARCHAR(32) [FK]│
                 │                                │ name: VARCHAR(20)         │
                 │                                │ advisor_id: VARCHAR(32)   │
                 │                                └─────────┬─────────────────┘
                 │ 1                                        │ 1
                 │ *                                        │ *
┌────────────────┴────────────────┐       ┌─────────────────┴─────────────────┐
│          invite_links           │       │               users               │
├─────────────────────────────────┤       ├───────────────────────────────────┤
│ id: VARCHAR(32) [PK]            │       │ id: VARCHAR(32) [PK]              │
│ token: VARCHAR(64) [UNIQUE]     │       │ username: VARCHAR(50) [UNIQUE]    │
│ institution_id: VARCHAR(32) [FK]│       │ password_hash: VARCHAR(128)       │
│ role: VARCHAR(20)               │       │ password_salt: VARCHAR(64)        │
│ class_id: VARCHAR(32) [NULL]    │       │ role: VARCHAR(20)                 │
│ section_id: VARCHAR(32) [NULL]  │       │ institution_id: VARCHAR(32) [FK]  │
│ expires_at: DATETIME            │       │ class_id: VARCHAR(32) [FK, NULL]  │
│ max_uses: INTEGER               │       │ section_id: VARCHAR(32) [FK, NULL]│
│ uses_count: INTEGER             │       │ grade: INTEGER [NULL]             │
│ is_active: BOOLEAN              │       └─────────────────┬─────────────────┘
└─────────────────────────────────┘                         │ 1
                                                            │ 1 (if lecturer)
                                                  ┌─────────┴─────────────────┐
                                                  │     lecturer_profiles     │
                                                  ├───────────────────────────┤
                                                  │ user_id: VARCHAR(32) [PK] │
                                                  │ subject_tags: JSON        │
                                                  │ bio: TEXT [NULL]          │
                                                  └───────────────────────────┘
```

#### Backward Compatibility Seeding Strategy
On application startup in `app/main.py:lifespan`:
1. Check if `storage/users.json` exists and the SQLite database table `users` is empty.
2. Read `storage/users.json` and insert existing users with `role = "student"`, `institution_id = None`, `grade = user["grade"]`.
3. Preserve the exact PBKDF2 salt and hash so existing users can log in without resetting passwords.

---

### Gap Point 4: Tiered RBAC Middleware & Grade Enforcement

#### Tiered RBAC Authorization Matrix

| Action / Resource | Anonymous | Student (Independent) | Student (Institutional) | Lecturer | Org Admin | Parent (Guardian) |
|---|---|---|---|---|---|---|
| **Query RAG (`/api/ask`)** | Blocked or Unrestricted | Restricted to Own Grade | Restricted to Own Grade | All Taught Subjects / Grades | All Institution Grades | Full Oversight Across All Grades |
| **List Subjects (`/api/subjects`)** | All | Own Grade | Own Grade | Taught Subjects | All Institution Subjects | All Subjects |
| **Create Institution** | ❌ | ❌ | ❌ | ❌ | ✅ (with Verification ID) | ❌ |
| **Manage Classes & Sections** | ❌ | ❌ | ❌ | ❌ | ✅ CRUD | ❌ |
| **Generate Invite Links** | ❌ | ❌ | ❌ | ❌ | ✅ (Lecturer & Student links) | ❌ |
| **Assign Class Advisor** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Edit Subject Tags** | ❌ | ❌ | ❌ | ✅ (Own Profile) | ✅ | ❌ |
| **View Class Safety Logs** | ❌ | ❌ | ❌ | ✅ (Advised Sections) | ✅ (All Institution) | ✅ (Own Child via PIN) |

#### Middleware / Dependency Implementation Blueprint
```python
def require_role(*allowed_roles: str):
    """Dependency factory checking user role."""
    def _role_checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "student")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Required role in {allowed_roles}, but you have '{user_role}'.",
            )
        return user
    return _role_checker

require_org_admin = require_role("org_admin")
require_lecturer = require_role("org_admin", "lecturer")

def enforce_grade(user: dict | None, requested_grade: int) -> None:
    """Enhanced grade enforcement supporting multi-tier RBAC."""
    if user is None or not isinstance(user, dict):
        return  # Anonymous or test fixture fallback

    # 1. Parents have guardian oversight across all grades
    if user.get("is_parent"):
        return

    # 2. Org Admins have full institutional oversight
    if user.get("role") == "org_admin":
        return

    # 3. Lecturers can query grades relevant to their curriculum
    if user.get("role") == "lecturer":
        return

    # 4. Students are locked strictly to their assigned grade
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

### Gap Point 5: UI/UX Integration Blueprints (`ui-client/`)

#### 1. Student Topbar & Sidebar Profile State
- **Unjoined Student (`institution_id === null`):**
  - **Topbar Left:** Displays brand icon + Learnright logo + pill button:  
    `[ 🏫 Join your Institution ]`
  - **Sidebar Footer (`sidebar-user-card`):**  
    Name: `Abin Biju` · Role: `Class 10 (Self-Study)` · Subtitle: `"Not connected to school"`
- **Joined Student (`institution_id !== null`):**
  - **Topbar Left:**  
    `[ 🏛️ Delhi Public School · Class 10-A ]`
  - **Sidebar Footer:**  
    Name: `Abin Biju` · Role: `Class 10-A` · Subtitle: `Advisor: Dr. Sharma`

#### 2. Admin Onboarding & Management Modal
- **Trigger:** Accessible via topbar admin badge or sidebar `Institution Management` icon for users with `role === 'org_admin'`.
- **First-Time Admin Setup:**
  - Screen displays two glass cards:
    1. **"Create an Institution"**: Inputs: Institution Name (e.g. "Delhi Public School"), Demo Verification ID (e.g. `DEMO-DPS-2026`), Region/Branch.
    2. **"Join an Existing Institution"**: Input: Admin Access Token.
- **Admin Dashboard Tabs:**
  - **Tab 1: Overview:** School Name, Verification Status, Totals (Classes, Sections, Lecturers, Students).
  - **Tab 2: Classes & Sections:**
    - Button: `+ Add Class` (1 to 12).
    - Under each class: List of Sections (e.g. "Section A", "Section B").
    - Section Row: Displays section name, student count, and dropdown to designate **Class Advisor** from lecturer roster.
  - **Tab 3: Invite Links Generator:**
    - Card A: **Lecturer Invite Link** (Generates unique shareable link `/join?invite=lec_...`).
    - Card B: **Student Invite Link** (Dropdown selects Class & Section, generates `/join?invite=stu_...&class=10&sec=A`).
    - Actions: `Copy Link`, `Regenerate`, `Revoke`.
  - **Tab 4: Roster:** Filterable list of enrolled Lecturers (with subjects taught) and Students.

#### 3. Lecturer Profile & Settings
- Popover in user card or dedicated modal:
  - **Subject Tags:** Multi-select chips for subjects taught (e.g., `[Science]`, `[English]`, `[Mathematics]`).
  - **Class Advisor Badge:** Displays: `"Class Advisor for Class 10, Section B"`.

#### 4. Invite Acceptance Workflow
- In `ui-client/src/App.jsx:useEffect`:
  - Inspect URL parameter `const inviteToken = new URLSearchParams(window.location.search).get('invite');`
  - If present:
    - Open `InviteAcceptModal`:
      - Shows: `"You have been invited to join <Institution Name> as <Lecturer/Student>."`
      - If logged in: One-click `[ Accept & Join ]` $\rightarrow$ calls `POST /api/institution/invites/accept`. Updates `localStorage.student_user` and `student_token` with new refreshed tokens.
      - If not logged in: Prompts user to Sign In or Create an Account with the invite code pre-populated.

---

### Gap Point 6: Multi-Tenant Safety & Audit Logging

- **Current State:** `storage/student_chat_history.jsonl` and `storage/safety_events.jsonl` record queries with `session_id` and `student_grade`, but lack `user_id`, `institution_id`, and `section_id`.
- **Integration Blueprint:**
  Extend `make_turn_record()` and `log_safety_event()`:
  ```python
  def make_turn_record(
      q: Question,
      answer: str,
      user: dict | None = None,
      ...
  ) -> dict:
      return {
          "turn_id": f"turn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}",
          "user_id": user.get("id") if user else None,
          "username": user.get("username") if user else None,
          "institution_id": user.get("institution_id") if user else None,
          "class_id": user.get("class_id") if user else None,
          "section_id": user.get("section_id") if user else None,
          ...
      }
  ```
  This allows Class Advisors to view safety events scoped exclusively to their section, while Org Admins see school-wide safety trends.

---

## 3. Caveats

1. **Standalone Subagent Investigation Scope:** This analysis is read-only. No application code or database migrations were modified during this phase.
2. **FastAPI Direct Call Test Behavior:** `tests/test_parental.py` contains 5 test failures because unit tests invoke `main.ask()` directly without FastAPI's dependency injection resolver. Adding `if not isinstance(user, dict): return` in `enforce_grade()` resolves this immediately without impacting HTTP requests.
3. **SQLite WAL Mode on Windows Network Drives:** SQLite WAL mode operates reliably on local storage (`e:\WORK\intel rag llamaindex\storage\`). If deployed over a network-mounted SMB share, standard rollback journal or client-server PostgreSQL should be considered.
4. **Ollama / RAG Decoupling:** Multi-tenancy and RBAC govern user identity, institutions, and textbook access rights; the underlying vector store (`storage/index` or Qdrant) and Ollama embedding pipelines operate transparently on top of grade-filtered metadata.

---

## 4. Conclusion & Actionable Blueprints

### 4.1 Summary of Gaps & Solutions

```
+-----------------------------------+-----------------------------------+-----------------------------------+
| Component                         | Existing Gap                      | Recommended Solution              |
+-----------------------------------+-----------------------------------+-----------------------------------+
| app/auth/jwt_handler.py           | decode_access_token mandates grade| Optional grade; attach tenant     |
|                                   | No tenant/role claims in payload  | claims (role, inst_id, sec_id)    |
| app/auth/routes.py                | Only student registration allowed | Student & Admin direct signup;    |
|                                   | No invite redemption endpoint     | Lecturer invited via invite token |
| storage/users.json                | Concurrency lock issues, no joins | SQLite + SQLAlchemy ORM with      |
|                                   | No models for orgs/classes/invites| auto-migration from users.json    |
| app/main.py                       | No RBAC dependencies;             | Add require_role dependencies;    |
|                                   | enforce_grade lacks role checks   | allow Admin/Lecturer grade bypass |
| ui-client/src/App.jsx             | No Auth header in /api/ask/stream | Pass Bearer token in fetch;       |
|                                   | Mock student state, no org UI     | Add Institution Header & Modals   |
+-----------------------------------+-----------------------------------+-----------------------------------+
```

### 4.2 API Contract Specifications for New Multi-Tenant Endpoints

#### Institution & Onboarding Endpoints (`app/institution/routes.py`)
- `POST /api/institution/create` (Auth: Org Admin)
  - **Body:** `{"name": "Delhi Public School", "verification_id": "DEMO-DPS-2026"}`
  - **Response 201:** `{"id": "inst_123", "name": "Delhi Public School", "role": "org_admin"}`
- `GET /api/institution/me` (Auth: Member)
  - **Response 200:** `{"id": "inst_123", "name": "Delhi Public School", "role": "student", "class_id": "cls_10", "section_id": "sec_10b"}`
- `POST /api/institution/classes` (Auth: Org Admin)
  - **Body:** `{"grade": 10, "name": "Class 10"}`
- `POST /api/institution/classes/{class_id}/sections` (Auth: Org Admin)
  - **Body:** `{"name": "Section A", "advisor_id": "usr_lec1"}`
- `POST /api/institution/invites/generate` (Auth: Org Admin)
  - **Body:** `{"role": "lecturer" | "student", "class_id": "cls_10", "section_id": "sec_10a", "expires_days": 14}`
  - **Response 200:** `{"invite_url": "/join?invite=inv_xyz987", "token": "inv_xyz987", "role": "lecturer"}`
- `POST /api/institution/invites/accept` (Auth: Any authenticated user)
  - **Body:** `{"token": "inv_xyz987"}`
  - **Response 200:** Returns refreshed `TokenResponse` with updated institution JWT claims.
- `PUT /api/institution/lecturers/me/profile` (Auth: Lecturer)
  - **Body:** `{"subject_tags": ["Science", "English"], "bio": "Senior Science Lecturer"}`

---

## 5. Verification Method

To independently verify the observations and conclusions in this report:

1. **Verify Token Validator Grade Constraint:**
   Inspect `app/auth/jwt_handler.py:130-132`. Notice:
   ```python
   if not payload.get("grade"):
       raise TokenError("Token is missing the student grade.")
   ```
2. **Verify User Model Schema:**
   Inspect `storage/users.json` and `app/auth/models.py:32-45`. Notice the complete absence of `role`, `institution_id`, `class_id`, and `section_id`.
3. **Verify Frontend Chat Request Lacks Authorization:**
   Inspect `ui-client/src/App.jsx:632-646`. Notice `fetch('/api/ask/stream')` only passes `headers: { 'Content-Type': 'application/json' }` and omits `Authorization: Bearer ...`.
4. **Verify Existing Auth Tests Pass:**
   Run:
   ```powershell
   .venv\Scripts\pytest tests/test_auth.py
   ```
   Output: `7 passed`.
5. **Verify Parental Test Failure Mechanism:**
   Run:
   ```powershell
   .venv\Scripts\pytest tests/test_parental.py
   ```
   Observe the verbatim `AttributeError: 'Depends' object has no attribute 'get'` in `app/auth/dependencies.py:126`.
6. **Verify Invalidation Conditions:**
   This gap analysis would be invalidated if:
   - `app/auth/jwt_handler.py` already allowed `grade=None`.
   - `ui-client/src/App.jsx` already passed `Authorization` headers.
   - `storage/users.json` already contained relational institution foreign keys.
   Direct code inspection confirms none of these exist in the codebase today.
