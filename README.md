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
  -> normal baselines and deterministic features
  -> candidate detection
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

The current implementation provides:

- a streaming JSONL data entry point with located validation errors;
- UTC timestamp, HTTP method, and path normalization;
- immutable API audit events and bounded-memory dataset summaries;
- deterministic, epoch-aligned, overlapping event windows;
- nested body-parameter extraction;
- parameter cardinality, entropy, sequence, timing, response, and stable-context
  features.

It does not yet produce anomaly candidates, security alerts, or LLM decisions.

```bash
pixi run sentinelflow inspect --input /path/to/api_requests.jsonl
```

Input errors fail fast by default and include the source filename and physical
line number. Use `--skip-invalid` when exploratory inspection should continue
past malformed rows and report their count.

Profile one nested body parameter without making an anomaly decision:

```bash
pixi run sentinelflow profile-parameter \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --window-seconds 60 \
  --overlap-seconds 10
```

The command emits one JSON object per non-empty actor/source/path window. Its
output contains measured evidence only; it intentionally does not label the
window as benign or malicious.

## Implementation plan

The detailed MVP scope, architecture, task checklist, evaluation design, and
acceptance criteria are documented in
[docs/mvp-implementation-plan.zh-CN.md](docs/mvp-implementation-plan.zh-CN.md).
The current trust boundaries and component responsibilities are documented in
[docs/architecture.md](docs/architecture.md).

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
