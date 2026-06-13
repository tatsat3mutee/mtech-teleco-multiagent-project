# Ablation Configuration Matrix

```mermaid
flowchart TB
    subgraph A["Config A — LLM only"]
        A1[Direct LLM call]
    end
    subgraph B["Config B — RAG only"]
        B1[Vector retrieval] --> B2[Single LLM call]
    end
    subgraph C["Config C — Single Agent + RAG"]
        C1[Agent plans query] --> C2[Vector retrieval] --> C3[Reason + report]
    end
    subgraph D["Config D — Multi-Agent + Vector RAG"]
        D1[Investigator] --> D2[Reasoner] --> D3[Critic] --> D4[Reporter]
        D3 -.->|revise once| D2
    end
    subgraph E["Config E — Multi-Agent + GraphRAG (full system)"]
        E1[Investigator<br/>graph-first] --> E2[Reasoner] --> E3[Critic] --> E4[Reporter]
        E3 -.->|revise once| E2
    end

    A --> B --> C --> D --> E

    style A fill:#f8d7da,stroke:#dc3545
    style B fill:#fff3cd,stroke:#ffc107
    style C fill:#fff3cd,stroke:#ffc107
    style D fill:#d1ecf1,stroke:#17a2b8
    style E fill:#d4edda,stroke:#28a745
```

Each configuration adds one architectural component over the previous one, isolating
its contribution. **E − D** isolates the GraphRAG retrieval gain; **D − C** isolates the
multi-agent + Critic gain; **B − A** isolates the retrieval grounding gain.
