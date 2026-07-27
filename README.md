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

## Implementation plan

The detailed MVP scope, architecture, task checklist, evaluation design, and
acceptance criteria are documented in
[docs/mvp-implementation-plan.zh-CN.md](docs/mvp-implementation-plan.zh-CN.md).

## Development environment

The project uses [Pixi](https://pixi.sh/) for reproducible environment and task
management.

```bash
# Create or update the local environment from pixi.lock
pixi install

# Enter the managed shell
pixi shell

# Run project tasks
pixi run test
pixi run lint
pixi run format
pixi run check
```

Add runtime dependencies with `pixi add <package>` and development dependencies
with `pixi add --feature dev <package>`. Commit both `pixi.toml` and `pixi.lock`
when dependencies change; `.pixi/` remains local and is ignored.

## License

Apache License 2.0.
