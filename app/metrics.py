import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

log = logging.getLogger("metrics")
metrics_lock = threading.Lock()


def record_conversation_metric(data: dict[str, Any]) -> dict[str, Any]:
    """Records one conversation turn's metrics to storage/conversation_metrics.jsonl and console log."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **data,
    }

    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        with metrics_lock:
            with open(settings.metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Failed to write conversation metrics to file: %s", e)

    q_preview = (record.get("question") or "")[:40]
    total_lat = record.get("total_latency_s", 0)
    tok_s = record.get("tokens_per_second", 0)
    toks = record.get("tokens_generated", 0)
    top_sc = record.get("top_similarity_score")
    chunks = record.get("chunks_matched", 0)
    pure = record.get("pure_llm", False)
    mode_str = "pure_llm" if pure else f"rag (chunks={chunks}, top={top_sc})"

    log.info(
        "📊 [CONV METRICS] session=%s | Q='%s...' | %s | tokens=%s (%.1f tok/s) | total=%.2fs",
        record.get("session_id", "default"),
        q_preview,
        mode_str,
        toks,
        tok_s,
        total_lat,
    )
    return record


def get_metrics_summary(limit: int = 50) -> dict[str, Any]:
    """Reads conversation_metrics.jsonl and computes aggregate analytics."""
    if not settings.metrics_file.exists():
        return {
            "total_conversations": 0,
            "rag_count": 0,
            "pure_llm_count": 0,
            "found_count": 0,
            "found_rate_percent": 0.0,
            "avg_latency_s": 0.0,
            "avg_tokens_per_second": 0.0,
            "avg_tokens_generated": 0.0,
            "recent_conversations": [],
        }

    records = []
    try:
        with metrics_lock:
            with open(settings.metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
    except Exception as e:
        log.warning("Failed to read conversation metrics: %s", e)

    if not records:
        return {
            "total_conversations": 0,
            "rag_count": 0,
            "pure_llm_count": 0,
            "found_count": 0,
            "found_rate_percent": 0.0,
            "avg_latency_s": 0.0,
            "avg_tokens_per_second": 0.0,
            "avg_tokens_generated": 0.0,
            "recent_conversations": [],
        }

    total = len(records)
    pure_llm_count = sum(1 for r in records if r.get("pure_llm"))
    rag_count = total - pure_llm_count
    found_count = sum(1 for r in records if r.get("found"))

    latencies = [r.get("total_latency_s", 0) for r in records if r.get("total_latency_s") is not None]
    tok_speeds = [
        r.get("tokens_per_second", 0)
        for r in records
        if r.get("tokens_per_second") is not None and r.get("tokens_per_second", 0) > 0
    ]
    gen_tokens = [r.get("tokens_generated", 0) for r in records if r.get("tokens_generated") is not None]

    return {
        "total_conversations": total,
        "rag_count": rag_count,
        "pure_llm_count": pure_llm_count,
        "found_count": found_count,
        "found_rate_percent": round((found_count / total) * 100, 1) if total > 0 else 0.0,
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "avg_tokens_per_second": round(sum(tok_speeds) / len(tok_speeds), 1) if tok_speeds else 0.0,
        "avg_tokens_generated": round(sum(gen_tokens) / len(gen_tokens), 1) if gen_tokens else 0.0,
        "recent_conversations": records[-limit:][::-1],
    }

