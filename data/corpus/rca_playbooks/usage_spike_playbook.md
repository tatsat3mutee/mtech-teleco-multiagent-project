# Usage Spike — RCA Playbook

## Overview

A usage spike anomaly occurs when a customer's MonthlyCharges increase suddenly to 5–10× their historical baseline in a single billing cycle. In the IBM Telco Customer Churn dataset, usage spike anomalies are concentrated in customers with InternetService = 'Fiber optic' and tenure > 18 months — established internet-heavy users with stable prior charges. A MonthlyCharges increase from a typical $89 to $890+ is the detection signature. Root causes range from billing system errors (most common) to legitimate high usage.

## Detection Signals

- **Primary:** MonthlyCharges > P95(all customers) × 2.0, with prior months showing stable charges (indicated by TotalCharges ÷ tenure ≪ current MonthlyCharges)
- **Secondary:** InternetService = 'Fiber optic', tenure > 18 months, StreamingTV or StreamingMovies = 'Yes'
- **Threshold:** MonthlyCharges > 10× the customer's historical average → IsolationForest confidence > 0.89 (SWARM routing: vector_first, pattern-matched against usage spike playbook)

## Common Root Causes

### 1. Roaming Charges Not Capped per Contract
**Description:** International or domestic roaming data charges were applied without the contracted roaming cap, resulting in per-MB billing at the highest retail rate.
**Indicators:** Usage spike corresponds to a travel period. Multiple charges from roaming zones appear in the detailed bill. Customer's contract includes a roaming data cap that was not applied.
**Investigation Steps:**
1. Extract detailed billing records for the spike period — look for roaming zone charge codes
2. Compare applied roaming rate against the customer's contracted roaming cap
3. Check if the roaming cap configuration exists in the rate card for this plan
4. Verify whether the cap is enforced in real-time or only during billing
**Resolution:** Apply the contracted roaming cap retroactively. Issue a corrective bill for the difference. Add real-time roaming cap enforcement to the billing engine.

### 2. Streaming Service Miscategorised as Premium Tier
**Description:** A streaming service subscription (StreamingTV or StreamingMovies) was reclassified as a premium-tier service during a catalogue update, causing it to be rated at the premium rate instead of the included bundle rate.
**Indicators:** Usage spike correlates with a service catalogue update date. Affected customers all have StreamingTV = 'Yes' or StreamingMovies = 'Yes'. MonthlyCharges increase by exactly the premium tier rate differential.
**Investigation Steps:**
1. Check service catalogue update history for the spike date
2. Compare pre- and post-update rate entries for StreamingTV/StreamingMovies
3. Identify all customers with streaming services who received the spike
4. Verify the intended rate classification in the updated catalogue
**Resolution:** Revert streaming service rate classification to bundle rate. Reprocess billing for the affected cycle. Add catalogue update validation that checks rate changes against existing contract terms.

### 3. Rating Plan Not Updated After Service Upgrade
**Description:** A customer upgraded their service plan (e.g., from DSL to Fiber optic), but the billing engine continued to use the old plan's rate — then at month-end the system detected the mismatch and applied the difference in a lump sum, creating an apparent spike.
**Indicators:** The spike amount matches the difference between old and new plan rates × number of days since upgrade. The spike occurs in the first billing cycle after a plan change. InternetService shows 'Fiber optic' but the prior month showed 'DSL'.
**Investigation Steps:**
1. Check plan change history for the spike date
2. Calculate expected proration: (new_rate - old_rate) × (days_remaining ÷ cycle_days)
3. Compare calculated proration against the actual spike amount
4. Verify the billing engine's plan change proration logic
**Resolution:** Correct the proration calculation. Issue a corrective bill if the applied amount is incorrect. Fix the plan change handler to apply proration at time of change, not month-end.

### 4. International Usage Applied at Incorrect Rate
**Description:** International usage (calls or data) was rated at a domestic premium rate rather than the applicable international rate, which — counterintuitively — may be lower for contracted international bundles.
**Indicators:** Charge spike includes international destination codes. The applied rate is higher than the customer's contracted international rate.
**Investigation Steps:**
1. Extract international destination charge codes from the spike period
2. Compare applied rates against the customer's international rate schedule
3. Check whether international bundle entitlements were correctly applied
4. Verify rate card currency and unit settings for international zones
**Resolution:** Recalculate charges at correct international rates. Issue corrective bill. Add international rate validation to the billing pipeline.

## Severity Assessment

- **Revenue Impact:** MEDIUM — may represent legitimate revenue or billing errors. Requires case-by-case assessment.
- **Customer Impact:** HIGH — unexpected large bill causes significant customer distress, payment default risk, and churn. IBM Telco: customers with sudden charge spikes churn at 3.1× baseline rate.
- **Detection Confidence:** IsolationForest score > 0.85 for charges > P95 × 2.0 combined with stable tenure history.

## Recommended Actions

1. Cross-reference the spike charges against the customer's rate card and contract terms
2. Check for roaming, streaming recategorisation, and plan change events in the spike period
3. Notify the customer immediately if the spike represents a system error; issue corrective bill
4. Add MLflow alert: usage_spike_rate > 0.002 (0.2%) AND avg_spike_amount > $200 triggers escalation
