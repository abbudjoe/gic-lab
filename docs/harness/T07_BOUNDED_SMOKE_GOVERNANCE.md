# T07 bounded research-smoke governance

Status: **ready-for-bounded-smoke-authorization; unauthorized; not executed**

Decision date: 2026-08-11

## Decision and authority

T07's sole prospective execution path is one manually supervised Lambda/Jupyter
research smoke. The frozen high-assurance track and all burned Gate L1/L2M identities
remain historical evidence. This profile does not revive or reuse their authority.

The repository deliberately remains unauthorized: every execution-permission boolean
in `docs/PROJECT_STATE.yaml` is false, the plan says `authorized: false`, and compute
record `CMP-0001` is `planned` with zero time and cost. A future current-turn user
authorization may be materialized as one fresh mode-0600, Git-ignored overlay bound to
the exact clean commit, plan, limits, private resource binding, run IDs, and one
3,600-second supervised window. The overlay does not rewrite repository authority.

The profile answers only whether the pinned artifact executed, whether its required
evidence/accounting was captured, whether the pair was contract-valid, and whether
cleanup completed. It is not an outcome sample and cannot support interpretation.

## Scientific lock

The following inputs remain byte-identical to fork commit
`397a391b736528dd1049023d629100193e823c49`:

| Input | SHA-256 |
|---|---|
| `protocol.yaml` | `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c` |
| `config.yaml` | `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d` |
| `run-plans/smoke.yaml` | `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425` |
| `conditions/smoke-reactive.yaml` | `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018` |
| `conditions/smoke-simulative.yaml` | `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436` |

The order is `SIRA-REACTIVE` then `SIRA-SIMULATIVE`, once each. Both use the same
open-ended query, seed 42, one browser step, zero retry, and
`gpt-4o-2024-11-20` for default, encoder, memory, policy, world-model, critic,
actor, and fallback roles. Directional-reproduction labeling remains unchanged;
`interpretation_allowed`, pilot, and training remain false.

## Occam admission rule and blockers

A control blocks only when failure could make the contrast misleading, disclose a
private value, materially exceed spend, leave a billable resource running, or prevent
reconstruction. The exact pre-execution blockers are:

- `repository_identity_drift`;
- `sira_source_identity_drift`;
- `immutable_model_unavailable`;
- `model_routing_mixed_or_floating`;
- `secret_channel_failure`;
- `projected_openai_api_cost_above_usd_4`;
- `lambda_price_or_projected_normal_cost_above_usd_2`;
- `evidence_root_not_fresh`;
- `selected_lambda_resource_unavailable`;
- `user_presence_unavailable`;
- `provider_termination_path_unavailable`; and
- `prior_attempt_running_instance_unresolved`.

After launch, Cloud IDE, bootstrap, model/API, browser/container, budget/wall,
evidence-download, or pair-contract failure means: no replay; create the bounded
failure archive when possible; download and verify it; terminate the exact instance;
verify terminal/nonbillable state; remove only the owned ruleset; restore and verify
the global baseline; then archive the local evidence.

## Retained controls

- An executable local supervisor, not a prose-only observer declaration. It writes a
  bounded append-only fsync ledger before each of 13 GET-only requests, validates raw
  bodies in memory, and retains only schema-declared, credential-filtered receipts
  under the ignored run root. A failed execution phase becomes a typed cleanup-only
  capability: attempted ordinals cannot replay, while termination/restoration GETs
  remain available after the execution window expires.
- Seven prelaunch GETs; two security GETs after manual firewall/ruleset changes and
  before launch; one post-launch instance binding GET; one terminal-instance GET
  before ruleset deletion; and two final security GETs after restoration.
- Private resource values materialized from the sealed inputs into one separately
  hashed binding. Public documents retain only aliases, counts, and hashes.
- A pinned SiRA commit/tree/lock/patch, pinned amd64 Playwright image identities,
  exact argument arrays, exact dated model routing, and one authenticated model
  metadata GET before either condition.
- Four owned containers with private PID/cgroup namespaces, no host PID/network/IPC,
  no privilege or runtime socket, capabilities dropped, no-new-privileges, read-only
  root, restart `no`, finite CPU/memory/PID/shared-memory/log/wall/call limits.
- Every container writes to a hard 67,108,864-byte `/giclab/attempt` tmpfs. Evidence is
  copied out through immutable container ID before removal; no writable host evidence
  bind is used. A bounded opt-in entrypoint barrier lets the supervisor prove a live
  running state and nonempty process snapshot before release. Stop failure escalates
  to kill, followed by terminal inspection, removal proof, and zero owned
  container/network/volume residue checks.
- `SIRA_API_KEY` is a private mode-0600 file mounted read-only at
  `/run/secrets/sira_api_key`; only the in-container child receives the environment
  value. `LAMBDA_API_KEY` is used only by the local in-process observer.
  `OPENAI_API_KEY` is rejected. No value belongs in Git, argv, labels, image,
  container configuration, path, log, screenshot, ledger, or archive.
- Success and post-root failure paths both produce bounded, secret-scanned evidence
  archives. Success includes the exact condition-command diff, normalized lifecycle
  events, per-condition regulation decisions, pair budgets, and runtime compute-use
  closeout. Before local sealing, the verifier checks decoded ZIP members, canonical
  paths, manifest membership and hashes, pair linkages, credential shapes, and the
  exact supplied secret value. The archive driver permits only the fixed run-root
  surface, reads every destination back, verifies source/destination SHA-256, fsyncs,
  atomically finalizes, retains the source, and has no internal-disk fallback.

## Deferred limitations

These seven limitations are explicit and nonblocking under the supplied profile:

1. Manual console launch is not exactly-once API-proven.
2. Browser descendant containment is practical container/process evidence, not a
   formal proof against every adversarial escape.
3. A provider or control-plane outage can extend billing.
4. Runtime supply-chain pins are practical artifact identities, not exhaustive
   attestation.
5. Setup is manually supervised and is not production automation.
6. Git/image setup network wire bytes are admitted by a 2 GiB ceiling and bounded by
   a hard 16 GiB disk delta, but only the uv wheel has exact byte-by-byte transfer
   enforcement.
7. One smoke pair has no scientific power.

The Google Flights task necessarily uses site-dependent egress. That does not permit
a changed task, model endpoint, provider, retry, or additional browser action.

## Claim and expiry boundary

Prohibited claims include that SiRA is better, simulative planning improved an
outcome, EXP-0001 passed or failed, H2K internalization is supported, or the system is
production-ready. The profile expires after the first complete pair or first terminal
infrastructure failure. Any retry requires new run identities, plan, review, and
authorization. T08 interpretation and every pilot or successor gate remain blocked.
