# T09 V13 explicit pilot-contract binding implementation ledger

Status: **implementation-complete-review-required**. This is Category 1 repair only.

## Provenance and scope

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

The operator attestation is not runtime verification. The user's no-delegation rule
overrides the assembly skill's independent-review stage, so implementation, tests, Git
operations, and final diff review remain in this task; external ChatGPT exact-head
review is still required.

In scope: preserve V12 stopped evidence, repair explicit version-bound identity
selection, retain V11/V12 behavior, create V13/0006 proposal identities, run local
fake/offline gates, and open one review-only draft PR.

Out of scope: real dotenv or secret access; OpenAI or Lambda calls; cloud mutation;
live Docker, browser, SiRA, FanOutQA, evaluator, or scientific execution; V13 run-root
materialization; merge or auto-merge.

## Definition of done

| ID | Required outcome | Evidence | Status |
| --- | --- | --- | --- |
| V13-DOD-01 | Exact base, tree, parents, merged PR #6 head, clean original checkout, and fresh branch/worktree are verified. | Git and GitHub read-only checks. | met |
| V13-DOD-02 | V12 stopped operational facts and cleanup are preserved without private paths or contents. | Sanitized 2,572-byte stopped disposition and historical validation. | met |
| V13-DOD-03 | No active pilot or qualifier path selects a current/latest/default contract. | Explicit resolver APIs, required CLI selector, source regression. | met |
| V13-DOD-04 | V11, V12, and V13 resolve isolated plan, host, attempt, evaluator, qualification, manifest, and package identities. | Historical/exact and cross-version tests. | met |
| V13-DOD-05 | V13 local qualification emits V13 plan and qualification identities and rejects V12 mixtures. | Fake/offline qualifier tests. | met |
| V13-DOD-06 | V13 metadata receipt uses fresh V13 authority while preserving one/zero/zero request ownership and rejecting V12 replay. | Fake transport and version-specific schema tests. | met |
| V13-DOD-07 | V13 plan/profile/execution/commands/runtime/four conditions are byte-bound and statically unauthorized. | Repository validator and package tests. | met |
| V13-DOD-08 | Both task pairs remain matched and include the equal explicit V13 selector. | Machine pair diffs. | met |
| V13-DOD-09 | Scientific hashes, tasks, model, evaluator, scoring, order, retries, and interpretation are unchanged. | V12/V13 semantic projection regression. | met |
| V13-DOD-10 | Focused, full, parity, static, privacy, and site gates have no newly failing or missing base nodes. | Final local and CI records. | partial — final gates pending |
| V13-DOD-11 | One draft PR targets the exact base, auto-merge is disabled, exact-head Actions complete, and no merge occurs. | PR and Actions receipts. | partial — PR pending |

## Implementation decisions

- Core architectural commit: `b8a85a35c721b9cadf753b9a32c3b38c6be60086`.
- V13 explicit contract and reviewed implementation ancestor:
  `315f03b67040a0fb6c0a66117c1ca8329409b6c4`.
- Removed active reliance on `ACTIVE_PROVIDER_CONTRACT`, `PLAN_ID`, `ATTEMPT_ORDER`,
  `RUNTIME_QUALIFICATION_ID`, `LOCAL_FINALIZER_QUALIFICATION_ID`, and
  `FROZEN_RUN_MANIFEST_ID`.
- V12 historical source validation resolves its reviewed ancestor and exact stopped
  merged package; V13 validation resolves only its own current package closure.
- The one-line global swap was rejected because it would make the next successor
  inherit whichever version happened to be assigned globally.

## Remaining phase

Complete final local gates and self-review, commit the generated package and records,
push normally, open one draft PR, and monitor exact-head GitHub Actions. Review, merge,
and any Category 3 authorization remain separate.
