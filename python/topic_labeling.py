"""
Topic labeling for Power BI dim_topic.

Primary: LLM JSON label when OPENAI_API_KEY is set (from .env via config, or shell).
Fallback: top-term concatenation — no manual name dictionary.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import pandas as pd

from config import (
    DIM_TOPIC_PATH,
    RANDOM_SEED,
    TOPIC_LABEL_CACHE_PATH,
    TOPIC_LABEL_LLM_MODEL,
    TOPIC_LABEL_TOP_N_TERMS,
)

_LABEL_SYSTEM = """You label Amazon product-review topic clusters for a business dashboard.
Return ONLY valid JSON: {"topic_label": "<3-6 word plain-English name>"}.
Rules: no quotes inside the label, no topic IDs, no marketing fluff, be specific to the keywords."""

_LABEL_FEW_SHOTS = [
    {
        "role": "user",
        "content": "Keywords: remote, tv, working, buttons, original\nReturn JSON.",
    },
    {
        "role": "assistant",
        "content": '{"topic_label": "TV remote quality issues"}',
    },
    {
        "role": "user",
        "content": "Keywords: cable, charging, fast, charger, usb\nReturn JSON.",
    },
    {
        "role": "assistant",
        "content": '{"topic_label": "USB charging cables"}',
    },
]


def top_term_label(terms: list[str], topic_id: int) -> str:
    """Deterministic label from top c-TF-IDF terms (API fallback)."""
    cleaned = [re.sub(r"[^a-z0-9]+", " ", t.lower()).strip() for t in terms]
    cleaned = [t for t in cleaned if t]
    if topic_id == -1 and not cleaned:
        return "Outlier unclustered reviews"
    if not cleaned:
        return f"Topic {topic_id}"
    return " ".join(cleaned[:TOPIC_LABEL_TOP_N_TERMS]).title()


def extract_bertopic_terms(
    topic_model, top_n: int = TOPIC_LABEL_TOP_N_TERMS
) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for tid, word_scores in topic_model.get_topics().items():
        out[int(tid)] = [w for w, _ in (word_scores or [])[:top_n]]
    return out


def _load_cache() -> pd.DataFrame:
    cols = ["topic_id", "top_terms", "topic_label", "labeling_method", "model", "labeled_at"]
    if not TOPIC_LABEL_CACHE_PATH.is_file():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(TOPIC_LABEL_CACHE_PATH)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def _save_cache(df: pd.DataFrame) -> None:
    TOPIC_LABEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values("topic_id").to_csv(TOPIC_LABEL_CACHE_PATH, index=False)


def _llm_label(terms: list[str]) -> str | None:
    """OpenAI chat with JSON response. Returns None if no key / offline / failure."""
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        print("openai package not installed; using top-term labels")
        return None

    keywords = ", ".join(terms) if terms else "(no keywords)"
    messages = [
        {"role": "system", "content": _LABEL_SYSTEM},
        *_LABEL_FEW_SHOTS,
        {"role": "user", "content": f"Keywords: {keywords}\nReturn JSON."},
    ]
    client_kwargs: dict = {"api_key": api_key}
    if os.environ.get("OPENAI_API_BASE"):
        client_kwargs["base_url"] = os.environ["OPENAI_API_BASE"]

    try:
        client = OpenAI(**client_kwargs)
        create_kwargs = {
            "model": TOPIC_LABEL_LLM_MODEL,
            "temperature": 0,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = client.chat.completions.create(**create_kwargs, seed=RANDOM_SEED)
        except TypeError:
            resp = client.chat.completions.create(**create_kwargs)

        data = json.loads(resp.choices[0].message.content or "")
        label = re.sub(r"\s+", " ", str(data.get("topic_label", "")).strip()).strip(" \"'")
        if not label or len(label) > 80:
            return None
        return label
    except Exception as e:
        print(f"LLM labeling failed ({type(e).__name__}: {e}); using top-term fallback")
        return None


def label_topics(top_terms_by_topic: dict[int, list[str]]) -> pd.DataFrame:
    """
    Label each topic_id. Cache hit when topic_id + top_terms match.
    Primary: LLM. Fallback: top-term concat. Writes cache + dim_topic.csv.
    """
    cache = _load_cache()
    cache_idx = {
        int(r.topic_id): r
        for r in cache.itertuples(index=False)
        if pd.notna(r.topic_id)
    }
    rows = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for topic_id in sorted(top_terms_by_topic.keys()):
        terms = [str(t) for t in top_terms_by_topic[topic_id]][:TOPIC_LABEL_TOP_N_TERMS]
        terms_str = "|".join(terms)
        prev = cache_idx.get(int(topic_id))

        if (
            prev is not None
            and str(prev.top_terms) == terms_str
            and pd.notna(prev.topic_label)
            and str(prev.topic_label).strip()
        ):
            rows.append(
                {
                    "topic_id": int(topic_id),
                    "top_terms": terms_str,
                    "topic_label": str(prev.topic_label).strip(),
                    "labeling_method": str(prev.labeling_method),
                    "model": prev.model if pd.notna(prev.model) else "",
                    "labeled_at": prev.labeled_at if pd.notna(prev.labeled_at) else now,
                }
            )
            continue

        llm_label = _llm_label(terms)
        if llm_label:
            method, model, label = "llm_json", TOPIC_LABEL_LLM_MODEL, llm_label
        else:
            method, model, label = "top_terms", "", top_term_label(terms, int(topic_id))

        rows.append(
            {
                "topic_id": int(topic_id),
                "top_terms": terms_str,
                "topic_label": label,
                "labeling_method": method,
                "model": model,
                "labeled_at": now,
            }
        )

    out = pd.DataFrame(rows)
    _save_cache(out)
    dim = out[["topic_id", "topic_label"]].copy()
    dim.to_csv(DIM_TOPIC_PATH, index=False)

    n_llm = int((out["labeling_method"] == "llm_json").sum())
    n_fb = int((out["labeling_method"] == "top_terms").sum())
    print(
        f"Topic labels: {len(out)} topics "
        f"(llm={n_llm}, top_terms_fallback={n_fb}) -> {DIM_TOPIC_PATH.name}"
    )
    print(f"Cache: {TOPIC_LABEL_CACHE_PATH.name}")
    return dim


def labels_from_cache(topic_ids) -> dict[int, str]:
    """Map topic_id -> label from cache, then dim_topic.csv, else Topic {id}."""
    cache = _load_cache()
    m: dict[int, str] = {}
    if not cache.empty:
        m = {
            int(r.topic_id): str(r.topic_label)
            for r in cache.itertuples(index=False)
            if pd.notna(r.topic_label)
        }
    elif DIM_TOPIC_PATH.is_file():
        dim = pd.read_csv(DIM_TOPIC_PATH)
        m = {int(r.topic_id): str(r.topic_label) for r in dim.itertuples(index=False)}
    return {int(t): m.get(int(t), f"Topic {int(t)}") for t in topic_ids}
