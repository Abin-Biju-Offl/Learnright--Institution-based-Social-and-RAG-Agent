# Parental Controls, Monitoring, and Filtering Architecture Analysis

**Author:** Teamwork Explorer (`teamwork_explorer_parental`)  
**Mission:** Parental Controls, Features, API, and UI in `ui-client/` for the NCERT Textbook Assistant  
**Date:** 2026-10-31  
**Project:** NCERT Textbook Assistant (RAG)  
**Status:** Complete Architectural Specification & Design  

---

## 1. Executive Summary & System Overview

The NCERT Textbook Assistant is designed for Indian school students (Class 5 to Class 10) studying Science, English, and Social Science curricula. While under-18 safety filtering (Requirement R1) prevents inappropriate generation, parents and guardians require active governance, visibility, and customizable guardrails over their child's AI learning environment (Requirement R2).

Parental oversight in an educational AI must satisfy four foundational principles:
1. **Uncompromised Student Privacy vs. Guardian Oversight**: Provide transparent, server-side monitoring of student interactions so parents can review questions, answers, and study habits, without creating an intrusive surveillance barrier that discourages genuine educational curiosity.
2. **Deterministic Security & Tamper Resistance**: A child should not be able to bypass parental controls by clearing browser cookies, using incognito mode, or guessing simple default PINs. Security must include salted cryptographic hashing, progressive brute-force lockout, and in-memory session tokens.
3. **Immediate Visibility into Blocked & Flagged Inquiries**: When a child queries self-harm, cyberbullying, violence, weapons, or adult content, the system must log the incident with rich contextual metadata (triggered category, matched rules, exact query, timestamp) and present it with triage status, parent notes, and crisis helpline resources.
4. **Customizable Filtering Strictness**: Parents have differing standards and children of different ages. A Class 5 student requires strict, gentle language safeguards, whereas a Class 10 student requires full access to NCERT Biology reproduction science (Chapter 7) while maintaining zero-tolerance for explicit or vulgar material. Parents must be able to toggle categories, adjust strictness profiles, and add custom blacklisted keywords (e.g. gambling, specific games, or unapproved topics).

This document establishes the end-to-end architecture for Parental Controls, spanning backend APIs, storage pipelines, security mechanisms, and a Google Gemini-themed React UI in `ui-client/`.

---

## 2. Codebase & UI Architectural Discovery

### 2.1 Frontend Architecture (`ui-client/`)
- **Technology Stack**: React 18 (`react: ^18.3.1`, `react-dom: ^18.3.1`), Vite 5 (`vite: ^5.4.11`), `@vitejs/plugin-react: ^4.3.4`.
- **UI Libraries**: Custom frosted glass Apple/Gemini theme, `metal-fx` (metallic buttons/badges), `border-beam` (animated border glow), `bot-avatars`, `thinking-orbs`.
- **Build & Serving Model**: `vite.config.js` builds into `../frontend/` without clearing previous static assets (`outDir: path.resolve(__dirname, '../frontend')`, `emptyOutDir: false`). During development, Vite dev server (`port: 5173`) proxies `/api` and `/pdfs` to `http://127.0.0.1:8000`. In production, FastAPI serves the compiled React application directly at root `/` via `StaticFiles(directory=ROOT / "frontend", html=True)`.
- **Current State Management (`ui-client/src/App.jsx`)**:
  - Chat sessions and messages are currently held in browser `localStorage` under `ncert-tutor-sessions-v3`.
  - While sufficient for student convenience, **client-only local storage is vulnerable to student clearing, incognito mode, and device switching**. Parental monitoring must be backed by server-side persistence.
- **Visual Design System (`ui-client/src/App.css`)**:
  - Dark theme adhering to Google Gemini Dark System (`#000000` app background, `#131314` sidebar, `#1e1f20` cards, `#18191b` modals).
  - Existing modal infrastructure: `.gemini-modal-overlay` with `backdrop-filter: blur(16px)` and `.gemini-modal-card` with `scaleUp` entrance animation.
  - Sidebar contains quick navigation: Library, Images, Scheduled/Activity, Customise, Videos, Notebooks, and Chat History.

### 2.2 Backend Architecture & Request Handling (`app/`)
- **FastAPI Application (`app/main.py`)**:
  - Ingress endpoints: `POST /api/ask` (synchronous JSON) and `POST /api/ask/stream` (newline-delimited JSON stream `application/x-ndjson`).
  - Request payload: `Question(question, grade, subject, chapter, language, pure_llm, session_id, history)`.
  - Service life cycle: `RAG` instance initialized in `lifespan` context manager, sharing vector store index, LLM instance, and index catalog.
- **Existing Logging & Storage Infrastructure**:
  - `storage/conversation_metrics.jsonl`: Performance telemetry (`total_latency_s`, `tokens_per_second`, `chunks_matched`).
  - `storage/feedback.jsonl`: Student 👍/👎 feedback records.
  - Thread safety: Standard library `threading.Lock` (`metrics_lock`, `feedback_lock`) guarantees atomic file append operations.
- **Identified Gap**:
  - No server-side persistence exists for complete chat transcripts (queries and full assistant answers).
  - No parental endpoints exist for authentication, history retrieval, flagged query review, or filtering settings.

---

## 3. Parental Controls & Features Specification

### 3.1 Authentication & Security Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Parental Authentication Flow                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [Parent Clicks Parental Controls]                                      │
│           │                                                             │
│           ▼                                                             │
│  GET /api/parent/auth/status                                            │
│           │                                                             │
│     ┌─────┴────────────────────────┐                                    │
│     ▼                              ▼                                    │
│  PIN NOT CONFIGURED         PIN CONFIGURED                              │
│     │                              │                                    │
│     ▼                              ▼                                    │
│  Prompt Setup 4-Digit PIN   Prompt Enter 4-Digit PIN                    │
│  (Confirm PIN Entry)               │                                    │
│     │                              ├──► [5 Failed Attempts]             │
│     ▼                              │     └──► 5-Min Lockout (429)       │
│  POST /api/parent/auth/setup       ├──► [8 Failed Attempts]             │
│     │                              │     └──► 15-Min Lockout (429)      │
│     │                              ▼                                    │
│     │                       POST /api/parent/auth/verify                │
│     │                              │                                    │
│     └──────────────┬───────────────┘                                    │
│                    ▼                                                    │
│         Issues Bearer Session Token                                     │
│         (32-Byte Cryptographic Nonce,                                   │
│          Expires after 15 min inactivity)                               │
│                    │                                                    │
│                    ▼                                                    │
│       Opens Parental Control Center                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### A. Cryptographic PIN Storage
- **Standard**: 4-digit to 6-digit numeric PIN (e.g. `1234` or `982143`).
- **Algorithm**: PBKDF2 with HMAC-SHA256, 100,000 iterations, 16-byte cryptographically secure random salt (`secrets.token_bytes(16)`).
- **Storage Format**: `salt_hex$hash_hex` stored in `storage/parental_config.json`.
- **Implementation Guarantee**: No plaintext PIN is ever logged, cached, or returned over the wire. Zero third-party C-extensions required (uses standard library `hashlib` and `secrets`).

#### B. Brute-Force & Denial-of-Service Protection
Curious children will attempt to guess simple parental PINs (`0000`, `1234`, birth years). The backend enforces progressive lockout:
- `1 - 4 Failed Attempts`: Returns `401 Unauthorized` with remaining attempts counter.
- `5 Failed Attempts`: Enforces a **5-minute hard lockout** (`lockout_until = now + 300s`).
- `8+ Failed Attempts`: Enforces a **15-minute hard lockout** (`lockout_until = now + 900s`).
- Lockout state is persisted to `storage/parental_config.json` so server restarts cannot bypass the active timer.

#### C. In-Memory Session Token Management
- When verified, the server generates a high-entropy session token: `token = secrets.token_urlsafe(32)`.
- The token is held in an in-memory session registry with a timestamp of last activity.
- Expiration: Inactivity timeout defaults to 15 minutes (`900` seconds).
- Frontend stores the token in React state / `sessionStorage` (never in `localStorage`), ensuring closing the browser tab instantly locks the parental portal.
- Explicit "Lock / Sign Out" button in UI calls `POST /api/parent/auth/logout`, invalidating the active token immediately.

#### D. Emergency PIN Reset Recovery Key
During initial PIN setup, a 16-character alphanumeric Emergency Recovery Key (e.g., `NCERT-9X4K-7M2Q-B81P`) is generated and presented once to the parent with a copy-to-clipboard action. If the PIN is forgotten, the parent can reset it via `POST /api/parent/auth/reset-pin` using the recovery key.

---

### 3.2 Student Chat History Monitoring System

#### A. Problem Analysis: Client vs. Server History
In the current implementation, chat history resides only in the student's browser `localStorage`. A student can easily clear browser data or use private tabs to obscure inappropriate conversations. To fulfill Requirement R2, a server-side audit logging pipeline is required.

#### B. Server-Side Chat Persistence Pipeline
Every question answered through `POST /api/ask` or `POST /api/ask/stream` is logged to `storage/student_chat_history.jsonl` upon turn completion.

##### Schema: `storage/student_chat_history.jsonl`
```json
{
  "turn_id": "turn_20261031_092144_a1b2",
  "session_id": "c71a3298-9021-4f11-b0e2-8812c3f19101",
  "timestamp": "2026-10-31T12:05:22Z",
  "student_grade": 10,
  "subject": "Science",
  "chapter": 7,
  "language": "English",
  "question": "What is the function of the scrotum in the male reproductive system?",
  "answer": "The testes are located outside the abdominal cavity within the scrotum because sperm formation requires a lower temperature than normal body temperature [1].",
  "sources": [
    {
      "chapter": 7,
      "page": 137,
      "file": "class-10/science/ch07.pdf",
      "score": 0.62
    }
  ],
  "pure_llm": false,
  "found": true,
  "safety_status": "CLEAN",
  "flagged": false,
  "safety_category": null,
  "latency_s": 1.15
}
```

#### C. Parent Chat History Viewer Features
The Parental Portal provides a dedicated "Student Chat History" tab with:
1. **Multi-Faceted Filtering**:
   - Filter by Grade (Class 5, Class 10, All).
   - Filter by Subject (Science, English, Social Science).
   - Filter by Safety Status (`All Conversations`, `Only Flagged / Blocked`, `Only Clean`).
   - Filter by Date Range (`Today`, `Last 7 Days`, `Last 30 Days`, `Custom Range`).
   - Free-text search on question and answer content.
2. **Conversation Thread Explorer**:
   - Conversations grouped by `session_id`.
   - Thread transcript card showing student bubble (left) and tutor answer bubble (right).
   - Visual badges: Green checkmark for verified NCERT citations, Amber alert for Pure LLM answers, Red shield for safety refusals.
3. **Data Export & Privacy Controls**:
   - "Export History" button: Downloads student chat log as clean JSON or formatted PDF/Markdown study report.
   - "Clear Archived History" button: Protected by secondary PIN confirmation to allow parents to reset old records while maintaining system integrity.

---

### 3.3 Flagged & Blocked Queries Review System

#### A. Unified Safety Event Logging
Working in conjunction with the Under-18 Content Taxonomy (from `teamwork_explorer_taxonomy`), every safety violation or custom-blocked query is logged to `storage/safety_events.jsonl`.

##### Schema: `storage/safety_events.jsonl`
```json
{
  "event_id": "evt_20261031_120401_f9c8",
  "timestamp": "2026-10-31T12:04:01Z",
  "session_id": "c71a3298-9021-4f11-b0e2-8812c3f19101",
  "student_grade": 10,
  "subject": "Science",
  "query_text": "How can someone make a crude explosive using fertilizer?",
  "category": "illegal_acts_weapons_drugs",
  "severity": "CRITICAL",
  "matched_rule": "explosives_fertilizer_synthesis",
  "filter_stage": "stage1_fast_regex",
  "action_taken": "BLOCKED_EDUCATIONAL_REFUSAL",
  "refusal_response": "I cannot answer this question. NCERT Textbook Assistant is designed to assist with academic school curriculum topics only. Inquiries regarding weapons, explosives, or hazardous materials are strictly prohibited.",
  "parent_review_status": "PENDING",
  "reviewed_at": null,
  "reviewed_by": null,
  "parent_notes": ""
}
```

#### B. Taxonomy Category Mapping
The review system organizes flags across the 7 established taxonomy categories plus custom blocked terms:
1. `adult_sexual`: Adult / sexual explicit inquiries, pornography, non-curricular anatomy.
2. `violence_gore`: Physical brutality, weapons violence, gore, torture.
3. `self_harm`: Suicide methods, self-harm, crisis phrases (**P0 Priority**).
4. `hate_speech`: Slurs, hate speech, religious/caste discrimination, defamation.
5. `illegal_acts_weapons_drugs`: Illicit substances, weapons fabrication, cyber crimes.
6. `cyberbullying`: Targeted insults, peer harassment, abusive language.
7. `other_inappropriate`: Gambling, extreme profanity, age-inappropriate media.
8. `custom_blocked`: Inquiries triggering parent-defined custom keywords or topics.

#### C. Parental Review & Triage Workflow
- **Sidebar Alert Badge**: When `parent_review_status === 'PENDING'`, a glowing amber/red badge appears next to the Parental Controls button (e.g. `⚠️ 3`).
- **Flagged Inquiries Tab**:
  - Displays list of flagged incidents sorted newest first.
  - Highlighting: Red border for `CRITICAL` (Self-harm, Weapons), Amber border for `HIGH` (Adult, Cyberbullying), Yellow for `MEDIUM`/`LOW`.
  - Details Drawer: Shows exact query, triggered category, timestamp, textbook subject in use, refusal reason, and refusal response delivered to the child.
  - Action Button: **"Mark as Reviewed"** — transitions status from `PENDING` to `REVIEWED`.
  - Notes Input: Allows parent to record an internal note (e.g., *"Discussed with Rohan on Saturday morning; explained why chemistry explosives are hazardous."*).
- **Crisis Helpline Banner**:
  - If a flag belongs to `self_harm`, the review card displays prominent emergency support contact details for Indian national helplines:
    - **Tele-MANAS** (National Mental Health Helpline): `14416` (24x7 Toll-Free)
    - **KIRAN** (Mental Health Rehabilitation Helpline): `1800-599-0019`
    - **CHILDLINE India**: `1098`

---

### 3.4 Configurable Content Filtering Preferences & Custom Restrictions

#### A. Multi-Tier Filtering Configuration
Parents can tailor filtering strictness to match their child's maturity and academic needs.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Content Filtering Configuration                      │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [Preset Profiles]                                                     │
│   (•) Strict Elementary (Class 5 recommended)                          │
│       - Zero tolerance for mature themes                              │
│       - Strict safe language vocabulary                                │
│       - Limits output to 2-4 simple textbook sentences                 │
│                                                                        │
│   ( ) Curriculum Standard (Class 10 recommended)                       │
│       - Permits NCERT Class 10 Biology (Reproduction, Contraception)   │
│       - Permits NCERT English & Social Science (Apartheid, Holocaust)  │
│       - Blocks adult/erotic, vulgarity, violence, self-harm, weapons   │
│                                                                        │
│   ( ) Custom Configuration                                             │
│       - Fine-tune individual category toggles and keywords             │
│                                                                        │
│  [Category Toggles]                                                    │
│   [x] Adult & Sexual Content        (Enforced)                         │
│   [x] Violence & Physical Harm       (Enforced)                         │
│   [LOCKED] Self-Harm & Suicide Crisis(Permanently Active for Safety)   │
│   [x] Hate Speech & Discrimination   (Enforced)                         │
│   [LOCKED] Weapons, Drugs & Illegal  (Permanently Active for Safety)   │
│   [x] Cyberbullying & Harassment     (Enforced)                         │
│   [x] Other Age-Inappropriate Themes (Enforced)                         │
│                                                                        │
│  [Custom Keyword / Topic Blacklist]                                    │
│   Add custom terms: [ e.g. "roblox", "instagram", "gambling" ] [+]    │
│   Tags: [ "vaping" × ] [ "crypto" × ] [ "minecraft cheats" × ]         │
│                                                                        │
│  [Curriculum Biology Protection]                                       │
│   [x] Allow NCERT Class 10 Reproductive Biology (Chapter 7)            │
│       (When disabled, human anatomy questions are politely deferred    │
│        to classroom teacher guidance)                                  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

#### B. Permanent Non-Negotiable Safeguards
For ethical and legal compliance with under-18 safety standards:
- `self_harm` (Suicide, self-injury) cannot be disabled by any setting.
- `illegal_acts_weapons_drugs` (Bomb making, lethal weapons, illicit narcotics) cannot be disabled.
- The UI renders these two toggles with a lock icon and tooltip: *"This safety category is permanently locked to protect child safety."*

#### C. Custom Keyword Blacklist Manager
- Parents can enter specific terms, phrases, or slang they wish to block.
- Normalization: Keywords are lowercased, whitespace-trimmed, and matched via word boundary regex (`\b{keyword}\b`) to avoid accidental false positives.
- If a student query contains any parent-blacklisted term:
  - Query is refused with: *"This topic has been restricted by parental control settings. Please focus on your NCERT textbook lessons."*
  - Logged with `category: "custom_blocked"`.

#### D. Configuration Storage Schema: `storage/parental_config.json`
```json
{
  "version": 1,
  "security": {
    "pin_hash": "b2f483...e91a",
    "pin_salt": "9c14...02df",
    "pin_configured": true,
    "recovery_key_hash": "7a81...3c4e",
    "failed_attempts": 0,
    "locked_until": null,
    "session_timeout_minutes": 15
  },
  "filtering": {
    "strictness_profile": "curriculum_standard",
    "categories": {
      "adult_sexual": true,
      "violence_gore": true,
      "self_harm": true,
      "hate_speech": true,
      "illegal_acts_weapons_drugs": true,
      "cyberbullying": true,
      "other_inappropriate": true
    },
    "allow_ncert_biology_reproduction": true,
    "custom_blocked_keywords": [
      "vaping",
      "crypto",
      "online gambling"
    ],
    "custom_blocked_topics": [
      "social media influencers"
    ],
    "safe_search_level": "strict"
  },
  "notifications": {
    "show_sidebar_badge": true,
    "alert_on_critical_severity": true
  },
  "updated_at": "2026-10-31T12:00:00Z"
}
```

---

## 4. Backend API Specification & Data Models

### 4.1 REST API Endpoints Specification

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/parent/auth/status` | Check if PIN is configured & lockout status | None |
| `POST` | `/api/parent/auth/setup` | Initial setup of parental PIN and recovery key | None (1-time) |
| `POST` | `/api/parent/auth/verify` | Verify PIN, returns 15-minute Bearer token | None |
| `POST` | `/api/parent/auth/change-pin` | Update PIN with current PIN or active token | Bearer Token |
| `POST` | `/api/parent/auth/reset-pin` | Reset PIN using 16-character Emergency Recovery Key | None |
| `POST` | `/api/parent/auth/logout` | Invalidate active session token immediately | Bearer Token |
| `GET` | `/api/parent/overview` | Dashboard summary metrics (counts, rates, activity) | Bearer Token |
| `GET` | `/api/parent/history` | Paginated student chat history with filters | Bearer Token |
| `GET` | `/api/parent/history/{turn_id}` | Detailed conversation turn transcript | Bearer Token |
| `DELETE`| `/api/parent/history` | Clear historical chats (secondary PIN confirmation) | Bearer Token |
| `GET` | `/api/parent/flagged` | List of flagged/refused query alerts | Bearer Token |
| `POST` | `/api/parent/flagged/{event_id}/review` | Mark alert as reviewed with optional parent notes | Bearer Token |
| `GET` | `/api/parent/settings` | Retrieve content filtering preferences | Bearer Token |
| `PUT` | `/api/parent/settings` | Update category toggles, strictness & keywords | Bearer Token |

---

### 4.2 Endpoint Contract Details

#### 1. `GET /api/parent/auth/status`
- **Response `200 OK`**:
  ```json
  {
    "pin_configured": true,
    "is_locked": false,
    "lockout_remaining_seconds": 0,
    "session_active": false
  }
  ```

#### 2. `POST /api/parent/auth/setup`
- **Request Body**:
  ```json
  {
    "pin": "2468",
    "confirm_pin": "2468"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "token": "tok_sec_9f81a7b...",
    "expires_in_seconds": 900,
    "recovery_key": "NCERT-9X4K-7M2Q-B81P"
  }
  ```
- **Error `400 Bad Request`**: PINs do not match, or PIN already configured.

#### 3. `POST /api/parent/auth/verify`
- **Request Body**:
  ```json
  {
    "pin": "2468"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "token": "tok_sec_9f81a7b...",
    "expires_in_seconds": 900
  }
  ```
- **Error `401 Unauthorized`**:
  ```json
  {
    "detail": "Incorrect PIN. 3 attempts remaining.",
    "attempts_remaining": 3
  }
  ```
- **Error `429 Too Many Requests`**:
  ```json
  {
    "detail": "Parental portal locked due to repeated incorrect PIN entries. Try again in 284 seconds.",
    "lockout_remaining_seconds": 284
  }
  ```

#### 4. `GET /api/parent/overview`
- **Headers**: `Authorization: Bearer <token>`
- **Response `200 OK`**:
  ```json
  {
    "total_student_queries": 142,
    "clean_queries": 138,
    "flagged_queries": 4,
    "unreviewed_alerts": 2,
    "safety_compliance_rate_percent": 97.2,
    "active_days_count": 6,
    "top_studied_subjects": [
      {"subject": "Science", "grade": 10, "queries": 88},
      {"subject": "English", "grade": 10, "queries": 34},
      {"subject": "Science", "grade": 5, "queries": 20}
    ],
    "flagged_category_breakdown": {
      "adult_sexual": 1,
      "violence_gore": 0,
      "self_harm": 0,
      "hate_speech": 0,
      "illegal_acts_weapons_drugs": 2,
      "cyberbullying": 1,
      "custom_blocked": 0
    },
    "current_strictness_profile": "curriculum_standard",
    "last_student_activity": "2026-10-31T11:45:10Z"
  }
  ```

#### 5. `GET /api/parent/history`
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**:
  - `limit`: int (default 25, max 100)
  - `offset`: int (default 0)
  - `grade`: int | None (5 or 10)
  - `subject`: str | None ("Science", "English", "Social Science")
  - `flagged_only`: bool (default false)
  - `search`: str | None (keyword query)
  - `date_from`: ISO timestamp | None
  - `date_to`: ISO timestamp | None
- **Response `200 OK`**:
  ```json
  {
    "total": 142,
    "offset": 0,
    "limit": 25,
    "records": [
      {
        "turn_id": "turn_01",
        "session_id": "sess_123",
        "timestamp": "2026-10-31T11:30:00Z",
        "student_grade": 10,
        "subject": "Science",
        "chapter": 6,
        "question": "What is photosynthesis?",
        "answer": "Photosynthesis is the process by which green plants synthesize food using sunlight [1].",
        "safety_status": "CLEAN",
        "flagged": false,
        "sources_count": 1
      }
    ]
  }
  ```

#### 6. `GET /api/parent/flagged`
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**:
  - `status`: str (default `"PENDING"`, options: `"ALL"`, `"PENDING"`, `"REVIEWED"`)
  - `category`: str | None
  - `limit`: int (default 50)
- **Response `200 OK`**:
  ```json
  {
    "total": 4,
    "unreviewed_count": 2,
    "events": [
      {
        "event_id": "evt_20261031_120401_f9c8",
        "timestamp": "2026-10-31T12:04:01Z",
        "session_id": "sess_123",
        "student_grade": 10,
        "subject": "Science",
        "query_text": "How can someone make a crude explosive using fertilizer?",
        "category": "illegal_acts_weapons_drugs",
        "severity": "CRITICAL",
        "matched_rule": "explosives_fertilizer_synthesis",
        "refusal_response": "I cannot answer this question...",
        "parent_review_status": "PENDING",
        "parent_notes": ""
      }
    ]
  }
  ```

#### 7. `POST /api/parent/flagged/{event_id}/review`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "notes": "Discussed laboratory safety rules with student."
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "event_id": "evt_20261031_120401_f9c8",
    "parent_review_status": "REVIEWED",
    "reviewed_at": "2026-10-31T12:10:00Z",
    "parent_notes": "Discussed laboratory safety rules with student."
  }
  ```

#### 8. `GET /api/parent/settings` and `PUT /api/parent/settings`
- **Headers**: `Authorization: Bearer <token>`
- **PUT Request Body**:
  ```json
  {
    "strictness_profile": "curriculum_standard",
    "categories": {
      "adult_sexual": true,
      "violence_gore": true,
      "self_harm": true,
      "hate_speech": true,
      "illegal_acts_weapons_drugs": true,
      "cyberbullying": true,
      "other_inappropriate": true
    },
    "allow_ncert_biology_reproduction": true,
    "custom_blocked_keywords": ["gambling", "vaping", "cheat codes"],
    "custom_blocked_topics": ["social media gossip"],
    "session_timeout_minutes": 15
  }
  ```
- **Response `200 OK`**: Returns updated settings object.

---

### 4.3 Pydantic Models (`app/parental/schemas.py`)

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class PinSetupRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    confirm_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")

class PinVerifyRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")

class ChangePinRequest(BaseModel):
    current_pin: str = Field(min_length=4, max_length=6)
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    confirm_new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")

class ResetPinRequest(BaseModel):
    recovery_key: str = Field(min_length=16, max_length=32)
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    confirm_new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")

class ReviewFlagRequest(BaseModel):
    notes: str = Field(default="", max_length=1000)

class CategorySettings(BaseModel):
    adult_sexual: bool = True
    violence_gore: bool = True
    self_harm: bool = True               # Inviolable locked
    hate_speech: bool = True
    illegal_acts_weapons_drugs: bool = True  # Inviolable locked
    cyberbullying: bool = True
    other_inappropriate: bool = True

class ParentalSettingsUpdate(BaseModel):
    strictness_profile: Literal["strict_elementary", "curriculum_standard", "custom"] = "curriculum_standard"
    categories: CategorySettings = Field(default_factory=CategorySettings)
    allow_ncert_biology_reproduction: bool = True
    custom_blocked_keywords: list[str] = Field(default_factory=list, max_length=100)
    custom_blocked_topics: list[str] = Field(default_factory=list, max_length=50)
    session_timeout_minutes: int = Field(default=15, ge=5, le=120)
```

---

### 4.4 Thread-Safe Persistence Architecture

The parental control subsystem must be robust against concurrent writes and unexpected process interruptions.

```
app/
├── parental/
│   ├── __init__.py           # Package exports
│   ├── auth.py               # PIN hashing, lockout counters, token generation & verification
│   ├── schemas.py            # Pydantic request/response models
│   ├── service.py            # Business logic for history, flagged queries, and settings
│   ├── storage.py            # Thread-safe JSON and JSONL read/write handlers
│   └── routes.py             # FastAPI APIRouter for /api/parent/*
```

#### Thread-Safe Atomic File Operations (`app/parental/storage.py`):
1. **Mutex Locks**:
   - `parental_config_lock = threading.Lock()` protects `storage/parental_config.json`.
   - `chat_history_lock = threading.Lock()` protects `storage/student_chat_history.jsonl`.
   - `safety_events_lock = threading.Lock()` protects `storage/safety_events.jsonl`.
2. **Atomic JSON Updates**:
   When writing `parental_config.json`, the service writes to a temporary file in the same directory (`parental_config.json.tmp`) and renames it atomically (`os.replace`). This guarantees the configuration file can never be corrupted by a power failure or sudden abort.

---

## 5. UI/UX Architecture & Component Design for `ui-client/`

### 5.1 Component Hierarchy in `ui-client/`

```
App.jsx
├── Aside (Gemini Sidebar)
│   ├── GeminiBrand & Toggle
│   ├── NewChatButton
│   ├── NavItems (Library, Images, Scheduled, Customise, Videos, Notebooks)
│   ├── HistoryList & Filter
│   └── SidebarFooter
│       ├── ParentalControlsNavButton (New: Shield/Lock Icon + Alert Badge)
│       ├── StatusBadge
│       └── FooterNote
│
├── Workspace (Main Chat Area)
│   ├── Topbar (Subject selection, Grade pills, Parental Lock Quick Button)
│   ├── MessageFeed
│   └── BottomBar (AppleGlassDropdowns, Ask Input, MetalFx Robot Button)
│
└── Modals
    ├── LibraryModal
    ├── ActivityModal
    ├── CustomiseModal
    ├── VideosModal
    ├── NotebooksModal
    ├── ParentalAuthModal     (New: PIN Entry / Setup / Lockout Timer)
    └── ParentalPortalModal   (New: Tabbed Management Center)
        ├── TabBar (Overview, Chat History, Flagged Alerts, Content Filtering, Security)
        ├── OverviewView
        ├── ChatHistoryView
        ├── FlaggedAlertsView
        ├── ContentFilteringView
        └── SecurityView
```

---

### 5.2 Parental Auth Modal (`ParentalAuthModal.jsx`)
- **Visual Design**:
  - Modal card styled with `.gemini-modal-card`, frosted glass blur, glowing metallic border.
  - Centered Shield icon with subtle Google blue/purple gradient glow.
- **State 1: Initial Setup (First Launch)**
  - Heading: *"Set Parental Controls PIN"*
  - Subtitle: *"Create a 4-digit PIN to monitor student conversations and configure content safety filters."*
  - Two input fields: "Enter 4-digit PIN" and "Confirm 4-digit PIN".
  - On submit: Displays **Emergency Recovery Key** with a copy button and confirmation check before proceeding.
- **State 2: Authentication Challenge**
  - Heading: *"Parental Verification"*
  - Subtitle: *"Enter your 4-digit PIN to access student history and safety controls."*
  - 4 circular digit indicators (`● ○ ○ ○`) that fill as digits are entered.
  - Touch-friendly on-screen numeric keypad (`1-9`, `Clear`, `0`, `Delete`) and keyboard numeric capture.
  - **Error Animation**: On incorrect PIN, input indicators shake horizontally (`@keyframes shake`) with red border flash. Remaining attempts displayed below.
- **State 3: Lockout Display**
  - Triggered when attempts reach 5.
  - Padlock icon with countdown circle.
  - Message: *"Too many incorrect attempts. Locked for security."*
  - Live ticking countdown: `04:59`, `04:58`... automatically re-enables PIN input when zero is reached.

---

### 5.3 Parental Portal Modal (`ParentalPortalModal.jsx`)

#### A. Header & Navigation Tabs
- **Modal Header**:
  - Left: Shield icon with title *"Parental Control Center"*.
  - Center: Status pill *"Class 10 · Active Protection"*.
  - Right: "Lock & Exit" button (`gemini-icon-btn`) and Close (`✕`).
- **Tab Bar (Horizontal Pills)**:
  1. `📊 Overview` (Live activity & summary metrics)
  2. `💬 Chat History` (Student queries & assistant replies)
  3. `🚨 Flagged Alerts` (Blocked/refused query alerts with badge counter `[2]`)
  4. `🛡️ Content Filtering` (Category toggles & custom blocked terms)
  5. `🔑 Security & PIN` (Change PIN, session auto-lock settings)

#### B. Tab 1: Overview View
- **Metric Tiles Grid**:
  - **Total Queries**: e.g. `142` (with week-over-week trend indicator).
  - **Safety Compliance**: `97.2%` (Clean queries vs flagged).
  - **Pending Alerts**: `2` (Highlighted in amber if `> 0`).
  - **Active Study Days**: `6 days` this week.
- **Subject Distribution Chart**: Visual horizontal bar indicating proportion of questions asked across Science (62%), English (24%), Social Science (14%).
- **Recent Interception Banner**: If any alerts are pending review, an action card prompts: *"Review 2 flagged queries submitted today."*

#### C. Tab 2: Student Chat History View
- **Search & Filter Bar**:
  - Search input: *"Search questions and answers..."*
  - Subject dropdown (All, Science, English, Social Science).
  - Grade selector (All, Class 5, Class 10).
  - Status toggle (All, Clean Only, Flagged Only).
- **Session & Transcript Cards**:
  - Expandable conversation turns.
  - Displays verbatim student question with timestamp (e.g. `Today at 2:14 PM`).
  - Displays assistant answer with citation chips (e.g. `[1] Ch 7 Page 137 ↗`).
  - Flagged turns have a distinct red border and an alert tag explaining the refusal.
- **Actions**:
  - "Export Log" button: Downloads `.json` or `.txt` format.

#### D. Tab 3: Flagged & Blocked Alerts View
- **Triage Controls**:
  - Filter pills: `Pending Review (2)` | `Reviewed (2)` | `All (4)`.
- **Alert Cards**:
  - **Header**: Category tag (`Weapons & Illegal Acts`), Severity badge (`CRITICAL` in bold red), Timestamp.
  - **Query Box**: The student's exact query displayed in high-contrast code box:
    > *"How can someone make a crude explosive using fertilizer?"*
  - **Refusal Explanation**: Why it was blocked and the exact response given to the student.
  - **Review Section**:
    - Optional textarea for parent notes: *"Spoke with Rahul about lab chemicals."*
    - Button: `Mark as Reviewed` (changes status, saves notes, decreases pending count).
- **National Helplines Widget**: Fixed banner at the bottom with Tele-MANAS (`14416`) and Childline (`1098`) for instant parent reference.

#### E. Tab 4: Content Filtering Preferences View
- **Strictness Profiles**:
  - Radio card selector: `Strict Elementary (Class 5)` vs `Curriculum Standard (Class 10)` vs `Custom`.
- **Category Toggles**:
  - Interactive switches with clear explanations:
    - *Adult & Sexual Content*: "Blocks explicit language, pornography, and non-educational anatomy." (Toggleable)
    - *Violence & Gore*: "Blocks descriptions of brutality, gore, and weapons violence." (Toggleable)
    - *Self-Harm & Suicide*: "Blocks crisis phrases and suicide methods." (Locked ON)
    - *Hate Speech & Bullying*: "Blocks slurs, discrimination, and peer harassment." (Toggleable)
    - *Weapons & Explosives*: "Blocks firearm guides and bomb synthesis." (Locked ON)
- **NCERT Biology Curriculum Exception**:
  - Checkbox: *"Allow Class 10 NCERT Reproductive Health & Biology (Chapter 7)"*
  - Rationale note: *"Ensures your child can study male/female reproductive systems, menstruation, and contraception for board exams without false blocks."*
- **Custom Blocked Keywords Tag Manager**:
  - Text input with `Add Keyword` button.
  - Tag chips displaying currently blocked terms with `✕` removal icon.
  - Dynamic update without requiring page reload.
- **Save Bar**: Subtle toast notification on successful settings update: *"Safety settings saved and active immediately."*

#### F. Tab 5: Security & PIN Management View
- **Change PIN Form**:
  - Fields: Current PIN, New PIN, Confirm New PIN.
  - Validation: Must be 4-6 numeric digits.
- **Session Auto-Lock Duration**:
  - Slider or radio buttons: `5 min`, `15 min` (Default), `30 min`, `60 min`.
- **Emergency Recovery Key Card**:
  - Displays masked recovery key with "Reveal" toggle and "Copy" button.
- **Sign Out / Lock Now Button**:
  - Immediately terminates active session and returns to student mode.

---

### 5.4 Theme Integration & CSS Classes (`ui-client/src/App.css`)

To maintain 100% visual fidelity with Google Gemini and the existing dark UI, the new parental components will use dedicated classes conforming to the established design tokens:

```css
/* Parental Portal Main Card */
.parental-modal-card {
  background: #18191b;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 24px;
  width: 100%;
  max-width: 820px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.85), 0 0 32px rgba(66, 133, 244, 0.18);
  overflow: hidden;
  animation: scaleUp 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Tab Bar Navigation */
.parental-tab-bar {
  display: flex;
  gap: 8px;
  padding: 12px 24px;
  background: #131314;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  overflow-x: auto;
}

.parental-tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 9999px;
  background: transparent;
  border: 1px solid transparent;
  color: #c4c7c5;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.parental-tab-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
}

.parental-tab-btn.active {
  background: #1e1f20;
  border-color: rgba(255, 255, 255, 0.16);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* Alert Notification Badge */
.parent-alert-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #ea4335;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  min-width: 18px;
  height: 18px;
  border-radius: 9999px;
  padding: 0 5px;
  margin-left: 6px;
  animation: pulse 2s infinite;
}

/* PIN Input Indicators */
.pin-dots-container {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin: 20px 0;
}

.pin-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  transition: all 0.15s ease;
}

.pin-dot.filled {
  background: #4285f4;
  border-color: #4285f4;
  box-shadow: 0 0 12px rgba(66, 133, 244, 0.5);
  transform: scale(1.15);
}

/* Shake Animation on Wrong PIN */
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-8px); }
  40%, 80% { transform: translateX(8px); }
}

.pin-shake {
  animation: shake 0.4s ease;
}
```

---

## 6. Automated Verification & Test Suite Plan

To fulfill Acceptance Criterion 4 ("Automated tests verify parental control operations: PIN protection, chat history access, and settings updates"), a dedicated test suite must be provided in `tests/test_parental.py`.

### 6.1 Backend Test Cases Matrix

| Test ID | Test Function | Purpose & Assertion |
|---|---|---|
| `TC-P01` | `test_parent_auth_status_initial` | Asserts `/api/parent/auth/status` returns `pin_configured: False` on clean setup. |
| `TC-P02` | `test_parent_pin_setup_and_verify` | Sets a 4-digit PIN, verifies PBKDF2 salt & hash storage, tests verification returning valid bearer token. |
| `TC-P03` | `test_parent_pin_brute_force_lockout` | Simulates 5 consecutive incorrect PIN attempts, asserts `HTTP 429 Too Many Requests` and lockout duration `> 0`. |
| `TC-P04` | `test_unauthenticated_access_denied` | Asserts `/api/parent/history`, `/api/parent/flagged`, `/api/parent/settings` return `401 Unauthorized` without token. |
| `TC-P05` | `test_chat_history_logging_and_retrieval` | Submits educational question to `/api/ask`, asserts turn is recorded in `storage/student_chat_history.jsonl` and visible via `GET /api/parent/history`. |
| `TC-P06` | `test_flagged_query_alert_and_review` | Submits inappropriate query (e.g. bomb creation), asserts safety refusal, confirms event logged in `storage/safety_events.jsonl`, and tests `POST /api/parent/flagged/{id}/review` updates status to `REVIEWED`. |
| `TC-P07` | `test_content_filtering_preferences_persistence` | Updates category toggles and custom blocked keywords via `PUT /api/parent/settings`, asserts persistence in `parental_config.json`. |
| `TC-P08` | `test_custom_blocked_keyword_enforcement` | Adds keyword `"fortnite"` to custom blocked list, submits question *"How to play fortnite?"*, asserts query is blocked under `custom_blocked` category. |
| `TC-P09` | `test_ncert_biology_whitelist_exception` | Verifies that Class 10 Biology reproduction queries (Chapter 7) remain accessible under standard profile. |
| `TC-P10` | `test_parent_change_pin_and_logout` | Tests changing PIN with valid token, verifies old PIN is invalidated, and asserts logout invalidates token immediately. |

---

## 7. Implementation Roadmap & Handover to Implementers

### Phase 1: Backend Safety & Parental Foundation
1. Create `app/parental/` package containing:
   - `auth.py`: Salted PBKDF2 PIN hashing, attempt counters, token generation.
   - `schemas.py`: Pydantic models for requests and responses.
   - `storage.py`: Thread-safe readers/writers for `parental_config.json`, `student_chat_history.jsonl`, and `safety_events.jsonl`.
   - `service.py`: History querying, triage management, settings manipulation.
   - `routes.py`: FastAPI router mounted on `/api/parent`.
2. Connect `POST /api/ask` and `POST /api/ask/stream` in `app/main.py` to:
   - Screen input against active `storage/parental_config.json` rules.
   - Log completed turns to `storage/student_chat_history.jsonl`.
   - Log safety violations to `storage/safety_events.jsonl`.

### Phase 2: Frontend UI Implementation (`ui-client/`)
1. Create `ui-client/src/components/parental/`:
   - `ParentalNavButton.jsx`: Sidebar button with ShieldLock icon and pending alerts pill.
   - `ParentalAuthModal.jsx`: 4-digit PIN keypad, setup flow, recovery key display, lockout countdown.
   - `ParentalPortalModal.jsx`: Main modal container with 5 tabs.
   - `tabs/OverviewTab.jsx`: Metric tiles, subject breakdown chart.
   - `tabs/HistoryTab.jsx`: Searchable, filterable student chat transcript viewer.
   - `tabs/FlaggedAlertsTab.jsx`: Triage cards with review action and helpline widget.
   - `tabs/FilteringTab.jsx`: Category toggles, strictness profiles, custom keyword manager.
   - `tabs/SecurityTab.jsx`: Change PIN, session duration, manual lock.
2. Add SVG icons to `GeminiIcons.jsx`: `ShieldLockIcon`, `AlertTriangleIcon`, `HistoryIcon`, `SlidersIcon`, `KeyIcon`.
3. Add parental CSS classes to `ui-client/src/App.css`.

### Phase 3: Automated Verification
1. Implement `tests/test_parental.py` covering TC-P01 through TC-P10.
2. Run test suite: `.venv\Scripts\pytest tests/test_parental.py -v`.
3. Build frontend bundle: `npm run build` in `ui-client/` to verify clean build into `frontend/`.
