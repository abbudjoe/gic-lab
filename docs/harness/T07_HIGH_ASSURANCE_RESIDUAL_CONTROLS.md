# T07 high-assurance residual controls

Status: **deferred; non-authorizing**

The high-assurance infrastructure track is frozen. This register separates controls
that must remain in a bounded smoke from production-grade controls that may be studied
later. It cannot authorize cloud, model, browser, container, or SiRA activity.

## Bounded-smoke admission boundary

A control is a hard blocker only if its failure could make the paired comparison
misleading, expose a credential or private value, materially exceed approved spending,
leave a billable resource running, or prevent reconstruction of what happened.

The bounded fork must therefore retain, at minimum:

- exact scientific and immutable-model identities;
- one externally assigned reactive/simulative pair and fixed order;
- exact command/configuration comparison;
- aggregate and per-condition cost/token/time/action/output caps;
- nonlogging least-privilege secrets with negative leakage scans;
- fresh immutable attempt identities and nonreplayable ledgers;
- raw response, log, session, and cleanup evidence with hashes;
- provider-side terminal-state verification for every billable resource; and
- the repaired exact firewall baseline and restoration semantics if that provider path
  is reused.

## Deferred production-grade controls

| Control | High-assurance finding | Bounded-smoke status |
|---|---|---|
| Kernel-proven descendant containment | Host process enumeration was insufficient; local container candidates were rejected. | Deferred unless the bounded topology could leak descendants, spend, secrets, or evidence outside its declared boundary. |
| Independent watchdog | A fully independent surviving cleanup authority was not completed. | Deferred only when provider-side wall/termination controls and a human recovery path bound billable exposure. |
| Exactly-once cloud launch recovery | Lambda launch idempotency and strong quiescence were not source-proven. | Deferred by avoiding automated launch or by choosing a topology with a simpler bounded ownership contract. |
| Simultaneous Mac/network/provider outage proof | End-to-end availability could not be guaranteed. | Deferred when provider hard limits and later reconciliation prevent unbounded spend or ambiguous evidence. |
| Full runtime supply-chain attestation | Every VM/runtime/browser transitive artifact was not immutably attested. | Deferred for a bounded smoke if exact selected binaries/images and observed manifests suffice to reconstruct the attempt. |
| Production transactional orchestration | Cross-process, cross-provider exactly-once state was not completed. | Deferred when the bounded workflow is single-attempt, visibly supervised, and fail-closed. |
| External archive finalization before success | The high-assurance path required synchronous external finalization. | May become a post-run safeguard if bounded local evidence is retained and later copy/hash verification cannot change scientific outcomes. |

Deferral is not a claim that these controls are unnecessary in production. Any bounded
fork must explicitly apply the admission rule to its concrete provider, budget,
credential, cleanup, and evidence topology. Every execution permission remains false
until a new plan and current-turn authorization establish that narrower contract.
