# SiRA upstream static audit

Assembly status: **successful**

## Control plane

- Work package: T01, pinned SiRA static audit.
- Authoritative task contract: build package
  `GIC_Lab_Phase_0_75_Build_Package_v1/prompts/01_SIRA_STATIC_AUDIT.md`.
- Upstream source contract: `sailing-lab/sira` at commit
  `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Mapped phase DoD: `P075-DOD-02`, `P075-DOD-04`, and `P075-DOD-07`.
- Target contract: produce a source-grounded, non-executing setup and command contract
  for paired SiRA reactive and simulative modes, with an explicit canonical trace-field
  map and no invented normalized fields.
- Success criterion: another engineer can reproduce the intended setup and command
  shape from the audit; every unknown remains explicit; relevant repository-local
  validation and independent spec-conformance review pass; and no model, browser,
  evaluator, API, benchmark, training, checkpoint, or cloud execution occurs.

## T01 definition-of-done ledger

| ID | Required outcome | Evidence | Status |
|---|---|---|---|
| T01-DOD-01 | The external clone's `HEAD` equals both the task pin and `SRC-SIRA-REPOSITORY.commit`. | Exact Git and manifest checks in the pin-verification section. | met |
| T01-DOD-02 | Python, package-manager, extras, browser, model/provider, API-key precedence, CLI, dataset, and released-data contracts are inventoried from pinned source. | Source-cited inventories below. | met |
| T01-DOD-03 | Evaluators, scoring assumptions, outputs, traces, screenshots, retry/seed/temperature/timeout/step limits, nondeterminism, and code/data/trace licenses are explicit. | Source-cited inventories and gap tables below. | met |
| T01-DOD-04 | The smallest source-supported paired smoke and exploratory pilot are identified without executing either. | Profile rationale below and paired profiles in `COMMAND_CONTRACT.yaml`. | met |
| T01-DOD-05 | Mac mini feasibility and material macOS/Linux differences are explicit. | Static platform assessment below. | met |
| T01-DOD-06 | Resolved reactive and simulative command templates differ only in approved identifiers and `--mode`. | Concrete argument arrays and pair contracts in `COMMAND_CONTRACT.yaml`. | met |
| T01-DOD-07 | Every available upstream trace field is mapped to canonical harness event types; unavailable canonical fields are marked unavailable, with no inferred critic score or GIC state. | `TRACE_FIELD_MAP.yaml` and schema-gap summary below. | met |
| T01-DOD-08 | All four required deliverables exist, including a proposed unmerged manifest fragment and an explicit T05 decision list. | This audit, two contract YAML files, and `PROPOSED_MANIFEST_FRAGMENT.yaml`. | met |
| T01-DOD-09 | Relevant local validation and independent spec-conformance review pass, followed by a post-review smoke. | Evidence log below. | met |
| T01-DOD-10 | Static-only and zero-spend constraints remain intact. | Evidence log, repository diff, project state, registry, and compute-manifest inspection. | met |

## Audit method and pin verification

The upstream repository was cloned to the ignored workspace `.tools/upstream/sira` and
checked out detached. No upstream dependency was installed and no upstream Python,
browser, evaluator, model, or visualization entry point was invoked. Source citations
below point to immutable GitHub blob URLs at the audited commit.

The following static checks all returned
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`:

```text
git -C .tools/upstream/sira rev-parse HEAD
git -C .tools/upstream/sira rev-parse 93fb8d72de71f9a4a13419670adeb34d93cf7acd^{commit}
read manifests/sources.yaml -> SRC-SIRA-REPOSITORY.commit
```

The clone was clean and detached (`## HEAD (no branch)`). The task pin, checked-out
commit, and existing manifest pin therefore agree.

## Runtime and installation contract

### Python, package manager, and dependencies

The project declares Python `>=3.10,<3.13`, recommends Python 3.10 through
`.python-version`, uses Hatchling for builds, and uses `uv` with prereleases allowed.
The checked-in `uv.lock` has SHA-256
`138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e`.
These facts come from
[`pyproject.toml` lines 1–55](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/pyproject.toml#L1-L55)
and [`.python-version`](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/.python-version).

Direct runtime requirements are:

- `browsergym-core==0.3.6.dev0`, `gymnasium`, `litellm`, `numpy`, `pandas`,
  `pillow`, `python-dotenv`, `pyyaml`, `tenacity`, and `termcolor`;
- `eval`: `ftfy`, `gradio>=5,<7`, `openai`, `rouge-score`, `scipy`, and `tqdm`;
- `viz`: `gradio>=5,<7`;
- `webarena`: `browsergym-webarena==0.3.6.dev0`; and
- `dev`: `pytest` and `ruff`.

The published installation recipe is `uv sync --extra eval` followed by
`uv run playwright install chromium`; WebArena additionally calls for its upstream
environment, the `webarena` extra, and site URL variables
([README lines 57–91](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/README.md#L57-L91)).
Those commands are future setup templates only and were not run in T01.

There is a blocking evaluator dependency gap: the FanOut normalizer imports `spacy`
and loads `en_core_web_sm`, but neither spaCy nor that model is declared by any extra
([`norm.py` lines 9–27](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/evaluation/fanout/utils/norm.py#L9-L27)).
The agent can be prepared from the lock, but the documented FanOut scoring environment
cannot be reproduced from the declared `eval` extra alone. T05/T07 must not improvise
an unpinned install; T05 must first record the additional package/model revisions and
licenses, and T04 should make the gap machine-visible.

### Browser dependencies

`browsergym-core` pulls Playwright, and the lock resolves Playwright 1.39.0 with both
macOS arm64 and Linux wheels. Chromium is a separate Playwright browser download, not
contained in the Python environment. The open-ended runner creates a headless Chromium
session at 1280×720, starts from `about:blank`, and uses a 5,000 ms BrowserGym/Playwright
environment timeout
([`run_web_agent.py` lines 115–129](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/scripts/run_web_agent.py#L115-L129)).
WebArena requires the extra, an externally prepared set of sites, seven site URL
variables, and site resets between conditions
([`run_inference.sh` lines 5–31](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/evaluation/webarena/run_inference.sh#L5-L31)).

## Models, providers, and secret resolution

The CLI accepts five literal model names and three checked-in module-routing configs:

| Name/config | Provider endpoint | Module routing |
|---|---|---|
| `gpt-4o`, `o1`, `o3-mini` | `https://api.openai.com/v1/` | One model for all modules when passed literally. |
| `deepseek-chat`, `deepseek-reasoner` | `https://api.deepseek.com` | One model for all modules when passed literally. |
| `model_o1_config.json` | OpenAI | `gpt-4o` default; `o1` policy. |
| `model_o3-mini_config.json` | OpenAI | `gpt-4o` default; `o3-mini` policy. |
| `model_r1_config.json` | DeepSeek | `deepseek-chat` default; `deepseek-reasoner` policy. |

The literal allowlist, endpoints, and config-file resolver are in
[`run_web_agent.py` lines 22–66](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/scripts/run_web_agent.py#L22-L66).
An arbitrary immutable provider model identifier is rejected unless upstream code is
changed. All five accepted names are aliases whose immutable serving revision is not
recorded by the runner. `gpt-4o` is the documented and CLI default, but it is not a
fully pinned model identity.

The provider key precedence is exactly:

1. `--api_key`;
2. `SIRA_API_KEY`;
3. `OPENAI_API_KEY`.

The runner loads repository `.env` without overriding already exported variables and
then applies that precedence
([`run_web_agent.py` lines 223–229](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/scripts/run_web_agent.py#L223-L229)).
The same resolved key is sent to either OpenAI or DeepSeek. The command contract omits
`--api_key` so secrets do not appear in an argument array or process listing; a later
authorized harness must inject `SIRA_API_KEY` by name and never log its value.

## CLI and mode contract

The sole reactive/simulative entry point is `scripts/run_web_agent.py`. It requires a
positional `job_name`, requires at least one usable task source (`--query` or
`--dataset`), supports datasets `fanout`, `flightqa`, and `webarena`, and exposes
`--mode reactive|simulative`. Other relevant flags are `--agent`, `--config_name`,
`--model`, `--api_key`, `--max_steps`, `--timeout`, `--max_retry`, `--data_root`,
`--output_dir`, `--start_idx`, `--end_idx`, `--shuffle`, and `--seed`
([`run_web_agent.py` lines 201–234](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/scripts/run_web_agent.py#L201-L234)).
If both `--query` and `--dataset` are supplied, the query branch runs and the dataset
is ignored; the CLI does not enforce mutual exclusion. The command contract therefore
supplies exactly one task source even though upstream does not enforce that invariant.

Default mode resolution is source-defined and must not be overridden in the matched
pair:

| Dataset | Reactive config | Simulative config |
|---|---|---|
| open-ended, FanOutQA, FlightQA | `web_reactive` | `web_simulative` |
| WebArena | `webarena_reactive` | `webarena_simulative` |

Reactive mode uses the policy directly. Simulative mode changes the planner to the
world-model path, samples 20 policy outputs, and clusters them to at most five actions.
When clustering yields multiple actions, it predicts one-step futures and requests 20
critic samples per evaluated future at search depth one. When clustering yields only
one action, DFS returns that action immediately without calling the world model or
critic
([`configs.py` lines 22–31](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/agent/configs.py#L22-L31),
[`planner.py` lines 41–59](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/agent/modules/planner.py#L41-L59), and
[`dfs.py` lines 105–130](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/search/dfs.py#L105-L130)).
Thus the **CLI pair** differs only in the approved job identifier and `--mode`, while
the mode intentionally resolves to different planner modules, sampling parameters,
and model-call multiplicity. Those mode-induced differences are part of the treatment,
not accidental configuration drift, and must be predeclared as such in T05.

The repository also releases an OpenHands baseline through `--agent openhands`, but it
is neither member of this requested reactive/simulative pair.

## Datasets and released data

| Task source | Released/local contract | Static identity and caveats |
|---|---|---|
| Open-ended query | Any `--query` string; starts at `about:blank`. | No ground truth or source evaluator. Live web. |
| FanOutQA | `data/fanout-final-dev.json`; 310 rows; fields `id`, `question`, `decomposition`, `answer`, `categories`. | SHA-256 `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`; 1,177,174 bytes. Questions are passed to the runner, but upstream IDs are not preserved in run traces. |
| FlightQA | `data/flightqa_counterfactual.csv`; 120 data rows; columns `num_constraints`, `constraints`, `question`, `seed_id`. | SHA-256 `2550a58636abeddad8ac25b3b5e79048b2e732aa150a7e3b5557454b17aa303b`; 32,618 bytes. Relative-date and live-flight content makes results time-dependent. |
| WebArena | No WebArena task data is released here; environment IDs are registered by `browsergym-webarena`. | Requires external sites and environment setup; tasks are sorted numerically unless shuffled. |

FanOut and Flight slices use Python's end-exclusive `[start_idx:end_idx]`. `--seed`
affects only optional dataset-order shuffling; it is not forwarded to the model,
BrowserGym, or websites
([`datasets.py` lines 8–69](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/web/utils/datasets.py#L8-L69)).
The proposed dataset records, hashes, and explicit unknown licenses are isolated in
`PROPOSED_MANIFEST_FRAGMENT.yaml`; they are not merged into `manifests/datasets.yaml`.

## Evaluators and scoring assumptions

### FanOutQA

The evaluator extracts only a final `send_msg_to_user(...)` response, classifies
several fixed error strings, and otherwise calls a run “Max Steps Reached.” Loose
accuracy is the mean fraction of normalized reference strings found as word-bounded
substrings in the answer; strict accuracy is the fraction of questions for which every
reference string is found. It also macro-averages ROUGE-1, ROUGE-2, and ROUGE-L
precision/recall/F-score over the requested slice, assigning zero to unanswered items
([`evaluator.py` lines 68–175](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/evaluation/fanout/evaluator.py#L68-L175)).
Normalization lowercases, repairs encoding, normalizes comma-formatted numbers,
lemmatizes with `en_core_web_sm`, removes only `[,.?!:;]`, and normalizes whitespace.
The missing spaCy/model declaration currently blocks reproducible scoring.

### FlightQA

Flight scoring is itself an OpenAI `gpt-4o` model call. It asks whether the final
answer is grounded in captured accessibility-tree observations and relevant to the
constraints, then sets `correct = grounded AND relevant`
([`evaluator.py` lines 37–139](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/evaluation/flight/evaluator.py#L37-L139)).
It uses a separate key precedence—gitignored `default_api_key.txt` if present, otherwise
`OPENAI_API_KEY`—with five parse attempts, no explicit evaluator temperature, no
immutable model revision, and unsafe Python `eval` to decode the final action string.
It is therefore cost-bearing, model-nondeterministic, and not the smallest pilot
evaluator.

### WebArena

For WebArena, the environment reward list is retained, and `test_result` is
`float(max(rewards) > 0)`. The success-rate helper averages that binary value. The
comparison helper sorts by numeric environment ID, requires matching ID multisets, and
runs a paired sample t-test
([`get_ttest.py` lines 18–50](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/evaluation/webarena/get_ttest.py#L18-L50)).
This is not suitable for the smallest local pilot because it requires external
WebArena infrastructure and resets.

## Outputs, traces, and screenshots

The main session artifact is
`<output_dir>/<job_name>_YYYY-MM-DD-HH-MM-SS.json`. It contains `goal`,
`instance_id`, `history`, `is_complete`, and `error`; WebArena adds `rewards` and
`test_result`. Each history item is a three-element JSON array containing the raw
serializable BrowserGym observation, the requested action string, and a `step_info`
mapping containing source-supported fields such as processed observation/state/plan/
action/memory update
([`run_web_agent.py` lines 140–198](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/scripts/run_web_agent.py#L140-L198)).

Other artifacts are:

- `src/sira/web/logs/<timestamp-with-microseconds>.log`: per-episode text log. It
  includes observation, state, plan, action, memory update, aggregate cost, and—in
  simulative mode—unstructured candidate, predicted-state, and aggregate critic text.
- `<cwd>/logs/sira_YYYY-MM-DD.log`: global utility log created by module import.
- `<output_dir>/output.jsonl`: WebArena-only append of `instance_id`, `goal`, and
  `test_result`.
- `evaluation/fanout/results/*.csv` and `evaluation/flight/results/*.json`: evaluator
  outputs created only by separate evaluator entry points. Their filenames contain
  only job name and slice, so reusing those identifiers overwrites earlier evidence.
- With `DEBUG>0`, `<output_dir>/<job-name-tail>/<epoch-seconds>.log`: raw per-call
  prompt/message text. Because filenames have only one-second precision and are opened
  with mode `w`, multiple calls in one second can overwrite earlier prompt evidence.

The viewport screenshot is converted to base64 JPEG at quality 10 and embedded at
`history[*][0].screenshot`; there are no standalone screenshot files
([`browser.py` lines 21–49](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/web/utils/browser.py#L21-L49)).
The visualizer decodes that field and reads URL, cleaned observation, state, plan, and
action from the session JSON. Screenshots, accessibility trees, pages, prompts, and
answers may contain personal or third-party content and must be retained under an
explicit sensitivity and publication policy.

Material trace weaknesses are explicit:

- timestamps are local-time filenames, not UTC fields; step timestamps are absent;
- same-job completions in the same second can overwrite the session JSON;
- session JSON records the requested action before `env.step`, but no structured
  execution result/reward for ordinary web/FanOut/Flight tasks;
- the next observation's `last_action` and `last_action_error` are the only available
  indirect action-result evidence;
- model response identity, call count, token count, and latency are not in JSON;
- candidate sets, simulated futures, and critic values are not structured in JSON;
  their text-log snippets lack stable candidate/prediction IDs and complete per-sample
  associations; and
- debug prompt logs can overwrite and may contain sensitive page content.
- the runner never calls `env.close()` and has no `finally` cleanup or browser-child
  verification, so an upstream command finishing is not evidence that Chromium and
  child processes were cleaned up; and
- evaluator result paths overwrite when the same job/slice identity is reused, while
  aggregate evaluator values printed to stdout are not contained in the result file.

`TRACE_FIELD_MAP.yaml` consequently maps direct JSON fields only when source support is
unambiguous, preserves all raw fields, and marks canonical `candidate_action`,
`predicted_future`, and `critic_evaluation` unavailable for reliable normalization.
The selected `plan` is not expanded into a candidate set; a language `state` is not
relabeled as calibrated GIC state; and text-log reward is not invented into a critic
score.

## Retry, randomness, timeout, and step limits

| Control | Source behavior | Contract consequence |
|---|---|---|
| Dataset retry | `--max_retry=0`; catches only LiteLLM `BadRequestError`; applies only to dataset runs. | Keep zero for smoke/pilot. Open-ended query ignores this flag. |
| Parser retry | Up to four model calls per parsed module output; no effective wait despite unused wait parameters. | Intrinsic and not controllable from CLI; attempts are incompletely observable. |
| Transport retry | Tenacity makes up to five attempts for rate limit, connection, or service-unavailable errors with random exponential 3–60 s backoff. | Intrinsic provider retry; harness wall/cost limits must wrap it. |
| Action clustering | Up to five immediate clustering attempts; an empty cluster mapping is retried by an unbounded outer loop. | Source has no hard global model-call/cost ceiling. Harness needs a wall/cost kill boundary. |
| Seed | Default 42, used only when `--shuffle` is present. | Does not seed provider sampling, clustering, browser, or live web. |
| Base temperature/top-p | 0 / 0.5 for models supporting these parameters; omitted for `o1` and `o3-mini`. | Provider behavior can still vary. |
| Simulative policy/critic | 1.0 / 0.95, with 20 samples each. | Mode deliberately adds sampling nondeterminism and many more completions. |
| API timeout | `None` by default. | `--timeout` does not bound model calls; harness requires a total wall limit. |
| Browser action timeout | CLI default 30 seconds via `signal.SIGALRM`. | Unix-specific mechanism available on macOS/Linux main threads; not a model timeout. |
| BrowserGym timeout | 5,000 ms for the open-ended environment constructor. | Separate from the action alarm. |
| Runner step limit | CLI default 30. | Set explicitly in every command. |
| Internal observation limit | Fixed config value 30, not replaced by CLI `--max_steps`. | Values above 30 do not provide more than 30 normal planning steps. |
| Repeated action | Sixth identical consecutive non-scroll action is replaced by a terminal error message. | Can terminate before the runner limit. |
| Consecutive action errors | Fourth consecutive observed action error triggers a terminal error message. | Error stop is source-defined. |

The retry and model-parameter sources are
[`agent/llm.py` lines 30–208](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/agent/llm.py#L30-L208),
[`web/utils/config.py` lines 20–72](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/web/utils/config.py#L20-L72), and
[`planner_utils.py` lines 59–193](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/agent/modules/planner_utils.py#L59-L193).

## Live-web and provider nondeterminism

Both intended profiles depend on mutable live websites. FanOut ground truth pins
answers/evidence, but agent observations are current web content. Flight results depend
on current date, availability, price, localization, and site behavior. WebArena is more
controlled but still depends on external site revisions and reset correctness. The web
agent injects the local current date/time into every non-WebArena identity prompt
([`identity.py` lines 34–56](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/src/sira/agent/variables/identity.py#L34-L56)).

Provider aliases, opaque backend revisions, concurrency, parser and transport retries,
and simulative temperature 1 sampling remain uncontrolled. The dataset seed does not
repair any of these. A later exploratory comparison must run pairs close together,
counterbalance condition order, retain timestamps/raw pages, and label the evidence
preliminary. No confirmatory causal conclusion is supportable from this live setup
without a stronger environment/version contract.

## Smallest paired smoke and exploratory pilot

### Paired smoke

The smallest source-supported smoke is the README's literal open-ended task
`go to google flights`, run once in each mode with `--max_steps 1`. One step exercises
mode resolution, headless browser construction, a real model path, action generation,
session JSON, and screenshot capture while minimizing exposure. Upstream does not close
the environment or verify child-process cleanup, so the future harness must supervise
the process group, terminate remaining browser children, and record cleanup
verification; the command alone cannot validate cleanup. The smoke is not an outcome
test and sets `interpretation_allowed: false`. The exact future command arrays are in
`COMMAND_CONTRACT.yaml`; they were not executed in T01.

### Exploratory pilot

The mathematical minimum that can produce a paired variance estimate is two tasks.
The smallest source-supported pilot is therefore FanOutQA indices 0 and 1, each run in
both modes (four runs), scored over its matching one-row slice:

1. `7dcbbbdc7f1120cd` — “What is the batting hand of each of the first five picks in
   the 1998 MLB draft?”
2. `2120afba8009bad3` — “What were box office values of the Star Wars films in the
   prequel and sequel trilogies?”

This is only sufficient to test paired execution, scoring, and variance plumbing—not
to estimate a stable scientific effect. The tasks must be run as one-task commands so
condition order can be counterbalanced: reactive→simulative for index 0 and
simulative→reactive for index 1. The reproducible scoring dependency gap must be closed
before authorization. T05 may select a larger exploratory sample, but it must not call
the two-task minimum confirmatory or adequately powered.

## Mac mini feasibility and Linux differences

The inspected host is a Mac mini-class Apple M4 arm64 machine with 16 GiB RAM, running
macOS 26.5.1. Static lock inspection found macOS arm64 wheels for Playwright 1.39.0 and
the relevant compiled dependencies; the workload uses remote API models and a local
headless browser rather than local model weights. The paired open-ended smoke and small
FanOut pilot are therefore **source-compatible in principle** with this Mac after the
pinned environment and platform Chromium are installed. This is not a runtime result:
T01 intentionally performed no install or execution.

Material platform boundaries are:

- Playwright downloads a platform-specific Chromium build; a browser installed on
  Linux cannot be copied as the Mac browser artifact or vice versa.
- `signal.SIGALRM` is available on macOS and Linux but requires the main process/thread;
  it is not portable to Windows.
- The simulative search uses a thread pool, not CUDA or Linux-only multiprocessing.
- Open-ended, FanOut, and Flight paths have no source-declared Linux-only dependency.
- WebArena is materially different: the checked-in helper assumes externally hosted
  sites and reset operations. The repository does not prove a turnkey macOS WebArena
  backend; treat WebArena hosting as a separate Linux/container deployment contract,
  even if the Mac connects to remote sites.
- Browser rendering, fonts, locale, timezone, and site personalization can differ
  between macOS arm64 and Linux runners and are not fingerprinted by upstream traces.

## License audit

The repository metadata and code declare Apache-2.0
([`CITATION.cff` lines 1–16](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/CITATION.cff#L1-L16)).
`NOTICE` says code was adapted from LLM Reasoners under Apache-2.0 and directs users to
third-party projects for BrowserGym, WebArena, and FanOutQA license/citation terms
([`NOTICE` lines 1–12](https://github.com/sailing-lab/sira/blob/93fb8d72de71f9a4a13419670adeb34d93cf7acd/NOTICE#L1-L12)).

No file in the pinned artifact assigns a specific license to
`fanout-final-dev.json` or `flightqa_counterfactual.csv`. Their license is therefore
`null`/unknown in the proposed manifest, regardless of the repository's code license.
Web content, embedded screenshots/accessibility trees, model outputs, and derived
trajectories combine third-party and generated material; no upstream file grants a
single derived-trace license. Public redistribution and retention of raw traces must
remain blocked pending task/site terms, dataset licenses, privacy review, and a project
license decision. This audit does not select a license.

## Command-contract summary

`COMMAND_CONTRACT.yaml` records commands as shell-free argument arrays. Within each
task pair, a deterministic pair check permits exactly two differences:

- the positional `job_name` identifier; and
- the value after `--mode` (`reactive` versus `simulative`).

All other values—including query/dataset slice, model alias, agent, step limit,
timeouts, retry policy, data root, output root, and seed—are byte-identical. The
contract does not include a key value and does not authorize execution. It also records
the source-resolved internal mode differences so they cannot be mistaken for drift.

## Canonical trace-map summary

`TRACE_FIELD_MAP.yaml` covers the session JSON, WebArena JSONL, per-episode and global
text logs, debug prompt logs, runner/evaluator stdout and stderr, and evaluator result
files. Every structured field or emitted text label has a canonical or explicit
raw-only disposition. Direct source evidence is mapped into the package's canonical
event vocabulary only when it is reliable. The following canonical types are
unavailable from reliable structured upstream evidence and must be emitted only by the
future harness itself or remain unavailable:

- harness lifecycle: `run_started`, `preflight_completed`, `command_started`,
  `command_completed`, `budget_update`, `artifact_recorded`, `run_stopped`;
- structured SiRA internals: `candidate_action`, `predicted_future`, and
  `critic_evaluation`; and
- all cloud lifecycle events.

The adapter may directly map `observation`, `belief_state` (named `state` upstream,
without a calibration claim), `plan`, `executed_action`, error/outcome fields, and
WebArena metrics. It must preserve the complete raw record, use harness-generated UTC
timestamps and IDs only with `derived` provenance, and never synthesize GIC state,
critic scores, predictions, execution results, token counts, or model revision.

## T05 decision list

| ID | Decision T05 must lock | Audit recommendation / current state |
|---|---|---|
| T05-SIRA-01 | Smoke task and cap | Use the one-step README query pair; interpretation disabled. Requires later explicit API/browser authorization. |
| T05-SIRA-02 | Pilot task count | Two fixed FanOut tasks are the variance-plumbing minimum; choose and prerecord any larger exploratory sample before evidence. |
| T05-SIRA-03 | Pilot order | Run one task reactive→simulative and the other simulative→reactive; pair closely in time. |
| T05-SIRA-04 | Model identity | `gpt-4o` is source-supported but mutable. Resolve an immutable provider revision or explicitly accept alias drift as a protocol limitation; upstream CLI cannot accept arbitrary names unchanged. |
| T05-SIRA-05 | Secret injection | Use `SIRA_API_KEY` from an isolated secret channel; forbid `--api_key` and secret values in logs. |
| T05-SIRA-06 | Mode-induced differences | Predeclare planner path, 20 policy samples, ≤5 clustered actions, temperature/top-p changes, and the conditional branch: multiple clusters invoke one-step world-model/critic evaluation with 20 critic samples per evaluated future, while one cluster bypasses both. |
| T05-SIRA-07 | Cost/token/wall guard | Upstream has no complete cost, token, call, or model-timeout cap and has a potentially unbounded clustering loop. Require harness-enforced total limits and stop evidence. |
| T05-SIRA-08 | Retry policy | Keep outer `--max_retry 0`; separately record intrinsic parser and transport retries. Do not select only successful retries without preserving attempts. |
| T05-SIRA-09 | Seed claim | Record seed 42 for dataset ordering only; do not label model/browser execution deterministic or seeded. |
| T05-SIRA-10 | FanOut evaluator environment | Pin spaCy and `en_core_web_sm` versions/hashes/licenses before scoring; block evaluation until the gap is resolved. |
| T05-SIRA-11 | Evaluator | Prefer deterministic FanOut string/ROUGE scoring over API-scored FlightQA for the first pilot, after closing the dependency gap. |
| T05-SIRA-12 | Dataset and trace licenses | Keep both data licenses and any public derived-trace license unresolved; do not publish raw traces until terms/privacy review completes. |
| T05-SIRA-13 | Trace retention | Preserve session JSON, text logs, stdout/stderr, evaluator output, hashes, and environment identity; classify screenshots/prompts as potentially sensitive. |
| T05-SIRA-14 | Adapter gaps | Emit no canonical candidate, predicted-future, critic-evaluation, action-result, token, or model-revision value from the current structured trace. Preserve text logs raw. |
| T05-SIRA-15 | Timestamp and collision repair | Use unique harness run/attempt directories and immutable evaluator job/slice identities, capture evaluator stdout immediately, hash results before any later attempt, and use UTC events; never rely on upstream filenames as identity. |
| T05-SIRA-16 | Browser/runtime fingerprint | Pin Python/lock/BrowserGym/Playwright/Chromium revisions plus OS/arch/locale/timezone; use platform-specific browser artifacts. |
| T05-SIRA-17 | Authorization boundary | Keep every run plan unauthorized. Installing Chromium, calling an API, or running either profile requires a later explicit human authorization. |
| T05-SIRA-18 | Cleanup contract | Treat upstream cleanup as absent. Require supervised process-group termination, browser-child enumeration/termination, timeout escalation, and recorded zero-live-child verification for every attempt. |

## Evidence log

- Preflight confirmed that Phase 0.75 forbids model, API, benchmark, training,
  checkpoint, browser, cloud, and paid-compute execution. No scout or other execution
  run is applicable to this static-audit item.
- `git -C .tools/upstream/sira rev-parse HEAD` — exact pin matched.
- `shasum -a 256` on the lock and two released data files — hashes recorded above and
  in the proposed manifest fragment.
- Static file, line, dependency-lock, data-shape, and host-platform inspection only;
  no upstream entry point or evaluator was imported or executed.
- Initial YAML smoke: `uv run --no-sync python ...` — did not reach document checks
  because `--no-sync` created an empty local GIC Lab environment with no PyYAML. This
  was an environment setup failure, not an audit-contract failure; no upstream package
  was installed.
- Recovery setup: `make setup` — passed; installed only this repository's frozen GIC
  Lab validation environment. The ignored upstream SiRA environment remained absent.
- YAML parse smoke — passed for all three YAML files.
- Proposed manifest check against `schemas/manifest.schema.json` — passed.
- Deterministic paired-argv check — passed for the smoke and both pilot task pairs;
  each pair differed only at argv index 5 (`job_name`) and index 9 (`--mode` value).
- `git diff --check` — passed.
- Pre-review repository contract check: `make validate` — passed.
- First independent spec-conformance review — **review-failed** with four valid
  findings: incomplete/incorrect auxiliary trace dispositions, an unsupported cleanup
  claim, an overstated unconditional world-model/critic path, and unrecorded evaluator
  overwrite behavior. No static-only, secret, compute, or command-parity violation was
  found. All four findings were accepted for repair.
- Review fixes made the CLI task-source precedence and Flight key-file wording exact,
  corrected the screenshot to a viewport artifact, made single-cluster simulative
  bypass explicit, added cleanup and evaluator-overwrite contracts, and gave every
  structured/auxiliary artifact a canonical or raw-only disposition.
- Review-fix document contract smoke — **passed**: all YAML parsed; the proposed
  manifest remained schema-valid; runtime pairs differed only at argv indices 5 and 9;
  evaluator pairs differed only at job-name index 5; trace artifacts and source-field
  inventories were one-to-one; every artifact declared a default disposition; the
  canonical event set exactly matched the package schema; and critic/candidate/future
  fields remained unavailable. `make validate` and `git diff --check` also passed.
- Independent spec-conformance rereview — **clean**; no actionable finding remained.
  T01-DOD-01 through T01-DOD-08 and T01-DOD-10 were independently classified `met`;
  T01-DOD-09 awaited only this ledger's post-review gate and closeout.
- Post-review document and zero-execution contract smoke — **passed**: repeated all
  document, schema, pair-parity, artifact-disposition, canonical-event, and unavailable-
  field assertions; reconfirmed the exact upstream/manifest/task pin; reconfirmed every
  execution permission false, empty experiment and compute entries, and USD 0 cost;
  and found no upstream `.venv`, `node_modules`, `browsing_data`, or `outputs` path.
  `make validate` and `git diff --check` passed again.
- Scout/evidence execution — **not applicable by T01 source contract**. This work item
  is a static audit and explicitly forbids installing or running the upstream agent,
  browser, model, API, evaluator, benchmark, or any paid/cloud resource.

## T01 outcome

T01 is successful. The exact SiRA pin now has a reproducible static setup and command
contract, a source-complete trace and schema-gap map, content-hashed proposed dataset
records with unknown licenses preserved as null, and explicit T05 decisions. The
matched command arrays differ only in job identity and `--mode`; simulative single-
cluster bypass, missing cleanup, evaluator overwrite, provider alias drift, missing
FanOut dependencies, live-web variance, and unavailable canonical fields are explicit
rather than inferred away. No upstream execution occurred and all project execution
permissions and compute accounting remain at zero.

T01 must stop here. T04 may consume this reviewed audit only after T03 is also
successful; T05 remains blocked until T01 through T04 are complete, and any later SiRA
installation or execution still requires the authorization defined by project policy.
