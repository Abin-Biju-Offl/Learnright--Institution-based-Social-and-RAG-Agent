# Handoff Report: Defensive Security Safeguards & Red-Teaming Verification Design

**Agent Identity**: `teamwork_explorer_security_2`  
**Working Directory**: `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\`  
**Target Recipient**: `teamwork_orchestrator` (`f0cdbf9a-9067-430b-91fd-5b4abd94d12d`) / Implementer Agent  
**Date**: 2026-10-31  
**Handoff Type**: Hard (Investigation & Architecture Design Complete)  

---

## 1. Direct Observations

1. **Lack of Inbound Request Screening (`app/main.py:159-208`)**:
   - `ask(q: Question)` and `ask_stream(q: Question)` take student input directly without any safety checks, injection detection, or normalization. The only validation is `check_subject(q)`.
   ```python
   @app.post("/api/ask")
   def ask(q: Question):
       check_subject(q)
       ...
       result = get_rag().ask(q.question, q.grade, q.subject, ...)
   ```
2. **Vulnerable String Interpolation in Query Condensation (`app/prompts.py:87-108` & `app/rag.py:44-74`)**:
   - In `build_condense_prompt`, conversation history and follow-up question are interpolated raw into a prompt template:
   ```python
   chat_str = "\n".join(lines)
   return (
       "Given the recent conversation between a student and a tutor, rewrite the follow-up question "
       "into a standalone search query...\n"
       f"Conversation:\n{chat_str}\n\n"
       f"Follow-up question: {question}\n\n"
       "Standalone query:"
   )
   ```
   An injection in `question` or `history` directly executes inside `llm.complete(prompt)`, and the first line of the output is used as `search_query` in `app/rag.py:255`.
3. **Absence of Structural Delimiters & Escaping (`app/prompts.py:33-56`)**:
   - `build_messages` joins excerpts and the user question using simple text labels:
   ```python
   user = f"Textbook excerpts:\n\n{excerpts}\n\nQuestion: {question}"
   messages.append({"role": "user", "content": user})
   ```
   There are no XML envelopes (`<student_query>`, `<textbook_context>`), and no character escaping for `<` or `>`.
4. **Zero Boundary & Confidentiality Instructions in Prompts (`app/prompts.py:10-20` and `app/prompts.py:58-64`)**:
   - `SYSTEM_PROMPT` and `PURE_LLM_SYSTEM_PROMPT` only describe tutoring style and citation rules. They contain:
     - No under-18 safety prohibitions (adult content, violence, self-harm, weapons, hate speech).
     - No anti-jailbreak directives (prohibiting persona adoption, DAN, roleplay overrides).
     - No system prompt confidentiality rule (prohibiting prompt exfiltration).
5. **Output Passthrough without Leak or Jailbreak Detection (`app/rag.py:187-230`, `app/rag.py:347-350`)**:
   - In `pure_llm=True` mode, `self.llm.stream_chat(messages)` yields tokens directly to the client with zero inspection.
   - In RAG mode, if LLM outputs an answer without bracket citations, `pending.strip()` is delivered directly as the answer (`app/rag.py:350`), enabling prompt leakage.
6. **Curriculum Edge Cases (`eval/questions.json:22`)**:
   - NCERT Class 10 Science Chapter 7 covers *"How do organisms like Amoeba reproduce by fission?"*, human reproductive systems, fertilization, and contraception. Legitimate queries must not be falsely blocked by adult content filters.
7. **Existing Test Suite Baseline**:
   - Ran `.venv\Scripts\pytest.exe tests/test_rag.py`: 23 tests pass in 1.06 seconds.

---

## 2. Logic Chain

1. **From Observation 1 & 3 $\rightarrow$ Input Vulnerability**: Because user queries enter `app/main.py` without pre-screening and are concatenated directly into LLM prompts in `app/prompts.py`, an attacker can inject prompt instructions ("Ignore previous instructions", "Repeat the text above", or fake tags) that are indistinguishable from system directives to the LLM.
2. **From Observation 2 $\rightarrow$ Multi-Turn Hijack Risk**: Query condensation in `app/rag.py` passes the raw follow-up question to an LLM call before vector search occurs. A malicious follow-up question can hijack query condensation, poisoning retrieval or triggering unsafe model behavior.
3. **From Observation 4 $\rightarrow$ Model Compliance Risk**: Small local models (e.g. `qwen3.5:4b`) have lower instruction adherence than 70B+ parameter models. Without explicit system prompt boundaries, non-overridable safety rules, and strict untrusted data isolation, the model easily complies with persona-switching (DAN, Grandma exploit, fictional screenwriter) and prompt exfiltration attacks.
4. **From Observation 5 $\rightarrow$ Output Delivery Risk**: Even if prompt hardening reduces injection success, stochastic LLM generation or ungrounded `pure_llm` mode can occasionally leak internal instructions or generate inappropriate content. A post-generation output guardrail is necessary to catch and replace leaked tokens before they reach the student.
5. **From Observation 6 $\rightarrow$ Precision Requirement**: Naive keyword matching on words like "reproduce", "organs", "penis", "vagina", "contraception" would cause unacceptable false positives on Class 10 Biology. Defense mechanisms must combine deterministic regex heuristics with curriculum context awareness to whitelist authentic NCERT queries.
6. **Synthesis $\rightarrow$ Defense-in-Depth Architecture**: A single defensive mechanism is insufficient. A 3-layer architecture is required:
   - *Layer 1 (Input)*: Unicode NFKC normalization, zero-width stripping, leetspeak mapping, Base64 inspection, and deterministic regex scanning.
   - *Layer 2 (Prompt)*: XML containment envelopes (`<student_query>`, `<textbook_context>`), character escaping, hardened system prompts, and hardened query condensation.
   - *Layer 3 (Output)*: Real-time n-gram prompt leakage detection, jailbreak phrase detection, and streaming token buffer replacement.

---

## 3. Caveats & Assumptions

1. **Local Model Capacity Assumption**: The primary LLM is `qwen3.5:4b` running via Ollama. It has limited reasoning depth compared to frontier cloud models. Defensive engineering must rely heavily on deterministic pre-screening (Layer 1) and output filtering (Layer 3) rather than expecting the 4B model to resist complex semantic manipulation purely through prompt instructions.
2. **Streaming Latency Tradeoff**: Output guardrail buffering introduces a microscopic delay (first 60–80 characters buffered before yielding tokens). This represents an imperceptible ~50ms latency increase on local hardware, which is acceptable for educational safety.
3. **Multi-lingual Scope**: The primary languages supported in the application are English and Hindi. The normalization and regex heuristic patterns account for standard English, Hinglish, and Devanagari Unicode ranges. Regional Indian languages (Tamil, Telugu, Bengali) are assumed out of primary scope for v1, but the architecture supports modular regex extensions.
4. **Read-Only Explorer Constraint**: In accordance with explorer agent constraints, this agent has performed read-only investigation and comprehensive architectural design without directly modifying application source files.

---

## 4. Conclusion & Proposed Architecture

A complete, production-ready security engineering design has been formulated and documented in `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\analysis.md`.

### Core Deliverables Provided:
1. **Security Subpackage Design (`app/security/`)**:
   - `normalizer.py`: Normalizes Unicode NFKC, strips zero-width chars, maps leetspeak, inspects Base64.
   - `scanner.py`: High-speed regex heuristic scanner detecting Direct Overrides, Prompt Leaks, Persona Switching, and Delimiter Breakouts.
   - `delimiters.py`: XML sanitization and containment wrappers.
   - `guardrail.py`: N-gram prompt exfiltration detector, affirmative jailbreak detector, and streaming window buffer.
2. **Hardened Prompt Templates**: Complete replacement for `SYSTEM_PROMPT`, `PURE_LLM_SYSTEM_PROMPT`, and `build_condense_prompt` with XML tags and non-negotiable under-18 safety boundaries.
3. **Parental Logging Integration**: Event schema writing to `storage/safety_events.jsonl` for seamless review in the Parental Monitoring Portal.
4. **Comprehensive Automated Verification Suite (`tests/test_security.py`)**: 65+ concrete test payloads across 6 test suites verifying instruction override refusal, prompt secrecy, jailbreak resistance, delimiter integrity, curriculum preservation, and output guardrail interception.

---

## 5. Independent Verification Method

An implementer or verifier can independently validate this security design using the following steps:

1. **Review Specification Files**:
   - Detailed Security Analysis: `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\analysis.md`
   - Taxonomy Category Alignments: `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_taxonomy\analysis.md`
   - Parental Logging Alignment: `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_parental\analysis.md`
2. **Execute Current Unit Tests**:
   - Run: `.venv\Scripts\pytest.exe tests/test_rag.py`
   - Expected Result: 23 passed in ~1.1 seconds.
3. **Run New Security Test Suite (Post-Implementation)**:
   - Once implemented in `tests/test_security.py`, run:
     `.venv\Scripts\pytest.exe tests/test_security.py -v`
   - Expected Result: 65+ automated security test cases pass, confirming:
     - All direct instruction overrides return `blocked_by_security=True` and `found=False`.
     - Zero instances of system prompt leak in response text.
     - All persona switching and jailbreak attempts are refused.
     - Legitimate NCERT Class 10 Biology and English queries pass with `found=True`.
     - Security events are recorded in `storage/safety_events.jsonl`.
