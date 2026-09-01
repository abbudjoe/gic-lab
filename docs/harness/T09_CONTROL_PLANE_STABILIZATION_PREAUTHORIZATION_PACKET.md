# T09 control-plane stabilization preauthorization packet

Live authorization: **false**

Scientific interpretation allowed: **false**

## Disposition

This is a review packet for a Category 1 control-plane change. It is not an execution
packet and contains no executable authorization block, credential locator, provider
account value, resource identifier, run root, or successor package identity.

The stopped V16 transaction consumed its authenticated metadata allowance and is not
replayable. It made zero launch or termination POSTs, created zero provider resources,
entered zero empirical attempts, and produced no scientific result. Its sanitized
record is `experiments/EXP-0001-sira-simulative-vs-reactive/T09_V16_PREFLIGHT_STOPPED_DISPOSITION.json`.

## Deterministic review gates

Review should require:

1. every contract passes the real-consumer completeness matrix and its mutation
   regressions;
2. active runtime source passes the AST version-dispatch lint;
3. offline composition passes for every registered contract;
4. the exact V16 happy path and all fifteen required failure scenarios pass through
   the shared controller and production wrappers over fake low-level effects;
5. proof-forgery failures precede staging, fake secret reads, metadata requests,
   provider calls, and condition reservations;
6. primitive-coupling mutations fail at metadata, launch/replacement, accounting,
   raw export, finalization, and cleanup;
7. the incident ledger links the V16 defect to production assembly, lifecycle
   omission, and zero-effect shadow regressions;
8. full, parity, static, privacy, and site gates pass.

## Future package boundary

Only after reviewed merge may a separate PR generate a fresh successor runtime
package. Both its externally supplied authorization overlay and frozen run manifest
must include the complete object defined by
`schemas/t09-control-receipt-bindings.schema.json`: exact control-plane commit/tree,
registry and lint receipts, composition, capsule, production-coupled happy path, all
fifteen failure scenarios, aggregate agent-check receipt, exact shared-source binding,
and incident receipt.

Validation must additionally prove that the capsule's historical-or-successor
runtime state selects the same provider contract, that every scenario reaching
package resolution names the same command-package digest, and that the happy path
contains nonzero reconciled fake model/browser accounting with zero projected real
cost. A lifecycle-omission receipt is the sole package-identity exception because it
must stop before package resolution.

Those validated documents make preparation auditable but do not grant authority. A
future live turn must supply exact current-turn authorization and separately reviewed
low-level effects to the existing production adapter assembly and shared controller.
PR 2 remains package-only; it must not change shared control-plane Python. All
existing safety, budget, freshness, cleanup, evidence, and scientific-freeze gates
still apply.

Concretely, PR 2 may change only the central declarative V17 contract registration,
the goal package state, V17 plans/profiles/contracts/conditions/schemas,
package-specific live `LowLevelEffects`, a package-specific externally validated
`EffectAuthorityGrant`, a V17 receipt root and binding, and V17 documents/tests. The
effects and grant remain unauthorized until a separate Category 3 turn.

PR 2 may not change:

```text
src/giclab/control/agent_check.py
src/giclab/control/cli.py
src/giclab/control/category3.py
src/giclab/control/production.py
src/giclab/control/proofs.py
src/giclab/control/composition.py
src/giclab/control/consumers.py
src/giclab/control/registry_validation.py
src/giclab/control/shadow.py
src/giclab/control/state_capsule.py
src/giclab/control/target.py
the shared controller state machine
the validated-proof architecture
```

If package preparation requires any prohibited change, it must stop and return to a
separate Category 1 control-plane repair. The package boundary is proven with a
temporary synthetic successor whose shared-source byte map remains unchanged; no
tracked V17 plan, identity, run root, or receipt root is created here.
