-- Document the schema in SQL

-- dim_category: one row per unique main/sub category combination
CREATE TABLE dim_category (
    category_id INTEGER PRIMARY KEY,
    category_main VARCHAR,
    category_sub VARCHAR
);

-- dim_product: one row per product
CREATE TABLE dim_product (
    product_id VARCHAR PRIMARY KEY,
    product_name VARCHAR,
    category_id INTEGER REFERENCES dim_category(category_id),
    price_tier VARCHAR
);

-- fact_product_metrics: one row per product, numeric measures
CREATE TABLE fact_product_metrics (
    product_id VARCHAR REFERENCES dim_product(product_id),
    actual_price NUMERIC,
    discounted_price NUMERIC,
    discount_percentage NUMERIC,
    rating NUMERIC,
    rating_count INTEGER,
    n_reviewers INTEGER
);
