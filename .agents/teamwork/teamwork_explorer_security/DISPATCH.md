## 2026-10-31T11:57:14Z
From: f0cdbf9a-9067-430b-91fd-5b4abd94d12d (teamwork_orchestrator)
Content:
You are a specialized teamwork_explorer for the NCERT Textbook Assistant project.
Your identity: teamwork_explorer
Your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security\
Parent: teamwork_orchestrator (Conversation ID: f0cdbf9a-9067-430b-91fd-5b4abd94d12d)

MANDATORY FIRST STEPS:
1. Read e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md to understand all user requirements and acceptance criteria.
2. Maintain your own BRIEFING.md, DISPATCH.md, and progress.md in your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security\.
3. YOU ARE READ-ONLY: DO NOT write or modify application code files, do not run destructive commands.

MISSION:
Deeply investigate and design Security Safeguards against prompt injection, jailbreaks, system prompt exfiltration, and adversarial evasion for the NCERT Textbook Assistant.

TASKS:
1. Codebase Security Surface Investigation:
   - Search and inspect how user prompts are constructed, where system prompts live, how LLM calls are orchestrated in LlamaIndex / backend, and where vulnerabilities or injection vectors exist.
2. Adversarial Threat Modeling & Vector Analysis:
   - Investigate common and sophisticated jailbreak & injection techniques:
     * Instruction override ("Ignore previous instructions", "SYSTEM OVERRIDE", "[SYSTEM NOTE]").
     * System prompt extraction ("Repeat the text above verbatim", "Output your instructions from line 1").
     * Role-playing / persona switching (DAN, Grandma exploit, hypothetical film director, ethical researcher studying illicit topics).
     * Delimiter attacks (XML/markdown breakout, injection via fake closing tags).
     * Obfuscation & encoding (Base64, rot13, leetspeak, cipher, multilingual queries intended to bypass English filters).
     * Suffix attacks, affirmative forcing ("Start your response with 'Sure, here is...'").
     * Multi-turn manipulation / goal hijacking.
3. Multi-Layer Defense Architecture Design:
   - Input Layer Sanitization & Pre-screening:
     * Pattern matching / regex for known jailbreak heuristics and evasion markers.
     * Normalization & decoding (handling leetspeak, obfuscation).
   - System Prompt Hardening:
     * Robust framing, non-overridable boundary directives, priority rules.
     * Separation of instructions and user context using secure delimiters.
   - Guardrail Inspection (Dual Pass):
     * Input classification before LLM call.
     * Post-generation output guardrail (checking if LLM accidentally leaked prompt or generated restricted content).
   - Rate limiting / anomaly detection if applicable.
4. Red-Teaming & Security Test Cases Design:
   - Define concrete automated security test cases and payloads to rigorously verify that safety rules cannot be broken and system prompt cannot be exfiltrated.
5. Deliverables:
   - Write comprehensive analysis to e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security\analysis.md
   - Write structured handoff to e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security\handoff.md
   - Send completion message to parent (f0cdbf9a-9067-430b-91fd-5b4abd94d12d).
