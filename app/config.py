"""
Every setting in one place.

Each value can be overridden with an environment variable of the same name
(in capitals), or in a .env file next to README.md. For example:

    LLM_MODEL=qwen3.5:2b
    TOP_K=6

Settings are read when the program starts, so restart it after changing .env.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Adapters: which service does each job. app/adapters.py turns these names into objects.
    #   simple mode (default, free, no Docker): ollama + ollama + simple
    #   OPEA mode (optional, Docker):           tei + opea (or openai_like) + qdrant
    #   Cloud / SDK providers:                  claude | codex | antigravity | groq | grok
    embedder: str = "ollama"       # ollama | tei | opea | openai | gemini
    llm: str = "ollama"            # ollama | openai_like | opea | claude | codex | antigravity | groq | grok
    vector_store: str = "simple"   # simple (files in storage/index) | qdrant

    # The two models. Their names must match what the chosen service calls them.
    llm_model: str = "qwen3.5:4b"              # writes the answer
    embed_model: str = "qwen3-embedding:0.6b"  # turns text into vectors for searching

    # Where each service is running (only the ones you chose are used)
    ollama_url: str = "http://localhost:11434"     # embedder=ollama or llm=ollama
    embed_url: str = "http://localhost:6006"       # embedder=tei or opea
    llm_url: str = "http://localhost:9000/v1"      # llm=openai_like or opea
    qdrant_url: str = ""                           # empty = Qdrant keeps its files in storage/qdrant, no server

    # API Keys & URLs for Cloud & SDK adapters
    anthropic_api_key: str = ""
    claude_api_key: str = ""
    openai_api_key: str = ""
    codex_api_key: str = ""
    gemini_api_key: str = ""
    antigravity_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    grok_api_key: str = ""
    grok_url: str = "https://api.x.ai/v1"

    # Where the textbook PDFs are, and where the index and feedback are saved
    data_dir: Path = ROOT / "data"
    storage_dir: Path = ROOT / "storage"

    # Ingestion: how big each searchable piece of text is (in tokens)
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Retrieval: how many chunks the LLM gets, and how similar a chunk must be
    # to the question (0 to 1). If nothing reaches min_score we say "not found".
    top_k: int = 4
    min_score: float = 0.30   # calibrated for qwen3-embedding: on-topic queries score 0.35 - 0.70+, off-topic < 0.25

    # Answer check: a claim is removed if more than this share of its words aren't in
    # the textbook excerpts or the question (one new word is always allowed).
    # Measured on real answers: supported claims 0 to 29% new words, made-up ones 57% or more.
    max_new_share: float = 0.4

    # Generation
    temperature: float = 0.0     # 0 = always the most likely words: sticks closest to the excerpts
    context_window: int = 8192   # always set this, or Ollama may reserve far more memory
    request_timeout: float = 300.0

    # Authentication & Authorization (JWT)
    jwt_secret: str = "dev-insecure-jwt-secret-key-change-in-production-123456789"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 7

    @property
    def index_dir(self) -> Path:
        return self.storage_dir / "index"

    @property
    def index_info_file(self) -> Path:
        return self.index_dir / "index_info.json"

    @property
    def feedback_file(self) -> Path:
        return self.storage_dir / "feedback.jsonl"

    @property
    def metrics_file(self) -> Path:
        return self.storage_dir / "conversation_metrics.jsonl"


settings = Settings()


def reload_env_settings():
    """Dynamically re-reads API keys and credentials from .env from disk so newly added keys are picked up immediately without restarting."""
    from dotenv import dotenv_values
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    vals = dotenv_values(env_path)
    for k, v in vals.items():
        if v is not None and v != "":
            attr = k.lower()
            if hasattr(settings, attr) and (attr.endswith("_key") or attr.endswith("_url")):
                setattr(settings, attr, v)
