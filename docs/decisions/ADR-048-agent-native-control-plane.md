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
real-consumer registry completeness, offline composition, an exact validated control
binding, a validated state capsule and complete production-coupled shadow matrix, and
deterministic staging. Cross-bind the capsule's exact historical or package-bound
successor runtime to the selected contract, and cross-bind every post-composition
shadow receipt to the selected command package. Caller booleans and hash-shaped
strings are not proof.

Use one Category 3 state machine and one production-wrapper adapter assembly. The
assembly wraps the retained lifecycle, metadata, provider launch/replacement,
provider-call accounting, browser accounting, raw evidence, downstream finalizer,
pinned evaluator, and cleanup primitives. Public CI injects deterministic fake
low-level effects under those wrappers. A pure fake world may support narrow unit
tests, but it cannot produce tracked control evidence. This change mints only
shadow-only authority and contains no live low-level implementation.

Resolve one frozen `SelectedRuntimeTarget` before every aggregate control gate. The
resolver reads the machine goal, enforces an exact consecutive successor and one of
the two non-authorizing package states, validates the selected package's exact plan
and command bytes, and accepts an explicit version only when it equals the
goal-derived target. State capsule, composition, shadow, agent-check, and receipt
refresh share this resolver. A package-specific receipt root is write-once and all
binding paths are relative to it; the legacy V16 root remains readable and cannot be
silently overwritten by the generator.

## Consequences

Adding a contract without an applicable executable consumer fails locally and in CI.
Mutation tests disable, reject, and misresolve every applicable consumer. Adding an
active literal version allowlist fails the AST gate. The complete production
orchestration can be rehearsed cheaply, including replacement history, accounting,
raw export, finalization, cleanup, and ambiguous outcomes, without treating fake
output as science.

The capability registry becomes intentionally explicit. Historical identity and
schema compatibility checks may still name exact versions, but must be narrowly
annotated or housed in the historical validation module. Current-turn authorization
remains external even when every deterministic check passes.

## Follow-up boundary

A later reviewed package-only PR may add one declarative V17 provider contract,
update the goal to `package-bound-not-authorized`, add V17 package data, provide
package-specific reviewed live low-level effects, supply a package-specific
externally validated authority grant, and seal V17 receipts. It must not change
`agent_check.py`, `cli.py`, `category3.py`, `production.py`, `proofs.py`,
`composition.py`, `consumers.py`, `registry_validation.py`, `shadow.py`,
`state_capsule.py`, `target.py`, the shared controller, or validated-proof
architecture. The package-only allowlist excludes `version_lint.py`, `Makefile`, and
`.github/workflows/ci.yml` as well. It also must not introduce a second controller,
infer authority from Git, or reuse the stopped V16 metadata/authorization reference.
Needing a prohibited shared change returns the work to a separate Category 1 repair.
