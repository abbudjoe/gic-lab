# T07 Gate L1.1 implementation ledger

Status: **complete; replacement Gate L1 plan unauthorized; Gate L2 blocked**

Baseline: `f9a80332da409789fefc435583aa0f1a10d3eb11`

Reviewed implementation freeze:
`0b900213801315f4312105297774b8ea5a6d9f04`

Final packet commit: reported by the final clean handoff; it is a direct descendant
of the implementation freeze and changes none of the plan-bound implementation
artifacts.

## Definition-of-done mapping

| ID | Requirement | State | Evidence |
|---|---|---|---|
| T07-L11-01 | Pass exact branch, baseline, clean-tree, V1-plan, missing-inventory/bundle, and scientific-hash starting checks before editing. | met | Starting table in `T07_GATE_L1_1_REQUEST_LEDGER_REPAIR.md`; V1 SHA regression. |
| T07-L11-02 | Preserve both blocked V1 attempts and permanently prevent V1/0001 replay. | met | V1 public executor rejects; historical private fake fixture only; repair record preserves both dispositions without changing the V1 plan or packet. |
| T07-L11-03 | Implement an exclusive, bounded, append-only, schema/state-validated, fsync-backed ledger before any future request. | met | `lambda_request_ledger.py`; request-ledger schema; identity, capacity, fsync, sequence, field-bundle, and tamper tests. |
| T07-L11-04 | Distinguish no intent, intent/no send, and unknown after send without claiming exactly-once networking. | met | Durable intent/send events, recovery state machine, prefix tests, and documentation. |
| T07-L11-05 | Record response progress and closed failure evidence; repair generic terminal handling. | met | Observer-enabled V2 transport, incremental parser, closed enums, terminal recovery, response-continuity tests, and crash injection. |
| T07-L11-06 | Keep secrets and raw response material out of ledgers, errors, output, and archives. | met | Lazy secret source; V2 public exception boundary; dummy credential and raw-response traceback-local scans; forbidden fallback contract. |
| T07-L11-07 | Create unique V2/0002 identities and exact finite caps; leave the plan unauthorized. | met | V2 plan at SHA-256 `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e`; strict loader rejects drift and pending authorization as a run binding. |
| T07-L11-08 | Seal only a complete ledger and reject incomplete evidence for Gate L2. | met | Two-phase `lambda_archive_v2.py`, exact provenance validator, complete bundle test, storage drift test, and finalizer-failure test. |
| T07-L11-09 | Run focused/full validation, independent review, repairs, and post-review gate; commit cleanly. | met | 102 focused tests; full repository gate; independent reviewer clean verdict after all findings; final clean commit. |
| T07-L11-10 | Preserve scientific and authorization boundaries. | met | No scientific diff; all execution/mutation permissions remain false; no live action occurred. |

## Implementation inventory

| Path | Role |
|---|---|
| `src/giclab/harness/lambda_request_ledger.py` | Durable writer, state machine, offline validator, identity tombstone, bounded preflight disposition. |
| `schemas/t07-lambda-request-ledger.schema.json` | Exact allowlisted event schema; SHA-256 `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73`. |
| `src/giclab/harness/lambda_inventory_plan.py` | Strict V2 plan/run/cap/implementation manifest loader. |
| `src/giclab/harness/lambda_inventory_v2.py` | Future observable in-process transport and fail-closed supervisor. |
| `src/giclab/harness/lambda_cloud.py` | Incremental response parser, V2 artifact identity, typed pagination/schema failures. |
| `src/giclab/harness/lambda_archive_v2.py` | Terminal-ledger-aware two-phase archive and exact Gate L2 eligibility verifier. |
| `schemas/t07-lambda-inventory-v2.schema.json` | V2 inventory/limits/ledger contract; SHA-256 `bbbe2516956658afa3d972c46a7a306eb769c4b17b95ec0171c85d29df161be6`. |
| `src/giclab/harness/lambda_inventory.py` | Historical V1 execution rejection; private fake-only compatibility fixture. |
| `src/giclab/validation.py` | Schema registration. |
| `tests/test_lambda_request_ledger.py` | Writer, fsync, tombstone, identity, state, sequence, semantic-tamper tests. |
| `tests/test_lambda_inventory_v2.py` | Supervisor/failure/secret/plan/transport-control tests. |
| `tests/test_lambda_archive_v2.py` | Concrete local fixture archive, storage identity, complete eligibility, finalizer failure. |

The V2 plan binds the implementation freeze plus the exact SHA-256 of thirteen
runtime/lock/schema artifacts. Runtime verification recomputes those hashes in
process. This solves the commit self-reference problem: the second packet commit may
change only plan, tests, and governance documents; it cannot silently change runtime
code.

## Required deterministic-test matrix

| # | Required case | State | Principal test evidence |
|---:|---|---|---|
| 1 | Eight successful 200 JSON responses | met | Exact eight request IDs, terminal ledger, sealed fake archive, no secret. |
| 2 | Failure before intent | met | Generic boundary test; no intent and no transport entry. |
| 3 | Failure after intent/before send | met | First- and second-ordinal tests; no send and no reused elapsed value. |
| 4 | DNS failure | met | Closed `dns/dns_failure` terminal event. |
| 5 | TLS failure | met | Closed `tls_handshake/tls_failure` terminal event. |
| 6 | HTTP 401 | met | Closed unauthorized status event. |
| 7 | HTTP 403 | met | Closed forbidden status event. |
| 8 | HTTP 429 | met | Closed rate-limit event; zero retry. |
| 9 | Redirect | met | Closed redirect event; no follow. |
| 10 | Unexpected content type | met | Normalized `unexpected` evidence and stop. |
| 11 | Oversized response | met | Closed response-size failure and response cap. |
| 12 | Malformed JSON | met | Immediate JSON failure before request 2. |
| 13 | Schema drift | met | Immediate schema failure before request 2. |
| 14 | Pagination/continuation | met | Immediate pagination failure; no additional request. |
| 15 | Crash after send-started | met | Unknown-outcome event; post-progress metadata retained. |
| 16 | Ledger creation failure | met | Fixed preflight disposition; no secret or request. |
| 17 | Ledger fsync failure | met | Tainted prefix preserved; no state advance. |
| 18 | Terminal ledger failure after possible send | met | Prefix retained; no inventory; fresh closed exception. |
| 19 | Secret canary absent everywhere | met | Ledger/files/output plus every traceback frame/cause/context; raw-response canary archive failure. |
| 20 | Old run identity cannot be reused | met | V1 public rejection, V2 dataclass identity rejection, exclusive run/tombstone tests. |
| 21 | Event order/sequence gaps rejected | met | Online state and offline tamper suite. |
| 22 | No curl/shell/HTTP subprocess | met | Whole fake supervisor subprocess spy. |
| 23 | Local-process caps valid | met | Exact 14-call and 37,814,274-byte constants; three storage observations. |
| 24 | Archive consumes a complete ledger | met | Concrete two-phase bundle and exact hash/provenance validation. |
| 25 | Incomplete ledger cannot yield eligible L2 inventory | met | Incomplete/unknown/finalizer failure rejection. |

## Validation and independent review

Commands use the locked environment without synchronization or installation:

```text
PYTHONPATH=src uv run --no-sync pytest -q \
  tests/test_lambda_request_ledger.py \
  tests/test_lambda_inventory_v2.py \
  tests/test_lambda_archive_v2.py \
  tests/test_lambda_inventory.py \
  tests/test_lambda_cloud.py \
  tests/test_harness_schemas.py
uv run --no-sync ruff check src tests
uv run --no-sync mypy --strict src/giclab
PYTHONPATH=src uv run --no-sync python -m giclab.validation all
PYTHONPATH=src make check \
  QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto
git diff --check
```

Focused result: **102 passed**. Ruff, strict mypy, repository validation, and the
accepted portable-Quarto full gate passed; the full suite reported **539 passed**.
The repository-defined gate checked the frozen lock and rebuilt/reinstalled only the
local `giclab` workspace package. It downloaded or installed no external dependency
or payload.

The independent reviewer found and drove repairs for durable ancestor fsync,
schema-failure identity burn, V1 replay, implementation manifest binding, response
completion ordering, complete-bundle eligibility, exact provenance cross-binding,
semantic ledger field bundles, response metadata/time/byte continuity, secret-bearing
traceback chains, raw response references, and pacing/current-request elapsed state.
Final implementation-freeze verdict: **clean**. Mock/control-plane evidence is not a
claim of live network or kernel/filesystem behavior.

The final packet review found one P2 documentation overstatement about when bounded
raw response memory is discarded. The repair now states the exact lifecycle: response
bodies remain memory-only, may be overwritten by a later completed fetch, and are
cleared at the supervisor boundary. The independent post-repair packet verdict was
**clean**, with no remaining P0–P3 finding.

## Terminal authorization state

```text
Gate L1.1 implementation complete
new Gate L1 plan unauthorized
cloud mutation false
paid compute false
prototype execution false
no account request made
no real secret accessed
Gate L2 blocked
```
