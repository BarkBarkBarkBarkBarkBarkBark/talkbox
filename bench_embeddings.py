"""
Embedding + vector search latency benchmark.

Tests the exact workload a kiosk does per query:
  1. Load model into memory
  2. Embed a short user query
  3. Embed N category strings (the "database")
  4. Cosine nearest-neighbor search over categories
  5. Report latency at each stage

Run locally first, then copy and run on the Pi:
  python3 bench_embeddings.py

Dependencies (auto-installed if missing):
  pip install sentence-transformers numpy
"""

import sys
import time

# ── Auto-install deps if missing ────────────────────────────────────────────
def _ensure(pkg, import_name=None):
    import importlib, subprocess
    try:
        importlib.import_module(import_name or pkg)
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("sentence-transformers", "sentence_transformers")
_ensure("numpy")

import numpy as np
from sentence_transformers import SentenceTransformer

# ── Config ───────────────────────────────────────────────────────────────────
# all-MiniLM-L6-v2 : 80 MB, 384-dim, very fast on CPU  ← good Pi candidate
# all-mpnet-base-v2: 420 MB, 768-dim, higher quality    ← Pi 5 can handle
MODEL_NAME = "all-MiniLM-L6-v2"

# Simulated category "database" — mirrors real kiosk categories
CATEGORIES = [
    "emergency shelter and housing assistance",
    "food bank and meal programs",
    "mental health counseling and crisis support",
    "substance abuse treatment and recovery",
    "medical and dental care low income",
    "domestic violence and family safety",
    "employment job training and placement",
    "childcare and early education programs",
    "legal aid and immigration services",
    "transportation and mobility assistance",
    "utility bill assistance and financial aid",
    "senior services and elder care",
    "youth programs and after school support",
    "disability services and accessibility resources",
    "veteran services and benefits assistance",
]

# Queries that mimic real kiosk input
QUERIES = [
    "i need a place to sleep tonight",
    "my family hasn't eaten in two days",
    "i'm thinking about hurting myself",
    "need help with rent i'm about to be evicted",
    "looking for a job",
]

WARMUP_RUNS = 1
TIMED_RUNS  = 5

# ── Benchmark ────────────────────────────────────────────────────────────────
def cosine_search(query_vec: np.ndarray, db_vecs: np.ndarray) -> tuple[int, float]:
    """Return (best_idx, similarity_score) — same math pgvector uses."""
    scores = db_vecs @ query_vec  # both L2-normalised → cosine similarity
    best = int(np.argmax(scores))
    return best, float(scores[best])


def run():
    print(f"\n{'='*60}")
    print(f"  Embedding benchmark — model: {MODEL_NAME}")
    print(f"{'='*60}\n")

    # ── 1. Model load ────────────────────────────────────────────────────────
    print("Loading model (first run downloads it, ~80 MB)...")
    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME)
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"  Model load:  {load_ms:>8.1f} ms  (one-time at startup)\n")

    # ── 2. Pre-embed all categories (happens once at seed / boot) ────────────
    print(f"Pre-embedding {len(CATEGORIES)} categories (seed-time, one-off)...")
    t0 = time.perf_counter()
    cat_vecs = model.encode(CATEGORIES, normalize_embeddings=True, show_progress_bar=False)
    cat_embed_ms = (time.perf_counter() - t0) * 1000
    print(f"  Category embed: {cat_embed_ms:>6.1f} ms total "
          f"({cat_embed_ms/len(CATEGORIES):.1f} ms/category)\n")

    # ── 3. Per-query latency (what the kiosk pays on every request) ──────────
    print(f"Per-query benchmark ({WARMUP_RUNS} warmup + {TIMED_RUNS} timed runs each)\n")
    print(f"  {'Query':<45} {'Embed':>8} {'Search':>8} {'Total':>8}   Top match")
    print(f"  {'-'*44} {'-'*8} {'-'*8} {'-'*8}   {'-'*30}")

    for query in QUERIES:
        # warmup
        for _ in range(WARMUP_RUNS):
            model.encode([query], normalize_embeddings=True, show_progress_bar=False)

        embed_times, search_times = [], []
        for _ in range(TIMED_RUNS):
            t0 = time.perf_counter()
            qvec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            embed_times.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            idx, score = cosine_search(qvec, cat_vecs)
            search_times.append((time.perf_counter() - t0) * 1000)

        avg_embed  = sum(embed_times)  / len(embed_times)
        avg_search = sum(search_times) / len(search_times)
        avg_total  = avg_embed + avg_search
        match = CATEGORIES[idx][:30]

        short_q = (query[:43] + "..") if len(query) > 43 else query
        print(f"  {short_q:<45} {avg_embed:>7.1f}ms {avg_search:>7.2f}ms "
              f"{avg_total:>7.1f}ms   {match}")

    # ── 4. Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    print(f"  Model:            {MODEL_NAME}")
    print(f"  Dimensions:       {cat_vecs.shape[1]}")
    print(f"  Category count:   {len(CATEGORIES)}")
    print(f"  Platform:         {sys.platform}")
    import platform
    print(f"  CPU:              {platform.processor() or platform.machine()}")
    try:
        import torch
        print(f"  Torch backend:    {'GPU' if torch.cuda.is_available() else 'CPU-only'}")
    except ImportError:
        pass
    print()
    print("  To run on the Pi (copy this script, then):")
    print("    pip3 install sentence-transformers numpy")
    print("    python3 bench_embeddings.py")
    print()


if __name__ == "__main__":
    run()
