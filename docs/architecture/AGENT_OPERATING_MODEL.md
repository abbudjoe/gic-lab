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
and false authority/science flags, then performs deterministic staging checks. It
does not accept caller proof booleans or hash-shaped receipt tuples.

The controller is the single control flow for the shadow and future live effect
channels. Its production-wrapper assembly calls the retained metadata, provider
launch/replacement, reservation/accounting, evidence, finalizer/evaluator, and
cleanup primitives. Public CI injects deterministic fake network, model, browser,
clock, filesystem, subprocess, and provider channels beneath those wrappers. This PR
contains no live-authority factory, credential-bearing adapter, endpoint, or fallback;
a future package must supply its own externally reviewed authority and low-level
effects to this same assembly and controller.

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
foundation is reviewed and merged. It must not reuse consumed V16 authority, and the
foundation itself creates no successor package identity.
