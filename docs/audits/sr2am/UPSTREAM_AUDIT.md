# SR²AM pinned-upstream static audit

Assembly status: **successful**

Audit date: 2026-08-07

## Source and target contracts

The authoritative work-item contract is T02, “Static audit of the pinned SR²AM
artifact and Lambda topology.” The source artifact is
`sailing-lab/sr2am@6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0`; the target is an
exact, budget-aware execution topology for `SR2AM-v0.1-8B` that does not install
or execute the upstream environment, download checkpoint shards, call services,
or mutate cloud state.

In scope: pinned-source inspection, public metadata inspection, compatibility
analysis, command design, trace mapping, time and storage estimates, and local
repository validation. Out of scope: model/API/benchmark execution, dependency
installation, checkpoint download, SandboxFusion startup, search or judge calls,
and any Lambda mutation.

## Executive conclusion

The first Lambda candidate should be **one H100 PCIe 80 GB x86_64 instance at
TP=1, DP=1, and request concurrency 1**. It is the least expensive current
one-GPU x86 H100 shape in the required matrix, has ample static memory headroom,
and avoids unproven ARM components. One H100 SXM is the first fallback; one A100
40 GB is a lower-cost but tighter-memory fallback. The currently listed A100
80 GB shape exposes eight GPUs and is not budget-minimal. GH200 has ample memory
but remains ineligible for the first smoke because five exact pins with x86
paths lack compatible CPython-3.13 ARM wheels and the unpinned SandboxFusion
image has no verified ARM manifest. The
full matrix is in [`LAMBDA_COMPATIBILITY.yaml`](LAMBDA_COMPATIBILITY.yaml).

The current upstream Python snapshot is **not an executable lock**. It has 349
requirements, three lower bounds rather than exact versions, no hashes or
platform markers, several source-only packages, and nine direct dependency
contradictions under CPython 3.13/Linux/x86_64 markers. They comprise one
`ortools`→`protobuf` conflict, seven `vllm` conflicts (`anthropic`,
`compressed-tensors`, `lark`, `llguidance`, `torch`, `torchaudio`, and
`torchvision`), and one `xformers`→`torch` conflict. Installing with `--no-deps`
suppresses resolution but does not establish compatibility. T11 must produce a
hash-locked, source-parity serving environment and pass import-only dry-run
gates before any checkpoint or paid run.

There are two distinct smoke contracts:

1. The smallest source-supported model-and-scorer smoke uses
   `--agent_type instruct` and one `lighteval/MATH` row with a deterministic
   scorer. It needs
   only SGLang and validates load, generation, JSONL output, and local scoring.
2. A full-topology `think`-path smoke must provision search, Jina page fetch, an
   OpenAI-compatible summarizer, a local visit-tokenizer dependency, and
   SandboxFusion even for a math-only row, because tool construction occurs
   before question processing and all tools are exposed to the model. A math
   row may still make no tool call, so it does not by itself prove tool-call and
   tool-result integration.

The first is an operational checkpoint smoke, not validation of SR²AM's
configurator/planner or agentic services. T11 must make that coverage decision
explicit instead of silently calling the service-free path a full artifact
smoke.

## Evidence method and identity

Evidence is classified as follows:

- **Pinned source observation:** file/line behavior at the exact Git commit.
- **Published metadata observation:** immutable Hugging Face revision metadata
  and versioned PyPI metadata; checkpoint payloads and wheels were not fetched.
- **Current provider observation:** official Lambda shapes, images, storage, and
  prices retrieved on 2026-08-07; these must be refreshed later.
- **Derived planning value:** arithmetic memory/time/cost estimates, always
  labeled unmeasured.
- **Unknown:** any fact that would require installation, import, model serving,
  a workload/model/search/judge/sandbox API call, a checkpoint payload, or cloud
  execution. Read-only public package/model/provider metadata queries remain in
  the published/current-metadata classes above.

The canonical project manifest pins
`SRC-SR2AM-REPOSITORY` to
`6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0`. The public remote's `main` ref and
the ignored detached clone both resolved to that value. The inspected Git tree
is `edc8a52edc78c8995fd415dc8f662407d631e010`, the upstream worktree was clean,
and no upstream file was edited. The commit is also available at the
[immutable GitHub tree](https://github.com/sailing-lab/sr2am/tree/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0).

## Frozen environment and platform audit

The upstream installation guide asks `uv` to create Python 3.13 and then run
`uv pip install --no-deps -r requirements.txt`; it describes the file as a
frozen environment snapshot
([README lines 52–72](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/README.md#L52-L72)).
There is no `pyproject.toml`, lockfile, container digest, wheel index pin, or
requirements hash in the source tree.

| Surface | Pinned inventory | Static finding |
|---|---|---|
| Python | 3.13 in README; runner comments say 3.10+ | Lambda Stack images currently default to 3.12 or 3.10, so T11 must provision and identify Python 3.13 rather than inherit an implicit system interpreter. |
| Requirements | 349 lines; 346 `==` pins; three `>=` bounds; SHA-256 `ee384e51ec2df84ea42be35acf2f937f96f63da6e1a0640ef8fcb0662a12b18c` | Not a complete reproducibility lock; lower bounds can drift and no artifact hashes are supplied. |
| Serving | `sglang==0.5.7`, `sglang-router==0.2.3`, `sgl-kernel==0.3.20`, `flashinfer-python/cubin==0.5.3`, `vllm==0.13.0` | The local path launches SGLang, not vLLM. Keeping incompatible unused packages in a one-shot environment expands failure risk. |
| Tensor stack | `torch==2.9.1`, `torchvision==0.24.1`, `torchaudio==2.9.1`, `triton==3.5.1`, `xformers==0.0.31`, `torch_memory_saver==0.0.9` | Direct metadata conflicts exist; ARM lacks published wheels for the last two packages. |
| CUDA stack | CUDA 12.8 runtime/cuDNN/NCCL packages, CuPy CUDA 12.x, `cuda-python==13.1.1`, `cuda-bindings==13.1.1` | The provider image's actual driver/runtime pair must be captured. Package version `13.1.1` is not itself proof of a CUDA 13 runtime requirement. |
| Native/source builds | Of 346 exact pins, a standard CPython-3.13/Ubuntu-22.04 target-tag screen found compatible paths for 330 on x86_64 and 325 on arm64; 16 and 21 exact pins respectively lacked a compatible wheel, and three lower-bounded requirements remain unresolved | This is metadata evidence only. Packages such as `pycrypto==2.6.1`, `pycosat==0.6.6`, and `peewee==3.18.1` would use source distributions in this screen and remain unproven. |
| Package manager | `uv` recommended; pip alternate; `--no-deps` proposed for conflicts | Bypassing dependency checks is not a compatibility gate. T11 needs an explicit minimal-serving dependency decision and import tests. |

The relevant pins appear in
[`requirements.txt`](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/requirements.txt).
The architecture screen queried versioned PyPI JSON only and installed nothing.
It intersected parsed wheel tags with `packaging`'s CPython 3.13 compatible tags
for Linux manylinux platforms through Ubuntu 22.04's glibc 2.35 and checked each
artifact's `Requires-Python`. Full rejected lists and the algorithm are recorded
in `LAMBDA_COMPATIBILITY.yaml` so the counts are independently auditable.
Core packages (`torch`, `triton`, `vllm`, `sgl-kernel`, `sglang-router`, and
CuPy) publish ARM artifacts at these versions, but complete-environment support
cannot be inferred from a subset. Conversely, x86 is not proven until its
source-only packages and the dependency contradictions are resolved.

Lambda currently lists `lambda-stack-24-04` and `lambda-stack-22-04` for both
x86-64 and arm64, while the minimal GPU Base and Ubuntu Server images are listed
only for x86-64
([official image table](https://docs.lambda.ai/public-cloud/on-demand/)).
That makes an x86 minimal image viable in principle and reinforces that an ARM
choice must be explicit rather than price-driven.

## Model identity, files, and static memory basis

The project manifest pins `MODEL-SR2AM-V0.1-8B` to Hugging Face revision
`5d72255092ac2ec006c2f9813029220aff79865e`. The revision metadata reports a
16,398,028,091-byte repository, including 16,381,516,768 bytes of BF16 weights
across four shards. No shard was downloaded.

| Shard | Published bytes | Published LFS SHA-256 |
|---|---:|---|
| `model-00000-of-00004.safetensors` | 5,271,206,888 | `b1829e88dbf081d819130da3a1034517679e5e50cd3ef9a2fc923f98544018e4` |
| `model-00001-of-00004.safetensors` | 5,335,160,768 | `15ecb71276d5ba58b90e2b26826850b62abfda647baf5a7644fdd8e883ef9152` |
| `model-00002-of-00004.safetensors` | 4,529,856,352 | `48232d76110351f95bf13750dbc450804431e690938c1a1ab101d57e40e3ed5d` |
| `model-00003-of-00004.safetensors` | 1,245,292,760 | `6c0a9fe8ea76cf0215d8910130979b00a88104dc111b8edeb3ad9c95aa86118f` |

The metadata and small config were read from the
[immutable model revision](https://huggingface.co/sailing-lab/SR2AM-v0.1-8B/tree/5d72255092ac2ec006c2f9813029220aff79865e).
The config declares `Qwen3ForCausalLM`, 36 layers, 8 KV heads, head dimension
128, BF16, and 40,960 maximum positions. The source README rounds the context to
32K in its model table but says approximately 16 GB VRAM
([README lines 37–44 and 96–107](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/README.md#L37-L44));
both the model config and 8B runner use 40,960, so the command contract retains
40,960 rather than silently lowering it.

Weight files alone occupy approximately 15.256 GiB. One fully occupied 40,960
token BF16 KV cache is approximately 5.625 GiB from the declared architecture,
for 20.881 GiB before runtime overhead. The README's approximately 16 GB claim
cannot be a conservative full-context serving budget. One 40 GB device is the
static minimum candidate; an 80 GB H100 is the preferred first-smoke device.

## Runtime and service inventory

| Component | Source implementation | Configuration | Output or side effect |
|---|---|---|---|
| Model server | `python -m sglang.launch_server` | Model path/name, context 40,960, TP/DP, Qwen tool parser, `0.0.0.0:8000` | Plain server log at `logs/sglang_server.log`; OpenAI-compatible API and `/health`. |
| Agent | `run_agent.py` | `think`, `configurator`, or `instruct`; timeouts, concurrency, turns, filtering | JSONL result rows plus W&B telemetry unless disabled. |
| Search | `WebSailorMiroflowMultiWebSearchToolFast` | SerpAPI default or Serper.dev; key read at construction | Tool message text and metrics containing query and result length. |
| Browser fetch | `WebSailorMultiVisitToolFast` | Jina Reader; optional Jina key | Page text is truncated and sent to the summarizer; only summarized tool output is retained in the trajectory. |
| Browser summarizer | Same visit tool | OpenAI-compatible endpoint; recommended Qwen instruct example; 28,000 page tokens and 32,768 context | Summary/evidence text and result length; no provider usage/request ID in trajectory. The source hard-codes the endpoint API key as `EMPTY`. |
| Visit tokenizer | Same visit-tool constructor | Qwen names call `AutoTokenizer.from_pretrained(summarize_model)` without a revision; other names use the local `gpt-4o` tiktoken encoding | May perform an implicit Hugging Face fetch/cache load before any question. The released CLI cannot independently pin the remote summarizer ID and local tokenizer artifact. |
| Code sandbox | `SandboxFusionCodeTool` | One or more hosts on port 8080; 60-second defaults | Code, stdout/result or error, and a fixed tool reward. |
| Final scorer | `default_compute_score` dispatcher | Selected by input `source` or `general_domain` | `judge_result`, numeric score, and boolean `correct`. The selected `lighteval/MATH` path is local; other branches use either self-hosted OpenAI-compatible judges or the public OpenAI API. |
| Aggregate evaluator | `evaluation/compute_rep_results.py` | JSONL, `k`, repetitions | Pass rate/pass@k printed to stdout; no output artifact unless the harness captures it. |
| Reasoning-token analysis | `avg_tokens_before_think_close.py` | Raw JSONL, local pinned tokenizer, extraction mode | Derived totals/averages printed to stdout. |

The README describes all three tools as required during inference and lists the
OpenAI key for evaluation
([README lines 76–94](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/README.md#L76-L94)).
The concrete service boundaries and the service-free exception are detailed in
[`SERVICE_TOPOLOGY.md`](SERVICE_TOPOLOGY.md).

For a Qwen/Qwen3 summarizer, visit-tool construction calls
`AutoTokenizer.from_pretrained(self.summarize_model)` without `revision=` or a
separate tokenizer path
([`tools/websailor_tools_fast.py` lines 290–311](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/tools/websailor_tools_fast.py#L290-L311)).
A remote summarizer endpoint is therefore insufficient: T11 must either approve
a source patch that separates and pins the tokenizer artifact or prove a
hash-verified offline cache contract and prevent unexpected network fallback.

### Sandbox provenance and safety gap

The sandbox setup script defaults to
`docker://varad0309/code_sandbox:server_unsecure`, with no digest, and uses
Enroot to create a writable container before installing packages one at a time
through the unauthenticated code-execution API
([`scripts/sandbox/setup_sandbox.sh` lines 15–29 and 120–206](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/scripts/sandbox/setup_sandbox.sh#L15-L29)).
Its `sandbox-requirements.txt` contains 256 unversioned names (SHA-256
`d04d29c7b5201b8b1ae227cb4659aa8bf223c46720705397afbe70c18c30fb23`).
The loop continues after individual install failures and reports them without
failing setup. Neither image identity, package environment, setup duration, nor
ARM support is established. T11 must not expose this service publicly, must pin
an approved digest and package lock or record a blocked substitution, must fail
on any required package error, and must not treat the name “SandboxFusion” as
proof of isolation.

## Single-machine runner findings

### GPU count and VRAM

The wrapper comment says 4–8 GPUs, its default is eight, and its README example
uses eight replicas. The actual 8B branch sets TP=1 and DP=`NUM_GPUS` without a
minimum check; only the 30B branch enforces four GPUs
([`scripts/run_inference_local.sh` lines 8–31 and 155–172](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/scripts/run_inference_local.sh#L8-L31)).
Therefore one GPU is the source-path minimum for 8B and eight is a throughput
choice. The conservative static memory floor is one 40 GB GPU, not the README's
approximately 16 GB figure.

### Defaults and concurrency

The local 8B wrapper resolves to TP=1, DP=number of GPUs, context 40,960,
temperature 0.8, 50 turns, 16,384 completion tokens per turn, 64 concurrent
questions, an outer attempt budget of one (no retry after the first attempt),
filtering on, tag removal on, and early-break disabled
([`scripts/run_inference_local.sh` lines 13–31 and 258–292](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/scripts/run_inference_local.sh#L13-L31)).
Direct `run_agent.py` defaults differ: configurator agent, eight concurrent
questions, an outer attempt budget of three (at most two retries after the first
attempt), 30 turns, 8,192 completion tokens, and 64-way
search/visit/code concurrency
([`run_agent.py` lines 432–487](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/run_agent.py#L432-L487)).
Both question processors interpret `num_retries` as a total attempt ceiling:
the filtering path loops over `remaining_retries`, and the base path loops over
`range(num_retries)`
([filtering processor](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/run_agent.py#L284-L323),
[base processor](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/agent_base.py#L291-L300)).
T11 must record the resolved child arguments, not merely the wrapper invocation.

Concurrency is not a request-count ceiling. Search `query` and visit `url` are
arrays with no `maxItems`; one assistant response may contain multiple tool
calls; search `num` is an unbounded JSON number with a source default of 10;
and the full source-parity path permits 50 model turns. For each URL, the
visit path can make up to four Jina requests. Its initial summary call, four
short-output retries, and three JSON-parse retries each invoke a helper that can
make up to ten logical summarizer SDK calls: 80 logical calls per URL. Pinned
`openai==2.6.1` adds up to two retries per logical call, making a static maximum
of 240 summarizer HTTP attempts per URL; likewise 50 logical model turns can
become 150 model HTTP attempts. Outer timeouts may interrupt these maxima
earlier. T11 must enforce hard per-run counters and stop conditions for logical
model and summarizer calls, SDK retry/wire attempts, tool calls, search queries,
requested search results, visited URLs, Jina requests, sandbox calls, model and
summarizer input/output tokens, and external API spend; setting each semaphore
to one controls simultaneity only. T11 must validate search `num` as an integer
from 1 through the proposed per-query maximum 10 and, before dispatch, add
`query_count × num` to a separate cumulative `search_results_requested` budget.
A per-query maximum alone does not bound unbounded query arrays or repeated tool
calls.

The `think` loop retains every assistant and tool message without pruning or
compaction and sends the whole message array plus every tool schema. Its nominal
50 turns times 16,384 requested output tokens is 819,200 tokens before prompts
or tool results, so it cannot fit the 40,960-token server context. T11 must use
the exact server-accounted input or reproduce the pinned server's full rendered
prompt: chat template and control tokens, every outbound message, and the full
tool-schema serialization. The `instruct` count similarly includes the rendered
user-only request, not merely the question string. For every request, reserve
the requested output allowance and stop before either the context window or a
run-level input/output-token budget would be exceeded
([think request](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/run_agent.py#L235-L249),
[instruct request](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/run_agent.py#L266-L275)).
Truncation, compaction, a smaller completion cap, or fewer turns is a versioned
protocol deviation rather than an implicit recovery.

The visit summarizer's own `prompt_length` estimate encodes only
`msgs[0]["content"]` and adds one; it does not establish the endpoint's rendered
chat-template/control-token count
([visit call](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/tools/websailor_tools_fast.py#L335-L360)).
T11 must obtain server-accounted summarizer input tokens or reproduce the exact
pinned summarizer rendering. If neither is available, the pre-request context
and token-budget gate is blocked.

The `instruct` class hard-codes 4,096 completion tokens and forwards neither the
parsed temperature nor the system prompt; it sends only user messages
([`run_agent.py` lines 266–277](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/run_agent.py#L266-L277)).
Consequently `--fix_datetime`, temperature, and the CLI completion cap do not
control service-free generation semantics. The system prompt is nevertheless
retained in the returned raw `messages`, so `--fix_datetime` stabilizes the
printed and JSONL trace even though it is not outbound model input. This limits
that path to operational smoke evidence.

The pinned model's
[`generation_config.json`](https://huggingface.co/sailing-lab/SR2AM-v0.1-8B/blob/5d72255092ac2ec006c2f9813029220aff79865e/generation_config.json)
declares `do_sample=true`, temperature 0.6, top-k 20, and top-p 0.95. Pinned
`sglang==0.5.7` resolves to tag commit
`232982a0dee4f0f9545189a7d9b6b9bb802e4910`; its server default is
`sampling_defaults="model"`, explicitly inheriting the model generation config
when available
([server definition](https://github.com/sgl-project/sglang/blob/232982a0dee4f0f9545189a7d9b6b9bb802e4910/python/sglang/srt/server_args.py#L375),
[CLI help](https://github.com/sgl-project/sglang/blob/232982a0dee4f0f9545189a7d9b6b9bb802e4910/python/sglang/srt/server_args.py#L3155)).
Its loader whitelists temperature, top-k, top-p, repetition penalty, and min-p,
not `do_sample`
([model-config loader](https://github.com/sgl-project/sglang/blob/232982a0dee4f0f9545189a7d9b6b9bb802e4910/python/sglang/srt/configs/model_config.py#L898-L922)).
Thus the instruct request effectively inherits temperature 0.6, top-k 20, and
top-p 0.95; it forwards no seed and remains stochastic. The full `think` profile
overrides temperature to 0.8, inherits top-k 20/top-p 0.95, and also forwards
no seed. Its `SR2AM-v0.1-8B` name matches none of `get_model_config`'s substring
keys, including `Qwen3-8B`, so it adds no model-specific `extra_body`. T11 must
either accept and record these behaviors or approve an explicit request/source
control. One pinned-server candidate is SGLang's
`--enable-deterministic-inference`, which enables batch-invariant operations and
uses seed 42 when no request supplies one
([server flag](https://github.com/sgl-project/sglang/blob/232982a0dee4f0f9545189a7d9b6b9bb802e4910/python/sglang/srt/server_args.py#L4169),
[seed fallback](https://github.com/sgl-project/sglang/blob/232982a0dee4f0f9545189a7d9b6b9bb802e4910/python/sglang/srt/sampling/sampling_batch_info.py#L90-L104)).
That option changes backend behavior and may affect performance, so the static
source-parity command leaves it off and T11 must validate and record the choice.
The deterministic property in the current smoke therefore belongs to the
selected scorer, not the generation.

### Startup/readiness/cleanup

The wrapper sources `.env`, starts SGLang, polls `/health` every ten seconds for
up to 600 seconds, runs the agent, and traps exit to signal the recorded parent
and direct children
([`scripts/run_inference_local.sh` lines 188–256](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/scripts/run_inference_local.sh#L188-L256)).
Its `curl -s` omits `--fail`, so any HTTP response status can be a false-positive
readiness result. It also does not readiness-check auxiliary services, reserve
their resources, create a real process group, prove descendants exited, sync
artifacts, or terminate a cloud instance. T11 must require an explicit 2xx
health response, a live owned PID, and a bounded `/v1/models` identity check.
Tool `release` also occurs only after a successful agent loop, not in `finally`
([`agent_base.py` lines 97–202](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/agent_base.py#L97-L202)).
The T11 harness must own those contracts.

Auxiliary ownership must be explicit rather than inferred from an endpoint.
Search and Jina are pre-existing external SaaS and are readiness/call-only. The
browsing summarizer and SandboxFusion must each be declared either pre-existing
and externally owned (probe but do not mutate lifecycle) or harness-launched
with an owned PID/process group or provider resource ID, cleanup authority,
bounded stop/termination, and terminal/non-billable proof. No separately
launched auxiliary process or resource may outlive the attempt or remain
billable.

The wrapper parses its summarizer and sandbox flags before sourcing `.env`, so
same-named `.env` variables overwrite CLI choices despite `.env.example` saying
the values may be overridden per run. It also exports the entire `.env` into
the SGLang child, giving the model server search, Jina, judge, or telemetry
credentials that it does not need. T11 must use direct argument arrays, record
resolved child arguments, and construct a separate allowlisted environment for
each process; ambient secrets must not be inherited.

## Input, scoring, and smallest smoke

The smallest source-supported input is one JSONL object containing `question`,
`general_domain`, and a ground truth in `reward_model` or `answer`
([README lines 111–137](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/README.md#L111-L137)).
The exact proposed row is in
[`COMMAND_CONTRACT.yaml`](COMMAND_CONTRACT.yaml): a `1 + 1` question requiring a
boxed answer, `general_domain: lighteval/MATH`, and ground truth `2`.

That domain dispatches to the local last-boxed-answer equivalence scorer rather
than an LLM judge
([`evaluation/reward_score/__init__.py` lines 208–226](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/evaluation/reward_score/__init__.py#L208-L226),
[`evaluation/reward_score/math.py` lines 17–28](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/evaluation/reward_score/math.py#L17-L28)).
By contrast, the source's named `math__aime24`, `math__aime25`, and
`math__math500` branches explicitly use an external LLM judge, so they are not
the minimum no-API scoring path.

Those nonselected evaluator paths are not one uniform “external judge.” The
math, STEM, and web judge modules can target self-hosted OpenAI-compatible
services through `MATH_LLM_JUDGE_URL`/`MATH_LLM_JUDGE_MODEL`,
`STEM_LLM_JUDGE_URL`/`STEM_LLM_JUDGE_MODEL`, or
`WEB_LLM_JUDGE_URL`/`WEB_LLM_JUDGE_MODEL`; those clients pass the literal API
key `EMPTY`. Other dispatcher branches use `OPENAI_API_KEY` and hard-coded
models: the math/STEM GPT branches use `gpt-4.1-mini-2025-04-14`, web branches
include `gpt-4.1-2025-04-14` and `o4-mini-2025-04-16`, and the HLE evaluator
uses `o4-mini`
([math judge](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/evaluation/reward_score/math_llm_judge/__init__.py#L422-L444),
[STEM judge](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/evaluation/reward_score/stem_llm_judge/__init__.py#L38-L57),
[web judge](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/evaluation/reward_score/web_llm_judge.py#L42-L50),
[HLE judge](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/evaluation/reward_score/hle.py#L1-L41)).
All are prohibited in the two proposed smoke profiles unless T11 supplies a
separate endpoint/model revision, credential scope, retry, token, cost, and
readiness contract for the exact selected dispatcher branch.

Smoke acceptance is operational: server ready; every required preflight, agent,
and aggregate command exits 0; aggregate stdout is non-empty; one non-error row
is preserved; the answer is a non-empty string; typed score/correct fields have
no evaluator error; artifacts are synced and hashed; and provider termination
is later confirmed. A valid-looking row flushed before a nonzero agent exit is
failure evidence, not success. Before the model call, the harness must run
known-positive (`\boxed{2}` vs `2`) and
known-negative (`\boxed{3}` vs `2`) answers through the exact async
`judge_answer` dispatch and observe no-error score dictionaries of 1.0 and 0.0
with empty captured stdout/stderr. This is necessary because the source scorer
swallows internal exceptions as 0.0 and the dispatcher can return
`{"score": 0.0, "error": ...}`. `correct: false`
after those gates does not make an infrastructure smoke fail and is not a
negative scientific result.

## Output, trace, and token-accounting audit

Filtering-mode success rows contain `dataset`, `question`, full `messages`,
`answer`, `correct`, `judge_result`, generation wall time, `rep_idx`, and a
timezone-free timestamp. Error rows always contain a `messages` key, but its
value is null unless partial-message capture is enabled and available; they also
contain the dataset/question, error text, retry index, and the naive timestamp
([`run_agent.py` lines 284–395](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/run_agent.py#L284-L395)).
Tool messages preserve result text, a reward, metrics, and call ID
([`agent_base.py` lines 158–180](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/agent_base.py#L158-L180)).

Material evidence gaps are:

- the ordinary `think`/`configurator` chat path drops `response.usage`, so the
  released local path has no complete prompt/completion token accounting;
- post-hoc reasoning counts require the pinned tokenizer and extraction choices
  and are not total model usage;
- model revision, environment identity, UTC timestamps, GPU time, API cost,
  provider request IDs, and artifact hashes are absent;
- typed belief, predicted future, critic evaluation, and selected plan fields do
  not exist; reasoning/configurator tags remain raw text only;
- each writer creates its own `asyncio.Lock`, so concurrent appends do not share
  a mutual-exclusion primitive;
- an existing output causes a derived filename, which is then opened in write
  mode and can itself be overwritten
  ([`agent_base.py` lines 405–458](https://github.com/sailing-lab/sr2am/blob/6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0/agent_base.py#L405-L458)).

The field-level normalization contract and explicit unavailable fields are in
[`TRACE_FIELD_MAP.yaml`](TRACE_FIELD_MAP.yaml). Raw upstream JSONL remains the
authority; normalized events cannot invent GIC state.

## Time, cost, and storage result

For the service-free smoke, cold-cache planning ranges are separated as
follows: validated environment
setup 15–45 minutes, 16.398 GB checkpoint download and published-hash
verification 7–27 minutes, SGLang readiness 2–10 minutes, one service-free model
request plus local score 0.5–6 minutes, and a ≤100 MiB artifact bundle hash/sync
1–5 minutes. The 25.5–93 minute sum is unmeasured. At the current USD 3.29/hour
one-H100-PCIe list rate it corresponds to roughly USD 1.40–5.10 before tax and
persistent storage; two hours would cost USD 6.58 before those additions. These
numbers are planning bounds, not authorization or promised runtime. The
full-topology profile has no defensible setup total yet: its implicit tokenizer
fetch/cache and unpinned 256-package sandbox bootstrap are separate unbounded
gaps and are not included in the 25.5–93 minute sum.

The checkpoint, validated environment cache, and raw artifacts belong on an
attached Lambda filesystem keyed by immutable revisions. Root/local SSD may
hold a staged checkpoint, active venv, source clone, server caches, and temporary
logs, but never the only raw evidence copy. Before provider termination, the
run must flush, hash, copy, and verify retained artifacts on the filesystem and
an approved external destination. Lambda states that local non-filesystem data
is destroyed on instance termination
([official import/export guidance](https://docs.lambda.ai/public-cloud/importing-exporting-data/));
filesystems persist and continue billing
([official filesystem guidance](https://docs.lambda.ai/public-cloud/filesystems/)).
Every local or attached filesystem receiving writes must also maintain the
repository's inviolable free-space floor: at least 150 GB or 20% of capacity,
whichever is greater ([`docs/STORAGE_POLICY.md`](../../STORAGE_POLICY.md)). T11
may choose a stricter threshold. Preflight must account for declared worst-case
writes, and runtime monitoring must stop before the next write or download would
cross the floor.
The full ownership table and formulas are in
[`SERVICE_TOPOLOGY.md`](SERVICE_TOPOLOGY.md).

## Decisions required before T11 can close

1. **Smoke coverage:** approve the service-free model/scorer smoke, the
   full-topology `think` path, or the recommended two-gate sequence on one
   bounded instance. Decide whether observed tool integration is required; if
   it is, acceptance needs at least one assistant tool call joined to its tool
   result. Do not describe mere service readiness as tool-use evidence.
2. **Environment repair:** choose and review a minimal SGLang serving lock/image
   versus an exact full-snapshot build. Record any omitted unused dependency as
   a source-parity decision; resolve all direct metadata conflicts and source
   builds with hashes and import-only tests.
3. **Instance choice set:** retain 1× H100 PCIe x86_64 as preferred, name allowed
   fallbacks, and keep GH200 excluded unless every ARM blocker is closed.
4. **Provider identifiers:** pin current Lambda instance type ID, region choice
   set, image ID, architecture, driver/CUDA versions, SSH key name, and current
   price using read-only metadata.
5. **Context and limits:** confirm 40,960 context, TP=1/DP=1, concurrency 1, one
   row, one total outer attempt (no outer retry), relevant model/tool timeouts,
   and hard maxima for model/tool
   calls, query and URL array lengths, results per query, provider attempts,
   model/summarizer input and output tokens, and API spend; any reduced context
   is an explicit deviation. Define input tokens from the exact server-accounted
   or pinned rendered request, including chat-template/control-token overhead and
   tool schemas. Decide whether the stochastic pinned model defaults are
   accepted, whether SGLang's deterministic-inference mode is validated and
   enabled, or whether another explicit sampling/seed source change is required
   for reproducibility.
6. **Tool services:** if the full-topology gate is included, select SerpAPI
   versus Serper.dev, pin a summarizer model/revision and endpoint, decide Jina
   key use, and approve either a source patch for an independently pinned visit
   tokenizer or a verified offline-cache contract. Record network,
   price/privacy/license, readiness, and artifact-cache decisions separately
   from GPU cost. Launch each process with an explicit environment allowlist;
   never export the full `.env` into SGLang or unrelated services. Assign every
   endpoint a lifecycle mode and owner; for any harness-launched summarizer,
   preserve its PID/resource ID and require terminal/non-billable cleanup proof.
7. **Sandbox boundary:** approve or reject the upstream `server_unsecure` image;
   confirm CPU/RAM reservation, network isolation, digest, a fully versioned and
   hashed replacement for the 256-name sandbox requirements file, fail-closed
   installation, setup-time budget, and cleanup ownership. It must not be
   reachable from the public internet. If harness-launched, preserve the
   PID/resource ID and require bounded termination plus terminal/non-billable
   proof; if pre-existing and external, probe but do not mutate it.
8. **Evaluator contract:** approve the one-row `lighteval/MATH` deterministic
   scorer, its pre-model positive/negative self-test, non-empty answer, and
   no-error result gates. Any released benchmark/LLM-judge path needs a separate
   decision for the exact dispatcher branch, endpoint type, model and revision,
   credential scope, retry/token limits, cost, and readiness.
9. **Token/accounting repair:** decide how the harness will enforce and count
   model calls, tokens, tool calls, per-tool items and internal attempts,
   latency, GPU seconds, and service spend despite missing default response
   usage. Post-hoc reasoning tokens alone are insufficient.
10. **Storage:** name the Lambda filesystem and region, decide whether creation
    or attachment will later be authorized, pin checkpoint/cache paths, select
    the external artifact destination, and set retention/deletion ownership.
11. **Budget and termination:** set maximum wall time, maximum spend, hard UTC
    deadline, memory danger thresholds, artifact-sync stop behavior, and
    explicit provider-termination authority for the Lambda instance and every
    harness-launched auxiliary resource. No separately launched resource may
    remain billable. The disk threshold cannot be lower
    than the fixed repository floor of max(150 GB, 20% free); T11 may make it
    stricter. Refresh pricing at preflight and launch.
12. **Artifact acceptance:** define the exact required bundle: raw JSONL,
    stdout/stderr, SGLang log, resolved argument arrays, source/model/environment
    identities, service identities, resource samples, checksums, aggregate
    output, command exit statuses, and termination proof. Require exit status 0
    from every required preflight process, the agent, and the aggregate command;
    output created before a nonzero exit does not satisfy acceptance.

Until those decisions are encoded and dry-run validated, no Lambda launch is
eligible. T02 itself changes no shared manifest; the schema-shaped proposal is
[`PROPOSED_MANIFEST_FRAGMENT.yaml`](PROPOSED_MANIFEST_FRAGMENT.yaml).

## T02 definition-of-done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T02-DOD-01 | Repository compute, storage, reproducibility, security, and plan controls are read before work; all static-only constraints remain intact. | Policy citations, repository diff, and zero-use compute records. | met |
| T02-DOD-02 | The inspected upstream HEAD exactly matches the source-manifest pin. | Detached clone HEAD, manifest entry, tree identity, and clean upstream status. | met |
| T02-DOD-03 | The frozen environment, platform assumptions, model server, search, browser summarizer, sandbox, evaluators, and output formats are inventoried with unknowns explicit. | `UPSTREAM_AUDIT.md` and pinned-source citations. | met |
| T02-DOD-04 | The single-machine runner's GPU/VRAM floor, service boundaries, startup/readiness/cleanup, defaults, concurrency, context, traces, and token accounting are exact. | `SERVICE_TOPOLOGY.md`, `COMMAND_CONTRACT.yaml`, and `TRACE_FIELD_MAP.yaml`. | met |
| T02-DOD-05 | Lambda H100 PCIe, H100 SXM, GH200, and applicable A100 shapes have an architecture-first compatibility decision basis. | `LAMBDA_COMPATIBILITY.yaml` plus official provider/package metadata. | met |
| T02-DOD-06 | Setup, checkpoint transfer, model readiness, one-task inference/scoring, and artifact transfer are estimated separately and labeled as unmeasured planning estimates. | Assumptions, formulas, bounds, and current price snapshot. | met |
| T02-DOD-07 | Durable and ephemeral storage ownership is explicit and preserves raw evidence before instance termination. | Storage contract in `SERVICE_TOPOLOGY.md`. | met |
| T02-DOD-08 | The smallest source-supported input and deterministic scoring path are defined without overstating agentic coverage. | One-row fixture contract and command profile. | met |
| T02-DOD-09 | All required audit files, a proposed manifest fragment, and the decisions needed before T11 exist without editing shared state. | Six files under `docs/audits/sr2am/` and a scoped Git diff. | met |
| T02-DOD-10 | Relevant local gates and independent spec-conformance review pass, followed by a clean post-review gate. | Exact commands and review record in this document. | met |

## Progress and evidence log

- 2026-08-07: Read repository doctrine, the authoritative Phase 0.75 plan,
  compute/reproducibility/storage/security policies, T02, the downstream T11
  contract, and the Lambda runbook contract.
- 2026-08-07: Created the package-prescribed branch
  `phase-0.75/sr2am-audit` and confined ownership to `docs/audits/sr2am/`.
- 2026-08-07: Cloned the public source with LFS smudging disabled under ignored
  `.tools/upstreams/sr2am`, checked out the exact manifest commit detached, and
  observed a clean upstream worktree. No tracked upstream file exceeds 10 MB;
  the source checkout including Git metadata occupies approximately 2.3 MB.
- 2026-08-07: Verified upstream `HEAD` as
  `6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0` and its tree as
  `edc8a52edc78c8995fd415dc8f662407d631e010`.
- 2026-08-07: Queried only public source/package/model/provider metadata. The
  CPython-3.13 wheel screen covered all 346 exact pins (330 x86_64-compatible,
  325 arm64-compatible), and the direct-dependency screen reproduced nine
  contradictions. No wheel, checkpoint shard, or file over 1 GB was fetched.
- 2026-08-07: Authored exactly the six required T02 files. Four YAML documents
  passed safe loading, the proposed model fragment passed the repository's
  Draft 2020-12 manifest schema, all 79 upstream Python files passed static AST
  parsing, all six upstream shell scripts passed `bash -n`, local Markdown
  targets resolved, whitespace checks passed, and `make validate` passed.
- 2026-08-07: A plain `make check` reached the notebook-render step and failed
  only because `quarto` was absent from that shell's `PATH`. Re-running with
  `QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  passed the full lock, format, lint, type, 32-test, repository-validation,
  site-data, 14-page render, and site-validation gate.
- 2026-08-07: Independent assembly spec-conformance review reproduced the
  source identity, wheel counts, and all nine dependency contradictions. Review
  findings were repaired at their contract surfaces, focused gates were rerun,
  and the fresh rereview verdict was **clean**, with T02-DOD-01 through
  T02-DOD-09 met and only parent post-review closeout pending.
- 2026-08-07: The parent post-review
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  passed with 32 tests and a 14-page notebook render. Repository scope remained
  exactly the six audit artifacts; no shared manifest, registry, navigation, or
  upstream source file changed.
- 2026-08-07: No scout or execution evidence run was applicable: T02's static
  contract forbids model/checkpoint/service/sandbox/cloud execution. No paid
  compute, model inference, search/judge call, SandboxFusion process, checkpoint
  payload, or cloud mutation occurred.

## Blockers and next permitted work

No blocker applies to the completed static audit. Model, API, benchmark,
checkpoint, sandbox, and cloud operations remain unauthorized. T06 may later
integrate the proposed model fragment into shared manifest state under its own
contract. T11 remains gated on the twelve recorded decisions, a versioned
compute record, explicit current-turn launch authority, and every command,
service, storage, budget, evidence, and cleanup preflight defined here.
