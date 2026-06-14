# SLA Breach — RCA Playbook

## Overview

An SLA breach anomaly occurs when a customer's MonthlyCharges significantly exceed the contractual billing cap for their service tier. In the IBM Telco Customer Churn dataset, SLA breaches are concentrated in customers with Contract = 'One year' or 'Two year' — these accounts have explicit rate commitments and billing caps that must be enforced. The detection signal is MonthlyCharges > P95 × 1.5 for the customer's contract cohort AND Contract != 'Month-to-month'. Month-to-month customers are excluded because their pricing is variable by design. Revenue impact: overbilled customers file disputes, churn at 3.2× the baseline rate, and incur penalty obligations.

## Detection Signals

- **Primary:** MonthlyCharges > P95_cohort × 1.5 AND Contract ∈ {'One year', 'Two year'}
- **Secondary:** tenure > 12 months (customers with established charge history); TotalCharges / tenure ratio > 1.5× the plan average
- **IBM Telco Threshold:** P95 of MonthlyCharges is $107.40 for Fiber optic + Two-year contract customers; breach threshold = $161.10. IsolationForest anomaly score < -0.18 with confidence > 0.84.
- **SWARM Routing:** vector_first — pattern matching against contract rate rules in the knowledge base.

## Common Root Causes

### 1. Rate Plan Not Reflected in Billing Configuration
**Description:** The customer's contracted rate ceiling was not correctly entered into the billing configuration when the contract was created or renewed. The billing engine applies a higher default rate instead of the negotiated contract rate.
**IBM Telco Indicators:** MonthlyCharges > contractual cap since contract start date; TotalCharges / tenure shows consistent overbilling from account creation; Contract = 'Two year' with MonthlyCharges in the top 1% of the same plan cohort.
**Investigation Steps:**
1. Pull contract terms from CRM — identify negotiated rate ceiling and plan code
2. Check billing configuration for the customer's plan code — verify rate cap field
3. Compare the configured rate with the contractual rate
4. Check configuration change log for the contract activation date
**Resolution:** Update billing configuration with correct contracted rate; reprocess all billing cycles from contract start date; issue refund for total overcharge amount.

### 2. Contract Renewal Billing Error
**Description:** At contract renewal, the old plan's billing cap was deactivated before the new plan's configuration was activated. During the gap, default uncapped rates were applied, generating charges above the new contract ceiling.
**IBM Telco Indicators:** MonthlyCharges spike exactly at contract renewal month; pre-renewal charges were within bounds; tenure > 24 months (established account at renewal time); Contract recently changed from 'One year' to 'Two year'.
**Investigation Steps:**
1. Check contract history for renewal event timestamp
2. Identify the gap between old plan deactivation and new plan activation
3. Retrieve the default rates applied during the gap window
4. Calculate overcharge: actual charges minus contracted rate × affected months
**Resolution:** Apply new contract rate retroactively to gap window; issue credit for gap-period overcharges; fix renewal workflow to eliminate configuration gap.

### 3. Plan Migration Proration Error
**Description:** A mid-cycle plan migration incorrectly prorated charges, double-applying both the old and new plan's monthly fees in the transition cycle. The combined amount exceeds the new plan's contractual ceiling.
**IBM Telco Indicators:** MonthlyCharges = approximately (old_monthly + new_monthly) in the transition month; TotalCharges shows a single anomalous month within an otherwise consistent billing pattern; InternetService or streaming tier changed in the same cycle.
**Investigation Steps:**
1. Pull billing detail for the transition cycle — identify double-charge components
2. Check plan migration timestamp vs. billing cycle boundary
3. Verify proration calculation: should be (days on old plan / days in cycle) × old_rate + (days on new plan / days in cycle) × new_rate
4. Confirm whether both full monthly charges or prorated amounts were applied
**Resolution:** Reverse the duplicate full-month charge; apply correct prorated amounts; fix proration logic in the plan migration workflow.

### 4. Streaming Service Tier Misclassification at Billing
**Description:** Streaming services (StreamingTV, StreamingMovies) were reclassified to a premium tier during a rate table update, causing the combined service bundle to exceed the base plan's contracted ceiling. The customer's contract rate was for the standard streaming tier.
**IBM Telco Indicators:** MonthlyCharges increase correlates with a rate table update event; streaming customers (StreamingTV='Yes' OR StreamingMovies='Yes') are disproportionately affected; non-streaming customers on the same base plan are within bounds; Contract = 'Two year' (price-protected accounts most visibly impacted).
**Investigation Steps:**
1. Identify the rate table update timestamp and which streaming tiers were modified
2. Compare streaming charge components before and after the rate update
3. Verify the customer's contract: did it specify a locked streaming rate?
4. Assess the scope — how many Two-year streaming customers are affected?
**Resolution:** Revert streaming tier to contracted rate; reprocess billing from rate table change date; issue corrective bills and credits to all affected accounts.

## Severity Assessment
- **Revenue Impact:** MEDIUM — Overcharges require refunds; contracts may include penalty clauses for systematic overbilling
- **Regulatory Risk:** HIGH — Enterprise and government contract customers (IBM Telco: 21% on Two-year contracts) may trigger regulatory complaints
- **Churn Correlation:** IBM Telco data shows customers with billing overcharges churn at 3.2× baseline within 3 months of the first overbilled cycle

## IBM Telco Contract Distribution
- Month-to-month: 55.0% of customers (excluded from SLA breach detection)
- One year: 20.9% of customers (moderate risk)
- Two year: 24.1% of customers (high risk — price commitment enforced)

## Recommended Actions
1. Flag all Contract ∈ {'One year', 'Two year'} accounts with MonthlyCharges > P95 × 1.5 using IsolationForest
2. Retrieve contract terms and compare against billing configuration
3. Identify root cause: configuration gap vs. renewal error vs. proration vs. tier misclassification
4. Calculate total overcharge amount from root cause start date
5. Issue refund and corrective bill; notify account management for relationship management
6. Fix underlying billing configuration; add contract rate cap validation to billing CI checks

## Source
[sla_breach, contract_billing_cap, rate_plan_configuration, billing_overage, two_year_contract, annual_contract]
