# Detection-to-Resolution Gap

```mermaid
flowchart LR
    A[Billing Transaction Stream<br/>millions per day] --> B{Automated<br/>Anomaly Detection}
    B -->|flagged in < 5 min| C[Anomaly Queue]
    C --> D[Manual Root-Cause Analysis<br/>by billing engineer]
    D --> E[Resolution<br/>re-rate / refund / credit]

    B -.->|fast, mature| C
    C ==>|SLOW MANUAL GAP<br/>65 to 120 min per case| D

    style B fill:#d4edda,stroke:#28a745
    style D fill:#f8d7da,stroke:#dc3545
    style C fill:#fff3cd,stroke:#ffc107
```

The detection stage is fast and mature (under five minutes). The dominant cost is the
**manual root-cause-analysis gap** (65–120 minutes per case), which this dissertation
automates with a multi-agent GraphRAG pipeline.
