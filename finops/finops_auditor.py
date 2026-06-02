"""
finops_auditor.py
Queries BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT to extract job metadata,
calculates exact query costs using GCP pricing, flags SQL anti-patterns,
and writes a Markdown report to reports/finops_report.md

Pricing reference: https://cloud.google.com/bigquery/pricing
  On-demand: $5.00 per TB scanned (as of 2024)

Usage:
  python finops/finops_auditor.py
"""

import os
import re
from datetime import datetime, timezone
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT_ID      = "ecommerce-pipeline-498214"
KEY_PATH        = os.environ.get("GCP_KEY_PATH", r"C:\de_projects\ci_cd\gcp_key.json")
REPORT_DIR      = os.path.join(os.path.dirname(__file__), "..", "reports")
REPORT_PATH     = os.path.join(REPORT_DIR, "finops_report.md")
LOOKBACK_DAYS   = 30

# GCP on-demand query pricing: $5 per TB
COST_PER_TB_USD = 5.0
BYTES_PER_TB    = 1_099_511_627_776  # 1 TB in bytes

# Cost threshold above which a single query is flagged as expensive
EXPENSIVE_QUERY_THRESHOLD_USD = 0.01

# ── Anti-pattern detection rules ─────────────────────────────────────────────
# Each rule: (label, regex_pattern, explanation)
ANTI_PATTERNS = [
    (
        "SELECT *",
        r"SELECT\s+\*",
        "Selects all columns, scanning unnecessary data and inflating cost. "
        "Specify only the columns you need."
    ),
    (
        "Missing partition filter on order_date",
        r"FROM\s+`?[a-z0-9_\-\.]+raw_transactions`?(?![\s\S]{0,500}order_date)",
        "Querying raw_transactions without filtering on order_date scans the "
        "entire table. Add WHERE order_date >= '...' to prune partitions."
    ),
    (
        "Missing partition filter on timestamp",
        r"FROM\s+`?[a-z0-9_\-\.]+raw_(user_clicks|system_errors)`?(?![\s\S]{0,500}timestamp)",
        "Querying raw_user_clicks or raw_system_errors without a timestamp "
        "filter scans all data. Add a WHERE timestamp >= '...' clause."
    ),
    (
        "CROSS JOIN detected",
        r"\bCROSS\s+JOIN\b",
        "A CROSS JOIN produces a cartesian product. On large tables this "
        "explodes row count and bytes scanned exponentially."
    ),
    (
        "Non-partitioned ORDER BY on large table",
        r"ORDER\s+BY(?![\s\S]{0,200}LIMIT)",
        "ORDER BY without LIMIT on a large result set forces a full sort "
        "pass in memory. Add LIMIT or remove the sort if not required."
    ),
]


def bytes_to_usd(total_bytes_billed: int) -> float:
    """Convert BigQuery billed bytes to USD using on-demand pricing."""
    tb = total_bytes_billed / BYTES_PER_TB
    return round(tb * COST_PER_TB_USD, 6)


def flag_anti_patterns(query_text: str) -> list[dict]:
    """Scan a SQL string and return a list of detected anti-pattern violations."""
    if not query_text:
        return []
    findings = []
    for label, pattern, explanation in ANTI_PATTERNS:
        if re.search(pattern, query_text, re.IGNORECASE | re.DOTALL):
            findings.append({"label": label, "explanation": explanation})
    return findings


def get_client() -> bigquery.Client:
    credentials = service_account.Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=PROJECT_ID, credentials=credentials)


def fetch_jobs(client: bigquery.Client) -> list[dict]:
    """Pull job metadata from INFORMATION_SCHEMA for the last LOOKBACK_DAYS days."""
    query = f"""
        SELECT
            job_id,
            user_email,
            creation_time,
            end_time,
            total_bytes_billed,
            total_bytes_processed,
            TIMESTAMP_DIFF(end_time, creation_time, SECOND)  AS duration_seconds,
            REGEXP_REPLACE(query, r'\\s+', ' ')               AS query_text,
            state,
            error_result
        FROM `{PROJECT_ID}`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {LOOKBACK_DAYS} DAY)
          AND job_type = 'QUERY'
          AND state    = 'DONE'
        ORDER BY total_bytes_billed DESC
        LIMIT 500
    """
    print(f"  Querying INFORMATION_SCHEMA.JOBS_BY_PROJECT (last {LOOKBACK_DAYS} days)...")
    rows = list(client.query(query).result())
    print(f"  Found {len(rows):,} completed query jobs")
    return rows


def analyse_jobs(rows: list) -> dict:
    """Compute cost metrics and flag anti-patterns for each job."""
    jobs = []
    total_cost_usd      = 0.0
    total_bytes_billed  = 0
    flagged_count       = 0

    for row in rows:
        bytes_billed = row.total_bytes_billed or 0
        cost_usd     = bytes_to_usd(bytes_billed)
        violations   = flag_anti_patterns(row.query_text)

        if violations:
            flagged_count += 1

        total_cost_usd     += cost_usd
        total_bytes_billed += bytes_billed

        jobs.append({
            "job_id":           row.job_id,
            "user_email":       row.user_email,
            "created_at":       row.creation_time.strftime("%Y-%m-%d %H:%M:%S UTC") if row.creation_time else "N/A",
            "duration_sec":     row.duration_seconds or 0,
            "bytes_billed":     bytes_billed,
            "bytes_processed":  row.total_bytes_processed or 0,
            "cost_usd":         cost_usd,
            "query_text":       (row.query_text or "")[:500],   # truncate for report
            "violations":       violations,
            "has_error":        row.error_result is not None,
        })

    return {
        "jobs":             jobs,
        "total_jobs":       len(jobs),
        "total_cost_usd":   round(total_cost_usd, 6),
        "total_bytes_gb":   round(total_bytes_billed / 1e9, 3),
        "flagged_count":    flagged_count,
        "generated_at":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def write_report(analysis: dict):
    """Write the FinOps findings to a Markdown report file."""
    os.makedirs(REPORT_DIR, exist_ok=True)

    jobs            = analysis["jobs"]
    expensive_jobs  = [j for j in jobs if j["cost_usd"] >= EXPENSIVE_QUERY_THRESHOLD_USD]
    flagged_jobs    = [j for j in jobs if j["violations"]]

    lines = []
    a = lines.append   # shorthand

    a("# FinOps Audit Report")
    a(f"\n**Generated:** {analysis['generated_at']}")
    a(f"**Project:** `{PROJECT_ID}`")
    a(f"**Lookback period:** Last {LOOKBACK_DAYS} days")
    a(f"**Pricing model:** ${COST_PER_TB_USD:.2f} per TB scanned (GCP on-demand)")

    a("\n---\n")
    a("## Executive Summary\n")
    a(f"| Metric | Value |")
    a(f"|--------|-------|")
    a(f"| Total queries analysed | {analysis['total_jobs']:,} |")
    a(f"| Total data scanned | {analysis['total_bytes_gb']:.3f} GB |")
    a(f"| **Total estimated cost** | **${analysis['total_cost_usd']:.4f} USD** |")
    a(f"| Queries with anti-patterns | {analysis['flagged_count']:,} |")
    a(f"| Expensive queries (> ${EXPENSIVE_QUERY_THRESHOLD_USD}) | {len(expensive_jobs):,} |")

    a("\n---\n")
    a("## Anti-Pattern Violations\n")

    if not flagged_jobs:
        a("No anti-pattern violations detected.")
    else:
        a(f"> {len(flagged_jobs)} queries flagged. Each represents avoidable cost or risk.\n")
        for i, job in enumerate(flagged_jobs[:20], 1):   # cap at 20 in report
            a(f"### Violation {i}: `{job['job_id']}`\n")
            a(f"- **User:** {job['user_email']}")
            a(f"- **Run at:** {job['created_at']}")
            a(f"- **Cost:** ${job['cost_usd']:.6f} USD")
            a(f"- **Data scanned:** {job['bytes_billed'] / 1e6:.2f} MB\n")
            a(f"**Flags:**\n")
            for v in job["violations"]:
                a(f"- **{v['label']}:** {v['explanation']}")
            a(f"\n**Query (truncated):**")
            a(f"```sql\n{job['query_text'][:300]}\n```\n")

    a("\n---\n")
    a("## Top 10 Most Expensive Queries\n")
    a("| # | Job ID | Cost (USD) | GB Scanned | Duration (s) | User |")
    a("|---|--------|-----------|------------|--------------|------|")
    for i, job in enumerate(jobs[:10], 1):
        gb = job["bytes_billed"] / 1e9
        a(f"| {i} | `{job['job_id'][:20]}...` | ${job['cost_usd']:.6f} | {gb:.3f} | {job['duration_sec']} | {job['user_email']} |")

    a("\n---\n")
    a("## All Queries — Cost Breakdown\n")
    a("| Job ID | Cost (USD) | GB Billed | Duration (s) | Violations |")
    a("|--------|-----------|-----------|--------------|------------|")
    for job in jobs:
        gb      = job["bytes_billed"] / 1e9
        flags   = ", ".join(v["label"] for v in job["violations"]) or "None"
        a(f"| `{job['job_id'][:20]}...` | ${job['cost_usd']:.6f} | {gb:.3f} | {job['duration_sec']} | {flags} |")

    a("\n---\n")
    a("## How This Saves Money\n")
    a("This auditor catches the following anti-patterns **before they reach production** via CI/CD:\n")
    for label, _, explanation in ANTI_PATTERNS:
        a(f"- **{label}:** {explanation}")

    a("\n---\n")
    a("*Report generated automatically by `finops/finops_auditor.py`*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Report written -> {REPORT_PATH}")


if __name__ == "__main__":
    print("=" * 60)
    print("FinOps Auditor")
    print(f"Project : {PROJECT_ID}")
    print(f"Lookback: {LOOKBACK_DAYS} days")
    print("=" * 60)

    client   = get_client()

    print("\n[1/3] Fetching job metadata...")
    rows     = fetch_jobs(client)

    print("\n[2/3] Analysing costs and flagging anti-patterns...")
    analysis = analyse_jobs(rows)

    print(f"\n  Total cost: ${analysis['total_cost_usd']:.4f} USD")
    print(f"  Data scanned: {analysis['total_bytes_gb']:.3f} GB")
    print(f"  Flagged queries: {analysis['flagged_count']}")

    print("\n[3/3] Writing Markdown report...")
    write_report(analysis)

    print("\n" + "=" * 60)
    print("Audit complete.")
    print("=" * 60)
