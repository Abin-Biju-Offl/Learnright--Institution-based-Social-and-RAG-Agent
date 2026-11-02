"""
Parental Controls Subsystem for NCERT Textbook Assistant.

Provides PBKDF2-salted PIN authentication, progressive brute-force lockout,
15-minute Bearer session management, server-side student chat history audit,
flagged queries triage/review, and customizable content filtering preferences.
"""

from app.parental.routes import parental_router

__all__ = ["parental_router"]
