# T09 SiRA pilot preauthorization packet

Status: **planning packet only; blocked on prerequisites; authorization absent**

This packet is not an authorization sentence, command, or permission overlay. It
records the exact fields a later user decision must bind after prerequisite closure.

## Proposed execution identity

| Field | Proposed value or required materialization |
|---|---|
| Parent plan | `PLAN-EXP0001-PILOT` |
| Clean GIC Lab commit | Must be the later final reviewed execution commit |
| SiRA source | `93fb8d72de71f9a4a13419670adeb34d93cf7acd` |
| Model | OpenAI `gpt-4o-2024-11-20`, all roles; availability reverified |
| Dataset | `DATA-SIRA-FANOUTQA-DEV` revision `76ad1feb689b754bfe4e5e24d3ea371b647efa67`; SHA-256 `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288` |
| Sample | Two counterbalanced task pairs; four condition attempts |
| Proposed substrate | One short-lived x86_64 A10 boundary per condition attempt, no persistent filesystem; exact provider/region/image must be freshly selected and bound |
| OpenAI cap | USD 40.00 aggregate; USD 10.00 per condition attempt |
| Provider-compute cap | USD 5.16 aggregate at the retained planning rate, subject to fresh price verification or a lower replacement |
| Total spend cap | USD 45.16; no unbounded charge category |
| Time | 3,600 seconds per attempt; 14,400 aggregate attempt-wall seconds |
| Model calls | 480 reactive and 1,830 simulative per attempt; 4,620 aggregate |
| Tokens | 1,000,000 per attempt; 4,000,000 aggregate |
| Browser actions | 30 per attempt; 120 aggregate |
| Accelerator | 1.0 A10-hour per attempt; 4.0 aggregate |
| Retries | Zero outer condition retries; source-owned internal retries retained/reconciled |
| Interpretation | Exploratory directional reproduction only; T07 smoke excluded |

## Preconditions before a user may authorize

- Pin and validate spaCy, `en_core_web_sm`, all evaluator transitive dependencies,
  licenses, hashes, and deterministic output.
- Resolve the locked protocol's zero-GPU operational cap through a reviewed version
  without changing treatment, task subset/order, scoring, or interpretation.
- Materialize final source/protocol/config/environment/image/browser/evaluator/command
  identities and recompute each child-plan and parent-profile binding.
- Prove the selected runtime enforces every declared per-attempt and aggregate cap.
- Freshly verify provider price/capacity, zero account instances, exact image,
  firewall baseline/restoration, storage, immutable model availability, and cleanup
  authority through read-only checks.
- Repair future provider evidence retention so ephemeral Jupyter values cannot enter
  raw archives, while lifecycle status remains reconstructable.
- Pass focused tests, independent spec/evidence/safety review, post-review tests,
  repository validation, and the full repository gate.

## Required later user decision

A later current-turn instruction must explicitly identify the clean commit, this plan,
all four child identities/hashes, OpenAI/model snapshot, selected cloud substrate,
API/provider/total spend, wall/model-call/token/browser/accelerator/output caps,
credential channel, empirical stop boundary, evidence destination, firewall/runtime
cleanup, exact provider termination, and terminal verification. No field may be
inferred from this packet, T07 authority, retained price, or project history.

On any prerequisite or dynamic-preflight failure, stop before empirical entry, retain
the failed attempt under a fresh identity when applicable, clean up exact owned
resources, and return for a new decision. T08 performed no action described here.
