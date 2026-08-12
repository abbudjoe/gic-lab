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
  under the ignored run root. Every derived report and state transition is replayed
  from that ledger, including active and terminal observation timestamps. A failed
  execution phase becomes a typed cleanup-only capability: attempted ordinals cannot
  replay, while termination/restoration GETs remain available after the execution
  window expires.
- Seven prelaunch GETs; two security GETs after manual firewall/ruleset changes and
  before launch; one post-launch instance binding GET; one terminal-instance GET
  before ruleset deletion; and two final security GETs after restoration.
- Private resource values materialized from the sealed inputs into one separately
  hashed binding. Public documents retain only aliases, counts, and hashes.
- The local supervisor creates a deterministic tracked-only USTAR upload archive from
  exactly the plan plus its 34 implementation artifacts, with a separately copied
  reviewed bootstrap and a release that binds both hashes. No untracked, ignored,
  private, `.env`, `.git`, `.secrets`, or prior-artifact input is admissible. The two
  upload files are retained locally and must be included in the sealed external
  archive.
- A pinned SiRA commit/tree/lock/patch, pinned amd64 Playwright image identities,
  exact argument arrays, exact dated model routing, and one authenticated model
  metadata GET before either condition. Every Chat Completions request explicitly
  selects API tier `default`; every reconciled response must report `default`, so the
  standard-price budget never relies on project-default `auto` routing.
- A single-use bootstrap release is created only after the post-launch ledger/report
  replay succeeds and the user attests the selected provider image in the console.
  The release, authorization, private binding, observer-state hash, report hash,
  commit, plan, and active timestamp are revalidated remotely and recorded in
  `bootstrap-authority.json` before any workload command.
- The fixed canonical root `/home/ubuntu/t07-bounded-output-0001` is exclusively
  created and fsynced before fallible invocation, authorization, release, archive,
  plan, contract, or secret validation. That directory—not a later imported module—is
  the one-shot attempt claim: any terminal pre-secret failure burns the run identity,
  seals a bounded early-failure prefix when possible, and forbids replay.
- Four owned containers with explicitly private PID and cgroup namespaces, no host
  PID/network/IPC, no privilege or runtime socket, capabilities dropped,
  no-new-privileges, read-only root, restart `no`, and finite
  CPU/memory/PID/shared-memory/log/wall/call limits. The remote bootstrap validates
  the realized Docker inspect document before release; the local inbound verifier
  independently replays that full realized policy from retained evidence.
- Every container writes to a hard 67,108,864-byte `/giclab/attempt` tmpfs. Evidence is
  copied out through immutable container ID before removal; no writable host evidence
  bind is used. A bounded opt-in entrypoint barrier lets the supervisor prove a live
  running state and nonempty process snapshot before release. Create, pre-stop
  inspect/process, stop/kill, terminal-inspect, removal, and residue commands have
  hash-bound receipts; residue proof requires exact empty raw outputs. Stop failure
  escalates to kill, followed by terminal inspection, removal proof, and zero owned
  container/network/volume residue checks.
- `SIRA_API_KEY` is a private mode-0600 file mounted read-only at
  `/run/secrets/sira_api_key`; only the in-container child receives the environment
  value. `LAMBDA_API_KEY` is used only by the local in-process observer.
  `OPENAI_API_KEY` is rejected. The remote bootstrap holds a no-follow file identity,
  truncates and fsyncs it before unlink, verifies absence, and requires manual deletion
  plus credential rotation on identity replacement or incomplete cleanup. No value
  belongs in Git, argv, labels, image, container configuration, path, log, screenshot,
  ledger, or archive. Semantic key/value and nested-JSON scans run before remote ZIP
  creation, after local ZIP decoding, and against the external copy.
- Success, post-root failure, and pre-root early failure paths all produce bounded,
  secret-scanned evidence archives. Early failure reserves its exact disposition and
  incident records, plus a cleanup receipt only when a secret lease was established
  and destroyed; pre-authority failure does not invent an authority record. These
  mandatory records precede optional files under a 1,048,576-byte cap.
  Success includes the exact condition-command diff, raw condition payload/log hashes,
  host environment, normalized lifecycle events, per-condition regulation decisions,
  pair budgets, and runtime compute-use closeout. Before provider termination, the
  local verifier must check decoded ZIP members, canonical paths, exact manifest
  membership and hashes, pair linkages, provider/authority binding, command receipts
  and meters, credential shapes, the actual supplied secret plus its raw/hex/base64/
  URL-safe/SHA-256 derivatives when safely available, and the closed credential-
  rotation invariant. Detected credential material or incomplete cleanup requires
  manual credential rotation and keeps security closeout unresolved.
  The final archive admits only the exact expected source set, snapshots each source
  SHA-256, rechecks it during copy, reads every destination back, verifies
  source/destination SHA-256, fsyncs, atomically finalizes, retains the source, and has
  no internal-disk fallback. Cleanup cannot be declared complete when remote secret
  cleanup is unverified.

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
