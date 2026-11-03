"""
Model Registry: per-model facts, context limits, and capabilities.

Complies with SKILL.md (Section 2 & 4.3):
- Centralizes model context limits, output reserves, and tokenizers.
- No hardcoding of limits inside business logic.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_name: str
    context_limit: int
    max_output: int = 600
    safety_margin_ratio: float = 0.08  # 8% token budget safety margin
    supports_system_role: bool = True
    tokenizer_type: Literal["tiktoken", "char_ratio"] = "tiktoken"
    tag: str = "Cloud"

    @property
    def model_id(self) -> str:
        return f"{self.provider}/{self.model_name}"


# Default registry for supported models
_REGISTRY: dict[str, ModelSpec] = {
    # Local Models (Ollama)
    "ollama/qwen3.5:4b": ModelSpec(
        provider="ollama",
        model_name="qwen3.5:4b",
        context_limit=8192,
        max_output=600,
        tokenizer_type="char_ratio",
        tag="Local",
    ),
    "ollama/qwen3.5:2b": ModelSpec(
        provider="ollama",
        model_name="qwen3.5:2b",
        context_limit=8192,
        max_output=600,
        tokenizer_type="char_ratio",
        tag="Local",
    ),
    "ollama/llama3.2": ModelSpec(
        provider="ollama",
        model_name="llama3.2",
        context_limit=8192,
        max_output=600,
        tokenizer_type="char_ratio",
        tag="Local",
    ),
    "ollama/llama3.2:3b": ModelSpec(
        provider="ollama",
        model_name="llama3.2:3b",
        context_limit=8192,
        max_output=600,
        tokenizer_type="char_ratio",
        tag="Local",
    ),
    "ollama/llama3.2:1b": ModelSpec(
        provider="ollama",
        model_name="llama3.2:1b",
        context_limit=8192,
        max_output=600,
        tokenizer_type="char_ratio",
        tag="Local",
    ),
    # Cloud Models: Groq
    "groq/llama-3.3-70b-versatile": ModelSpec(
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        context_limit=131072,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Groq Cloud",
    ),
    "groq/llama-3.1-8b-instant": ModelSpec(
        provider="groq",
        model_name="llama-3.1-8b-instant",
        context_limit=131072,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Groq Cloud",
    ),
    # Cloud Models: Claude Agent SDK (Anthropic)
    "claude/claude-3-5-sonnet-latest": ModelSpec(
        provider="claude",
        model_name="claude-3-5-sonnet-latest",
        context_limit=200000,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Claude Agent SDK",
    ),
    "claude/claude-3-7-sonnet-latest": ModelSpec(
        provider="claude",
        model_name="claude-3-7-sonnet-latest",
        context_limit=200000,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Claude Agent SDK",
    ),
    "claude/claude-3-haiku-20240307": ModelSpec(
        provider="claude",
        model_name="claude-3-haiku-20240307",
        context_limit=200000,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Claude Agent SDK",
    ),
    # Cloud Models: Codex / OpenAI SDK
    "codex/gpt-4o-mini": ModelSpec(
        provider="codex",
        model_name="gpt-4o-mini",
        context_limit=128000,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Codex / OpenAI",
    ),
    "codex/gpt-4o": ModelSpec(
        provider="codex",
        model_name="gpt-4o",
        context_limit=128000,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Codex / OpenAI",
    ),
    "openai/gpt-4o-mini": ModelSpec(
        provider="openai",
        model_name="gpt-4o-mini",
        context_limit=128000,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="OpenAI",
    ),
    # Cloud Models: AntiGravity SDK / Google Gemini
    "antigravity/gemini-2.0-flash": ModelSpec(
        provider="antigravity",
        model_name="gemini-2.0-flash",
        context_limit=1048576,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="AntiGravity SDK",
    ),
    "gemini/gemini-2.0-flash": ModelSpec(
        provider="gemini",
        model_name="gemini-2.0-flash",
        context_limit=1048576,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Gemini",
    ),
    # Cloud Models: xAI Grok
    "grok/grok-2-latest": ModelSpec(
        provider="grok",
        model_name="grok-2-latest",
        context_limit=131072,
        max_output=600,
        tokenizer_type="tiktoken",
        tag="Grok API",
    ),
}


def get_model_spec(provider: str, model_name: str) -> ModelSpec:
    """Retrieve specifications for a given model or construct a safe default."""
    clean_provider = provider.lower().strip()
    clean_model = model_name.strip()
    if "/" in clean_model and clean_model.startswith(f"{clean_provider}/"):
        clean_model = clean_model.split("/", 1)[1]

    key = f"{clean_provider}/{clean_model}"
    if key in _REGISTRY:
        return _REGISTRY[key]

    # Exact match if clean_model matches any spec's model_name
    for reg_key, spec in _REGISTRY.items():
        if spec.provider == clean_provider and spec.model_name == clean_model:
            return spec

    # Prefix match if full version tag omitted (e.g. "qwen3.5" -> "qwen3.5:4b")
    for reg_key, spec in _REGISTRY.items():
        if spec.provider == clean_provider and spec.model_name.startswith(clean_model):
            return spec

    # Safe fallback defaults
    is_cloud = clean_provider != "ollama"
    context_limit = 128000 if is_cloud else 8192
    return ModelSpec(
        provider=clean_provider,
        model_name=clean_model,
        context_limit=context_limit,
        max_output=600,
        tokenizer_type="tiktoken" if is_cloud else "char_ratio",
        tag="Cloud" if is_cloud else "Local",
    )
