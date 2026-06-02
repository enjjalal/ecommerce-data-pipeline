"""
seed_bigquery.py
Uploads the locally generated CSV files into BigQuery under dataset: raw_stage
Tables created:
  - raw_stage.raw_transactions
  - raw_stage.raw_user_clicks
  - raw_stage.raw_system_errors

Usage:
  Set environment variable GCP_KEY_PATH to point to your service account JSON key.
  Then run: python seed_bigquery.py
"""

import os
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT_ID  = "ecommerce-pipeline-498214"
DATASET_ID  = "raw_stage"
REGION      = "US"

KEY_PATH    = os.environ.get("GCP_KEY_PATH", r"C:\de_projects\ci_cd\gcp_key.json")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "output")

# ── Table schemas ─────────────────────────────────────────────────────────────
SCHEMAS = {
    "raw_transactions": [
        bigquery.SchemaField("order_id",        "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("user_id",         "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("product_id",      "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("category",        "STRING"),
        bigquery.SchemaField("quantity",        "INTEGER"),
        bigquery.SchemaField("unit_price",      "FLOAT"),
        bigquery.SchemaField("discount_pct",    "FLOAT"),
        bigquery.SchemaField("status",          "STRING"),
        bigquery.SchemaField("payment_method",  "STRING"),
        bigquery.SchemaField("order_date",      "TIMESTAMP"),
        bigquery.SchemaField("shipping_date",   "TIMESTAMP"),
        bigquery.SchemaField("country",         "STRING"),
        bigquery.SchemaField("city",            "STRING"),
    ],
    "raw_user_clicks": [
        bigquery.SchemaField("click_id",         "STRING",  mode="REQUIRED"),
        bigquery.SchemaField("user_id",          "STRING",  mode="REQUIRED"),
        bigquery.SchemaField("session_id",       "STRING"),
        bigquery.SchemaField("page",             "STRING"),
        bigquery.SchemaField("device",           "STRING"),
        bigquery.SchemaField("referrer",         "STRING"),
        bigquery.SchemaField("time_on_page_sec", "INTEGER"),
        bigquery.SchemaField("clicked_cta",      "BOOLEAN"),
        bigquery.SchemaField("timestamp",        "TIMESTAMP"),
    ],
    "raw_system_errors": [
        bigquery.SchemaField("error_id",    "STRING",  mode="REQUIRED"),
        bigquery.SchemaField("service",     "STRING"),
        bigquery.SchemaField("error_code",  "STRING"),
        bigquery.SchemaField("severity",    "STRING"),
        bigquery.SchemaField("message",     "STRING"),
        bigquery.SchemaField("stack_trace", "STRING"),
        bigquery.SchemaField("resolved",    "BOOLEAN"),
        bigquery.SchemaField("timestamp",   "TIMESTAMP"),
    ],
}

CSV_FILES = {
    "raw_transactions": "transactions.csv",
    "raw_user_clicks":  "user_clicks.csv",
    "raw_system_errors":"system_errors.csv",
}


def get_client():
    credentials = service_account.Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=PROJECT_ID, credentials=credentials)


def create_dataset(client):
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset_ref.location = REGION
    dataset = client.create_dataset(dataset_ref, exists_ok=True)
    print(f"[OK] Dataset ready: {PROJECT_ID}.{DATASET_ID}")
    return dataset


def upload_table(client, table_name, csv_filename):
    table_ref   = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
    csv_path    = os.path.join(OUTPUT_DIR, csv_filename)

    if not os.path.exists(csv_path):
        print(f"[SKIP] File not found: {csv_path}")
        return

    job_config = bigquery.LoadJobConfig(
        schema            = SCHEMAS[table_name],
        source_format     = bigquery.SourceFormat.CSV,
        skip_leading_rows = 1,          # skip CSV header row
        write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE,  # overwrite on re-run
        allow_quoted_newlines = True,
    )

    print(f"[UPLOAD] {csv_filename} -> {table_ref} ...")
    with open(csv_path, "rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)

    job.result()  # wait for completion

    table   = client.get_table(table_ref)
    print(f"[OK] {table_name}: {table.num_rows:,} rows loaded")


if __name__ == "__main__":
    print("=" * 60)
    print("BigQuery Seeder")
    print(f"Project : {PROJECT_ID}")
    print(f"Dataset : {DATASET_ID}")
    print(f"Key     : {KEY_PATH}")
    print("=" * 60)

    if not os.path.exists(KEY_PATH):
        raise FileNotFoundError(
            f"GCP key not found at: {KEY_PATH}\n"
            "Set the GCP_KEY_PATH environment variable or place gcp_key.json "
            "at C:\\de_projects\\ci_cd\\gcp_key.json"
        )

    client = get_client()
    create_dataset(client)

    for table_name, csv_file in CSV_FILES.items():
        upload_table(client, table_name, csv_file)

    print("\n" + "=" * 60)
    print("Seeding complete. Check BigQuery console to verify.")
    print("=" * 60)
