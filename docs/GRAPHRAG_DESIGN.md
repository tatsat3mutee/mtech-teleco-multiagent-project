# GraphRAG Design

This document specifies the graph-based retrieval component, its entity and relation
taxonomy, the extraction approach, and how it integrates with the hybrid retriever.

## 1. Motivation

Conventional RAG retrieves isolated passages and discards the relationships between
them. Telecom root-cause analysis, however, requires multi-hop reasoning: a CDR
failure impacts an SLA, which in turn triggers a refund policy. GraphRAG materialises
these relationships as a knowledge graph, so that the retriever can traverse the
causal chain at query time rather than relying on the language model to infer it from
disconnected text.

## 2. Entities extracted

| Entity type | Example | Source field |
|---|---|---|
| Service | "Mobile Data", "Voice", "SMS" | Playbook §Services |
| Customer | "Postpaid", "Prepaid", "Enterprise" | Playbook §CustomerSegments |
| Bill | "Invoice", "CreditNote", "Adjustment" | Playbook §BillingArtifacts |
| CDR | "VoiceCDR", "DataCDR", "SMSCDR" | Playbook §CDRTypes |
| SLA | "AvailabilitySLA", "LatencySLA" | Playbook §SLAs |
| Incident | "ServiceOutage", "BillingError" | Playbook §IncidentClasses |
| Cause | "ConfigDrift", "NetworkFailure", "RatingError" | Playbook §RootCauses |

## 3. Relations extracted

| Relation | Direction | Example triple |
|---|---|---|
| CAUSES | Cause → Incident | (RatingError) CAUSES (BillingError) |
| AFFECTS | Incident → Service | (ServiceOutage) AFFECTS (Mobile Data) |
| BREACHES | Incident → SLA | (ServiceOutage) BREACHES (AvailabilitySLA) |
| INCLUDES | Bill → CDR | (Invoice) INCLUDES (DataCDR) |
| APPLIES_TO | SLA → Customer | (AvailabilitySLA) APPLIES_TO (Enterprise) |

## 4. Extraction approach

Entities and relations are extracted using a hybrid of rule-based matching and
LLM-assisted extraction:

- **Rule-based pass:** regular-expression and keyword matching against the known
  entity terms defined in the taxonomy above.
- **LLM-assisted pass:** a structured prompt that returns JSON lists of entities and
  relations, each citing the source chunk ID it was extracted from.
- **Deduplication:** entities are merged by case-insensitive name match, with
  alternative surface forms recorded as aliases.

## 5. Graph storage

- NetworkX `MultiDiGraph` (allows multiple relations between same node pair)
- Pickled to `data/graph_rag/kb_graph.pkl` (gitignored, rebuildable via `scripts/build_graph_rag.py`)
- Node attributes: `type`, `source_chunks` (list of chunk IDs), `aliases`
- Edge attributes: `relation`, `source_chunk`, `confidence`

## 6. Retrieval algorithm

At query time the component proceeds as follows:

1. Extract entities from the anomaly query using the same extractor as §4.
2. Match the query entities to graph nodes (exact match first, then fuzzy match).
3. Perform a k-hop breadth-first traversal from the matched nodes (default k = 2).
4. Score each retrieved node as
   `score = α · relevance + β · (1 / hop_distance) + γ · source_chunk_count`.
5. Map the selected nodes back to their source chunks, deduplicate, and return the
   top-K chunks.

## 7. Integration with hybrid retriever

- Hybrid retriever returns dense+BM25 fusion top-K
- GraphRAG returns entity-grounded top-K
- Final ranked list = reciprocal rank fusion of the two

## 8. Limitations and future work

- No persistent graph database; Neo4j is a candidate for a production deployment.
- The taxonomy is hand-curated and does not evolve automatically; learned schema
  extraction is future work.
- Entity extraction is English-only.
- Edge confidence scores are heuristic rather than calibrated.
