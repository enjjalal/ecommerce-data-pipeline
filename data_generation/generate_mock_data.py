"""
generate_mock_data.py
Generates 1,000,000 rows of mock e-commerce data across three event types:
  - transactions  (600,000 rows)
  - user_clicks   (300,000 rows)
  - system_errors (100,000 rows)
Outputs: local JSON and CSV files inside data_generation/output/
"""

import json
import csv
import os
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Config ──────────────────────────────────────────────────────────────────
TOTAL_ROWS          = 1_000_000
TRANSACTION_ROWS    = 600_000
CLICK_ROWS          = 300_000
ERROR_ROWS          = 100_000

START_DATE = datetime(2023, 1, 1)
END_DATE   = datetime(2024, 12, 31)

STATUSES        = ["completed", "pending", "cancelled", "refunded"]
STATUS_WEIGHTS  = [0.70, 0.15, 0.10, 0.05]

CATEGORIES      = ["electronics", "clothing", "books", "home", "sports", "beauty"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "crypto", "bank_transfer"]

PAGES           = ["/home", "/product", "/cart", "/checkout", "/account", "/search", "/category"]
DEVICES         = ["desktop", "mobile", "tablet"]
DEVICE_WEIGHTS  = [0.45, 0.45, 0.10]

ERROR_CODES     = ["500", "503", "404", "429", "502"]
SERVICES        = ["payment-service", "auth-service", "inventory-service", "shipping-service", "recommendation-engine"]
SEVERITIES      = ["critical", "high", "medium", "low"]
SEVERITY_WEIGHTS= [0.05, 0.20, 0.50, 0.25]

# Pre-generate a pool of consistent user IDs (realistic: repeat customers)
USER_POOL = [fake.uuid4() for _ in range(50_000)]


def random_timestamp():
    delta = END_DATE - START_DATE
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return (START_DATE + timedelta(seconds=random_seconds)).isoformat()


def generate_transactions(n):
    print(f"  Generating {n:,} transactions...")
    rows = []
    for i in range(n):
        order_date = START_DATE + timedelta(seconds=random.randint(0, int((END_DATE - START_DATE).total_seconds())))
        # shipping is 1–10 days after order — intentionally mostly valid, but
        # ~0.5% are backdated to create test failures for Day 3 custom tests
        shipping_offset = timedelta(days=random.randint(1, 10))
        if random.random() < 0.005:          # inject bad data
            shipping_offset = timedelta(days=-random.randint(1, 5))
        shipping_date = order_date + shipping_offset

        rows.append({
            "order_id":       fake.uuid4(),
            "user_id":        random.choice(USER_POOL),
            "product_id":     fake.uuid4(),
            "category":       random.choice(CATEGORIES),
            "quantity":       random.randint(1, 10),
            "unit_price":     round(random.uniform(5.0, 1500.0), 2),
            "discount_pct":   round(random.uniform(0.0, 0.40), 2),
            "status":         random.choices(STATUSES, weights=STATUS_WEIGHTS)[0],
            "payment_method": random.choice(PAYMENT_METHODS),
            "order_date":     order_date.isoformat(),
            "shipping_date":  shipping_date.isoformat(),
            "country":        fake.country_code(),
            "city":           fake.city(),
        })

        if (i + 1) % 100_000 == 0:
            print(f"    {i + 1:,} / {n:,}")
    return rows


def generate_clicks(n):
    print(f"  Generating {n:,} user clicks...")
    rows = []
    for i in range(n):
        rows.append({
            "click_id":        fake.uuid4(),
            "user_id":         random.choice(USER_POOL),
            "session_id":      fake.uuid4(),
            "page":            random.choice(PAGES),
            "device":          random.choices(DEVICES, weights=DEVICE_WEIGHTS)[0],
            "referrer":        random.choice(["google", "direct", "email", "social", "affiliate"]),
            "time_on_page_sec":random.randint(1, 600),
            "clicked_cta":     random.choice([True, False]),
            "timestamp":       random_timestamp(),
        })

        if (i + 1) % 100_000 == 0:
            print(f"    {i + 1:,} / {n:,}")
    return rows


def generate_errors(n):
    print(f"  Generating {n:,} system errors...")
    rows = []
    for i in range(n):
        rows.append({
            "error_id":   fake.uuid4(),
            "service":    random.choice(SERVICES),
            "error_code": random.choice(ERROR_CODES),
            "severity":   random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0],
            "message":    fake.sentence(nb_words=10),
            "stack_trace":fake.text(max_nb_chars=300),
            "resolved":   random.choice([True, False]),
            "timestamp":  random_timestamp(),
        })

        if (i + 1) % 25_000 == 0:
            print(f"    {i + 1:,} / {n:,}")
    return rows


def write_json(data, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved JSON -> {path}  ({len(data):,} rows)")


def write_csv(data, filename):
    if not data:
        return
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  Saved CSV  -> {path}  ({len(data):,} rows)")


if __name__ == "__main__":
    print("=" * 60)
    print("E-Commerce Mock Data Generator")
    print(f"Total target rows: {TOTAL_ROWS:,}")
    print("=" * 60)

    print("\n[1/3] Transactions")
    transactions = generate_transactions(TRANSACTION_ROWS)
    write_json(transactions, "transactions.json")
    write_csv(transactions,  "transactions.csv")

    print("\n[2/3] User Clicks")
    clicks = generate_clicks(CLICK_ROWS)
    write_json(clicks, "user_clicks.json")
    write_csv(clicks,  "user_clicks.csv")

    print("\n[3/3] System Errors")
    errors = generate_errors(ERROR_ROWS)
    write_json(errors, "system_errors.json")
    write_csv(errors,  "system_errors.csv")

    print("\n" + "=" * 60)
    print("Done. Files written to data_generation/output/")
    print("=" * 60)
