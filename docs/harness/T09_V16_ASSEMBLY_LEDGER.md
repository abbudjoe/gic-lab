# Phase 1 — T09 V16 downstream-source and structural-privacy repair

Status: **successful — draft PR open for independent exact-head review**

## Source contract

This Category 1 workstream repairs the two source-proven defects exposed by the
first empirically entered V15 condition. The governing operator attestation is:

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

The immutable base is commit
`be09fe18dd46d0e5fe1aa65cfac29190edfa8aac`, tree
`ff6242c0e57f11e1b0ca158a5af3bb782865782b`, with ordered parents
`bce89afa79a120f7f5acb22fb20512ec9581f7a5` and
`c764c852597b7c7a8f67f91963cfb749386c6887`.

## Scope

In scope:

- replace the unrelated one-MiB downstream-source ceiling with finite,
  role-specific Git-blob contracts;
- repair structural credential heuristics with lexical token boundaries while
  preserving exact-secret and other privacy checks;
- prove exact generated-preflight privacy and empirical-prefix cleanup resume;
- preserve the consumed V15 prefix in a sanitized public disposition;
- optionally re-finalize the immutable private V15 archive offline as regression
  evidence only;
- mint an unauthorized, unexecuted V16/AUTONOMOUS-0009 successor package;
- validate, commit in non-circular stages, push, and open one draft PR.

Out of scope:

- any real secret or dotenv access;
- OpenAI, Lambda, cloud, SSH, Jupyter, live Docker/browser, SiRA, evaluator, or
  scientific execution;
- reuse or pairing of V15 evidence as a V16 result;
- changing the scientific contract, merging, auto-merge, force-push, or
  delegated implementation/review.

## Definition of done

| ID | Requirement | Planned evidence | Status |
|---|---|---|---|
| V16-DOD-01 | Base, parents, remote, PR #10, branch/worktree absence, and V15 terminal closeout are exact. | Git/GitHub identity output and retained closeout receipts. | met |
| V16-DOD-02 | An explicit source-role contract binds selector, finalizer, projection, and schema to exact paths and finite caps. | Focused unit tests and source review. | met |
| V16-DOD-03 | Git blob size and identity are proven before bounded byte comparison; local files cannot change during validation. | Temporary-Git tests for boundary, mutation, metadata, commit, and blob failures. | met |
| V16-DOD-04 | The exact 1,084,958-byte selector and a boundary-sized selector pass; cap+1 and cross-role inputs fail. | Focused downstream-source tests. | met |
| V16-DOD-05 | Downstream receipts expose role/path/bytes/cap/blob/SHA only, with no source contents or unbounded subprocess output. | Receipt assertions and direct source review. | met |
| V16-DOD-06 | OpenAI-, AWS-, and Bearer-style heuristics use consistent left/right lexical boundaries and retain chunk-spanning true positives. | Runtime-constructed positive and embedded-negative tests. | met |
| V16-DOD-07 | Exact-secret, sensitive-JSON, Jupyter, private-network, path, and publication blocking remain fail closed. | Focused privacy regression suite. | met |
| V16-DOD-08 | Production-generated offline-runtime-preflight evidence is structurally privacy-clean while a nearby real canary is detected. | `t09_preflight.run()` regression and `privacy_violations()` assertions. | met |
| V16-DOD-09 | Empirical-prefix cleanup publishes `host-cleanup.json`, then reuses byte-identical receipts with zero repeated mutations. | Full cleanup production-path test. | met |
| V16-DOD-10 | Genuine heuristic and exact-secret findings still block clean publication/continuation. | Negative cleanup tests. | met |
| V16-DOD-11 | Private V15 archive identity is verified and, when available, finalized network-disabled without mutating raw evidence or creating a V16 result. | Value-safe private regression receipt. | met |
| V16-DOD-12 | Sanitized V15 empirical-prefix disposition records exact public evidence, defects, costs, cleanup, and no-comparison rule. | Tracked JSON validation. | met |
| V16-DOD-13 | V16/AUTONOMOUS-0009 plan, profile, contracts, schemas, conditions, packet, ledger, and active state are fresh and version-bound. | V16 package tests and repository validation. | met |
| V16-DOD-14 | Every V16 authorization/execution/live flag is false and no overlay, run root, receipt, provider resource, or attempt exists. | Package assertions and filesystem checks. | met |
| V16-DOD-15 | V11-V15 controls and frozen science remain unchanged; both V16 pair diffs are valid with equal explicit V16 selectors. | Historical package tests, science hashes, and fresh command rendering. | met |
| V16-DOD-16 | Core code/tests are committed before package artifacts bind that immutable ancestor; no self-referential commit binding exists. | Commit topology and artifact fields. | met |
| V16-DOD-17 | Focused, format, Ruff, strict mypy, validation, diff, full pytest, site/Quarto, parity, and CI-check gates have no new failures or missing nodes. | Exact command logs and parity reports. | met |
| V16-DOD-18 | Direct Sol/max self-review is clean for caps, Git plumbing, privacy boundaries, cleanup resume, V15 immutability, V16 freshness, and science. | Recorded review checklist and post-review reruns. | met |
| V16-DOD-19 | One draft PR targets the exact destination head, remains unmerged with auto-merge disabled, and exact-head Actions are monitored. | GitHub PR/check metadata and terminal handoff. | met |

## Implementation mapping

- Git-bound source implementation/tests map to V16-DOD-02 through V16-DOD-05.
- Privacy and cleanup implementation/tests map to V16-DOD-06 through V16-DOD-10.
- Historical/private evidence work maps to V16-DOD-11 and V16-DOD-12.
- V16 package/docs and non-circular commits map to V16-DOD-13 through V16-DOD-16.
- Final gates, direct review, and PR handoff map to V16-DOD-17 through V16-DOD-19.

## Evidence log

- 2026-08-31: verified remote `abbudjoe/gic-lab`, exact destination head,
  base tree/parents, merged PR #10 reviewed head, branch/worktree absence, clean
  original checkout, no tracked V16 artifact, and retained V15 terminal closeout.
- 2026-08-31: created branch
  `codex/t09-v16-downstream-source-and-privacy-repair` in the preferred worktree
  at the exact base and starting tree.

- 2026-08-31: committed core repair `faa064f2b3d677bce1cbaae659805ee4f8f4641c`; focused source, privacy, and cleanup regressions pass.
- 2026-08-31: verified the private V15 archive identity, ran network-disabled validation/projection, preserved 24-call and 49,642-token accounting, and rehashed the archive unchanged.
- 2026-08-31: registered explicit V16 support at `687a0d1ecd51d1f068558b637f9179765c398562`; two renders are byte-identical with valid V16 selectors and pair diffs.
- 2026-08-31: exact final-head local gates passed: format, Ruff, strict mypy,
  repository validation, diff checks, focused regressions, portable Quarto/site,
  full normalized parity, and `make ci-check`; parity reported zero newly failing
  nodes, zero missing base nodes, zero invalid transitions, and four newly passing
  nodes while preserving the 23 inherited base failures.
- 2026-08-31: direct nondelegated review found finite role caps, bounded Git
  plumbing, consistent lexical privacy boundaries, byte-identical cleanup resume,
  immutable V15 evidence, fresh unauthorized V16 identities, and unchanged science.
- 2026-08-31: opened draft PR #11 against
  `phase-1/sira-pilot-autonomous-r2`; auto-merge is disabled and the final published
  exact-head Actions outcome is recorded in the terminal handoff.

## Decisions and blockers

- Direct self-review replaces the assembly skill's usual subagent review because
  the governing request expressly prohibits delegation. Independent review is
  reserved for ChatGPT on the exact draft-PR head.
- All runtime evidence must be fake, temporary, or network-disabled. Any path
  requiring a real credential/provider action is blocked by category and must not
  be attempted.
- No blocker is currently known.

## Next permitted phase

Independent ChatGPT exact-head review of draft PR #11. No merge or Category 3 action
is authorized by this Category 1 handoff.
