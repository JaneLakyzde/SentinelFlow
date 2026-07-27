# Architecture Notes

SentinelFlow will separate the reusable audit engine from domain-specific
knowledge.

The shared engine will eventually own event ingestion, windowing, feature
extraction, model invocation, alert processing, and evaluation. Each domain
package will define its own schemas, rules, examples, and LLM skill.

No implementation decisions are fixed by this initial scaffold.
