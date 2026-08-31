# ADR-048: Agent-native T09 control plane

Status: **accepted for review**

Live authorization: **false**

Scientific interpretation allowed: **false**

## Context

T09 behavior accumulated in independent version lists. V16 existed in the central
provider registry, metadata handling, rendering, and command package, yet the
lifecycle loader retained an allowlist ending at V15. The deterministic defect was
therefore discovered only after the single authenticated metadata allowance had been
consumed.

## Decision

Use an explicit frozen capability record on every provider contract. Keep the central
provider registry and plan-ID lookup as the only active registry; provide no default,
current, or latest contract. Dispatch lifecycle, metadata, replacement, cleanup,
command package, control root, authorization, package transition, selector, and stage
identity from semantic capabilities.

Before any external effect, require repository identity, active-version lint,
registry completeness, offline composition, a valid state capsule, shadow evidence,
and deterministic staging. Use one Category 3 state machine with injected adapters.
Only fake local adapters exist in this change.

## Consequences

Adding a contract without an applicable consumer fails locally and in CI. Adding an
active literal version allowlist fails the AST gate. The complete orchestration can
be rehearsed cheaply, including cleanup and ambiguous outcomes, without treating
fake output as science.

The capability registry becomes intentionally explicit. Historical identity and
schema compatibility checks may still name exact versions, but must be narrowly
annotated or housed in the historical validation module. Current-turn authorization
remains external even when every deterministic check passes.

## Follow-up boundary

A later reviewed PR may generate a fresh runtime package that consumes these receipt
bindings. It must not introduce a second controller, infer authority from Git, or
reuse the stopped V16 metadata/authorization reference.
