# SentinelFlow

[简体中文](README.zh-CN.md) | English

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
  features;
- configurable high-recall parameter-enumeration candidates;
- stable deduplication across overlapping windows;
- a versioned API Security Skill and provider-independent LLM review contract;
- a DeepSeek OpenAI-compatible adapter with bounded retries and JSON output;
- a content-addressed local model-response cache;
- an isolated evaluator for candidate Recall, false-positive rates, and LLM
  Precision gain.

The LLM review layer requires an injected provider client. No model provider or
credential is selected by default. The first concrete adapter supports DeepSeek
through its OpenAI-compatible Chat Completions endpoint.

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
  --overlap-seconds 40
```

The command emits one JSON object per non-empty actor/source/path window. Its
output contains measured evidence only; it intentionally does not label the
window as benign or malicious.

Generate the deterministic candidate baseline:

```bash
pixi run sentinelflow detect-parameter-enumeration \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --config configs/parameter-enumeration.yaml \
  --output candidates.jsonl
```

`candidates.jsonl` contains high-recall intermediate candidates, not security
alerts. Thresholds, pagination exclusions, and response statuses are versioned
in `configs/parameter-enumeration.yaml`. The Skill-constrained LLM reviewer
validates model JSON, evidence types, and cited request numbers before accepting
a decision.

Review the detected candidates with DeepSeek:

```bash
cp .env.example .env
# Set SENTINELFLOW_LLM_API_KEY in .env, then:
pixi run sentinelflow review-parameter-enumeration \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --config configs/parameter-enumeration.yaml \
  --output outputs/reviews.jsonl
```

The command loads credentials from `.env`, which is ignored by Git. Process
environment variables override dotenv values. Each JSONL record contains the
locally validated decision plus provider model, token usage, latency, schema
repair attempts, and cache status. Identical requests reuse the
content-addressed cache under `outputs/cache`; use `--no-cache` only when a
fresh provider call is intentional.

An optional trusted normal-context JSON object can declare known pagination,
batch, or retry contracts:

```bash
pixi run sentinelflow review-parameter-enumeration \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --normal-context /path/to/normal-context.json \
  --output outputs/reviews.jsonl
```

Ground Truth must never be placed in the normal-context file. The reviewer sees
only deterministic candidates and minimal normalized projections of the cited
events. One provider or validation failure is written as an error record without
discarding the remaining candidates.

Evaluate candidates and reviews in a separate process after auditing:

```bash
pixi run sentinelflow evaluate-parameter-enumeration \
  --ground-truth /path/to/ground_truth.jsonl \
  --candidates outputs/candidates.jsonl \
  --reviews outputs/reviews.jsonl \
  --output outputs/evaluation-report.json
```

The evaluator reports candidate- and LLM-level precision, contiguous-episode
Recall, request-level Recall, normal-event false-positive rate, pagination-event
false-positive rate, and LLM precision gain. Ground Truth is accepted only by
this evaluator command, never by detection or review commands.

## Experiment results

The 2026-07-28 development experiment used 3,000 aligned synthetic API events
from the sibling `ad-scout/api_security_lab` generator: 106
parameter-enumeration events in 13 contiguous episodes, 2,646 normal events, and
248 events from five other anomaly categories. The pure-normal partition
contains the 2,646 normal events plus eight legitimate pagination events.

Increasing the 60-second window overlap from 10 to 40 seconds on the development
partition raised episode Recall from 84.62% to 100% without producing a
candidate on the pure-normal partition.

| Measurement | Result |
|---|---:|
| Candidate episode Recall | 13/13 (100%) |
| Candidate target-event Recall | 106/106 (100%) |
| Candidate-level Precision | 13/13 (100%) |
| Pure-normal candidates | 0/2,654 |
| Standard-config pagination event FPR | 0/8 (0%) |
| DeepSeek review completion | 14/14 (100%) |

The standard configuration suppresses declared pagination parameters before LLM
review, so its observed LLM Precision gain is zero. A controlled ablation
disabled only that suppression and admitted one legitimate pagination
candidate:

| Pagination ablation | Candidate only | Candidate + DeepSeek |
|---|---:|---:|
| Episode Recall | 100% | 100% |
| Precision | 92.86% | 100% |
| Pagination event FPR | 100% | 0% |

In that ablation, DeepSeek retained all 13 attack candidates as alerts and
classified the pagination candidate as benign, yielding a **+7.14 percentage
point Precision gain** without Recall loss. These are development/synthetic
results, not blind-test claims. See
[the full Chinese experiment report](docs/experiment-results.zh-CN.md) and the
[dataset manifest](datasets/ad-scout-20260726.manifest.json).

## Implementation plan

The detailed MVP scope, architecture, task checklist, evaluation design, and
acceptance criteria are documented in
[docs/mvp-implementation-plan.zh-CN.md](docs/mvp-implementation-plan.zh-CN.md).
The current trust boundaries and component responsibilities are documented in
[docs/architecture.md](docs/architecture.md).
The current measured results and limitations are documented in
[docs/experiment-results.zh-CN.md](docs/experiment-results.zh-CN.md).

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
