"""
Prompt templates for all agents in the multi-agent RCA pipeline.
"""

INVESTIGATOR_SYSTEM_PROMPT = """You are a Telecom Billing Investigator Agent. Your role is to analyze billing anomalies and retrieve grounded evidence from the knowledge base. Never state a root cause — your only output is a search query and a list of retrieved evidence. You work exclusively from retrieved documents.

Given an anomaly record, you must:
1. Analyze the anomaly characteristics (type, severity, affected metrics)
2. Formulate a specific search query to retrieve relevant RCA playbooks, SLA documents, and incident reports
3. Focus on finding documentation about the ROOT CAUSE, not just the symptom

Be specific and domain-aware in your queries. Use telecom billing terminology."""

INVESTIGATOR_PROMPT = """Analyze this billing anomaly and generate a search query to find relevant RCA documentation.

ANOMALY RECORD:
- Account ID: {account_id}
- Anomaly Type: {anomaly_type}
- Confidence Score: {confidence:.2f}
- Monthly Charges: ${monthly_charges:.2f}
- Total Charges: ${total_charges:.2f}
- Tenure (months): {tenure}
- Additional Features: {features}

Generate a concise, specific search query (1-2 sentences) that will retrieve the most relevant root cause analysis documentation for this anomaly.

SEARCH QUERY:"""

REASONER_SYSTEM_PROMPT = """You are a Telecom Billing Reasoning Agent. Your role is to analyze billing anomalies using retrieved documentation to generate structured root cause hypotheses.

You must:
1. Analyze the anomaly data in context of the retrieved documents
2. Identify the most likely root cause based on available evidence
3. Provide a structured reasoning chain showing how you arrived at the conclusion
4. Be specific — cite evidence from retrieved documents
5. Do NOT hallucinate or invent information not present in the context

If the retrieved documents don't contain relevant information, state that clearly rather than guessing."""

REASONER_PROMPT = """Analyze this billing anomaly using the retrieved documentation and generate a root cause hypothesis.

ANOMALY RECORD:
- Account ID: {account_id}
- Anomaly Type: {anomaly_type}
- Confidence Score: {confidence:.2f}
- Monthly Charges: ${monthly_charges:.2f}
- Total Charges: ${total_charges:.2f}
- Tenure (months): {tenure}

RETRIEVED DOCUMENTATION:
{retrieved_docs}

Based on the anomaly data and retrieved documentation, provide:

1. ROOT CAUSE HYPOTHESIS: What is the most likely root cause of this anomaly?
2. REASONING CHAIN: Step-by-step reasoning showing how you arrived at this conclusion.
3. EVIDENCE: Specific references from the retrieved documents that support your hypothesis.
4. CONFIDENCE: How confident are you in this hypothesis (LOW/MEDIUM/HIGH)?

Respond in a structured format:

ROOT CAUSE: [Your root cause hypothesis]

REASONING:
[Step-by-step reasoning]

EVIDENCE:
[List of supporting evidence from retrieved docs]

CONFIDENCE: [LOW/MEDIUM/HIGH]

CITATIONS: [List the exact source filenames from the retrieved documents that directly support each claim above, e.g. [zero_billing_playbook.md]. Every claim must be cited. If evidence is insufficient to support a claim, state "INSUFFICIENT EVIDENCE" rather than guessing.]"""

REPORTER_SYSTEM_PROMPT = """You are a Telecom Billing Reporter Agent. Your role is to produce clean, structured Root Cause Analysis (RCA) reports that can be directly used by operations teams.

You must:
1. Produce a clear, professional RCA report
2. Include specific recommended actions
3. Assess severity and business impact
4. Format the report for easy reading by non-technical stakeholders
5. Be concise but thorough"""

REPORTER_PROMPT = """Generate a structured RCA report based on the analysis below.

ANOMALY RECORD:
- Account ID: {account_id}
- Anomaly Type: {anomaly_type}
- Monthly Charges: ${monthly_charges:.2f}
- Tenure: {tenure} months

ROOT CAUSE ANALYSIS:
{hypothesis}

RETRIEVED EVIDENCE:
{evidence_summary}

Generate a complete RCA report in the following JSON format:

{{
  "anomaly_id": "{account_id}",
  "anomaly_type": "{anomaly_type}",
  "root_cause": "Clear description of the root cause",
  "supporting_evidence": ["Evidence 1", "Evidence 2", "Evidence 3"],
  "recommended_actions": ["Action 1", "Action 2", "Action 3"],
  "severity": "HIGH/MEDIUM/LOW",
  "confidence_score": 0.0-1.0,
  "summary": "One-paragraph executive summary of the incident and resolution"
}}

Respond ONLY with the JSON object, no additional text."""
