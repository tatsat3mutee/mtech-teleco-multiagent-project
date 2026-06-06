# System Architecture

```mermaid
graph TB
    subgraph UI["UI & Deployment Layer"]
        ST[Streamlit<br/>5 Pages]
        API[FastAPI<br/>REST API]
        MLF[MLflow<br/>Experiment Tracking]
        LF[Langfuse<br/>Tracing]
    end

    subgraph Agents["Agent Layer (LangGraph)"]
        INV[Investigator<br/>Agent]
        RES[Reasoner<br/>Agent]
        CRI[Critic<br/>Agent]
        REP[Reporter<br/>Agent]
        LLM[LiteLLM Router<br/>Groq → Gemini → DeepSeek → Kimi]
    end

    subgraph RAG["RAG Layer"]
        EMB[Embedder<br/>all-MiniLM-L6-v2]
        CHK[Chunker]
        CDB[(ChromaDB<br/>384-dim)]
        BM[BM25<br/>Sparse Index]
        HYB[Hybrid Retriever<br/>RRF Fusion]
        GR[GraphRAG<br/>NetworkX]
    end

    subgraph Detection["Detection Layer"]
        IF[IsolationForest]
        RB[Rule-Based<br/>Pre-filter]
        STAT[Statistical<br/>Z-Score]
    end

    subgraph Data["Data Layer"]
        IBM[IBM Telco<br/>Loader]
        MAV[Maven<br/>Loader]
        SEBD[SEBD Enterprise<br/>Billing Loader]
        INJ[Anomaly<br/>Injector]
        AUG[Data<br/>Augmentor]
    end

    %% Connections
    ST --> Agents
    API --> Agents
    Agents --> MLF
    Agents --> LF

    INV --> HYB
    INV --> GR
    RES --> LLM
    CRI --> LLM
    REP --> LLM
    CRI -.->|revision| RES

    HYB --> CDB
    HYB --> BM
    EMB --> CDB
    CHK --> EMB

    Detection --> Agents
    IF --> Detection
    RB --> Detection
    STAT --> Detection

    Data --> Detection
    IBM --> INJ
    MAV --> INJ
    SEBD --> INJ
    INJ --> AUG
```
