# Zero Billing — RCA Playbook

## Overview

A zero-billing anomaly occurs when an active customer (tenure > 0, services provisioned) shows MonthlyCharges = $0 for the current billing cycle. In the IBM Telco Customer Churn dataset, zero-billing accounts have a median tenure of 28 months and 71% hold Fiber optic internet service — established, high-value customers with clear billing history. Revenue impact: 100% charge leakage for the affected billing cycle.

## Detection Signals

- **Primary:** MonthlyCharges = 0.0 AND tenure > 0 (active account with prior charge history)
- **Secondary:** InternetService ∈ {'Fiber optic', 'DSL'}, TotalCharges > 0, Churn_Binary = 0
- **Threshold:** rule_based_prefilter flags this at 100% precision. IsolationForest anomaly score < -0.2 with MonthlyCharges = 0 → confidence > 0.90.

## Common Root Causes

### 1. Rating Engine Configuration Error
**Description:** Rate card incorrectly set to $0 for a service plan — typically after a system upgrade or maintenance window.
**Indicators:** Multiple accounts on the same Contract/InternetService plan show zero billing simultaneously. Issue onset matches a deployment date.
**Investigation Steps:**
1. Group zero-billed accounts by Contract and InternetService — concentration in one plan → rate card error
2. Compare current rate card version to pre-upgrade snapshot
3. Check billing system deployment log for maintenance window timing
4. Validate all rate entries for affected service bundles
**Resolution:** Revert rate card to pre-upgrade configuration. Reprocess the billing cycle for all affected accounts. Add rate card validation to the deployment pipeline.

### 2. Billing Cycle Boundary Error
**Description:** Billing batch scheduler skips charge generation for accounts whose cycle starts on a month boundary when the batch job completes after midnight.
**Indicators:** Affected accounts cluster on the same billing cycle start date. Issue recurs monthly on a predictable schedule.
**Investigation Steps:**
1. Extract billing cycle start dates for zero-billed accounts
2. Check if dates cluster around month boundaries (1st, 28th–31st)
3. Review batch job completion timestamps vs. cycle boundary timestamps
4. Verify time synchronisation across billing servers
**Resolution:** Fix boundary condition in billing cycle scheduler. Run a compensatory billing pass for missed cycles. Alert when zero-billing rate exceeds 0.1% for any single cycle.

### 3. Provisioning Sync Failure
**Description:** The provisioning system shows services as active, but the billing engine never received the activation event — no charge record exists to rate.
**Indicators:** Account shows active services in CRM but MonthlyCharges = 0. Issue is isolated to specific accounts (not plan-wide). TotalCharges > 0 confirms prior billing.
**Investigation Steps:**
1. Compare provisioning service status against billing engine charge records
2. Check event queue for unprocessed service activation events
3. Review activation timestamps vs. billing cycle start time
4. Inspect integration health between provisioning system and billing engine
**Resolution:** Replay missed activation events. Generate corrective charge for missed cycles. Add event delivery monitoring with dead-letter queue alerting.

### 4. Payment Posting Timeout
**Description:** Billing engine generated the charge correctly but the payment posting step timed out and rolled back without retry — leaving MonthlyCharges = 0 in the customer record.
**Indicators:** Internal charge records show a generated charge; customer-facing MonthlyCharges = 0. Payment posting logs show timeout errors.
**Investigation Steps:**
1. Cross-reference internal charge records against customer-facing MonthlyCharges
2. Review payment posting timeout logs for the billing cycle
3. Verify retry configuration for failed posting operations
4. Check network stability between billing engine and payment system
**Resolution:** Implement idempotent retry with exponential backoff. Repost charges for affected accounts. Set billing completeness monitoring alert in MLflow.

## Severity Assessment

- **Revenue Impact:** HIGH — 100% charge leakage per affected account per cycle. IBM Telco median MonthlyCharges ≈ $65; at 3% rate ≈ $185K monthly leakage per 100K customers.
- **Customer Impact:** LOW — customer receives free service; unlikely to complain. No churn risk increase.
- **Detection Confidence:** IsolationForest score < -0.5 with MonthlyCharges = 0 and tenure > 6 → confidence > 0.90. Rule-based prefilter is deterministic.

## Recommended Actions

1. Trigger billing record reprocessing for all zero-billed active accounts in the current cycle
2. Group affected accounts by InternetService and Contract to isolate plan-specific vs. system-wide root cause
3. Issue corrective billing statement for the missed cycle amount
4. Add MLflow alert: zero_billing_rate > 0.001 (0.1%) triggers escalation
