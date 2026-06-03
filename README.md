# E-Commerce Data Engineering Pipeline

![CI Status](https://github.com/enjjalal/ecommerce-data-pipeline/actions/workflows/data_pipeline_ci.yml/badge.svg)

A production-grade, end-to-end data engineering portfolio project built on Google Cloud Platform. Generates 1,000,000 rows of realistic e-commerce event data, transforms it through a layered dbt pipeline in BigQuery, enforces automated data quality gates, and runs a custom FinOps cost auditor on every code push via GitHub Actions CI/CD.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL ENVIRONMENT                            │
│                                                                     │
│  ┌──────────────────┐        ┌──────────────────┐                  │
│  │ generate_mock_   │        │  seed_bigquery   │                  │
│  │ data.py          │──────> │  .py             │──────────────┐   │
│  │                  │        │                  │              │   │
│  │ Faker: 1M rows   │        │ BQ Python API    │              │   │
│  │ transactions     │        │ CSV upload       │              │   │
│  │ clicks / errors  │        │                  │              │   │
│  └──────────────────┘        └──────────────────┘              │   │
└────────────────────────────────────────────────────────────────│───┘
                                                                 │
                                                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GOOGLE BIGQUERY (GCP)                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Dataset: raw_stage                                         │   │
│  │  ┌──────────────────┐ ┌─────────────────┐ ┌─────────────┐  │   │
│  │  │ raw_transactions │ │ raw_user_clicks  │ │raw_system_  │  │   │
│  │  │ 600,000 rows     │ │ 300,000 rows     │ │errors       │  │   │
│  │  │                  │ │                  │ │100,000 rows │  │   │
│  │  └────────┬─────────┘ └────────┬─────────┘ └──────┬──────┘  │   │
│  └───────────│────────────────────│────────────────────│────────┘   │
│              │     dbt run        │                    │            │
│              ▼                    ▼                    │            │
│  ┌─────────────────────────────────────────────────┐  │            │
│  │  Dataset: dev_staging  (dbt views)              │  │            │
│  │  ┌──────────────────┐   ┌─────────────────────┐ │  │            │
│  │  │   stg_orders     │   │     stg_users        │ │  │            │
│  │  │ - Clean columns  │   │ - User profiles      │ │  │            │
│  │  │ - revenue_usd    │   │ - Session aggregates │ │  │            │
│  │  │ - Quality flags  │   │ - Primary device     │ │  │            │
│  │  └────────┬─────────┘   └──────────┬──────────┘ │  │            │
│  └───────────│──────────────────────────────────────┘  │            │
│              │     dbt run                              │            │
│              ▼                                          │            │
│  ┌─────────────────────────────────────────────────┐               │
│  │  Dataset: dev_marts  (dbt table)                │               │
│  │  ┌───────────────────────────────────────────┐  │               │
│  │  │       mart_finance_performance            │  │               │
│  │  │ - Cumulative revenue (window function)    │  │               │
│  │  │ - User lifetime value (window function)   │  │               │
│  │  │ - 7-day rolling revenue                   │  │               │
│  │  │ - Revenue share %                         │  │               │
│  │  │ - User order sequence                     │  │               │
│  │  └───────────────────────────────────────────┘  │               │
│  └─────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌──────────────────────┐    ┌────────────────────────────────────────┐
│   dbt test           │    │        finops_auditor.py               │
│                      │    │                                        │
│ - unique             │    │  Queries INFORMATION_SCHEMA            │
│ - not_null           │    │  .JOBS_BY_PROJECT                      │
│ - accepted_values    │    │                                        │
│ - relationships      │    │  Cost formula: bytes / TB * $5.00      │
│ - custom: shipping   │    │                                        │
│   date logic test    │    │  Flags: SELECT *, missing partition     │
│                      │    │  filters, CROSS JOIN, unbound ORDER BY │
│  15 tests total      │    │                                        │
│  13 PASS / 1 WARN    │    │  Output: reports/finops_report.md      │
│  1 intentional FAIL  │    │                                        │
└──────────┬───────────┘    └──────────────────┬─────────────────────┘
           │                                   │
           └──────────────┬────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GITHUB ACTIONS CI/CD  (on every push/PR)               │
│                                                                     │
│  Ubuntu container                                                   │
│  │                                                                  │
│  ├── Install Python 3.11 + dependencies                             │
│  ├── Decode GCP secret → /tmp/gcp_key.json                          │
│  ├── Write dbt profiles.yml at runtime                              │
│  ├── dbt run        → rebuild all models                            │
│  ├── dbt test       → 14 quality gates (hard block on failure)      │
│  ├── dbt test       → shipping date test (informational)            │
│  ├── finops_auditor → cost + anti-pattern report                    │
│  └── Upload finops_report.md as CI artifact                         │
│                                                                     │
│  Total pipeline runtime: ~90 seconds                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stack

| Layer | Technology |
|---|---|
| Cloud Warehouse | Google BigQuery (GCP) |
| Transformation | dbt Core 1.11 |
| Data Generation | Python 3.11 + Faker |
| FinOps Auditing | Python + BigQuery INFORMATION_SCHEMA |
| CI/CD | GitHub Actions |
| Authentication | GCP Service Account + GitHub Secrets |

---

## Project Structure

```
ecommerce-data-pipeline/
│
├── data_generation/
│   ├── generate_mock_data.py     # Generates 1M rows across 3 event types
│   ├── seed_bigquery.py          # Uploads CSV files to BigQuery raw_stage
│   └── output/                   # Local JSON + CSV files (git-ignored)
│
├── dbt_project/
│   ├── dbt_project.yml           # dbt project config
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml       # Formal source declarations + lineage
│   │   │   ├── schema.yml        # Column-level tests and constraints
│   │   │   ├── stg_orders.sql    # Cleaned transactions + revenue calc
│   │   │   └── stg_users.sql     # User engagement profiles
│   │   └── marts/
│   │       └── mart_finance_performance.sql  # Window function analytics
│   └── tests/
│       └── assert_shipping_date_after_order_date.sql  # Custom logic test
│
├── finops/
│   └── finops_auditor.py         # Cost parser + anti-pattern detector
│
├── .github/
│   └── workflows/
│       └── data_pipeline_ci.yml  # Full CI/CD pipeline definition
│
├── reports/                      # Generated at runtime, git-ignored
├── requirements.txt
└── README.md
```

---

## Data Model

### Raw Layer — `raw_stage`
Three tables loaded directly from the mock data generator with no transformations applied.

| Table | Rows | Description |
|---|---|---|
| `raw_transactions` | 600,000 | Orders with price, quantity, status, dates |
| `raw_user_clicks` | 300,000 | Clickstream events with device, referrer, page |
| `raw_system_errors` | 100,000 | Service error logs with severity and resolution |

### Staging Layer — `dev_staging` (dbt views)
Clean, standardised views on top of raw. No data stored — computed on read.

| Model | Key transformations |
|---|---|
| `stg_orders` | Lowercase/trim strings, cast types, calculate `revenue_usd`, flag invalid shipping dates |
| `stg_users` | Aggregate clicks to one row per user, derive primary device and referrer |

### Mart Layer — `dev_marts` (dbt table)
Business-ready table for analytics and BI tooling. Physically stored in BigQuery.

| Model | Rows | Key metrics |
|---|---|---|
| `mart_finance_performance` | ~418,000 | Cumulative revenue, user LTV, 7-day rolling revenue, revenue share % |

---

## Data Quality Gates

15 automated tests run on every CI push via `dbt test`:

| Test | Column | Result |
|---|---|---|
| `unique` | `order_id`, `user_id` | PASS |
| `not_null` | All ID and metric fields | PASS |
| `accepted_values` | `status`, `primary_device` | PASS |
| `relationships` | `user_id` FK to stg_users | WARN (expected — not all buyers click) |
| Custom: shipping date logic | `shipping_date` vs `order_date` | FAIL — 2,939 bad rows caught |

The shipping date test intentionally fails — ~0.5% of rows were seeded with invalid dates during data generation to demonstrate the CI gate working in practice.

---

## FinOps: How This Saves Money

BigQuery charges **$5.00 per terabyte scanned** on the on-demand pricing model. At scale, a single poorly-written query scanning an unpartitioned 10TB table costs $50 per run. Run it 20 times a day across a team and you have a $1,000/day habit nobody notices until the billing alert fires.

The `finops_auditor.py` script runs on **every CI push** and catches the following anti-patterns before they reach production:

| Anti-Pattern | Why It's Expensive | How It's Detected |
|---|---|---|
| `SELECT *` | Scans all columns even unused ones — multiplies cost on wide tables | Regex match on query text |
| Missing partition filter | Scans entire table instead of a date slice | Absence of date filter on known large tables |
| `CROSS JOIN` | Cartesian product explodes row count exponentially | Keyword match |
| Unbound `ORDER BY` | Forces a full in-memory sort pass on the entire result | `ORDER BY` without `LIMIT` |

**First audit result on this project:** 63 queries, 1.122 GB scanned, **$0.0051 total cost**, 17 queries flagged. Every flagged query is logged with its job ID, user, cost, and the exact SQL — giving engineering leads an audit trail with zero manual work.

---

## Running Locally

```bash
# 1. Clone and set up environment
git clone https://github.com/enjjalal/ecommerce-data-pipeline.git
cd ecommerce-data-pipeline
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Add your GCP service account key
cp /path/to/your/gcp_key.json gcp_key.json

# 3. Generate mock data
python data_generation/generate_mock_data.py

# 4. Upload to BigQuery
python data_generation/seed_bigquery.py

# 5. Run dbt
cd dbt_project
dbt run --profiles-dir ~/.dbt
dbt test --profiles-dir ~/.dbt

# 6. Run FinOps audit
cd ..
python finops/finops_auditor.py
# Report saved to: reports/finops_report.md
```

---

## CI/CD Pipeline

Every push or pull request to `main` automatically:
1. Spins up a clean Ubuntu container
2. Installs all dependencies from `requirements.txt`
3. Authenticates to GCP via GitHub Secret (base64-encoded service account key)
4. Runs `dbt run` to rebuild all models
5. Runs `dbt test` — pipeline blocks on any structural failure
6. Runs the FinOps auditor and uploads the report as a downloadable CI artifact

Live pipeline: [GitHub Actions](https://github.com/enjjalal/ecommerce-data-pipeline/actions)
