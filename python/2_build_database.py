"""
Rebuild amazon_sales_intelligence.db from sql/schema.sql + processed star-schema CSVs.
Run after Phase 1 (or whenever those CSVs change).
"""
from config import SCHEMA_PATH, STAR_CSV_PATHS, STAR_TABLES, TABLE_COLUMNS
from utils import get_connection, validate_star_schema


def build_database():
    missing = [t for t, path in STAR_CSV_PATHS.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing processed CSVs: {missing}. Run Phase 1 (1_build_model) first."
        )

    with get_connection() as con:
        for table in reversed(STAR_TABLES):
            con.execute(f"DROP TABLE IF EXISTS {table}")

        con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

        for table in STAR_TABLES:
            cols = ", ".join(TABLE_COLUMNS[table])
            con.execute(
                f"INSERT INTO {table} ({cols}) SELECT {cols} FROM read_csv_auto(?)",
                [STAR_CSV_PATHS[table].as_posix()],
            )
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {n} rows")

        validate_star_schema(con)
        print("FK validation OK")


if __name__ == "__main__":
    build_database()
