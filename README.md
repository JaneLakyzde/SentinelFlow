# SentinelFlow

SentinelFlow is a planned, extensible framework for explainable security
auditing of event sequences with deterministic analysis and large language
models.

The first domain will focus on API request logs, including authorization
violations, parameter enumeration, interface abuse, replay, sequence violations,
and parameter anomalies.

## Planned architecture

```text
Event logs
  -> normalization and context construction
  -> feature extraction and candidate detection
  -> domain skill and LLM analysis
  -> explainable alerts
  -> precision, recall, FPR, and F1 evaluation
```

## Repository layout

```text
sentinelflow/
  core/          Shared event and window abstractions
  features/      Deterministic feature extraction
  detectors/     Candidate anomaly detection
  llm/           Model adapters and output contracts
  agents/        Multi-step investigation orchestration
  alerts/        Alert validation and deduplication
  evaluation/    Evaluation metrics and reports
domains/
  api_security/
    schemas/     API event and alert schemas
    rules/       Domain rules and taxonomy
    examples/    Small safe examples
    skills/      Versioned LLM skills
configs/         Runtime configuration
datasets/        Dataset manifests and documentation
docs/            Architecture and design notes
tests/           Automated tests
```

## Status

This repository currently contains only the initial project structure. Core
implementation will be added step by step.

## License

Apache License 2.0.
