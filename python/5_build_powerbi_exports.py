"""
Build Power BI import tables from star-schema + Phase 4 NLP outputs.

Writes:
  - fact_product_analytics.csv — 1 row/product (metrics + NLP + watchlist/Critical flags)
  - dim_topic.csv — topic_id + topic_label
  - topic_summary_actionable.csv — re-saved with topic_label

Run after Phase 4:
  python 5_build_powerbi_exports.py
"""
from __future__ import annotations

import pandas as pd

from config import (
    DIM_TOPIC_PATH,
    FACT_PRODUCT_ANALYTICS_PATH,
    NLP_RESULTS_PATH,
    TOPIC_SUMMARY_ACTIONABLE_PATH,
)
from topic_labeling import labels_from_cache
from utils import load_star_schema


def build_powerbi_exports() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not NLP_RESULTS_PATH.is_file():
        raise FileNotFoundError(f"Missing {NLP_RESULTS_PATH.name}. Run Phase 4 first.")
    if not TOPIC_SUMMARY_ACTIONABLE_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {TOPIC_SUMMARY_ACTIONABLE_PATH.name}. Run Phase 4 Block E first."
        )

    star = load_star_schema()
    nlp = pd.read_csv(NLP_RESULTS_PATH)
    actionable = pd.read_csv(TOPIC_SUMMARY_ACTIONABLE_PATH)

    fact = star.merge(
        nlp[["product_id", "predicted_stars", "prediction_confidence", "topic"]],
        on="product_id",
        how="inner",
    )
    if len(fact) != len(star):
        raise ValueError(
            f"NLP merge dropped rows: fact={len(fact)} vs star={len(star)}"
        )

    if "is_critical" not in actionable.columns:
        raise ValueError(
            f"{TOPIC_SUMMARY_ACTIONABLE_PATH.name} missing is_critical. Re-run Phase 4 Block E."
        )

    keys = actionable[["category_main", "topic", "is_critical"]].drop_duplicates()
    keys = keys.assign(is_watchlist_product=True)
    fact = fact.merge(keys, on=["category_main", "topic"], how="left")
    fact["is_watchlist_product"] = fact["is_watchlist_product"].fillna(False).astype(bool)
    fact["is_critical_product"] = fact["is_critical"].fillna(False).astype(bool)
    fact_out = fact.drop(columns=["is_critical", "category_main", "category_sub"])

    topic_ids = sorted(nlp["topic"].unique())
    label_map = labels_from_cache(topic_ids)
    dim_topic = pd.DataFrame(
        {"topic_id": topic_ids, "topic_label": [label_map[int(t)] for t in topic_ids]}
    )
    dim_topic.to_csv(DIM_TOPIC_PATH, index=False)

    actionable_out = actionable.copy()
    actionable_out["topic_label"] = [
        label_map[int(t)] for t in actionable_out["topic"]
    ]
    actionable_out["is_critical"] = actionable_out["is_critical"].astype(bool)

    fact_out.to_csv(FACT_PRODUCT_ANALYTICS_PATH, index=False)
    actionable_out.to_csv(TOPIC_SUMMARY_ACTIONABLE_PATH, index=False)

    n_watch = int(fact_out["is_watchlist_product"].sum())
    n_crit = int(fact_out["is_critical_product"].sum())
    n_crit_cells = int(actionable_out["is_critical"].sum())
    print(
        f"{FACT_PRODUCT_ANALYTICS_PATH.name}: {fact_out.shape[0]} rows x "
        f"{fact_out.shape[1]} cols | watchlist={n_watch} | critical={n_crit}"
    )
    print(f"{DIM_TOPIC_PATH.name}: {len(dim_topic)} topics")
    print(
        f"{TOPIC_SUMMARY_ACTIONABLE_PATH.name}: {len(actionable_out)} watchlist cells "
        f"({n_crit_cells} critical) with topic_label"
    )
    return fact_out, dim_topic, actionable_out


if __name__ == "__main__":
    build_powerbi_exports()
