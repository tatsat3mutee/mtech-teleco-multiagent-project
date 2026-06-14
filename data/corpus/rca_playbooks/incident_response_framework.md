# Incident Response Framework for Billing Anomalies

## Incident Classification

### Severity Levels
| Level | Description | Response Time | IBM Telco Examples |
|-------|-------------|---------------|-------------------|
| P1 - Critical | Billing system failure affecting >10% of accounts | 15 minutes | Zero-billing across all Fiber optic accounts; mass duplicate charges on billing cycle date |
| P2 - High | Billing error affecting specific customer segment | 1 hour | Zero-billing for all Two-year contract customers; SLA breach for enterprise accounts |
| P3 - Medium | Isolated anomaly, limited customer impact | 4 hours | Individual usage spike (single account, tenure > 18 months); single billing record failure |
| P4 - Low | Minor billing discrepancy, no immediate revenue impact | 24 hours | Marginal charge rounding on Month-to-month accounts |

## Anomaly Detection Pipeline

### IsolationForest Confidence Score Interpretation
The multi-agent RCA pipeline uses IsolationForest anomaly scores as the primary triage signal:

| Confidence Score | Severity | Action |
|-----------------|----------|--------|
| ≥ 0.90 | P1/P2 | Immediate escalation; SWARM routing to graph_first retrieval |
| 0.75 – 0.89 | P2/P3 | Investigator agent activated; vector_first retrieval |
| 0.60 – 0.74 | P3 | Reasoner reviews; critic validation required |
| < 0.60 | P4 | Logged; no immediate action |

### Rule-Based Prefilter
`rule_based_prefilter(df)` runs before IsolationForest:
- Flags MonthlyCharges = 0 AND tenure > 0 at 100% precision → immediate P2 escalation
- These deterministic violations bypass confidence scoring and go directly to the investigator agent

## Root Cause Analysis (RCA) Methodology

### Step 1: Anomaly Characterization
- What is the anomaly type? (zero_billing, duplicate_charge, usage_spike, billing_record_failure, sla_breach)
- How many accounts are affected? (single account vs. cohort vs. segment-wide)
- What is the time window? (single billing cycle vs. recurring)
- What is the estimated revenue impact? (MonthlyCharges × affected accounts)
- IBM Telco feature context: tenure, InternetService, Contract, StreamingTV/StreamingMovies

### Step 2: SWARM Routing Decision
The SWARM router selects the retrieval strategy before any LLM call:
- `graph_first`: zero_billing, billing_record_failure — multi-hop causal chains through billing system graph
- `vector_first`: duplicate_charge, usage_spike, sla_breach — pattern matching against playbook evidence

The routing explanation is logged to `state["routing_explanation"]` for audit and UI display.

### Step 3: Evidence Collection
- Retrieve top-k documents from knowledge base using the chosen retrieval strategy
- IsolationForest anomaly score and detected feature values
- IBM Telco fields: MonthlyCharges, TotalCharges, tenure, Contract, InternetService, streaming flags
- Change management records for the relevant billing cycle date

### Step 4: Hypothesis Generation (Reasoner Agent)
Hypotheses are grounded in retrieved playbook evidence. Each hypothesis must include:
- Root cause description referencing IBM Telco feature signals
- Supporting evidence citations: `[source: playbook_filename.md, section: Root Cause X]`
- Confidence assessment based on evidence quality
- INSUFFICIENT EVIDENCE declaration if fewer than 2 supporting documents retrieved

### Step 5: Hypothesis Validation (Critic Agent)
- Verify each hypothesis against retrieved evidence — no unsupported claims
- Check for alternative explanations not yet considered
- Assess whether the recommended action matches the root cause
- Flag for revision if evidence grounding score < 0.70

### Step 6: Resolution (Reporter Agent)
- Generate structured RCA report with anomaly context, root cause, evidence, and recommended action
- Include account-level context: tenure bucket, contract type, service configuration
- Specify reprocessing scope: single account vs. billing cycle vs. customer cohort

### Step 7: Prevention
- Add monitoring threshold: IsolationForest anomaly rate > 1% triggers P2 alert
- Update playbooks with new failure mode patterns
- Log all confirmed root causes to MLflow for ablation analysis

## Escalation Matrix

| Condition | Escalation Target | Action |
|-----------|-------------------|--------|
| Revenue impact > $10K (MonthlyCharges × affected accounts) | Revenue Assurance Manager | Immediate notification |
| >500 accounts affected in one billing cycle | VP Operations | Incident bridge activation |
| Contract customer (One year / Two year) overbilled | Account Management | Direct customer notification |
| Zero-billing rate > 0.5% of active accounts | Billing Platform Engineering | Pipeline health check |
| Duplicate charge rate > 0.01% | Billing Engineering | Idempotency audit |

## Mean Time to Resolution (MTTR) Targets
- P1: MTTR < 2 hours
- P2: MTTR < 8 hours
- P3: MTTR < 24 hours
- P4: MTTR < 72 hours

## Common Resolution Patterns

### Pattern: Billing Record Reprocessing
Trigger: Missing charges (zero_billing) or null charges (billing_record_failure)
Steps: Identify failed batch window → fix root cause (config or pipeline) → reprocess affected accounts → validate MonthlyCharges are non-zero → notify accounts

### Pattern: Duplicate Charge Reversal
Trigger: MonthlyCharges ≈ 2× historical average
Steps: Identify duplicate charge components → reverse excess charges → fix idempotency logic → reprocess → validate via TotalCharges/tenure consistency check

### Pattern: Contract Rate Correction
Trigger: SLA breach (MonthlyCharges > P95 × 1.5 for contract customers)
Steps: Pull contract rate from CRM → fix billing configuration → reprocess from overcharge start date → issue refund → notify account management

### Pattern: Rate Card Reset
Trigger: Usage spike (MonthlyCharges 5–10× baseline for Fiber optic / streaming customers)
Steps: Identify incorrect rate rule → revert to standard rate → reprocess affected billing cycle → verify charges return to normal band

## Source
[incident_response, rca_methodology, isolationforest, swarm_routing, billing_anomaly, escalation]
