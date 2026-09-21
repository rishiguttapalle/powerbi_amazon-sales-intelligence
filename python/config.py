from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "python" / "outputs"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
DB_PATH = PROJECT_ROOT / "amazon_sales_intelligence.db"

RAW_SALES_PATH = DATA_RAW / "amazon_sales.xlsx"
PRODUCTS_CLEAN_PATH = DATA_PROCESSED / "products_clean.csv"
REVIEW_TEXT_PATH = DATA_PROCESSED / "review_text.csv"
NLP_RESULTS_PATH = DATA_PROCESSED / "nlp_results.csv"
TOPIC_SUMMARY_PATH = DATA_PROCESSED / "topic_summary.csv"
TOPIC_SUMMARY_ACTIONABLE_PATH = DATA_PROCESSED / "topic_summary_actionable.csv"
NLP_OUTLIER_XTAB_PATH = DATA_PROCESSED / "nlp_outlier_xtab.csv"

# Parent → child load order (drop in reverse)
STAR_TABLES = ("dim_category", "dim_product", "fact_product_metrics")
TABLE_COLUMNS = {
    "dim_category": ["category_id", "category_main", "category_sub"],
    "dim_product": ["product_id", "product_name", "category_id", "price_tier"],
    "fact_product_metrics": [
        "product_id",
        "actual_price",
        "discounted_price",
        "discount_percentage",
        "rating",
        "rating_count",
        "n_reviewers",
    ],
}
STAR_CSV_PATHS = {t: DATA_PROCESSED / f"{t}.csv" for t in STAR_TABLES}
DIM_CATEGORY_PATH = STAR_CSV_PATHS["dim_category"]
DIM_PRODUCT_PATH = STAR_CSV_PATHS["dim_product"]
FACT_METRICS_PATH = STAR_CSV_PATHS["fact_product_metrics"]

RANDOM_SEED = 42
PRICE_TIER_QUANTILES = 4
PRICE_TIER_LABELS = ["Budget", "Mid", "Premium", "Luxury"]
SMALL_CATEGORY_THRESHOLD = 10

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SENTIMENT_MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"
BERTOPIC_MIN_TOPIC_SIZE = 15
NMF_N_TOPICS = 10
TFIDF_MAX_FEATURES = 2000
# Min products in a category×topic cell for Phase 5 "threat zone" export
TOPIC_MIN_PRODUCTS = 10
# Extra stops for BERTopic/NMF c-TF-IDF labels (clustering uses embeddings, not these)
NLP_DOMAIN_STOPWORDS = frozenset({
    "product", "products", "amazon", "good", "nice", "quality", "price",
    "like", "love", "great", "best", "awesome", "excellent", "thank", "thanks",
    "really", "also", "one", "get", "got", "use", "using", "used", "item",
    "order", "ordered", "delivery", "review", "reviews", "buy", "bought",
})
