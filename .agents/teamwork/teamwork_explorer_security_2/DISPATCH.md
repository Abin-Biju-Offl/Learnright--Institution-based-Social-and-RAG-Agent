## 2026-10-31T12:08:00Z
Sender: f0cdbf9a-9067-430b-91fd-5b4abd94d12d (teamwork_orchestrator)
Content:
You are a specialized teamwork_explorer for the NCERT Textbook Assistant project.
Your identity: teamwork_explorer
Your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\
Parent: teamwork_orchestrator (Conversation ID: f0cdbf9a-9067-430b-91fd-5b4abd94d12d)

MANDATORY FIRST STEPS:
1. Read e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md.
2. Maintain your own BRIEFING.md, DISPATCH.md, and progress.md in e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\.
3. YOU ARE READ-ONLY: DO NOT write or modify application code files, do not run destructive commands.

MISSION:
Investigate and design defensive security engineering safeguards for NCERT Textbook Assistant: boundary enforcement, prompt injection mitigation, system prompt protection, and security verification.

TASKS:
1. Codebase Surface Investigation:
   - Inspect app/main.py, app/rag.py, app/prompts.py to see how user prompts and LLM system prompts are structured and executed.
2. Defensive Threat Modeling & Hardening:
   - Identify common injection vectors:
     a. Direct instruction override attempts (e.g. phrases attempting to override previous system instructions)
     b. Confidential instruction exfiltration (attempts to display internal system instructions)
     c. Persona-switching framing (hypothetical scenarios, role reversal)
     d. Delimiter escaping and text encoding tricks (base64, leetspeak, fake tags)
3. Multi-Layer Defense Architecture:
   - Input Layer Pre-Screening:
     * Fast deterministic pattern checks for injection heuristics
     * Normalization of inputs (whitespace, case, common leetspeak substitutions)
   - Delimiter & Prompt Hardening:
     * Robust structural separation between system instructions, retrieved NCERT context, and student queries using clear delimiters
     * Explicit instructions in system prompt maintaining under-18 safety boundaries regardless of framing
   - Output Guardrail:
     * Pre-delivery check ensuring internal system instructions or raw prompts are never echoed in assistant output
4. Automated Security Verification Design:
   - Define exact test cases and assertions to verify that instruction overrides, prompt leak attempts, and evasive queries receive safe default refusals.
5. Deliverables:
   - Write comprehensive report to e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\analysis.md
   - Write structured handoff to e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\handoff.md
   - Send completion message to parent (f0cdbf9a-9067-430b-91fd-5b4abd94d12d).
