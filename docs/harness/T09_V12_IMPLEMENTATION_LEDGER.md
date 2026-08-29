# T09 V12 implementation ledger

Status: Category 1R repair implementation is complete. The existing draft PR
remains open for exact-head review; this record is not a Category 3
authorization.

The repair started from the exact reviewed head
`b557ccc99a121e5347e649a0691a15563b6afdd5` (tree
`fc123fc5d8f21ae0aab18a376dc167616670a14c`) on
`codex/t09-v12-model-metadata-receipt-handoff`, based on
`42a8ce6945c29f4221e03bb836f18421e50f3b1e` (tree
`4271fccaf870cfd6a7963ac43daba5b616a0104a`). The two implementation commits
are `73eb9597c25779fad0cc63bd5c64de49bc173aa6` and
`14927012373da3aa3ffecdb3a387d92dc8faecb1`; a later documentation/closure
commit records the final gates without amending either commit.

| Item | Status | Source / evidence |
| --- | --- | --- |
| Exact base and reviewed-head identity | met | Required base/head/tree/parent and clean-worktree checks passed before editing. |
| V11 stopped conflict retained | met | Historical evidence remains immutable: 2,939 bytes; SHA-256 `03a3de457592b2d1e33e3c703d1ffd44abe13bcd8c99b597ac2822d1eef997be`. |
| Explicit freshness ownership | met | Provider launch uses `PRELAUNCH_FRESH`; host uses `DURABLE_OFFLINE`. |
| Canonical receipt and semantic binding | met | Exact V12 receipt schema, mode-0600 exclusive sealing, authorization/plan/package/run/model/endpoint/count bindings, and hash checks. |
| Provider admission boundary | met | Freshness is checked at the actual launch-send boundary before the Lambda POST; the retained receipt is validated from the same sealed document. |
| Host durable validation | met | Host validates the source-bound receipt offline, keeps prelaunch timestamp ordering, and does not use current-wall-clock age expiry or a network fallback. |
| Fresh unauthorized V12 package | met | Plan/profile/identity/execution/command artifacts retain AUTONOMOUS-0005 identities and false authorization/execution flags. |
| Scientific contract and pair semantics | met | V11 immutability, V12 scientific hashes, task order, and pair-diff regressions pass unchanged. |
| Focused repair regressions | met | 108 focused V12/provider/V11 tests pass, including delayed fake-clock and launch-boundary tests. |
| Independent source/spec rereview | pending final rereview | Initial rereview findings were repaired; a final rereview is required against the post-closure tree. |
| Full/static/site/exact-head gates | pending final run | Must be rerun after the final closure commit and exact final head is known. |
| Draft PR and auto-merge state | pending final inspection | The same PR #5 and branch must remain draft, unmerged, and auto-merge disabled. |

## Receipt handoff and timing ownership

The V11 defect was duplicated ownership of an exact-one authenticated model
metadata GET. The local control plane performed the GET before Lambda launch,
while the merged host runtime would perform another GET during qualification.
Two requests were rejected because the frozen contract permits exactly one.

V12 keeps one local GET and hands off a canonical receipt:

```text
local GET (1) -> sealed receipt -> provider admission (fresh at POST boundary)
-> source-bound receipt copy -> host durable offline validation (0 GETs)
```

The provider freshness policy is `PRELAUNCH_FRESH` with a 1,800-second window,
evaluated using the exact request-send start timestamp. Receipt response
completion and creation must both precede that timestamp. The host policy is
`DURABLE_OFFLINE`: it rechecks immutable bindings, the receipt SHA, provider
entry ordering, and the prelaunch timestamp ordering, but never re-expire the
receipt against the current host clock. Provider and host each make zero
OpenAI metadata requests, and V12 has no fallback to the historical
`model_metadata_preflight()` network path.

## Request accounting

| Plane | Metadata network requests |
| --- | ---: |
| Local control plane | 1 |
| Provider launch | 0 |
| Host runtime | 0 |
| Category 1 live requests | 0 |

No real secret was read and no live provider, cloud, browser, Docker, SiRA,
FanOutQA, evaluator, or scientific execution occurred during this repair.

## V12 package

Plan: `PLAN-EXP0001-PILOT-V12`.

At this ledger update the tracked plan is 16,300 bytes with SHA-256
`c66bfbff8c075370a3ee0101c09de17c8ec0f031ee3d73895006acf6fda42501`.
The plan explicitly binds one local request, provider/host request counts of
zero, a 1,800-second provider freshness window, freshness ownership at the
local/provider launch boundary, host current-time freshness `false`, mandatory
prelaunch timestamp ordering, and receipt replay `false`.

V12 remains `authorized: false`, `execution_allowed: false`,
`cloud_mutation_allowed: false`, `paid_compute_allowed: false`,
`live_qualification_performed: false`, `pilot_executed: false`, and has no
materialized empirical run roots.

## Focused and final validation record

Focused command:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
.venv/bin/python -u -m pytest -q \
tests/test_t09_v12_model_metadata_receipt.py \
tests/test_t09_pragmatic_provider.py \
tests/test_t09_v11_plan.py
108 passed
```

The focused suite uses fake transports and clocks. Its delayed integration
advances beyond 1,800 seconds and beyond the 3,600-second iteration wall while
the host still accepts the exact provider-admitted receipt offline.

The final `make format`, Ruff, strict mypy, `make validate`, full pytest,
portable Quarto/site validation, `git diff --check`, and exact-base parity
results will be recorded here after the final closure commit. Any baseline
failures will be reported as observed; no exclusion or skip workaround is
permitted.

The V12 preauthorization packet continues to state: implementation complete;
local tests complete; PR review required; merge required; live metadata request
not performed in Category 1; Lambda not launched; pilot not executed;
authorization false.
