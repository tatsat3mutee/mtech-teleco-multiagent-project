# Telecom Billing Architecture Overview

## IBM Telco Customer Churn Dataset — Feature Reference

The IBM Telco Customer Churn dataset (7,043 customers) is the primary training and evaluation dataset for this RCA system. Key billing-relevant features:

| Feature | Type | Values | Billing Relevance |
|---------|------|--------|-------------------|
| MonthlyCharges | float | $18.25 – $118.75 | Primary anomaly signal |
| TotalCharges | float | $18.80 – $8,684.80 | Cumulative billing history |
| tenure | int | 0 – 72 months | Account maturity indicator |
| Contract | categorical | Month-to-month, One year, Two year | Rate commitment tier |
| InternetService | categorical | DSL, Fiber optic, No | Service tier determining base rate |
| StreamingTV | categorical | Yes, No, No internet service | Bundle component — affects rating complexity |
| StreamingMovies | categorical | Yes, No, No internet service | Bundle component — affects rating complexity |
| PaymentMethod | categorical | Electronic check, Mailed check, Bank transfer, Credit card | Collection path |
| Churn | binary | Yes / No (26.5% churn rate) | Outcome correlated with billing errors |

## Billing Pipeline Architecture

### Stage 1: Service Provisioning
Customer subscribes to services (InternetService + optional StreamingTV/StreamingMovies bundles). Provisioning records activate the billing account. **Failure mode:** Provisioning sync failure → billing account activated without charge configuration → zero_billing anomaly.

### Stage 2: Usage and Charge Accumulation
Active services accumulate charges throughout the billing cycle. Recurring charges: monthly plan fee + service add-ons. **Failure mode:** Bundle rating engine error → NaN MonthlyCharges for streaming customers → billing_record_failure anomaly.

### Stage 3: Cycle-End Batch Processing
At billing cycle end, the batch job aggregates all charge components, applies contract caps and discounts, and produces the final MonthlyCharges value. **Failure mode:** Batch job timeout or proration error → charges exceed contract cap → sla_breach anomaly.

### Stage 4: Invoice Generation and Payment Collection
Invoice is generated from MonthlyCharges; payment collected via PaymentMethod. Retry logic handles payment failures. **Failure mode:** Retry without idempotency → duplicate charges applied → duplicate_charge anomaly.

### Stage 5: Revenue Assurance Reconciliation
Automated checks compare expected vs. actual revenue. IsolationForest detector flags statistical outliers. Rule-based prefilter catches deterministic violations (MonthlyCharges = 0 with tenure > 0).

## Anomaly Type Reference

### Revenue Leakage Anomalies
- **zero_billing:** MonthlyCharges = 0 AND tenure > 0 — active account receiving no invoice. Detection confidence > 0.90 via rule-based prefilter.
- **billing_record_failure:** NaN charges for streaming customers (StreamingTV='Yes' OR StreamingMovies='Yes') — billing pipeline failed to rate multi-component bundle.

### Overbilling Anomalies
- **duplicate_charge:** MonthlyCharges ≈ 2× historical average — retry logic or batch re-run applied charges twice.
- **sla_breach:** MonthlyCharges > P95 × 1.5 for contract customers — billing cap not enforced for One year / Two year contract holders.

### Demand-Side Anomalies
- **usage_spike:** MonthlyCharges increases 5–10× for Fiber optic internet customers (tenure > 18 months) — roaming, miscategorised streaming traffic, or incorrect rate card.

## IsolationForest Detection Configuration

The anomaly detector uses IsolationForest on the following features:
- `tenure` — account maturity
- `MonthlyCharges` — current cycle charge amount
- `TotalCharges` — cumulative billing history

Derived features added by `_get_feature_cols()`:
- `charges_per_month` = TotalCharges / tenure (expected consistency indicator)
- `monthly_total_ratio` = MonthlyCharges / (TotalCharges + 1) (normalised charge level)

`rule_based_prefilter()` runs before IsolationForest and flags MonthlyCharges = 0 AND tenure > 0 at 100% precision, reducing false negatives for the most critical revenue leakage case.

## Key Performance Indicators (KPIs)

| KPI | Target | IBM Telco Baseline |
|-----|--------|-------------------|
| Billing Accuracy | ≥99.5% | Measured by anomaly injection rate < 0.5% |
| Zero-billing Rate | <0.1% | Rule-based prefilter catches 100% of cases |
| Revenue Leakage Rate | <0.5% | Sum of zero_billing + billing_record_failure charges |
| Duplicate Charge Rate | <0.01% | Idempotency controls target |
| SLA Breach Rate | <0.1% | Applies to Contract ∈ {One year, Two year} only |
| Churn Rate | <26.5% | IBM Telco dataset observed rate |

## SWARM Routing Decision Map

| Anomaly Type | Retrieval Strategy | Rationale |
|---|---|---|
| zero_billing | graph_first | Multi-hop: provisioning → billing config → rating engine → invoice |
| billing_record_failure | graph_first | Multi-hop: service catalogue → bundle rating → pipeline → charge record |
| duplicate_charge | vector_first | Pattern matching: idempotency failure signatures in billing history |
| usage_spike | vector_first | Pattern matching: rate card anomalies vs. historical charge profile |
| sla_breach | vector_first | Pattern matching: contract rate configuration against charge records |

## Source
[telecom_billing, ibm_telco, anomaly_detection, isolationforest, billing_pipeline, revenue_assurance]
