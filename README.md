# Amazon Product Pricing & Customer Satisfaction Intelligence

> **Business question:** Does deeper discounting actually earn more customer engagement and satisfaction — or is it concentrated in categories that would sell anyway, meaning the discount budget is being wasted?

This repository is a reproducible analytics pipeline on a public Amazon product/review dataset:

**data audit → star schema → DuckDB warehouse → confound-controlled statistics → NLP on reviews → Power BI dashboard**

Paths, thresholds, and shared helpers live in `python/config.py` and `python/utils.py` so notebooks never hardcode local machine paths.

---

## Status

| Phase | Deliverable | Status |
|------:|-------------|--------|
| 0 | Data audit + cleaning | Done |
| 1 | Star-schema data model (CSV) | Done |
| 2 | DuckDB database build | Done |
| 3 | Statistical analysis (confound-controlled) | Done |
| 4 | NLP on review text (sentiment + topics) | Done |
| 5.0 | Power BI export tables | Done |
| 5.1+ | Power BI dashboard | Ready to start |

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd powerbi_amazon-sales-intelligence
```

### 2. Create a virtual environment and install dependencies

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Use **Python 3.11+** (developed with 3.13). When opening notebooks under `python/`, select this project’s `venv` as the Jupyter kernel.

**Optional (Phase 4 NLP — CPU PyTorch):**

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 3. Download the dataset

| | |
|---|---|
| **Source** | [Kaggle — Amazon Sales Dataset](https://www.kaggle.com/datasets/karkavelrajaj/amazon-sales-dataset) |
| **Place at** | `data/raw/amazon_sales.xlsx` |

Processed CSVs and the DuckDB file are **gitignored**. Anyone cloning the repo rebuilds them locally with the pipeline below.

### 4. Optional — LLM topic labels (`.env`)

Copy the example and add your key (file is gitignored):

```powershell
Copy-Item .env.example .env
# then edit .env and set OPENAI_API_KEY=sk-...
```

Without a key, Phase 4 still runs and uses **top-term** topic labels. With a key, re-run Phase 4 Block D to refresh `dim_topic.csv` / `topic_label_cache.csv`.

---

## Running the pipeline

Run steps **in order**. Phase 2 always **rebuilds** the DuckDB warehouse from the latest star-schema CSVs (drop → create → load → FK validate), so the database stays in sync after re-running Phase 1.

| Step | Run | Produces |
|-----:|-----|----------|
| 0 | `python/0_data_audit.ipynb` | `data/processed/products_clean.csv` |
| 1 | `python/1_build_model.ipynb` | `dim_*.csv`, `fact_*.csv`, `review_text.csv` |
| 2 | `2_build_database.py` (see below) | `amazon_sales_intelligence.db` |
| 3 | `python/3_hypothesis_test.ipynb` | Controlled discount vs rating / engagement results |
| 4 | `python/4_review_nlp.ipynb` | NLP outputs + Step 5.0 exports |
| 5.0 | `python/5_build_powerbi_exports.py` | `fact_product_analytics.csv`, `dim_topic.csv` (+ actionable labels) |
| 5 | Power BI Desktop *(planned)* | Dashboard under `dashboard/` |

### Phase 2 — rebuild the database

From the repo root:

```powershell
.\venv\Scripts\python.exe python\2_build_database.py
```

Or from `python/`:

```powershell
cd python
..\venv\Scripts\python.exe 2_build_database.py
```

**Expected load sizes (current dataset):** 29 categories · 1,350 products · 1,350 fact rows · FK validation OK.

---

## Repository layout

```text
.
├── data/
│   ├── raw/                      # amazon_sales.xlsx (download from Kaggle)
│   └── processed/                # generated CSVs (gitignored)
├── python/
│   ├── config.py                 # Paths, thresholds, NLP stops / models
│   ├── utils.py                  # Shared loaders, parsers, DB helpers
│   ├── 0_data_audit.ipynb
│   ├── 1_build_model.ipynb
│   ├── 2_build_database.py
│   ├── 3_hypothesis_test.ipynb
│   ├── 4_review_nlp.ipynb
│   ├── 5_build_powerbi_exports.py  # Step 5.0 Power BI tables
│   └── topic_labeling.py           # LLM / top-term topic labels
├── sql/
│   └── schema.sql
├── dashboard/                    # Phase 5.1+ (.pbix)
├── legacy/                       # Earlier Power BI prototype
├── .env.example                  # Template for OPENAI_API_KEY
├── requirements.txt
└── amazon_sales_intelligence.db  # Generated (gitignored)
```

---

## What each phase does

### Phase 0 — Data audit
Inspect shape, dtypes, and nulls; detect non-numeric rating placeholders (`|`); drop bad rows; export a cleaned working table.

### Phase 1 — Data model
Parse INR prices, split the category hierarchy, bucket price tiers, aggregate to **product** grain, and write a star schema:

- `dim_category` → `dim_product` → `fact_product_metrics`
- `review_text` kept as a Python-side CSV (not loaded into the PBI-facing fact grain)

### Phase 2 — Database
Apply `sql/schema.sql`, load star CSVs into DuckDB with **named-column** inserts, and validate foreign keys.

### Phase 3 — Statistical analysis
Answers the business question with confound control:

1. Log-transform skewed engagement counts  
2. Naive Pearson / Spearman (surface association)  
3. ANOVA — does discount depth differ by category? *(confound is real)*  
4. OLS with HC3 robust SEs — discount effect **conditional on category + price tier**

**Headline result (current data):** after controlling for category and price tier, deeper discounts remain associated with **lower** ratings and **lower** lifetime rating volume. Category mix does **not** explain the relationship away; if anything, it partly masked it.

### Phase 4 — NLP
Sentiment (transformer star ratings) and topic structure on review text — the *why* behind Phase 3.

| Check | What we do |
|-------|------------|
| Trust gate | Predicted stars vs product `rating` (MAE / Pearson) before topics |
| Topic keywords | BERTopic c-TF-IDF uses **English + domain stopwords** (`NLP_DOMAIN_STOPWORDS`); clustering still uses embeddings + seeded UMAP |
| Topic labels | Put `OPENAI_API_KEY` in repo-root `.env` for LLM labels (`topic_labeling.py`, cached); otherwise top-term concatenation |
| Outliers | `topic = -1` kept in `nlp_results.csv`, excluded from topic summaries; Block F exports discount×rating outlier rates to `nlp_outlier_xtab.csv` |
| Actionable export | `topic_summary_actionable.csv` keeps only cells with **`n_products ≥ TOPIC_MIN_PRODUCTS` (10)** and low-rating / high-discount flags |

**Current run (summary):**

- Trust gate: MAE ≈ 0.76, Pearson r ≈ 0.42  
- Method: `BERTopic (all-MiniLM-L6-v2, seeded UMAP, stopword vectorizer)`  
- Outlier share ≈ 7.6%; deepest-discount quartile is **not** overall outlier-heavy — Phase 3 signal lives mainly in named topics  
- Phase 5 should prefer **`topic_summary_actionable.csv`**

**Outputs:**

- `data/processed/nlp_results.csv`
- `data/processed/topic_summary.csv`
- `data/processed/topic_summary_actionable.csv` (includes `topic_label` after Step 5.0)
- `data/processed/nlp_outlier_xtab.csv`
- `data/processed/fact_product_analytics.csv` — Power BI fact (1 row/product)
- `data/processed/dim_topic.csv` — Power BI topic dimension

### Phase 5 — Dashboard
**Step 5.0 is done.** Import into Power BI Desktop:

| Table | Role |
|-------|------|
| `fact_product_analytics.csv` | Fact (1 row/product) |
| `dim_category.csv` | Category dimension |
| `dim_topic.csv` | Topic labels |
| `topic_summary_actionable.csv` | Threat-zone page (disconnected or related by category + topic) |
| `nlp_outlier_xtab.csv` | Optional outlier callout |

Rebuild exports anytime:

```powershell
.\venv\Scripts\python.exe python\5_build_powerbi_exports.py
```

Expected: **1350** fact rows; threat-zone product count printed in the console. Legacy prototype (reference only): `legacy/`.

---

## Configuration

Central constants: `python/config.py`

- Paths (`RAW_SALES_PATH`, processed CSVs, `DB_PATH`, `STAR_CSV_PATHS`, NLP output paths)
- `PRICE_TIER_QUANTILES` / `PRICE_TIER_LABELS`
- `SMALL_CATEGORY_THRESHOLD` (Phase 3 → `Other`)
- `TOPIC_MIN_PRODUCTS`, `NLP_DOMAIN_STOPWORDS`, `NLP_OUTLIER_XTAB_PATH` (Phase 4)
- `TOPIC_LABEL_CACHE_PATH`, `TOPIC_LABEL_LLM_MODEL`, `TOPIC_LABEL_TOP_N_TERMS` (topic labeling; key from `.env`)
- NLP model names (`SENTIMENT_MODEL`, `EMBEDDING_MODEL`, …)

Shared helpers: `python/utils.py`

- `parse_inr`, `parse_int_commas`
- `load_products_clean`, `load_star_schema`
- `collapse_small_categories`, `get_connection`, `validate_star_schema`

---

## Tech stack

| Layer | Tools |
|-------|--------|
| Environment | VS Code, Git, Python venv |
| Data | pandas, openpyxl, DuckDB |
| Stats | scipy, statsmodels |
| NLP | transformers, sentence-transformers, BERTopic, scikit-learn, openai (optional labels) |
| BI | Power BI Desktop |
| Repro | `requirements.txt`, `config.py`, `utils.py` |

---

## Data note

The Amazon sales spreadsheet is a third-party Kaggle dataset. This repo expects you to download the raw file locally rather than committing it.
