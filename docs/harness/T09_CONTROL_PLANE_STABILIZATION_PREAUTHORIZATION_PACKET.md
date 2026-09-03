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
8. the exact base shadow-assumption inventory is sealed and the narrow anti-shadow
   lint reports zero findings in effect-neutral shared source;
9. runtime-created noncanonical credentials, injected real/fake clock shapes,
   package-derived budgets, and multi-call/multi-role/multi-action condition traces
   pass their mutation matrices;
10. request-bound stage, retained provider-entry, preflight, qualification, dynamic
    freeze, exact raw seal, qualified-local finalizer, evaluator, and zero-resource
    cleanup receipts pass their mutations;
11. an exact temporary package effect path/hash/factory/protocol and externally
    supplied no-network test grant drive the unchanged shared controller and
    production assembly while the shared-source byte map remains unchanged;
12. the current V16 root binds the anti-shadow and live-effect conformance receipts
    from an immutable implementation ancestor while the legacy V16 root remains
    historically valid; and
13. full, parity, static, privacy, and site gates pass.

## Future package boundary

Only after reviewed merge may a separate PR generate a fresh successor runtime
package. Both its externally supplied authorization overlay and frozen run manifest
must include the complete object defined by
`schemas/t09-control-receipt-bindings.schema.json`: exact control-plane commit/tree,
the exact bound goal snapshot, registry and lint receipts, composition, capsule,
production-coupled happy path, all fifteen failure scenarios, aggregate agent-check
receipt, exact shared-source binding, anti-shadow lint, live-effect conformance, and
incident receipt. The binding must also carry the selected package's explicit
package-effect registration (or exact `null` for historical V3–V16 packages).

Validation must additionally prove that the capsule's historical-or-successor
runtime state selects the same provider contract, that every scenario reaching
package resolution names the same command-package digest, and that the happy path
contains nonzero reconciled fake model/browser accounting with zero projected real
cost. A lifecycle-omission receipt is the sole package-identity exception because it
must stop before package resolution.

Every sealed root is a historical proof. Its goal snapshot must match its bound
control commit, its package state must resolve against its sealed registry version
set, and its package/source bytes must remain valid. Repository validation enumerates
the retained legacy V16 root and every package root and fully validates all of them.
Only the one root used for current preparation must additionally equal the current
goal-derived target. A later V17 selection must not invalidate or hide V16 proof.

Those validated documents make preparation auditable but do not grant authority. A
future live turn must supply exact current-turn external overlay source material and
separately reviewed low-level effects to the existing validator, production adapter
assembly, and shared controller. The shared validator, not the package, mints the
opaque single-use proof after the selected contract validates its authorization
prefix and source. PR 2 remains package-only. All existing safety, budget, freshness,
cleanup, evidence, and scientific-freeze gates still apply.

Concretely, PR 2 may change only the central declarative V17 contract registration,
the goal package state, V17 plans/profiles/contracts/conditions/schemas,
package-specific live `LowLevelEffects`, package-specific external authorization
policy/overlay schema, a V17 receipt root and binding, and V17 documents/tests. The
effects and external overlay remain unauthorized until a separate Category 3 turn.

PR 2 may not change:

```text
src/giclab/control/adapters.py
src/giclab/control/agent_check.py
src/giclab/control/anti_shadow_lint.py
src/giclab/control/category3.py
src/giclab/control/cli.py
src/giclab/control/production.py
src/giclab/control/effects.py
src/giclab/control/proofs.py
src/giclab/control/composition.py
src/giclab/control/consumers.py
src/giclab/control/contracts.py
src/giclab/control/live_conformance.py
src/giclab/control/registry_validation.py
src/giclab/control/shadow.py
src/giclab/control/shadow_effects.py
src/giclab/control/state_capsule.py
src/giclab/control/target.py
src/giclab/control/version_lint.py
src/giclab/harness/t09_cleanup_state.py
src/giclab/harness/t09_pragmatic_provider.py
src/giclab/harness/t09_sira_pilot.py
src/giclab/validation.py
containers/sira-smoke/pragmatic/t09_remote_runner.py
Makefile
.github/workflows/ci.yml
```

The allowlist is exhaustive, so other shared control source is also outside PR 2 even
when it is not repeated in the exact no-touch list above. If package preparation
requires any prohibited change, it must stop and return to a separate Category 1
control-plane repair. The boundary is proven with a temporary synthetic successor
whose shared-source byte map remains unchanged; no tracked V17 plan, effect,
authorization, identity, run root, or receipt root is created here.

PR #14 review 5088727234 additionally requires the merged V16 root to prove the exact
retained first-pair decision, bounded essential-failure export, unified single-use
authority transaction, held module/root/artifact identities, and byte-identical
public conformance projection. These are shared prerequisites, not files PR 2 may
repair. If any later V17 fixture needs another shared change, package generation must
stop.

PR #14 review 5097085114 additionally requires retained-source provider lifecycle
cost proof, a complete bounded and privacy-scanned essential-failure envelope,
controller-guaranteed authority terminalization and descriptor release after held-root
pathname loss, and topology-free deterministic public receipts. Those cost-proof,
failure-envelope, terminalization, held-identity, loader, authority, conformance, and
public-projection implementations are also frozen shared control. A future V17 PR may
add only the listed package declaration/data/effect/policy/root/doc/test surfaces. If
it needs any shared file above—or another shared controller, loader, authority,
cost-proof, failure-envelope, held-identity, conformance, proof, target, or capsule
change—it must stop and open a separate Category 1 repair.

PR #14 review 5101177903 additionally freezes held-first complete-envelope admission
and selected-target-driven public topology validation. A later package-only V17 change
must generate `control/receipts/packages/v17` through the unchanged shared generator;
that receipt must name V17 and its exact root while the retained V16 roots continue to
validate independently. Every bound JSON, YAML, and textual member—including
`bound-goal-record.yaml`—must remain in the exact scanned inventory. A V17-only runtime
path, device/inode/UID field, omitted member, or unbound extra must fail without a
shared scanner edit. If package generation needs to alter held-size admission,
anti-shadow/topology scanning, agent-check, receipt generation, schemas shared by the
control plane, or any no-touch file above, it must stop for a new Category 1 repair.
