# T07 preauthorization packet

Status: **authorization blocked: complete descendant containment unavailable**

Prepared: 2026-08-08

## Authorization target

- Clean GIC Lab implementation commit: `[IMPLEMENTATION_COMMIT_PENDING]`.
- Branch: `phase-1/sira-smoke`.
- Profile plan ID: `PLAN-EXP0001-SMOKE`.
- Profile path:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml`.
- Profile SHA-256:
  `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425`.
- Reactive condition plan ID: `RUN-EXP0001-SMOKE-REACTIVE`.
- Reactive condition path:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml`.
- Reactive condition SHA-256:
  `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018`.
- Simulative condition plan ID: `RUN-EXP0001-SMOKE-SIMULATIVE`.
- Simulative condition path:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml`.
- Simulative condition SHA-256:
  `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436`.
- Pinned SiRA commit:
  `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Protocol SHA-256:
  `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c`.
- Scientific configuration SHA-256:
  `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d`.
- Reactive resolved adapter-configuration SHA-256:
  `75ae4bacf985a1f29c14c6b60da7ba05d76215a05023fe87965a5af4c0aa50e3`.
- Simulative resolved adapter-configuration SHA-256:
  `9b8ef39965d757f861efc893605a44af6b63dfb486471451ec99dfc1f8d72dcf`.
- Immutable routing SHA-256:
  `8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619`.
- Repository-owned runtime adaptation path:
  `src/giclab/harness/sira_gate_a_runtime.py`.
- Runtime adaptation SHA-256:
  `894783a47c19efc5e141a90a4dd63920b9440e1ef231aad5b2738b1f524bbbcd`.

The previous read-only packet and its baseline commit are superseded as an
authorization basis. The locked profile and condition-plan files were not changed;
their SHA-256 values were independently reverified and remain byte-identical. This
packet restates those exact values alongside the new implementation identity.

## Provider and model

| Field | Exact value |
|---|---|
| Provider | `OpenAI` |
| API base URL | `https://api.openai.com/v1/` |
| Immutable revision | `gpt-4o-2024-11-20` |
| Service tier | standard |
| Input price | USD 2.50 per million tokens |
| Cached-input price | USD 1.25 per million tokens |
| Output price | USD 10.00 per million tokens |

Official documentation was reverified read-only on 2026-08-08. The official GPT-4o
model page lists `gpt-4o-2024-11-20` as an available snapshot and lists Chat
Completions and Responses among supported endpoints. The official pricing page lists
the standard GPT-4o family rates above; applying those family rates to the dated
snapshot is an inference because the pricing page does not list the snapshot on a
separate row. No model-list, model-availability, completion, or
other provider API request was made. The dated snapshot is not the current target of
the floating `gpt-4o` alias; the runtime therefore sends the snapshot string directly
and rejects the alias. If the provider returns a different price, model identity, or
unsupported-revision response during a later authorized preflight/request, execution
must stop without increasing a cap or falling back.

Official sources:

- <https://developers.openai.com/api/docs/models/gpt-4o>
- <https://developers.openai.com/api/docs/pricing>

## Hard limits

Cached input is a subset of input. The category ceilings below are independently
enforced, and `total model tokens = input tokens + output tokens` is also enforced.
The cost boundary prices uncached input, cached input, and output separately, while
the authorization remains conservative because every permitted token would fit if
priced at the USD 10.00 output rate.

| Resource | Aggregate profile | Reactive condition | Simulative condition |
|---|---:|---:|---:|
| API cost | USD 4.00 | USD 2.00 | USD 2.00 |
| Input tokens | 400,000 | 200,000 | 200,000 |
| Cached-input tokens | 400,000 | 200,000 | 200,000 |
| Output tokens | 400,000 | 200,000 | 200,000 |
| Total model tokens | 400,000 | 200,000 | 200,000 |
| Wall time | 240 seconds | 120 seconds | 120 seconds |
| Model/API call attempts | 77 | 16 | 61 |
| Browser steps/actions | 2 | 1 | 1 |
| Generic plan `max_tool_calls` | 2 derived | 1 | 1 |
| Retained output bytes | 209,715,200 | 104,857,600 | 104,857,600 |

Every provider choice has an additional runtime safety ceiling of 4,096 output
tokens. Multi-sample requests reserve `n × 4,096` output tokens before sending; this
is essential for SiRA's `n=20` policy and critic requests.

The model-attempt ceilings are source-derived maxima for one browser step. Reactive
permits four parser attempts each for encoder, policy, actor, and memory. Simulative
adds four policy attempts, five clustering attempts, up to five world-model paths with
four attempts each, and up to five critic paths with four attempts each, for 61 total.
The boundary reserves the declared worst case before sending, counts failed sends,
serializes no implicit retry loop, and reconciles actual provider usage after every
response. Concurrent requests reserve capacity atomically. The sealed two-child
profile and condition ceilings make the aggregate maxima structurally enforceable:
only attempt 1 for each condition is in this authorization surface. Any replacement
requires a new explicit authorization that accounts for all prior usage.

The output-byte monitor counts stdout/stderr plus every non-harness file created or
grown anywhere under the owned attempt root, including session JSON, screenshots,
source/debug logs, and provider/runtime ledgers. Crossing the ceiling terminates the
owned process tree, deterministically truncates failure output at the exact aggregate
byte ceiling (structured files before pipe logs), and makes successful sealing
impossible. Truncation is recorded as infrastructure failure; truncated content is not
valid scientific evidence. Harness run-plan, command, event, cleanup, and manifest
envelope bytes are recorded separately.

## Immutable routing status

Routing is implemented and tested for every pinned SiRA route: `default`, `encoder`,
`memory`, `policy`, `world_model`, `critic`, `actor`, and `fallback`. Every route is
exactly `gpt-4o-2024-11-20`. The repository-owned runtime constructs the role map,
rejects any other command model, fixes the OpenAI base URL, disables LiteLLM transport
retry by setting zero retries, and sends parser/provider retries back through the same
budget boundary. Mixed routes, floating `gpt-4o`, other aliases, provider fallback,
and `OPENAI_API_KEY` fallback are rejected by code and tests.

A code/control-plane change is still required before a live request: the local runner
must provide a kernel-enforced process container that cannot lose descendants when a
child changes session and its parent exits. The current polling tracker is useful
evidence but is not a proof. Gate A commands set
`GICLAB_REQUIRE_DESCENDANT_CONTAINMENT=1`; preflight deterministically refuses them
because that capability is not implemented. Scientific protocol fields remain
unchanged. After that blocker is repaired and rereviewed, operational materialization
would still be required: install the exact runtime/browser, observe their identities,
render and hash final commands, seal canonical children, and change only the
authorization control plane.

## Installation actions awaiting authorization

None of these actions has been executed. The exact planned locations are outside the
pinned source checkout so the upstream Git tree remains clean, including ignored-path
inspection.

1. Create the pinned source checkout:

   ```text
   /usr/bin/git clone --no-checkout https://github.com/sailing-lab/sira.git /Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/source
   /usr/bin/git -C /Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/source checkout --detach 93fb8d72de71f9a4a13419670adeb34d93cf7acd
   ```

2. Install the frozen SiRA Python dependency environment outside the checkout:

   ```text
   UV_PROJECT_ENVIRONMENT=/Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/environment UV_CACHE_DIR=/Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/uv-cache /opt/homebrew/Cellar/uv/0.11.7/bin/uv sync --frozen --extra eval --project /Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/source --python 3.10
   ```

3. Install the pinned Playwright Chromium artifact into its owned cache:

   ```text
   PLAYWRIGHT_BROWSERS_PATH=/Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/playwright UV_CACHE_DIR=/Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/uv-cache /Users/joseph/.local/share/gic-lab/t07/sira-93fb8d72de71f9a4a13419670adeb34d93cf7acd/environment/bin/python -m playwright install chromium
   ```

After installation, preflight must record and hash Python, the exact `uv.lock`, the
installed dependency tree, Playwright 1.39.0, Chromium revision and executable,
Darwin/arm64, locale/timezone, the clean source tree, the runtime adaptation, and all
three owned runtime roots (environment, uv cache, and browser cache). The live command
uses `uv run --frozen --no-sync` with the owned `UV_CACHE_DIR`; it cannot install or
repair dependencies implicitly.

The GIC Lab development environment used only for repository tests was installed by
`make setup`. It is not the SiRA environment. The SiRA dependency environment and
Playwright Chromium have not been installed.

## Secret contract

The only required secret variable name is:

```text
SIRA_API_KEY
```

No secret value was read, printed, persisted, hashed, or inspected in Gate A. Values
are forbidden in argv, environment records, paths, logs, events, and authorization
documents. Only the named channel may be inherited by the subprocess. Ambient
credentials are not enumerated or inherited; `OPENAI_API_KEY` is removed/rejected as
an undeclared fallback. Runtime stdout/stderr and every retained file are checked by
the generic exact-value scrubber after the named value is injected during a later
authorized execution.

## Evidence and cleanup contract

The generic executor creates the immutable condition attempt root with `exist_ok=false`
before process creation. The Gate A command owns that exact root and redirects or
captures the upstream session JSON, source/global/debug logs, embedded screenshots,
stdout, stderr, evaluator directory, provider ledger, runtime environment record,
normalized events, command/run-plan records, artifact manifest, and both runtime and
process cleanup records. Only attempt 1 for each condition is sealed here. A
replacement increments the typed attempt number, cannot reuse or overwrite the prior
root, and is not authorized without a new authorization decision.

The required cleanup contract for any future eligible runner is:

1. close every tracked BrowserGym environment;
2. continuously track descendants by parentage, including children that create a new
   process group or session;
3. enumerate non-zombie owned process-group members and tracked descendants;
4. send TERM to the group and escaped descendants;
5. wait at most 1.0 second;
6. send KILL if any owned process remains;
7. re-enumerate for at most 1.0 second;
8. require `live_pids_after: []` and `zero_live_children: true`;
9. retain and hash cleanup evidence even on timeout, output quota, launch failure, or
   command failure.

Failure to prove zero live descendants makes the attempt infrastructure-invalid and
blocks successful sealing. The current runner cannot make that proof race-free and
therefore blocks before launch. Within the output cap, raw evidence is retained;
output-quota failure may truncate bytes exactly at the declared ceiling. No cloud
resource exists in this profile and no cloud mutation or provider resource cleanup is
authorized.

## Reactive versus simulative resolution

The complete machine-readable command/configuration comparison is
`docs/harness/sira/T07_GATE_A_CONDITION_DIFF.yaml`. The full planned argument arrays
are recorded there. Exactly these differences are permitted:

- condition-owned attempt root and `--output_dir`;
- `--gate-mode` and upstream `--mode`;
- condition/job identity;
- corresponding owned-output-root binding; and
- source-declared planner/sampling behavior induced by mode.

All task, query, provider, model, upstream commit, runtime adaptation, executable,
environment/cache locations, secret names, wall/token/cost/action/output limits,
timeouts, retries, seed, instrumentation, and non-condition command fields are equal.
Reactive resolves to `web_reactive`/policy with base temperature 0.0 and top-p 0.5.
Simulative resolves to `web_simulative`/world-model search with five candidate actions,
depth one, 20 policy samples, 20 critic samples, and temperature/top-p 1.0/0.95; its
single-cluster branch bypasses world-model/critic evaluation. Any other difference is
rejected.

Final command SHA-256 values are intentionally not guessed before installation. They
bind executable bytes, clean input trees, environment/browser identities, cwd inode,
and final attempt paths, and must be materialized after the authorized installation
but before any provider/browser action. The authorization mechanism rejects children
outside the exact reactive/simulative plan-and-command fingerprint set.

## Readiness ledger

| Obligation | Status before authorization |
|---|---|
| Immutable all-role routing | met and tested |
| Single provider budget boundary | met and fake-client tested |
| Retry and concurrent reservation accounting | met and tested |
| Browser-action and output-byte hard caps | met and tested, including atomic replace and immediate exit |
| Fresh attempt ownership and retry isolation | met and tested |
| Source-log and evidence ownership | met and tested |
| External environment/cache contract | met; installation pending authorization |
| Process-group TERM/KILL and zero-child evidence | blocked: no race-free kernel descendant containment |
| Exact smoke-only authorization/sealed children | met and tested |
| Machine condition diff | met and tested |
| Secret-name-only contract | met and tested; value presence not inspected |
| Exact environment/Chromium identity | pending authorized installation |
| Final command hashes and canonical fingerprints | pending post-install materialization |
| Project/profile/condition authorization fields | false; may change only after authorization |
| Live smoke | not run and unauthorized |

## Validation and review

Commands completed across implementation, review repair, and final validation:

```text
git status --short
git rev-parse HEAD
git switch -c phase-1/sira-smoke
make setup
PYTHONPATH=src uv run --no-sync pytest -q tests/test_sira_gate_a.py tests/test_sira_adapter.py tests/test_harness_executor.py tests/test_harness_budget.py tests/test_harness_policy.py
uv run --no-sync ruff check src tests
uv run --no-sync mypy src/giclab/harness
make check QUARTO=/tmp/giclab-t07-quarto.nT1Msu/bin/quarto
git diff --check
```

The final ledger records repository validation, pre-review `make check`, independent
spec-conformance review, any repairs/rereview, and post-review `make check`.

No OpenAI/model API request, experimental browser session, SiRA condition, evaluator,
pilot, cloud job, or paid compute action occurred.

## Blockers and authorization decision

There is one unresolved authorization blocker: no race-free, kernel-enforced complete
descendant containment mechanism is implemented for this local runner. A fast child
can create a new session and reparent before polling observes its ancestry. The Gate A
command now fails closed at deterministic preflight, so neither installation nor live
execution should be authorized from this packet. Repair requires a versioned
containment implementation, synthetic escape regression, independent clean rereview,
and another full `make check`. Final environment and command identities also remain
pending because installation was correctly not performed.

Public release of raw web traces remains blocked by licensing/privacy review, but this
does not block private access-controlled smoke retention. Scientific interpretation,
the pilot, benchmarks, training, and all cloud mutation remain prohibited.

## Authorization block status: NOT READY TO USE

The following requested block is retained as a template, but it is intentionally
non-authorizable until the containment blocker above is repaired and this status is
regenerated as ready.

```text
DO NOT USE: authorization is blocked until kernel-enforced complete descendant
containment is implemented, tested, and independently rereviewed.

I authorize T07 Gate B for exactly PLAN-EXP0001-SMOKE at GIC Lab commit
[IMPLEMENTATION_COMMIT_PENDING], using OpenAI at https://api.openai.com/v1/ and
exactly gpt-4o-2024-11-20 with no alias or fallback.

I authorize the three exact source/dependency/Playwright installation actions in
docs/harness/T07_PREAUTHORIZATION_PACKET.md, followed by deterministic preflight and,
only if every identity and enforcement check passes, exactly one reactive condition
and one simulative condition in the locked order.

Aggregate caps: USD 4.00 API cost; 400,000 total model tokens (also independently
400,000 input, 400,000 cached-input, and 400,000 output); 240 seconds wall time;
77 model/API call attempts; 2 browser actions; 2 generic tool calls; and 209,715,200
output bytes.

Per-condition caps: USD 2.00; 200,000 total model tokens (also independently 200,000
input, 200,000 cached-input, and 200,000 output); 120 seconds; 1 browser action;
1 generic tool call; 104,857,600 output bytes; and at most 16 model/API attempts for
reactive or 61 for simulative.

The only secret variable name is SIRA_API_KEY. Do not print, persist, hash, or inspect
its value. Required cleanup is tracked environment close, kernel-enforced descendant
containment, supervised TERM, KILL after the bounded grace period if needed, verified
zero live descendants, and retained/hashed attempt evidence.

You may set paid_compute_allowed and prototype_execution_allowed true only for the
sealed PLAN-EXP0001-SMOKE family and materialize its exact parent/child authorization
records. Benchmark, training, cloud mutation, pilot execution, and scientific
interpretation remain false/prohibited. Stop after the one smoke pair and do not begin
analysis or the pilot.
```
