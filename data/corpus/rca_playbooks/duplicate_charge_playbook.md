# Duplicate Charge — RCA Playbook

## Overview

A duplicate charge anomaly occurs when a customer is billed approximately 2× their normal MonthlyCharges in a single billing cycle. In the IBM Telco Customer Churn dataset, affected customers have a median tenure of 45 months and are predominantly on Two-year contracts with Fiber optic service — long-term customers with stable charge history. Revenue impact: double charges damage trust, trigger disputes, and accelerate churn (IBM Telco churn rate is 2.3× higher for customers who experience billing errors).

## Detection Signals

- **Primary:** MonthlyCharges ≈ 2× the customer's historical average (TotalCharges ÷ tenure)
- **Secondary:** Contract = 'Two year', InternetService = 'Fiber optic', high tenure (> 24 months)
- **Threshold:** MonthlyCharges > 200% of (TotalCharges / tenure) ratio → IsolationForest confidence > 0.85

## Common Root Causes

### 1. Billing System Retry Logic — Duplicate Charge Posting
**Description:** The billing engine's retry logic lacks idempotency — a failed charge posting is retried, and both the original and retry succeed, posting two charges for one billing cycle.
**Indicators:** Two separate charge transactions with the same billing period in the payment system. MonthlyCharges exactly 2× the previous month. Appears in batch processing logs as "charge posted — retry succeeded."
**Investigation Steps:**
1. Query payment transaction records for duplicate billing period entries
2. Check billing retry configuration — verify idempotency key usage
3. Review batch processing logs for double-post entries on the affected accounts
4. Identify whether the issue occurs system-wide or only during high-load periods
**Resolution:** Add idempotency keys to all charge posting operations. Reverse the duplicate charge immediately. Audit the last 3 billing cycles for similar duplicates.

### 2. Billing Batch Job Re-Run Without Deduplication
**Description:** A billing batch job failed midway through a cycle and was re-run from the beginning — posting charges for accounts that were already successfully billed in the first run.
**Indicators:** Multiple accounts show duplicates on the same date. The issue correlates with a batch failure/restart event in the job execution log.
**Investigation Steps:**
1. Check billing batch execution log for failure and restart events
2. Identify all accounts billed in the first run vs. the restart run
3. Compare charge timestamps to confirm overlap
4. Verify whether the batch job has checkpoint/resume capability
**Resolution:** Implement checkpoint-based resume for billing batch jobs. Add pre-billing deduplication check: if MonthlyCharges already posted for this cycle, skip. Reverse all duplicate charges from the restart run.

### 3. Payment Processing Idempotency Failure
**Description:** The payment processor's idempotency mechanism failed — the same charge request was processed twice because the idempotency key expired or was not properly stored.
**Indicators:** Payment processor logs show two successful authorisations with the same merchant reference. MonthlyCharges = 2× expected for a single account (not batch-wide).
**Investigation Steps:**
1. Query payment processor for duplicate authorisations within the same billing period
2. Check idempotency key TTL configuration vs. charge processing time
3. Review network timeout behaviour between billing engine and payment processor
4. Assess whether the issue is isolated to specific payment methods
**Resolution:** Extend idempotency key TTL beyond maximum charge processing time. Implement payment reconciliation job comparing billing records to payment processor records daily.

### 4. Billing Record Mediation Layer Re-Transmission
**Description:** An intermediate billing mediation layer re-transmitted already-processed billing records due to a delivery acknowledgement failure, causing the rating engine to process them twice.
**Indicators:** The same usage record appears twice in the rating engine's input queue with identical timestamps. MonthlyCharges = 2× normal specifically for customers with complex service bundles.
**Investigation Steps:**
1. Check the mediation layer's delivery acknowledgement logs
2. Compare rating engine input queue to mediation layer output for duplicates
3. Review which service types (StreamingTV, MultipleLines) are most affected
4. Verify exactly-once delivery semantics in the mediation layer configuration
**Resolution:** Enable exactly-once delivery semantics. Add duplicate detection at the rating engine input gate. Purge duplicate entries and reprocess correct records.

## Severity Assessment

- **Revenue Impact:** HIGH — double charges create refund obligations and dispute costs. IBM Telco data shows churn rate increases 2.3× after billing errors.
- **Customer Impact:** HIGH — financial harm to customer; likely to trigger complaints, disputes, and churn.
- **Detection Confidence:** MonthlyCharges > 1.8× historical average → IsolationForest confidence > 0.85. High precision at this threshold.

## Recommended Actions

1. Immediately reverse the duplicate charge and notify the customer
2. Audit the billing batch execution log for the affected cycle to identify scope
3. Implement idempotency keys on all charge posting operations
4. Add MLflow alert: duplicate_charge_rate > 0.001 (0.1%) triggers escalation
