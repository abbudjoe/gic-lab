# Agent operating model

Live authorization: **false**

Scientific interpretation allowed: **false**

## Purpose

The control foundation lets an agent determine what exists, what is valid, what is
permitted, and what should happen next without reconstructing state from historical
turns. It does not turn repository state into execution authority.

Five distinctions are invariant:

- A version is an immutable package or evidence identity.
- A semantic capability selects runtime behavior.
- The scientific contract fixes treatment, tasks, evaluator, model, order, and
  interpretation.
- Current-turn authorization is an external capability and is never inferred from
  Git.
- Observed evidence is append-only fact and is never rewritten by a control decision.

## Source-of-truth boundary

Authoritative machine-readable surfaces are the provider-contract registry, goal
record, incident records, composition and shadow receipts, state-capsule schema and
generator, and scientific protocol/configuration/package artifacts. Reviewed human
projections are execution plans, implementation ledgers, preauthorization packets,
`PROJECT_STATE`, PR bodies, and turn handoffs.

A projection may explain machine state. It may not declare live authority or
scientific interpretation contrary to the machine-readable flags. Repository
validation checks the control projections for the explicit false markers above.

## Control flow

`PROVIDER_CONTRACTS` is the only active version-to-contract registry. Every retained
contract explicitly declares lifecycle, metadata, replacement, cleanup, command,
control-root, authorization, package-transition, selector, and stage-identity
capabilities. Runtime consumers dispatch on those capabilities, never on a latest or
current version.

The registry check invokes every applicable resolver in one `CONTROL_CONSUMERS`
registry. Those are the same lifecycle, metadata, replacement, cleanup, command,
control-root, authorization, package-transition, provider-selector, stage-identity,
and production-assembly resolvers used to build the runtime adapters. A row cannot
pass by returning a declared enum. Offline composition then binds the selected
contract, profile, lifecycle, execution and command packages, pair diffs, cleanup and
replacement policy, source/privacy roles, budgets, evidence identities,
authorization schema, and control-receipt binding schema. Neither phase accepts an
effect adapter.

Every aggregate control entry point first resolves one frozen
`SelectedRuntimeTarget` from `control/goals/EXP-0001.yaml`. The goal must name a
registered historical package, its exact numerical successor, and either
`not-created` or `package-bound-not-authorized`. The first state selects the
historical package and requires that the successor is absent from the registry; the
second selects the exactly registered successor and validates its plan, profile,
execution contract, and centrally declared command-package digest. An explicit
`--provider-contract` is accepted only when it equals that goal-derived selection.
There is no default/current/latest registry lookup, and neither selection path grants
authority.

State-capsule, selected composition, mandatory shadow, agent-check, and receipt
generation consume that same typed target. The target projection binds its source,
goal-record digest, historical and successor state, selected contract and plan, and
command-package digest. Receipt generation writes one new package-specific root at
`control/receipts/packages/<version-lower>/`, builds and validates the complete tree
in a same-parent staging directory, syncs it, and publishes it with one atomic
no-replace directory commit. Symlinks and escapes fail; an unsealed exact final root
is atomically quarantined at its deterministic recovery path; and a sealed root is
immutable. Every binding path is relative to that one root. The retained V16 root is
current evidence only while the goal selects V16 and remains independently valid
historical evidence after a successor becomes current.

The shared Category 3 controller owns this sequence:

```text
identity → composition → validated capsule and receipt binding → local staging
→ secret channel → metadata → provider preflight/freshness → launch
→ provider/host qualification → freeze → four conditions and checkpoint
→ raw sealing/export → finalization → evaluation → cleanup → terminal verification
```

`ValidatedStateCapsule`, `ValidatedControlReceiptSet`,
`ValidatedDeterministicStaging`, and `PreparedCategory3` are opaque frozen values
minted only by exact validators. Preparation loads one binding document, validates
every referenced file byte and semantic hash, proves one commit/tree, contract,
package, complete scenario set, aggregate cross-binding, exact shared-source set,
and false authority/science flags, then performs deterministic staging checks. Each
sealed root contains the exact goal bytes used to select it. Historical validation
proves those bytes against the root's bound commit, resolves `not-created` or
`package-bound-not-authorized` against the sealed registry receipt's exact version
set, and validates bound package and shared-source bytes without substituting the
working-tree goal. Repository validation enumerates the legacy root and every
`control/receipts/packages/<version>` seal; all roots must pass historical validation,
and exactly one must additionally equal the current goal-derived target. Every
post-composition shadow receipt must agree with its root's selected contract and
command package. The happy path must also carry nonzero reconciled fake accounting
and zero projected real cost. It does not accept caller proof booleans or hash-shaped
receipt tuples.

The controller is the single control flow for deterministic conformance and future
live effect channels. `ProductionCategory3World` and
`build_production_adapter_assembly` own transitions, package and grant validation,
package-derived budgets, the retained provider-accounting boundary, typed receipt
validation, evidence ordering, and the infrastructure/science distinction. They call
only effect-neutral interfaces from `giclab.control.effects`:

```text
execute_category3_transaction
        -> ProductionCategory3World / build_production_adapter_assembly
        -> typed clock, metadata, provider, host, condition, finalizer, evaluator,
           and cleanup requests and receipts
        -> exact package-specific LowLevelEffects plus one externally validated grant
```

`RuntimeClock` keeps monotonic time, wall time, and sleep in separate validated
domains. The strict mixed-dotenv parser's exact mutable OpenAI credential reaches one
injected `ModelMetadataChannel` request and is destroyed on success and failure. The
selected plan, execution contract, condition plans, and command manifests—not shared
literals—supply aggregate and condition call/token/cost/action/output/wall caps,
attempt order, model, service tier, and zero-retry policy.

Condition accounting uses one authority: a real-time typed event observer supplied by
the production wrapper. The effect emits each stable call, browser action, output-byte
total, process exit, completion, and raw-publication event; the wrapper applies the
retained `ProviderBudgetBoundary` and reconciles the effect's file-backed ledgers and
outcome. There is no second authoritative runner ledger. Stage, provider-entry,
preflight, host/image/runtime/browser/finalizer qualification, dynamic freeze, raw
seal/export, qualified-local finalization, evaluation, and cleanup all return exact
request-bound receipts. Raw files are revalidated before and after finalization, and
the evaluator consumes the effect-produced finalized session.

Bounded provider replacement also uses a typed outcome. Only a validated retained
pre-empirical closeout may raise `ReplacementEligibleFailure`; an arbitrary adapter
failure or a mutated receipt is terminated and stopped without authorizing another
launch.

Public CI injects `shadow_effects` beneath this same assembly. Fake clocks,
runtime-created credential canaries, deterministic provider/model/browser traces,
canned fixture answers, and `ShadowFaultPlan` exist only below the effect boundary.
The shared assembly never branches on a scenario name. The static anti-shadow gate
records the base defect inventory and rejects fixture constants, fixed epochs, canned
answers, fixed caps, and scenario-driven branches from effect-neutral source.

An `EffectAuthorizationContext` binds the exact control commit/tree, provider
contract, plan and command package, validated control proof, effect path/bytes/SHA/
factory/protocol, transaction root, and external authorization identity. Shared code
can mint only an exact shadow-only grant. A package-bound successor must centrally
declare its effect implementation; the loader rejects path escape, symlink, untracked
or changed bytes, wrong factory/module/protocol/package, and any missing or mismatched
external live grant. This PR defines and tests that boundary but contains no live
grant, live adapter, endpoint, secret, or provider operation.

Scientific-attempt consumption, provider capability consumption, metadata allowance,
evidence completeness, cleanup state, and interpretation permission remain separate
typed state. Ambiguous provider outcomes remain ambiguous; infrastructure failures
cannot become scores.

## Accretive operation

Future incidents add immutable observed facts and exact regression nodes. Future
contracts add one complete capability declaration and must pass every consumer in the
registry matrix. A future live package must bind the exact document required by
`schemas/t09-control-receipt-bindings.schema.json` in both its authorization overlay
and frozen manifest. Binding valid control evidence does not create live authority.

The next PR may mechanically generate a fresh package from these receipts after this
foundation is reviewed and merged. It may add one central declarative V17 contract,
move the goal to `package-bound-not-authorized`, add V17 plan/profile/contracts/
conditions/schemas, add package-specific live `LowLevelEffects` and an externally
validated package-specific `EffectAuthorityGrant`, add a V17 receipt root and
binding, and update V17 documents/tests. It must not reuse consumed V16 authority,
and this foundation itself creates no successor package identity.

That package-only PR must not change `adapters.py`, `agent_check.py`,
`anti_shadow_lint.py`, `category3.py`, `cli.py`, `composition.py`, `consumers.py`,
`contracts.py`, `effects.py`, `live_conformance.py`, `production.py`, `proofs.py`,
`registry_validation.py`, `shadow.py`, `shadow_effects.py`, `state_capsule.py`,
`target.py`, the shared controller state machine, effect protocol, or validated-proof
architecture. The package-only allowlist also excludes `version_lint.py`, `Makefile`,
and `.github/workflows/ci.yml`; none is a V17 package-data surface. If a successor
requires any such shared change, package generation stops and a separate Category 1
control-plane repair is required.

## Exact-head review repair

Review 5088727234 of PR #14 found four remaining authority gaps at reviewed commit
`3291af1e64ec1ea89b8773a586c97a917f1052a2`. The repair keeps the same controller,
production assembly, effect protocol direction, and real-time event observer. It
strengthens who decides, what survives failure, and which filesystem and authority
identities remain held.

The first-pair checkpoint now reconstructs both Task A attempts from retained raw,
finalizer, evaluator, command-pair, and provider-lifecycle records. It passes those
facts, authoritative aggregate usage, injected-clock wall values, and conservative
frozen-plan projections to `t09_sira_pilot.first_pair_decision`. A score of `0.0` is
scored; `None` is not. The exact returned decision and reasons are persisted through
`record_first_pair_checkpoint`. `stop-before-task-b` is a clean operational stop: it
creates no Task B reservation or entry, permits no scientific interpretation, and
still performs cleanup.

Every infrastructure failure after empirical entry is a typed consumed outcome. The
wrapper closes descendants, reconciles known and unknown calls, validates a bounded
no-follow essential bundle, invokes `mark_essential_failure_sealed`, and requires an
export acknowledgement. The attempt remains consumed, unscored, nonretryable, and
ineligible for finalization or evaluation. A nonzero process exit has this
classification even if an answer was emitted.

Live effects, metadata, launch, cleanup, and terminal consumption now share one
opaque `ValidatedLiveEffectAuthority`. Only the shared validator can mint it, after
calling the selected contract's authorization validator over an external private
overlay. The exact source, control/package/effect/root context, cost caps, zero-retry
policy, interpretation boundary, turn scope, and one-campaign limit are one durable
single-use state machine. Reservation occurs before any secret read; replay or an
ambiguous/replaced state fails closed. A package supplies overlay schema and policy,
not a trusted duck-typed grant.

Effect source bytes are opened once with no-follow semantics, checked against the
declared hash and Git blob, compiled from the held bytes without `.pyc` or pathname
reopen, and revalidated after execution and factory construction. Shared code opens
and holds the external transaction root, derives its device/inode/owner/mode/mount
identity, and checks every path component. Raw, finalized, and evaluator artifacts
are sealed and held by descriptor across each consumer. Their identities are
revalidated before and after use, and all held descriptors are released only after
cleanup and terminal evidence materialization.

The public conformance receipt records reproducible attestations rather than private
temporary paths, inode numbers, or per-run authorization hashes. Exact values remain
bound and validated inside the runtime transaction; stable public booleans and
semantic projections prove which checks passed. Two equivalent successor repositories
therefore generate byte-identical complete receipt trees without weakening the
runtime TOCTOU checks.

No V17 package, effect module, receipt root, external overlay, run root, or
`AUTONOMOUS-0010` identity is created by this repair. Repository, Category 3, live,
and scientific authority remain false. The exact package-only successor allowlist and
no-touch shared-source list are maintained in the T09 preauthorization packet.

## Second exact-head rereview repair

Review 5097085114 of PR #14 found four transitive gaps at reviewed commit
`a4b0fef4c8e2dd98941fd5f812acc208b8a5e47f`: provider cost could still be selected
by a self-consistent effect receipt, failure-envelope metadata sat outside the bounded
payload, a held-root pathname mismatch could interrupt controller terminalization,
and public receipts retained unstable filesystem topology.

Provider cost is now a shared-derived lifecycle proof. The wrapper reloads the exact
provider profile and retained price source, validates every consumed entry/owner and
closeout record by launch ordinal and opaque owner, reconstructs closed and active
wall-time intervals with exact decimal arithmetic, reconciles prior preflight and
current empirical cost, and only then asks the effect to acknowledge that proof. The
effect cannot omit a slot, move an interval, substitute a zero price, or understate a
self-hashed total. `PairCheckpointInput` requires explicit scored-attempt and finalizer
closure evidence at every call site.

An essential failure is one complete finite envelope. Its payload, canonical manifest,
canonical completion receipt, and canonical export acknowledgement are all regular,
single-link, current-user files beneath the held transaction root. Per-member caps, a
finite entry cap, and the 67,108,864-byte aggregate cap cover the complete declared
envelope. Structural and byte-level privacy checks include every member before and
after export and again at terminal scanning; rejected evidence remains unscored and
publication-blocked.

Privacy scanning and cleanup use the held root descriptor when its original pathname
is replaced. The replacement pathname is neither scanned nor mutated. The controller
owns an outer `finally` that terminalizes every validated live authority as complete or
failed-nonreplayable and then releases every artifact, overlay, effect-source, and root
descriptor. Terminal evidence is materialized before release, and an in-memory
empirical/raw prefix remains honest when the durable pathname is unavailable.

Public control evidence uses stable attestations rather than absolute roots, device,
inode, UID, mount, or topology-derived hashes. Exact values remain private and held for
runtime revalidation. Deterministic shadow capability identities are derived from a
validated root-relative role, and local-secret cleanup authority is root-relative, so
equivalent runs under different private roots produce the same public semantic receipt.
This projection does not weaken the exact private identity used by live authorization.

The real-time typed event observer remains the only condition accountant. All EXP-0001
science, ordering, retry, and cost contracts remain unchanged; this repair performed no
live or scientific execution and creates no V17 artifact or authority.
