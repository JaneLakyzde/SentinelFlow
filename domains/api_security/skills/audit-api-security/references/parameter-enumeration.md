# Parameter-enumeration review

## Minimum alert evidence

Require all of the following:

1. `parameter_cardinality` meets the configured minimum.
2. At least one of `consecutive_sequence`, `fixed_step_sequence`,
   `random_high_cardinality`, or `response_distribution` supports more than an
   isolated typo.
3. Actor, path, parameter, and cited requests form one coherent activity.
4. The strongest supplied benign alternative does not explain the activity.
5. Context is sufficiently complete for the preceding claims.

## Decision table

| Supplied pattern | Normal context | Decision |
|---|---|---|
| Multiple values plus systematic or high-cardinality signal | No supported normal explanation | `alert` |
| Increasing declared page/offset values with stable page size and successful responses | Pagination contract is supplied | `benign` |
| Repeated same value after timeout or 5xx with bounded backoff | Retry evidence is supplied | `benign` |
| High cardinality from a declared batch actor and endpoint | Batch authorization and comparable baseline are supplied | `benign` |
| Candidate resembles pagination/batch/retry but context is absent | Cannot exclude normal behavior | `abstain` |
| Evidence primarily indicates replay, abuse, authorization, or sequence violation | Not parameter enumeration | `out_of_scope` |

## False-positive controls

- Never alert on one 404 or one changed identifier.
- Do not treat numeric ordering alone as proof; identifiers may grow naturally
  or contain gaps.
- Do not combine different actors solely because they share an IP.
- Treat pagination as supported only when the parameter contract or normal
  context says so; do not infer it from a parameter name alone.
- Treat batch work as supported only with declared actor/endpoint or baseline
  evidence.
- Treat retries as supported only when values repeat and timeout, transport,
  5xx, idempotency, or backoff evidence is supplied.

## Confidence guidance

- `0.90–1.00`: multiple independent signals, complete context, and normal
  alternatives contradicted by supplied evidence.
- `0.75–0.89`: minimum evidence is complete with minor limitations.
- `0.50–0.74`: mixed evidence; normally `abstain`.
- Below `0.50`: insufficient evidence; use `abstain` or `benign`.
