from contextlib import contextmanager

import duckdb
import pandas as pd

from config import DB_PATH, PRODUCTS_CLEAN_PATH, SMALL_CATEGORY_THRESHOLD


@contextmanager
def get_connection(db_path=DB_PATH):
    con = duckdb.connect(str(db_path))
    try:
        yield con
    finally:
        con.close()


def load_star_schema():
    """Joined fact + product + category table for Phases 3+."""
    with get_connection() as con:
        return con.execute("""
            SELECT f.*, p.category_id, p.price_tier, c.category_main, c.category_sub
            FROM fact_product_metrics f
            JOIN dim_product p USING (product_id)
            JOIN dim_category c USING (category_id)
        """).df()


def load_products_clean():
    return pd.read_csv(PRODUCTS_CLEAN_PATH)


def parse_inr(series: pd.Series) -> pd.Series:
    """Strip ₹ / thousands-commas → float (NaN on failure)."""
    return pd.to_numeric(
        series.astype(str).str.replace(r"[₹,]", "", regex=True),
        errors="coerce",
    )


def parse_int_commas(series: pd.Series) -> pd.Series:
    """Strip thousands-commas → non-null int (failed parses → 0)."""
    return (
        pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")
        .fillna(0)
        .astype(int)
    )


def collapse_small_categories(
    df: pd.DataFrame,
    col: str = "category_main",
    threshold: int = SMALL_CATEGORY_THRESHOLD,
    other: str = "Other",
) -> pd.DataFrame:
    """Map categories with fewer than `threshold` rows to `other`."""
    counts = df[col].value_counts()
    small = counts[counts < threshold].index
    if len(small) == 0:
        return df
    out = df.copy()
    out[col] = out[col].mask(out[col].isin(small), other)
    return out


def validate_star_schema(con) -> dict[str, int]:
    """Raise if fact/product rows reference missing parents."""
    checks = {
        "orphaned_products": """
            SELECT COUNT(*) FROM dim_product p
            LEFT JOIN dim_category c USING (category_id)
            WHERE c.category_id IS NULL
        """,
        "orphaned_metrics": """
            SELECT COUNT(*) FROM fact_product_metrics f
            LEFT JOIN dim_product p USING (product_id)
            WHERE p.product_id IS NULL
        """,
    }
    counts = {name: con.execute(sql).fetchone()[0] for name, sql in checks.items()}
    bad = {k: v for k, v in counts.items() if v}
    if bad:
        raise ValueError(f"Star-schema integrity failed: {bad}")
    return counts
