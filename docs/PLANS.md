# Execution Plans

Significant work in this repository must be governed by a self-contained execution
plan. The machine-readable goal state, semantic contract registry,
capability/authority state, and transaction receipts form the executable local
control plane. The human execution plan is its reviewed projection: it explains
scope, definition of done (DoD), evidence, decisions, and next authority without
duplicating runtime feature dispatch or independently redefining machine-readable
state.

Plans remain mandatory for significant work. If plan prose conflicts with a typed
contract, observed receipt, or external current-turn authority state, the plan must
be corrected; it does not override those surfaces.

Exactly one active plan has phase authority. A concurrent bounded implementation may
use `Plan role: **workstream**`; it remains subordinate to the authoritative phase
plan and cannot change project permissions, science, or phase state.

## Required plan sections

Every plan must record:

1. the phase or workstream and its source contract;
2. explicit in-scope and out-of-scope work;
3. an auditable DoD with one status per item;
4. implementation-to-DoD mappings;
5. planned and observed evidence;
6. progress and decision logs;
7. blockers and user actions, if any; and
8. the next permitted phase.

Allowed DoD states are `met`, `partial`, `blocked`, and `not-started`. During execution, the overall assembly status may be `in-progress`, `smoke-failed`, `review-failed`, `spec-failed`, `scout-pending`, `scout-failed`, `successful`, or `blocked-user-action`.

No phase may advance while a required DoD item is `partial`, `blocked`, or `not-started` unless the user explicitly changes the contract. Plans move from `docs/exec-plans/active/` to `docs/exec-plans/completed/` only after their evidence and DoD ledger are complete.

## Evidence rule

Claims of completion must cite concrete repository paths and exact commands. Diagnostic output is not evidence of a scientific result. Paid compute, cloud mutation, prototype execution, benchmark execution, and training each require an approved phase contract and any authorization required by `docs/COMPUTE_POLICY.md`.
