# Billing Record Failure — RCA Playbook

## Overview

A billing record failure anomaly occurs when a customer's MonthlyCharges and/or TotalCharges contain NULL or NaN values, indicating that the billing pipeline failed to produce a complete charge record for the billing cycle. In the IBM Telco Customer Churn dataset, this anomaly is concentrated in customers with StreamingTV = 'Yes' OR StreamingMovies = 'Yes' — multi-service accounts whose bundle rating is more complex. Accounts with tenure > 0 and NaN TotalCharges represent an active customer whose billing history has been interrupted.

## Detection Signals

- **Primary:** MonthlyCharges = NaN OR TotalCharges = NaN for an account with tenure > 0
- **Secondary:** StreamingTV = 'Yes' OR StreamingMovies = 'Yes' (streaming service accounts are disproportionately affected); InternetService = 'Fiber optic'
- **Threshold:** IsolationForest treats NaN-filled (median-imputed) values as outliers with confidence > 0.88. SWARM routing: graph_first — billing system → ingestion pipeline → bundle rating engine is a multi-hop causal chain.

## Common Root Causes

### 1. Billing Record Ingestion Pipeline Timeout
**Description:** The billing record ingestion pipeline timed out when processing a large batch of complex multi-service accounts, leaving incomplete records that were written to the billing database without charge values.
**Indicators:** Multiple accounts show NaN charges on the same billing cycle date. Affected accounts share a common service bundle (e.g., StreamingTV + StreamingMovies + InternetService). Pipeline execution log shows timeout errors for the affected batch window.
**Investigation Steps:**
1. Check billing pipeline execution log for timeout errors on the affected date
2. Identify all accounts in the failed batch — group by service bundle complexity
3. Confirm that the incomplete records were written without charges (NaN vs. 0.0 distinction matters)
4. Verify pipeline timeout configuration vs. actual processing time for complex bundles
**Resolution:** Increase pipeline timeout for complex multi-service batches. Implement partial-batch retry: failed accounts are re-queued individually. Reprocess incomplete records for the affected cycle.

### 2. Service Bundle Rating Failure
**Description:** The rating engine failed to calculate charges for accounts with a specific service bundle combination (e.g., StreamingTV + StreamingMovies + Fiber optic internet) because the bundle rate configuration was incomplete or conflicting.
**Indicators:** NaN charges are concentrated in accounts with specific service combinations. Other accounts on similar plans without the conflicting bundle combination were billed successfully. Bundle rate configuration log shows errors for the affected service combination.
**Investigation Steps:**
1. Group NaN-charge accounts by service bundle (StreamingTV × StreamingMovies × InternetService combinations)
2. Check bundle rate configuration for the identified combination
3. Verify whether the bundle rate was recently modified or migrated
4. Attempt manual rating calculation for a representative account to confirm the error
**Resolution:** Fix the bundle rate configuration for the affected service combination. Reprocess billing for all accounts with that bundle. Add bundle rating integration test to the billing pipeline CI.

### 3. Billing Cycle Batch Job Failure on Multi-Service Accounts
**Description:** The end-of-cycle billing batch job failed partway through processing, and only accounts processed before the failure point have charge records. Multi-service accounts are typically processed later in the batch (sorted by service count) and are disproportionately affected.
**Indicators:** Accounts without charge records all have higher service counts (multiple active services). The failure split correlates with a batch job error timestamp. Accounts processed before the error timestamp have complete records.
**Investigation Steps:**
1. Retrieve batch job execution log and identify the failure timestamp
2. Extract all accounts processed after the failure timestamp — these have NaN charges
3. Verify the failure cause (disk space, memory, network, database connection)
4. Confirm the batch job has no checkpoint/resume capability (if not, full re-run needed)
**Resolution:** Implement checkpoint-based resume for billing batch jobs. Fix the underlying failure cause. Re-run the batch from the checkpoint for all unprocessed accounts.

### 4. Data Pipeline NaN Propagation from Upstream Service Catalogue
**Description:** An upstream service catalogue export contained NULL values for certain service attributes (e.g., StreamingTV rate = NULL), and the billing pipeline propagated these NULLs to the charge calculation output without validation.
**Indicators:** NaN charges correlate with specific service SKUs. The service catalogue was recently updated. The NaN propagation follows the data lineage from catalogue → rating → billing record.
**Investigation Steps:**
1. Check the service catalogue for NULL rate entries for the affected service SKUs
2. Trace the data lineage: catalogue export → rating engine input → billing record output
3. Verify whether the billing pipeline validates non-NULL rates before processing
4. Identify the catalogue export that introduced the NULL values
**Resolution:** Add NULL validation at the billing pipeline input gate — reject records with NULL rates and route to a dead-letter queue for manual review. Fix the catalogue NULL entries. Reprocess affected accounts.

## Severity Assessment

- **Revenue Impact:** HIGH — NaN charges mean zero revenue collection for affected accounts. Complex multi-service accounts typically have above-average MonthlyCharges (IBM Telco: streaming customers average $89/month vs. $65 overall).
- **Customer Impact:** MEDIUM — customers with NaN charges may receive $0 bills (windfall) or error notices. Confusion causes support contacts.
- **Detection Confidence:** NaN TotalCharges with tenure > 0 → IsolationForest confidence > 0.88. Streaming flag (StreamingTV or StreamingMovies = Yes) narrows the investigation to the correct account population.

## Recommended Actions

1. Identify all accounts with NaN charges in the current billing cycle — group by service bundle
2. Determine whether the failure is pipeline-wide (batch failure) or bundle-specific (rating error)
3. Reprocess billing records for all affected accounts after fixing the root cause
4. Add MLflow alert: billing_record_failure_rate > 0.001 (0.1%) triggers escalation
