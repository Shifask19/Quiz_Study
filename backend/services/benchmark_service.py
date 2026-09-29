"""
On-device AI benchmark service.

Runs controlled tests to measure real inference performance:
  - Embedding latency
  - Generation latency
  - Tokens per second
  - Memory usage (where available)

IMPORTANT: Only real measured values are reported.
No numbers are fabricated or hard-coded.
"""
import time
import platform
import logging
import tracemalloc
from datetime import datetime, timezone

def _now() -> datetime:
    return datetime.now(timezone.utc)
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from backend.database.models import BenchmarkResult
from backend.models.factory import get_model

logger = logging.getLogger(__name__)

BENCHMARK_PROMPTS = [
    "Explain what database normalization means and why it is important in relational databases.",
    "Describe the difference between a process and a thread in operating systems.",
    "What is the time complexity of merge sort and how does it work?",
]

BENCHMARK_EMBED_TEXTS = [
    "Database normalization reduces data redundancy.",
    "The CPU executes instructions stored in memory.",
    "Binary search has O(log n) time complexity.",
]


def get_device_info() -> Dict[str, str]:
    """Return hardware/OS information."""
    info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["total_ram_gb"] = f"{mem.total / (1024**3):.1f}"
        info["available_ram_gb"] = f"{mem.available / (1024**3):.1f}"
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            info["cpu_freq_mhz"] = f"{cpu_freq.current:.0f}"
        info["cpu_cores"] = str(psutil.cpu_count(logical=False))
        info["cpu_threads"] = str(psutil.cpu_count(logical=True))
    except ImportError:
        info["note"] = "Install psutil for detailed hardware info: pip install psutil"
    return info


def _get_memory_mb() -> Optional[float]:
    """Return current process memory usage in MB, or None if unavailable."""
    try:
        import psutil, os
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def run_benchmark(
    db: Session,
    iterations: int = 3,
) -> Dict[str, Any]:
    """
    Run the full benchmark suite.

    Returns:
      - model info
      - embedding latency (avg ms)
      - generation latency (avg ms)
      - tokens/sec
      - memory usage
      - raw per-iteration results
      - device info
    """
    model = get_model()
    model_info = model.get_info()
    device_info = get_device_info()

    embed_latencies: List[float] = []
    gen_latencies: List[float] = []
    tokens_per_sec_list: List[float] = []
    mem_before = _get_memory_mb()

    raw_results = []

    for i in range(iterations):
        iter_result = {"iteration": i + 1}

        # --- Embedding benchmark ---
        embed_text = BENCHMARK_EMBED_TEXTS[i % len(BENCHMARK_EMBED_TEXTS)]
        t0 = time.perf_counter()
        try:
            emb = model.embed(embed_text)
            embed_lat = (time.perf_counter() - t0) * 1000
            embed_latencies.append(embed_lat)
            iter_result["embed_latency_ms"] = round(embed_lat, 2)
            iter_result["embed_dims"] = emb.dimensions
        except Exception as e:
            iter_result["embed_error"] = str(e)

        # --- Generation benchmark ---
        prompt = BENCHMARK_PROMPTS[i % len(BENCHMARK_PROMPTS)]
        t0 = time.perf_counter()
        try:
            gen = model.generate(prompt, max_tokens=128, temperature=0.0)
            gen_lat = (time.perf_counter() - t0) * 1000
            gen_latencies.append(gen_lat)
            if gen.tokens_per_second > 0:
                tokens_per_sec_list.append(gen.tokens_per_second)
            iter_result["gen_latency_ms"] = round(gen_lat, 2)
            iter_result["tokens_generated"] = gen.tokens_generated
            iter_result["tokens_per_second"] = round(gen.tokens_per_second, 2)
            iter_result["answer_preview"] = gen.text[:80] + "..." if len(gen.text) > 80 else gen.text
        except Exception as e:
            iter_result["gen_error"] = str(e)

        raw_results.append(iter_result)

    mem_after = _get_memory_mb()
    mem_used = None
    if mem_before is not None and mem_after is not None:
        mem_used = round(mem_after, 1)

    def safe_avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None

    avg_embed = safe_avg(embed_latencies)
    avg_gen = safe_avg(gen_latencies)
    avg_tps = safe_avg(tokens_per_sec_list)

    # Save to DB
    result = BenchmarkResult(
        run_at=_now(),
        model_name=model_info.name,
        backend=model_info.backend,
        device=model_info.device,
        avg_inference_latency_ms=avg_gen or 0.0,
        tokens_per_second=avg_tps,
        memory_usage_mb=mem_used,
        embedding_latency_ms=avg_embed,
        retrieval_latency_ms=None,
        iterations=iterations,
        raw_results=raw_results,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "benchmark_id": result.id,
        "run_at": result.run_at.isoformat(),
        "model": model_info.name,
        "backend": model_info.backend,
        "device": model_info.device,
        "provider": model_info.provider,
        "is_available": model_info.is_available,
        "supports_npu": model_info.supports_npu,
        "avg_embedding_latency_ms": avg_embed,
        "avg_generation_latency_ms": avg_gen,
        "avg_tokens_per_second": avg_tps,
        "memory_usage_mb": mem_used,
        "iterations": iterations,
        "raw_results": raw_results,
        "device_info": device_info,
        "note": (
            "Mock provider — values reflect mock processing time only. "
            "Configure AI_PROVIDER=local_llm or onnx for real inference benchmarks."
            if model_info.provider == "mock" else
            "Real measured values. Results depend on hardware and model."
        ),
    }


def get_benchmark_history(db: Session, limit: int = 10) -> List[Dict]:
    """Return recent benchmark results."""
    results = (
        db.query(BenchmarkResult)
        .order_by(BenchmarkResult.run_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "run_at": r.run_at.isoformat() if r.run_at else None,
            "model": r.model_name,
            "backend": r.backend,
            "avg_gen_latency_ms": r.avg_inference_latency_ms,
            "avg_embed_latency_ms": r.embedding_latency_ms,
            "tokens_per_second": r.tokens_per_second,
            "memory_mb": r.memory_usage_mb,
        }
        for r in results
    ]
