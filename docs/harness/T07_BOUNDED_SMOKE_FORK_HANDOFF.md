# T07 bounded-smoke fork handoff

Status: **fork-ready after final clean closeout commit; execution unauthorized**

## Branch contract

```text
parent branch: phase-1/sira-smoke-lambda
child branch: phase-1/sira-smoke-bounded
fork point: the final clean high-assurance closeout commit
```

After the final commit is reported, the exact local fork commands are:

```bash
git switch phase-1/sira-smoke-lambda
git status --short
git rev-parse HEAD
git switch -c phase-1/sira-smoke-bounded <FINAL-CLEAN-CLOSEOUT-COMMIT>
```

The status output must be empty and the resolved HEAD must equal the reported fork
point. If the child branch already exists elsewhere, attach a clean worktree to that
exact fork or create a uniquely named bounded-smoke task branch. No command above
authorizes execution.

## Reusable controls

The following are reusable implementations, schemas or evidence patterns—not blanket
empirical qualification. The read-only account evidence and actual archive copies are
observed; model routing, workload capture, runtime cleanup and provider termination
controls are fake-tested/control-plane evidence until the child qualifies them under
its concrete topology.

- immutable `gpt-4o-2024-11-20` routing across every SiRA model-using module;
- exact reactive versus simulative command/configuration comparison;
- aggregate and per-condition API cost, token, wall, browser, call, and output caps;
- secret-channel isolation and negative leakage scans;
- fresh attempt roots and immutable attempt identities;
- raw logs, browser sessions, response bodies, and request-ledger capture;
- append-only/fsync-backed request observability;
- sealed read-only Lambda inventory and resource aliases;
- artifact manifests and SHA-256 verification; 
- provider-side terminal/absence verifier logic, requiring fresh empirical
  qualification for the selected billable resource; and
- baseline `l2m-firewall-baseline-b0ef71115811`, canonical semantic SHA-256
  `b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764`, with
  description-aware restoration payload semantics.

## Deferred and nonblocking controls

- kernel-proven descendant containment;
- an independently surviving watchdog;
- exactly-once automated cloud-launch recovery;
- proof against simultaneous Mac, network, and provider outage;
- full transitive runtime supply-chain attestation;
- production-grade transactional orchestration; and
- external archive finalization as a pre-success prerequisite rather than a post-run
  safeguard.

The child plan must apply the Occam admission rule in
`docs/harness/T07_HIGH_ASSURANCE_RESIDUAL_CONTROLS.md`. A deferred control becomes a
hard blocker whenever its concrete absence could distort the comparison, leak a
credential/private value, exceed spending, strand billable resources, or destroy
reconstructability.

## Preserved scientific boundary

The fork inherits `EXP-0001`, `PLAN-EXP0001-SMOKE`, `SIRA-REACTIVE` first,
`SIRA-SIMULATIVE` second, `gpt-4o-2024-11-20`, directional reproduction,
`interpretation_allowed: false`, pilot unauthorized, and training false. It may not
weaken or reinterpret those fields. The high-assurance branch contains no successful
smoke result and no trajectory evidence.

The bounded child must create its own plan, run/attempt identities, caps, cleanup
contract, review record, and current-turn authorization. It must not reuse any burned
Gate L1, Gate L2, Gate L2M, or firewall-capture identity.
