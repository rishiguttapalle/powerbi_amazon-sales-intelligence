"""
Unit / integration checks for Phase 4 topic labeling (LLM primary path).

Does NOT modify production modules — only calls topic_labeling helpers and
restores dim_topic / topic_label_cache after the live API probe.

Usage (repo root):
  .\\venv\\Scripts\\python.exe unit_tests\\test_topic_labeling_llm.py
"""
from __future__ import annotations

import os
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from config import (  # noqa: E402
    DIM_TOPIC_PATH,
    TOPIC_LABEL_CACHE_PATH,
    TOPIC_LABEL_LLM_MODEL,
)
from topic_labeling import (  # noqa: E402
    _llm_label,
    label_topics,
    top_term_label,
)


def _mask(s: str, keep: int = 4) -> str:
    s = (s or "").strip()
    if len(s) <= keep:
        return "***"
    return s[:keep] + "..." + f"(len={len(s)})"


def _check_env() -> list[str]:
    errors: list[str] = []
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    base = (os.environ.get("OPENAI_API_BASE") or "").strip()
    print(f"OPENAI_API_KEY: {_mask(key)}")
    print(f"OPENAI_API_BASE: {base or '(unset → default OpenAI API)'}")
    print(f"TOPIC_LABEL_LLM_MODEL: {TOPIC_LABEL_LLM_MODEL}")

    if not key:
        errors.append("OPENAI_API_KEY is empty — LLM primary path cannot run")
        return errors

    if key.startswith("gsk_") and not base:
        errors.append(
            "Key looks like Groq (gsk_*) but OPENAI_API_BASE is unset; "
            "client would hit api.openai.com and fail"
        )
    elif key.startswith("gsk_") and base:
        print("PASS: Groq key + OPENAI_API_BASE configured for LLM redirect")
    if base and "groq.com" in base and not key.startswith("gsk_"):
        print("NOTE: Groq base URL set but key does not start with gsk_")
    return errors


def _probe_llm_single() -> tuple[str | None, list[str]]:
    errors: list[str] = []
    terms = ["cable", "charging", "fast", "charger", "usb"]
    print(f"\n--- Probe _llm_label({terms}) ---")
    label = _llm_label(terms)
    if not label:
        errors.append("_llm_label returned None (API missing/failed or bad JSON)")
        return None, errors
    print(f"PASS: LLM returned label={label!r}")
    fallback = top_term_label(terms, 0)
    if label.strip().lower() == fallback.strip().lower():
        print(
            f"NOTE: LLM label equals top-term fallback ({fallback!r}); "
            "still valid if method would be llm_json"
        )
    return label, errors


def _probe_label_topics_main_flow() -> list[str]:
    """Cache-miss path through label_topics -> expect llm_json (then restore files)."""
    errors: list[str] = []
    sample = {
        0: ["cable", "charging", "fast", "charger", "usb"],
        1: ["sound", "bass", "earphones", "ear", "music"],
        7: ["remote", "tv", "working", "original", "works"],
    }

    backups: dict[Path, Path] = {}
    for p in (TOPIC_LABEL_CACHE_PATH, DIM_TOPIC_PATH):
        if p.is_file():
            bak = p.with_suffix(p.suffix + ".bak_llm_test")
            shutil.copy2(p, bak)
            backups[p] = bak

    print("\n--- Probe label_topics (cache miss -> LLM primary) ---")
    try:
        for p in backups:
            p.unlink()
        dim = label_topics(sample)
        if TOPIC_LABEL_CACHE_PATH.is_file():
            import pandas as pd

            cache = pd.read_csv(TOPIC_LABEL_CACHE_PATH)
            methods = cache.set_index("topic_id")["labeling_method"].to_dict()
            labels = cache.set_index("topic_id")["topic_label"].to_dict()
            print(cache.to_string(index=False))
            for tid in sample:
                m = str(methods.get(tid, ""))
                if m != "llm_json":
                    errors.append(
                        f"topic {tid}: expected labeling_method=llm_json, got {m!r} "
                        f"(label={labels.get(tid)!r})"
                    )
                else:
                    print(f"PASS: topic {tid} llm_json -> {labels.get(tid)!r}")
            if len(dim) != len(sample):
                errors.append(f"dim_topic rows={len(dim)} expected {len(sample)}")
        else:
            errors.append("topic_label_cache.csv was not written")
    finally:
        for p, bak in backups.items():
            if p.exists():
                p.unlink()
            if bak.exists():
                shutil.move(str(bak), str(p))
        print("Restored original topic_label_cache.csv / dim_topic.csv")

    return errors


def _probe_fallback_without_key() -> list[str]:
    """Without key, _llm_label must return None (no crash)."""
    errors: list[str] = []
    print("\n--- Probe fallback gate (no key) ---")
    saved = os.environ.pop("OPENAI_API_KEY", None)
    try:
        out = _llm_label(["usb", "cable"])
        if out is not None:
            errors.append(f"expected None without key, got {out!r}")
        else:
            print("PASS: _llm_label returns None when OPENAI_API_KEY unset")
    finally:
        if saved is not None:
            os.environ["OPENAI_API_KEY"] = saved
    return errors


def main() -> int:
    print("=" * 70)
    print("Topic labeling LLM primary-path test")
    print("=" * 70)

    errors: list[str] = []
    errors.extend(_check_env())
    if any("OPENAI_API_KEY is empty" in e for e in errors):
        print("\nFAILED (env):")
        for e in errors:
            print(" -", e)
        return 1

    label, e1 = _probe_llm_single()
    errors.extend(e1)

    # Only run full label_topics if single probe worked (avoids caching failures)
    if label:
        errors.extend(_probe_label_topics_main_flow())
    else:
        print("Skipping label_topics probe because single _llm_label failed")

    errors.extend(_probe_fallback_without_key())

    print("\n" + "=" * 70)
    if errors:
        print("FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("ALL LLM TOPIC-LABELING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
