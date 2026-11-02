# Progress Heartbeat — explorer_codebase

Last visited: 2026-11-02T09:07:30Z
Status: Completed

## Tasks
- [x] Initial setup (DISPATCH.md, BRIEFING.md, progress.md)
- [x] 1. Authentication Subsystem Analysis (`app/auth/`)
  - Examined `app/auth/jwt_handler.py`, `models.py`, `passwords.py`, `schemas.py`, `dependencies.py`, `routes.py`
  - Verified tests in `tests/test_auth.py` (7/7 passed)
  - Found mandatory `grade` claim blocking Admin/Lecturer auth
  - Analyzed PyJWT claims vs session resolution
- [x] 2. Storage & State Analysis (`storage/users.json`, `storage/parental_config.json`, `app/parental/`, JSON vs SQLite)
  - Analyzed multi-worker concurrency hazards of flat JSON with `os.replace`
  - Verified relational modeling needs for Institutions, Classes, Sections, Invites, Lecturer profiles
  - Assessed feasibility of SQLite + SQLAlchemy with automated backward-compatible JSON migration
- [x] 3. FastAPI Routing, Middleware & Grade Enforcement (`app/main.py`)
  - Analyzed router mounting, `get_optional_user`, and `enforce_grade`
  - Found bug where `enforce_grade` crashes when `user` is FastAPI `Depends` object during direct invocation
  - Designed tiered RBAC dependencies (`require_role`, `require_org_admin`, `require_lecturer`)
- [x] 4. Frontend Architecture Analysis (`ui-client/`)
  - Examined React 18 + Vite structure, lack of react-router-dom, state-driven UI
  - Found missing `Authorization: Bearer <token>` in `fetch('/api/ask/stream')`
  - Mapped integration points for Student header/sidebar, Admin Onboarding/Dashboard, Lecturer Tags, and Invite Acceptance
- [x] 5. Synthesis & Integration Blueprints (PyJWT extensions, Admin flow, Student flow, Lecturer profiles, RBAC matrix, backward compatibility)
- [x] 6. Final Handoff Report (`handoff.md`)
