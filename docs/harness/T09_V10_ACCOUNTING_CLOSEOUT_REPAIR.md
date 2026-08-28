# T09 V10 accounting and closeout repair

This Category 1 repair prepares a successor control package. It does not execute V10,
change frozen science, or alter V8/V9 evidence.

## Accounting provenance

V8 recorded 33 confirmed sends: 30 responses and three `RateLimitError` provider
exceptions. The exception path failed to publish a terminal accounting transition.
That historical attempt remains consumed, infrastructure-invalid, and unscored.

V9 repaired terminal provider exceptions, but its Task A simulative release order
exposed a second primitive: repeatedly subtracting binary floating-point reservation
totals left a tiny negative residue after 12 known responses. Eleven calls were
terminal; one response-known call was nonterminal. V9 remains immutable,
infrastructure-invalid, unscored, and unavailable to any realized pair.

Commit `bb56edc68367e85b3a918f4b086c65cd578a231c` fixed the primitive. Outstanding
condition and aggregate projections are rebuilt from the authoritative owned per-call
reservation records with `math.fsum`; an empty record set produces an exact positive
zero. The current implementation retains that repair and exposes the same projection
in accounting evidence. Focused regressions cover V8 33/30/3, the exact V9 12-call
release order, atomic call/token/cost admission, response and provider-exception
terminalization, pre-send release, sent-unknown reservation retention, bounded flush,
shutdown, duplicate-send rejection, and zero retries.

## Canonical offline-refinalization receipt

`finalization-complete.json` remains the single completion receipt. Schema
`schemas/t09-offline-refinalization-receipt.schema.json` and the independent selector
bind the immutable raw manifest, frozen science and run-manifest identities, attempt,
task, condition, finalizer/selector/projection sources, absolute Python 3.11.14
interpreter, dependency closure, exact evaluator/scoring contract, network denial,
zero model/browser replay, no raw mutation, semantic output, and terminal state.

Receipt creation follows raw-manifest validation and checks the same raw bytes again.
The semantic fields are deterministic for one raw attempt and closure. Missing or
contradictory identities fail closed. The receipt carries public aliases where exact
private paths are unnecessary and excludes credentials, private network identities,
prompts, and answers.

## Durable early cleanup authority

`src/giclab/harness/t09_cleanup_state.py` provides one minimal exact-owner journal.
Its first fsync'd version is written immediately after the exact provider instance ID
is known and before the post-identity package transition. Every target registration,
lifecycle change, and cleanup result is an exclusive, hash-chained version; earlier
authority cannot disappear during a partial transition.

The journal starts with the exact provider instance and firewall baseline. Exact owned
rulesets, temporary local or remote secrets, and containers are registered as they
become known; values of secrets are never recorded. Cleanup attempts every unfinished
exact target, persists each outcome, tolerates already-absent owned resources, and is
idempotent after completion. Its basic closeout receipt uses no pilot, campaign,
attempt, image, or finalizer state and omits private cleanup locators.

The provider copy is the immutable journal prefix. The remote host extends that exact
hash chain only for its temporary-secret and exact-ID container authority; provider
closeout imports the continuation through `--remote-cleanup-journal`, then records
provider termination, firewall restoration, and local-secret cleanup on the same
chain. Public aliases are display-only: early container cleanup resolves the exact
container ID and verifies the V10 namespace plus plan, host, and role labels before
deletion. Provider termination and a truthful partial basic receipt remain possible
when the optional remote continuation or every later pilot object is absent.

Short-lived utility, evaluator, and finalizer containers use the same authority. The
common Docker runner polls the daemon-owned cidfile while the child is live, appends
the exact ID before waiting further, and records only positively verified removal or
absence. A journal-registration failure cannot skip exact removal and is retained in
the cleanup receipt; an interrupted target remains available to no-pilot closeout.

## Preserved scientific boundary

EXP-0001 still uses SiRA `93fb8d72de71f9a4a13419670adeb34d93cf7acd`, every
role uses `gpt-4o-2024-11-20`, the November 2023 FanOutQA development snapshot remains
at source commit `989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33` and blob
`76ad1feb689b754bfe4e5e24d3ea371b647efa67`, and the exact pinned evaluator remains
unchanged. Task A `7dcbbbdc7f1120cd` stays reactive then simulative, followed by the
continuation checkpoint; Task B `2120afba8009bad3` stays simulative then reactive.
Condition retries remain zero and interpretation remains descriptive calibration only.
