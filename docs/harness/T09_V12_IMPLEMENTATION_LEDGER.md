# T09 V12 implementation ledger

Status: implementation complete; final exact-head gates are recorded below and
PR review is pending. This is a Category 1 repair record, not an execution
authorization.

The repair is based on the exact reviewed base
`42a8ce6945c29f4221e03bb836f18421e50f3b1e` (tree
`4271fccaf870cfd6a7963ac43daba5b616a0104a`) on
`codex/t09-v12-model-metadata-receipt-handoff`. The implementation commit
before the documentation/closure record is
`e91a71b9a535060ecf30cb63a3e44632e20e7c82`; the reviewed runner-binding
commit is `70f88e98df7cad56f2361c8a465b8044ef02da3b`.

| Item | Status | Source / evidence |
| --- | --- | --- |
| Exact base commit/tree/parents | met | `42a8ce6945c29f4221e03bb836f18421e50f3b1e`, `4271fccaf870cfd6a7963ac43daba5b616a0104a` |
| PR #4 merge/reviewed-head identity | met | merge `42a8ce...`; reviewed second parent `6d8757...` |
| V11 conflict evidence retained read-only | met | 2,939 bytes; SHA-256 `03a3de457592b2d1e33e3c703d1ffd44abe13bcd8c99b597ac2822d1eef997be` |
| Canonical receipt schema and semantic hash | met | `schemas/t09-model-metadata-receipt.schema.json`; `src/giclab/harness/t09_model_metadata_receipt.py` |
| Strict dotenv and one-shot transport | met | strict non-shell `OPENAI_API_KEY` parser, injected fake transport, one request/no retry/redirect/pagination regressions |
| Provider receipt validation before Lambda mutation | met | `src/giclab/harness/t09_pragmatic_provider.py`; validation and retained source-bound copy precede any Lambda POST |
| Host receipt validation without OpenAI transport | met | `containers/sira-smoke/pragmatic/t09_remote_runner.py`; exact retained-copy resolution and offline acknowledgement |
| Fresh unauthorized V12 package | met | V12 plan/profile/identity/execution/command artifacts with all execution flags false |
| Scientific fields and pair semantics unchanged | met | focused V11/V12 immutability and scientific-contract regressions |
| Independent source/spec rereview | met | Carver final read-only source/spec rereview: conditional pass; its stale-plan wording finding was reconciled in the authoritative Phase 1 plan; no code or contract blocker remained; not Category 3 approval |
| Full suite, static/site, and exact-head parity | met | `make ci-check` against exact base: static/site gates passed; head full suite 1,664 passed, 30 unchanged baseline failures, 0 skipped/xfailed/xpassed; no newly failing, missing, or invalid transitions; parity passed |
| Draft PR, no merge, auto-merge disabled | pending | one draft PR is opened only after the final commit and gates |

## Receipt handoff

The sole Category 3 metadata owner is the local pre-Lambda control plane. Its
canonical receipt is created exclusively with mode `0600`, fsync, exact model
identity, `request_count: 1`, and zero redirect/retry/pagination counts. The V12
provider launch requires that receipt, verifies its semantic SHA-256 and private
authorization binding before any Lambda launch POST, and retains a fresh
source-bound copy at `entry-source/model-metadata-receipt.json`. The host runtime
resolves only that retained copy (or an exact path to it), validates it offline,
and records the receipt hash in its acknowledgement. V12 has no network fallback.

The tracked V12 plan retains `exact_reviewed_merged_commit:
pending-category-2-merge`; a future private Category 3 overlay must bind the
actual reviewed merge identity and exact plan hash before execution.

## Request accounting

| Plane | Metadata network requests |
| --- | ---: |
| Local control plane | 1 |
| Provider launch | 0 |
| Host runtime | 0 |
| Category 1 execution performed | 0 |

No real secret was read and no live provider, cloud, browser, SiRA, evaluator,
or scientific request was made during this repair.

Focused command and result:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q -s \
  tests/test_t09_v12_model_metadata_receipt.py \
  tests/test_t09_pragmatic_provider.py \
  tests/test_t09_v11_plan.py
78 passed
```

Final gate ledger:

```text
make format: passed
make lint (Ruff): passed
make typecheck (strict mypy): passed
make validate: passed
git diff --check: passed
make site (portable Quarto/site validation): passed
BASE_SHA=42a8ce6945c29f4221e03bb836f18421e50f3b1e HEAD_SHA=70f88e9 make ci-check: passed
exact-head parity: 1,664 passed / 1,694 collected; 30 unchanged baseline failures; 0 skipped, xfailed, or xpassed; 0 newly failing; 0 missing base-collected nodes; 0 invalid/weakened transitions
```

The direct `make test` attempt was not treated as a clean result: its raw
observed output before manual interruption during local cleanup was `1,368
passed, 26 failed`. The exact-base outcome-aware parity gate then ran the full
base/head suites and is the authoritative full-suite result recorded above;
the 30 head failures were unchanged baseline nodes.

At this closure point the tracked V12 plan is 15,966 bytes with SHA-256
`b58326cd8974eede6d89bc4c08aaa59f006fd04d051c96ea4aff6c3fe42d13ed`.

The retained V11 conflict evidence remains private and immutable: 2,939 bytes,
SHA-256 `03a3de457592b2d1e33e3c703d1ffd44abe13bcd8c99b597ac2822d1eef997be`.
