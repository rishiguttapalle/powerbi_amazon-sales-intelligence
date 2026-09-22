# Amazon Product Pricing & Customer Satisfaction Intelligence

> **Business question:** Does deeper discounting actually earn more customer engagement and satisfaction — or is it concentrated in categories that would sell anyway, meaning the discount budget is being wasted?

Reproducible analytics pipeline on a public Amazon product/review dataset:

**data audit → star schema → DuckDB warehouse → confound-controlled statistics → NLP on reviews → Power BI dashboard**

Paths, thresholds, and shared helpers live in `python/config.py` and `python/utils.py` (no hardcoded machine paths in notebooks).

---

## Status

| Phase | Deliverable | Status |
|------:|-------------|--------|
| 0 | Data audit + cleaning | Done |
| 1 | Star-schema data model (CSV) | Done |
| 2 | DuckDB database build | Done |
| 3 | Statistical analysis (confound-controlled) | Done |
| 4 | NLP on review text (sentiment + topics) | Done |
| 5 | Power BI dashboard | Done |

**Dashboard file:** [`dashboard/amazon_sales_intelligence.pbix`](dashboard/amazon_sales_intelligence.pbix)

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

Processed CSVs and the DuckDB file are **gitignored**. Rebuild them locally with the pipeline below.

### 4. Optional — LLM topic labels (`.env`)

```powershell
Copy-Item .env.example .env
# edit .env → OPENAI_API_KEY=sk-...
```

Without a key, Phase 4 uses **top-term** topic labels. With a key, re-run Phase 4 Block D to refresh `dim_topic.csv` / `topic_label_cache.csv`.

---

## Running the pipeline

Run steps **in order**. Phase 2 always **rebuilds** DuckDB from the latest star-schema CSVs.

| Step | Run | Produces |
|-----:|-----|----------|
| 0 | `python/0_data_audit.ipynb` | `products_clean.csv` |
| 1 | `python/1_build_model.ipynb` | `dim_*.csv`, `fact_product_metrics.csv`, `review_text.csv` |
| 2 | `python/2_build_database.py` | `amazon_sales_intelligence.db` |
| 3 | `python/3_hypothesis_test.ipynb` | Controlled discount vs rating / engagement results |
| 4 | `python/4_review_nlp.ipynb` | NLP outputs + watchlist / Critical flags |
| 5.0 | `python/5_build_powerbi_exports.py` | `fact_product_analytics.csv`, `dim_topic.csv`, actionable labels |
| 5 | Open `dashboard/amazon_sales_intelligence.pbix` | Interactive dashboard |

### Phase 2 — rebuild the database

```powershell
.\venv\Scripts\python.exe python\2_build_database.py
```

**Expected load sizes (current dataset):** 29 categories · 1,350 products · 1,350 fact rows · FK validation OK.

### Refresh Power BI exports

```powershell
.\venv\Scripts\python.exe python\5_build_powerbi_exports.py
```

Then **Refresh** in Power BI Desktop. Expect **1,350** fact rows; console prints watchlist (~619) and Critical (~133) counts.

---

## Repository layout

```text
.
├── data/
│   ├── raw/                      # amazon_sales.xlsx (from Kaggle)
│   └── processed/                # generated CSVs (gitignored)
├── python/
│   ├── config.py                 # Paths, thresholds, NLP / label settings
│   ├── utils.py                  # Shared loaders, parsers, DB helpers
│   ├── topic_labeling.py         # LLM / top-term topic labels + cache
│   ├── 0_data_audit.ipynb
│   ├── 1_build_model.ipynb
│   ├── 2_build_database.py
│   ├── 3_hypothesis_test.ipynb
│   ├── 4_review_nlp.ipynb
│   └── 5_build_powerbi_exports.py
├── sql/schema.sql
├── dashboard/
│   └── amazon_sales_intelligence.pbix
├── legacy/                       # Earlier prototype (reference only)
├── .env.example
└── requirements.txt
```

---

## What each phase does

### Phase 0 — Data audit
Inspect shape, dtypes, and nulls; drop non-numeric rating placeholders (`|`); export `products_clean.csv`.

### Phase 1 — Data model
Parse INR prices, split category hierarchy, bucket price tiers, aggregate to **product** grain:

- Star: `dim_category` → `dim_product` → `fact_product_metrics`
- `review_text.csv` kept for NLP (not loaded into DuckDB fact grain)

### Phase 2 — Database
Apply `sql/schema.sql`, named-column CSV loads into DuckDB, FK validation.

### Phase 3 — Statistical analysis
1. Log-transform skewed engagement counts  
2. Naive Pearson / Spearman  
3. ANOVA — discount depth differs by category *(confound is real)*  
4. OLS with HC3 robust SEs — discount effect **conditional on category + price tier**

**Headline result:** after controls, deeper discounts remain associated with **lower** ratings and **lower** lifetime rating volume. Category mix does **not** explain the relationship away.

### Phase 4 — NLP
Sentiment + topics — the *why* behind Phase 3.

| Check | What we do |
|-------|------------|
| Trust gate | Predicted stars vs product `rating` (MAE / Pearson) before topics |
| Topics | BERTopic + seeded UMAP; English + `NLP_DOMAIN_STOPWORDS` for c-TF-IDF keywords |
| Labels | `OPENAI_API_KEY` in `.env` → LLM JSON labels (cached); else top-term concat |
| Outliers | `topic = -1` kept in `nlp_results.csv`; Block F → `nlp_outlier_xtab.csv` |
| Watchlist / Critical | **Watchlist:** `n ≥ 10` + below-category-median rating & above-category-median discount. **Critical:** among watchlist, rating ≤ Q1 & discount ≥ median (Page 1 KPI) |

**Current run (summary):** trust gate MAE ≈ 0.76, r ≈ 0.42; BERTopic outlier share ≈ 7.6%; deepest-discount quartile is **not** outlier-heavy — Phase 3 signal lives in named topics.

**Key outputs:** `nlp_results.csv`, `topic_summary.csv`, `topic_summary_actionable.csv`, `nlp_outlier_xtab.csv`, `fact_product_analytics.csv`, `dim_topic.csv`, `topic_label_cache.csv`

### Phase 5 — Power BI dashboard

Open [`dashboard/amazon_sales_intelligence.pbix`](dashboard/amazon_sales_intelligence.pbix).

#### Model

| Table | Role |
|-------|------|
| `fact_product_analytics` | 1 row/product — metrics, NLP, `is_watchlist_product`, `is_critical_product` |
| `dim_category` | Category dimension (`category_id`) |
| `dim_topic` | Topic labels (`topic_id` ↔ fact `topic`) |
| `topic_summary_actionable` | 14 watchlist cells (disconnected exploration table) |
| `_Measures` | KPI measures (Total Products, Avg Rating, Critical, etc.) |

**KPI rule:** headline **Critical** (~133 products, ~10% of catalog). Watchlist (~619 / 14 cells) is the broader relative list — not “half the catalog is failing.”

#### Pages (business questions)

| Page | Business question | What you see |
|------|-------------------|--------------|
| **1 — Executive Overview** | Does deeper discounting hurt satisfaction overall — and how large is the Critical hotspot? | KPI cards (Total, Avg Rating, Avg Discount, Critical, % Critical); category scatter (discount vs rating); slicers: category, price tier |
| **2 — Discount & Rating Analysis** | Where (by category / price tier) is high discount paired with weaker ratings? | Combo chart (discount + rating by category); slicers: category, price tier |
| **3 — Threat Zones / Watchlist** | Which review themes are on the relative watchlist, and which are Critical enough to act on first? | Watchlist + Critical cards; watchlist cell table; product detail table; slicers: category, price tier |

Legacy prototype (reference only): `legacy/`.

---

## Configuration

Central constants: `python/config.py`

- Paths (raw/processed CSVs, `DB_PATH`, NLP / Power BI export paths)
- `PRICE_TIER_QUANTILES` / `PRICE_TIER_LABELS`
- `SMALL_CATEGORY_THRESHOLD` (Phase 3 → `Other`)
- `TOPIC_MIN_PRODUCTS`, `CRITICAL_RATING_QUANTILE`, `CRITICAL_DISCOUNT_QUANTILE`, `NLP_DOMAIN_STOPWORDS`
- `TOPIC_LABEL_CACHE_PATH`, `TOPIC_LABEL_LLM_MODEL`, `TOPIC_LABEL_TOP_N_TERMS`
- `SENTIMENT_MODEL`, `EMBEDDING_MODEL`, `BERTOPIC_MIN_TOPIC_SIZE`

Shared helpers: `python/utils.py` — `parse_inr`, `parse_int_commas`, `load_products_clean`, `load_star_schema`, `collapse_small_categories`, `get_connection`, `validate_star_schema`

---

## Tech stack

| Layer | Tools |
|-------|--------|
| Environment | VS Code, Git, Python venv |
| Data | pandas, openpyxl, DuckDB |
| Stats | scipy, statsmodels |
| NLP | transformers, sentence-transformers, BERTopic, scikit-learn, openai (optional) |
| BI | Power BI Desktop (`.pbix` in `dashboard/`) |
| Repro | `requirements.txt`, `config.py`, `utils.py`, `.env.example` |

---

## Data note

The Amazon sales spreadsheet is a third-party Kaggle dataset. Download it locally; do not commit the raw file.
