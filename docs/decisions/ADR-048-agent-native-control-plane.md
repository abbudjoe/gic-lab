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

The post-merge package boundary audit showed that wrapping production primitives was
not sufficient: shared production source still selected fake credentials, advanced a
synthetic clock, built fixture stage/freeze data, forced one CRITIC call with fixed
caps, synthesized raw/finalizer identities, replaced condition answers, branched on a
fake scenario, and authorized only a contract version/revision pair. Those were
shared control-plane defects because a package effect could not perform the real
transaction without hiding work or changing shared source.

Therefore the production assembly now depends on typed effect-neutral interfaces.
One injected `RuntimeClock` supplies separate monotonic, wall-time, and sleep domains;
one `ModelMetadataChannel` receives the exact mutable credential selected by the
strict parser; exact package documents supply budgets and command/session identity;
and typed stage, preflight, qualification, freeze, condition, raw, finalizer,
evaluator, and cleanup receipts are validated against their requests. The
authoritative condition accountant is Option A: the production wrapper's real-time
event observer applies `ProviderBudgetBoundary` as calls and actions occur, then
reconciles the file-backed effect outcome. An effect may not install a competing
authoritative ledger.

Replacement authority is equally explicit: only a validated retained pre-empirical
closeout produces the typed replacement-eligible failure consumed by the controller.
Generic transport, effect, and receipt-validation failures cannot spend the bounded
replacement slot.

Deterministic credentials, time, traces, answers, and failure plans live only in
`shadow_effects.py`; public CI still drives the same controller and production
assembly. The complete base assumption inventory and zero-finding shared-source scan
are sealed in the anti-shadow receipt. A temporary no-network package module proves
the exact loader, externally supplied test grant, multi-event sessions, raw-to-
finalizer-to-evaluator chain, cleanup, zero real cost, and unchanged shared-source byte
map. It creates no tracked V17 identity.

Live authority is a full `EffectAuthorizationContext`, not a version switch. It binds
control commit/tree, contract, plan and command package, control-proof semantic hash,
exact effect implementation path/bytes/SHA/factory/protocol, transaction root, and
external authorization reference/source hash. Shared code can mint only shadow
authority. A live grant and live effects may exist only in the future package module,
and the central loader imports its sole declared factory only after every byte and
grant binding passes.

Resolve one frozen `SelectedRuntimeTarget` before every aggregate control gate. The
resolver reads the machine goal, enforces an exact consecutive successor and one of
the two non-authorizing package states, validates the selected package's exact plan
and command bytes, and accepts an explicit version only when it equals the
goal-derived target. State capsule, composition, shadow, agent-check, and receipt
refresh share this resolver. A package-specific receipt root is assembled, validated,
and synced under one same-parent staging directory, then published through one atomic
no-replace directory commit. All binding paths are relative to that root. Unsealed
conflicts are preserved at one deterministic recovery path; sealed roots, including
the legacy V16 root, cannot be overwritten.

Bind one exact goal snapshot into every sealed root. Historical receipt validation
uses that snapshot, the root's sealed registry version set, its immutable control
commit/tree, package bytes, and shared-source binding. It never substitutes the
working-tree goal or today's expanded registry. Repository validation enumerates all
sealed roots and validates each historically; a separately named current-target
validator requires equality with the one goal-derived active target before Category 3
preparation.

## Consequences

Adding a contract without an applicable executable consumer fails locally and in CI.
Mutation tests disable, reject, and misresolve every applicable consumer. Adding an
active literal version allowlist fails the AST gate. The complete production
orchestration can be rehearsed cheaply, including replacement history, accounting,
raw export, finalization, cleanup, and ambiguous outcomes, without treating fake
output as science.

The capability registry becomes intentionally explicit. Historical identity and
schema compatibility checks may still name exact versions, but only assertions or
adjudications with narrow line-scoped historical annotations are exempt. No active
module receives a blanket lint allowlist. Current-turn authorization remains external
even when every deterministic check passes.

## Follow-up boundary

A later reviewed package-only PR may add one declarative V17 provider contract,
update the goal to `package-bound-not-authorized`, add V17 package data, provide
package-specific reviewed live low-level effects, supply a package-specific
externally validated authority grant, and seal V17 receipts. It must not change
`adapters.py`, `agent_check.py`, `anti_shadow_lint.py`, `category3.py`, `cli.py`,
`composition.py`, `consumers.py`, `contracts.py`, `effects.py`,
`live_conformance.py`, `production.py`, `proofs.py`, `registry_validation.py`,
`shadow.py`, `shadow_effects.py`, `state_capsule.py`, `target.py`, the shared
controller, effect protocol, or validated-proof architecture. The package-only
allowlist excludes `version_lint.py`, `Makefile`, and `.github/workflows/ci.yml` as
well. It also must not introduce a second controller, infer authority from Git, or
reuse the stopped V16 metadata/authorization reference. Needing a prohibited shared
change returns the work to a separate Category 1 repair.

## Exact-head review amendment: checkpoint, failure evidence, authority, and identity

Review 5088727234 showed that effect-neutral interfaces alone were insufficient. The
controller could still bypass the retained first-pair policy, infrastructure failures
could lose essential evidence, live authorization could split across phases, and
validated filesystem paths could be replaced before use.

This ADR therefore adds four decisions:

1. `t09_sira_pilot.first_pair_decision` is the sole Task A continuation policy. The
   production wrapper derives every input from retained evidence and package budgets;
   the controller consumes its typed continue/stop result. A policy stop is not an
   infrastructure exception.
2. Any post-entry infrastructure failure is a consumed typed transaction. Bounded
   essential evidence must be sealed, exported, and acknowledged before a clean
   evidence stop can be claimed. Nonzero exits are always unscored.
3. One opaque validator-minted, external, single-use authorization transaction binds
   effect loading, metadata, provider launch, cleanup, and terminal consumption. The
   selected provider contract validates the reference and source. Structural or
   equality-returning grant objects are not authority.
4. Effect source, transaction root, and downstream artifacts use held descriptors and
   exact byte/inode identities across use. Pathname resolution is not a security
   identity. Descriptors are released only after terminal evidence is complete.

The conformance receipt publishes deterministic redacted attestations for runtime-only
inode and private authorization identities, while the runtime validator retains and
cross-checks the exact values. This keeps equivalent receipt trees byte-identical and
does not turn repository evidence into live authority.

The amendment preserves Option A accounting: the production wrapper's real-time event
observer remains the only authoritative condition accountant. It also preserves all
EXP-0001 science, ordering, retry, cost, and descriptive-only interpretation
contracts. No live execution or V17 artifact is part of this decision.
