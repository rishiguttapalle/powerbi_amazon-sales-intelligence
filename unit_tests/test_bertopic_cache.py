"""
Unit / integration checks for Block D BERTopic disk cache.
Does NOT modify notebook or production modules — only reads and executes
the existing Block D cell source against the same data as Phase 4.

Usage (repo root):
  .\\venv\\Scripts\\python.exe unit_tests\\test_bertopic_cache.py
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from config import (  # noqa: E402
    ARTIFACTS_DIR,
    BERTOPIC_META_PATH,
    BERTOPIC_MIN_TOPIC_SIZE,
    BERTOPIC_MODEL_DIR,
    BERTOPIC_TOPICS_PATH,
    EMBEDDING_MODEL,
    NLP_DOMAIN_STOPWORDS,
    NLP_RESULTS_PATH,
    RANDOM_SEED,
    REVIEW_TEXT_PATH,
)
from utils import load_star_schema  # noqa: E402


def _load_block_d_source() -> str:
    nb = json.loads((ROOT / "python" / "4_review_nlp.ipynb").read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        src = "".join(cell.get("source", []))
        if "_bertopic_cache_valid" in src and "fit_transform" in src:
            return src
    raise RuntimeError("Block D cache cell not found in 4_review_nlp.ipynb")


def _build_text_df() -> pd.DataFrame:
    review_text = pd.read_csv(REVIEW_TEXT_PATH)
    metrics_df = load_star_schema()
    text_df = review_text.merge(metrics_df, on="product_id", how="inner")
    assert len(text_df) == len(metrics_df)
    text_df["full_text"] = (
        text_df["review_title"].fillna("") + ". " + text_df["review_content"].fillna("")
    )
    return text_df


def _run_block_d(text_df: pd.DataFrame, *, expect_cached: bool | None) -> dict:
    """Execute notebook Block D source in an isolated namespace."""
    src = _load_block_d_source()
    # Names referenced by Block D cell source (and its imports).
    ns: dict = {
        "text_df": text_df.copy(),
        "EMBEDDING_MODEL": EMBEDDING_MODEL,
        "BERTOPIC_MIN_TOPIC_SIZE": BERTOPIC_MIN_TOPIC_SIZE,
        "RANDOM_SEED": RANDOM_SEED,
        "NLP_DOMAIN_STOPWORDS": NLP_DOMAIN_STOPWORDS,
        "ARTIFACTS_DIR": ARTIFACTS_DIR,
        "BERTOPIC_MODEL_DIR": BERTOPIC_MODEL_DIR,
        "BERTOPIC_TOPICS_PATH": BERTOPIC_TOPICS_PATH,
        "BERTOPIC_META_PATH": BERTOPIC_META_PATH,
    }

    # Count SentenceTransformer constructions (fit path only; cache hit allows 0-1).
    st_calls = {"n": 0}
    import sentence_transformers as st_mod

    RealST = st_mod.SentenceTransformer

    class CountingST(RealST):
        def __init__(self, *args, **kwargs):
            st_calls["n"] += 1
            super().__init__(*args, **kwargs)

    st_mod.SentenceTransformer = CountingST

    buf: list[str] = []
    real_print = print

    def capture_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        buf.append(msg)
        real_print(*args, **kwargs)

    ns["print"] = capture_print

    t0 = time.perf_counter()
    try:
        exec(compile(src, "<Block D>", "exec"), ns, ns)
    finally:
        st_mod.SentenceTransformer = RealST
    elapsed = time.perf_counter() - t0

    log = "\n".join(buf)
    cached = "[cached]" in ns.get("method_used", "") or "Loading fitted BERTopic" in log
    if expect_cached is True and not cached:
        raise AssertionError(f"Expected cache hit; method_used={ns.get('method_used')!r}\n{log}")
    if expect_cached is False and cached:
        raise AssertionError(f"Expected cache miss (fit); got cached path\n{log}")

    topics = np.asarray(ns["text_df"]["topic"])
    return {
        "topics": topics,
        "method_used": ns["method_used"],
        "elapsed_s": elapsed,
        "st_calls": st_calls["n"],
        "cached": cached,
        "topic_model": ns["topic_model"],
        "log": log,
    }


def main() -> int:
    print("=" * 70)
    print("BERTopic cache test (no notebook/code changes)")
    print("=" * 70)

    text_df = _build_text_df()
    print(f"docs={len(text_df)} products")

    baseline = None
    if NLP_RESULTS_PATH.is_file():
        baseline = pd.read_csv(NLP_RESULTS_PATH)
        print(f"baseline nlp_results: {len(baseline)} rows, topics={baseline['topic'].nunique()}")

    # --- Run 1: fit + save (cache miss) ---
    print("\n--- RUN 1: fit + save (expect cache miss) ---")
    # Ensure clean miss for a true unit path: if cache exists, still run miss only when forced
    # First run uses whatever state exists; if cache already valid, run1 will be hit.
    cache_exists = (
        BERTOPIC_MODEL_DIR.is_dir()
        and BERTOPIC_TOPICS_PATH.is_file()
        and BERTOPIC_META_PATH.is_file()
    )
    if cache_exists:
        print("Cache already present — RUN 1 will be a cache HIT (no re-fit).")
        r1 = _run_block_d(text_df, expect_cached=True)
    else:
        print("No cache — RUN 1 will FIT (may take several minutes).")
        r1 = _run_block_d(text_df, expect_cached=False)

    print(
        f"RUN1: cached={r1['cached']} st_calls={r1['st_calls']} "
        f"elapsed={r1['elapsed_s']:.2f}s method={r1['method_used']}"
    )

    # --- Run 2: must load cache (no fit; ST calls 0-1 from BERTopic.load) ---
    print("\n--- RUN 2: load cache (expect cache hit) ---")
    r2 = _run_block_d(text_df, expect_cached=True)
    print(
        f"RUN2: cached={r2['cached']} st_calls={r2['st_calls']} "
        f"elapsed={r2['elapsed_s']:.2f}s method={r2['method_used']}"
    )

    errors: list[str] = []

    if not r2["cached"]:
        errors.append("RUN2 did not take cache path")
    # Block D else-branch does not call SentenceTransformer on cache hit.
    # BERTopic.load may still instantiate the embedding pointer from safetensors meta
    # (HF local cache — no re-download / no UMAP+cluster). Allow 0-1 ST loads.
    if r2["st_calls"] > 1:
        errors.append(
            f"RUN2 SentenceTransformer calls={r2['st_calls']} (expected 0-1 from BERTopic.load)"
        )
    else:
        print(
            f"PASS: RUN2 ST calls={r2['st_calls']} "
            "(0=ideal; 1=BERTopic.load embedding pointer from local HF cache)"
        )
    if not np.array_equal(r1["topics"], r2["topics"]):
        errors.append("RUN1 vs RUN2 topic assignments differ")
    else:
        print("PASS: RUN1 topics == RUN2 topics")

    # Cache hit should be much faster than a full fit when RUN1 was a fit
    if not r1["cached"] and r2["elapsed_s"] > 0:
        speedup = r1["elapsed_s"] / max(r2["elapsed_s"], 1e-6)
        print(
            f"Speedup RUN1/RUN2 ~ {speedup:.1f}x "
            f"({r1['elapsed_s']:.1f}s -> {r2['elapsed_s']:.1f}s)"
        )
        if r2["elapsed_s"] >= r1["elapsed_s"]:
            errors.append("Cache hit was not faster than fit - unexpected")

    # Artifact files
    for p in (BERTOPIC_MODEL_DIR, BERTOPIC_TOPICS_PATH, BERTOPIC_META_PATH):
        if not p.exists():
            errors.append(f"Missing artifact: {p}")
    print("PASS: artifact files present" if not any("Missing artifact" in e for e in errors) else "")

    # Terms extractable from loaded model
    from topic_labeling import extract_bertopic_terms

    terms1 = extract_bertopic_terms(r1["topic_model"])
    terms2 = extract_bertopic_terms(r2["topic_model"])
    if terms1 != terms2:
        errors.append("extract_bertopic_terms differs between RUN1 and RUN2")
    else:
        print(f"PASS: topic terms identical ({len(terms1)} topics)")

    # Compare to existing nlp_results (same pipeline grain)
    if baseline is not None:
        merged = text_df[["product_id"]].copy()
        merged["topic_run"] = r2["topics"]
        m = merged.merge(baseline[["product_id", "topic"]], on="product_id", how="inner")
        match = (m["topic_run"].astype(int) == m["topic"].astype(int)).mean()
        print(
            f"Match vs current nlp_results.csv: {match:.1%} "
            f"({int((m['topic_run'].astype(int) == m['topic'].astype(int)).sum())}/{len(m)})"
        )
        if not r1["cached"] and match < 1.0:
            # Fresh fit can differ from an older BERTopic run — report, don't fail unit cache tests
            print(
                "NOTE: Fresh FIT topics may differ from previously saved nlp_results "
                "(UMAP/BERTopic non-determinism across runs/versions). "
                "Cache fidelity is RUN1==RUN2; baseline compare is informational."
            )
        elif r1["cached"] and match < 1.0:
            errors.append(
                "Cache hit topics disagree with nlp_results.csv — cache may be from a different fit"
            )
        elif match == 1.0:
            print("PASS: topics match nlp_results.csv end-to-end")

    # Downstream spot-check: topic counts / outlier share stable across runs
    out1 = float((r1["topics"] == -1).mean())
    out2 = float((r2["topics"] == -1).mean())
    if abs(out1 - out2) > 1e-12:
        errors.append("Outlier share changed between runs")
    else:
        print(f"PASS: outlier share stable ({out2:.1%})")

    print("\n" + "=" * 70)
    if errors:
        print("FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("ALL CACHE UNIT/INTEGRATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
