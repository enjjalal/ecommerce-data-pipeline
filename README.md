# E-Commerce Data Engineering Pipeline

> End-to-end data engineering portfolio project: 1M-row mock e-commerce data → BigQuery → dbt transformations → FinOps cost auditing → CI/CD automation.

## Architecture

```
[Python Generator] → [BigQuery raw_stage] → [dbt: staging models] → [dbt: business marts]
                                                                              ↓
                                                                   [FinOps Auditor]
                                                                              ↓
                                                                  [GitHub Actions CI/CD]
```

## Stack
- **Cloud Warehouse:** Google BigQuery (GCP)
- **Transformation:** dbt Core
- **Data Generation:** Python + Faker
- **FinOps Auditing:** Python + BigQuery INFORMATION_SCHEMA
- **CI/CD:** GitHub Actions

## Project Structure
```
├── data_generation/       # Mock data scripts
├── dbt_project/           # dbt models, tests, sources
├── finops/                # Cost auditing scripts
├── .github/workflows/     # CI/CD pipeline
└── reports/               # Generated audit reports
```

## Days
- **Day 1:** Cloud setup & mock data generation
- **Day 2:** dbt modeling (staging + marts)
- **Day 3:** Data quality testing
- **Day 4:** FinOps metadata parser
- **Day 5:** CI/CD pipeline
- **Day 6-7:** Documentation & polish
