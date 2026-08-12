# T08 SiRA smoke pair diff

Classification: **`matched_pair_valid_with_documented_evidence_gaps`**

Pair valid: **true**

Scientific interpretation allowed: **false**

The machine-readable record is
`experiments/EXP-0001-sira-simulative-vs-reactive/T08_SMOKE_PAIR_DIFF.json`.
T08 recomputes the diff from the hash-verified run manifest and condition evidence,
then requires exact equality with both retained T07 diff files.

## Equal fields

The two conditions share the frozen GIC Lab commit, SiRA commit/tree, query/seed and
one-step task, Python 3.11.14, UV lock and installed-package manifest, built image,
Playwright/Chromium revision and executable, immutable GPT-4o snapshot, model-role
routing, runtime adaptation/preflight/runner code, price calculation, environment,
agent/browser/network tools, maximum browser steps, and A10 execution-host class.

Both retained runtime-environment documents compare equal. The actual container image
and working directory are also observed in each container-inspect record. No
invalidating difference was found.

The machine record distinguishes the comparison authority. Task/session, Python,
container image, model/routing, runtime adaptation, environment, tools/isolation, and
browser-step fields are compared from condition-owned records (and, where applicable,
checked against the shared manifest). Frozen commits, dependency/browser bundle, and
execution-host class exist only as shared immutable bindings and are labeled that way;
the price calculation is labeled a shared recomputation method. A shared binding is
not presented as two independent observations.

## Exact command differences

Both Docker argument arrays contain 79 elements. Exactly six positions differ:

| Index | Approved owner | Field |
|---:|---|---|
| 5 | run identity | container name |
| 35 | evidence isolation | condition-owned attempt root |
| 41 | treatment assignment | condition label |
| 56 | source-declared treatment | gate mode |
| 60 | run identity/treatment | job name |
| 64 | source-declared treatment | upstream mode |

All other command elements are byte-equal. The independently recomputed record equals
`condition-command-diff.json` exactly.

## Exact configuration differences

The condition configuration objects differ only on:

- condition label;
- Docker argument array, whose reactive/simulative canonical SHA-256 values are
  `a8729859f21e2b459f17088620452c0878b4306e694a108d6a64389f058a476f` and
  `608da27aac39de83bb59d088fd6d4b455e0c760475502ff4b0c6174996517173`;
- source-mode model-call attempt cap, 16 reactive versus 61 simulative; and
- fixed execution order, reactive first and simulative second.

The source-resolved planner differences are treatment-owned: reactive uses the policy
path; simulative uses the world-model/planner configuration declared by the pinned
source. Realized call/token/cost/wall values and condition-owned output paths are also
allowed to differ. The independently recomputed configuration record equals
`condition-configuration-diff.json` exactly.

## Documented evidence gaps

Per-call provider receipts and allocation are absent; one simulative call role is not
exactly reconstructable; normalized events and regulation records are T08-derived
rather than T07-retained; and locale/timezone identity was not retained per condition.
These gaps are disclosed but do not alter treatment identity or prevent reconstruction
of execution and aggregate accounting. Invalidating differences: **none**.
