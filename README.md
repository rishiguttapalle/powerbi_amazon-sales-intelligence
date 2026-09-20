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
| 4 | NLP on review text (sentiment + topics) | In progress |
| 5 | Power BI dashboard | Planned *(legacy prototype in `legacy/`)* |

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

---

## Running the pipeline

Run steps **in order**. Phase 2 always **rebuilds** the DuckDB warehouse from the latest star-schema CSVs (drop → create → load → FK validate), so the database stays in sync after re-running Phase 1.

| Step | Run | Produces |
|-----:|-----|----------|
| 0 | `python/0_data_audit.ipynb` | `data/processed/products_clean.csv` |
| 1 | `python/1_build_model.ipynb` | `dim_*.csv`, `fact_*.csv`, `review_text.csv` |
| 2 | `2_build_database.py` (see below) | `amazon_sales_intelligence.db` |
| 3 | `python/3_hypothesis_test.ipynb` | Controlled discount vs rating / engagement results |
| 4 | NLP notebook *(in progress)* | Sentiment + topics on `review_text` |
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
│   └── processed/                # products_clean + star-schema CSVs (generated)
├── python/
│   ├── config.py                 # Paths, thresholds, NLP model names
│   ├── utils.py                  # Shared loaders, parsers, DB helpers
│   ├── 0_data_audit.ipynb        # Phase 0 — audit + clean export
│   ├── 1_build_model.ipynb       # Phase 1 — star schema CSVs
│   ├── 2_build_database.py       # Phase 2 — rebuild DuckDB
│   ├── 3_hypothesis_test.ipynb   # Phase 3 — correlations, ANOVA, controlled OLS
│   └── outputs/                  # Optional analysis artifacts
├── sql/
│   └── schema.sql                # dim_category, dim_product, fact_product_metrics
├── dashboard/                    # Power BI deliverable (Phase 5)
├── legacy/                       # Earlier Power BI prototype + notes
├── requirements.txt
└── amazon_sales_intelligence.db  # Generated DuckDB warehouse (gitignored)
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

### Phase 4 — NLP *(in progress)*
Sentiment and topic structure on review text. Model names and related knobs live in `python/config.py` (`SENTIMENT_MODEL`, `EMBEDDING_MODEL`, …).

### Phase 5 — Dashboard *(planned)*
Executive visuals in Power BI on the star schema (and NLP outputs once available). A prior prototype lives under `legacy/`.

---

## Configuration

Central constants: `python/config.py`

- Paths (`RAW_SALES_PATH`, processed CSVs, `DB_PATH`, `STAR_CSV_PATHS`)
- `PRICE_TIER_QUANTILES` / `PRICE_TIER_LABELS`
- `SMALL_CATEGORY_THRESHOLD` (unstable categories → `Other` in Phase 3)
- NLP model names (Phase 4)

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
| NLP | transformers, sentence-transformers, BERTopic, scikit-learn |
| BI | Power BI Desktop |
| Repro | `requirements.txt`, `config.py`, `utils.py` |

---

## Data note

The Amazon sales spreadsheet is a third-party Kaggle dataset. This repo expects you to download the raw file locally rather than committing it.
