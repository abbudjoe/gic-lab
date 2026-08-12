# T07 bounded smoke execution plan

Status: **blocked historical V1 provenance; superseded; never execute**

V1 stopped before its first Lambda request and before writing a bounded private
binding. Preserve this document unchanged as design provenance below, but do not use
its plan or run identities. The active replacement is
`PLAN-T07-BOUNDED-SIRA-SMOKE-V2`; see
`T07_BOUNDED_SMOKE_V2_AUTHORIZATION_PACKET.md` and
`T07_BOUNDED_SMOKE_USER_RUNBOOK.md`. V2 also remains unauthorized.

## Immutable identity

| Field | Exact value |
|---|---|
| Parent/fork commit | `397a391b736528dd1049023d629100193e823c49` |
| Frozen milestone | annotated tag `t07-high-assurance-infrastructure-v1` |
| Branch | `phase-1/sira-smoke-bounded` |
| Reviewed implementation commit | `e3c68268ecb02375a7b3f78da0187ce1136f06c0` |
| Plan ID | `PLAN-T07-BOUNDED-SIRA-SMOKE-V1` |
| Host run | `RUN-T07-BOUNDED-HOST-0001` |
| Reactive run | `RUN-T07-BOUNDED-SIRA-REACTIVE-0001` |
| Simulative run | `RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001` |
| Plan path | `containers/sira-smoke/bounded/bounded-smoke-plan-v1.json` |
| Plan bytes / SHA-256 | 55,789 / `0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f` |
| Plan schema SHA-256 | `225c81bb21c5a361ec7c96adcd9eca29c0953b3874c657ed78cb2dc6bea0a71d` |
| Authorization schema SHA-256 | `8b542cd152818304761a1bc11027a1abfa7187cf49698929fb11fedbfed13b09` |
| Private-binding schema SHA-256 | `39e9f8ea7205e924fef25995b6c801196b35f85473e32ce58d18ed110a857b43` |
| Observer-ledger schema SHA-256 | `2d9ad9e1e43d7a229ee2ebfb44af82b5f7e6234300bd9a14d1072e0a53c4ad61` |
| Evidence schema SHA-256 | `3f1b710ca9256696a56936a8fcbb71f9eed7fc36392579ed50ca0767df30d22e` |
| State | `ready-for-bounded-smoke-authorization` |

The committed plan contains 34 exact implementation-artifact byte/hash bindings and
is unauthorized. `AUTH-T07-BOUNDED-SIRA-SMOKE-V1-PENDING` cannot execute anything.

## External authorization and private binding

A future authorization starts with the plan's shell-free `materialize` array. The
hash-first local bootstrap verifies the contract and supervisor module before import;
the supervisor then verifies the exact clean branch/commit, locked plan and artifact
hashes, repository permissions still false, planned zero-cost compute record, private
source/restoration hashes, and both local/external storage floors. It exclusively
creates:

- `artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0001/authorization.json`;
- `private-binding.json`;
- `observer-state.json`;
- `request-ledger.jsonl`; and
- `MATERIALIZATION_SUMMARY.json`.

The authorization and private binding are mode 0600. The authorization binds one
exact 3,600-second supervised window, plan/limits/private-binding hashes, pricing,
permissions, and all run IDs. The private file derives the exact selected provider
IDs, key fingerprint, IPv4 `/32`, unique ruleset name/rule, and restoration payload
without publishing their values. Any existing run root, mismatch, expiry, sequence
gap, or write/fsync failure stops.

The next exact local array, `prepare_bundle`, deterministically renders a USTAR archive
containing `BUNDLE_MANIFEST.json`, the plan, and the 34 plan-bound tracked artifacts
(36 members total), plus the reviewed bootstrap as a separate file. The combined
upload surface is capped at 8,388,608 bytes and stored only under
`artifacts/t07/bounded-upload/RUN-T07-BOUNDED-HOST-0001`. The post-launch
`release_bootstrap` array re-verifies this surface and binds its archive, manifest,
bootstrap, instance-observation, authorization, and private-binding hashes before the
user uploads anything.

## Lambda observer and user-only mutations

The observer is in-process HTTPS to `https://cloud.lambda.ai`, with no shell HTTP,
redirect, pagination request, or retry. It uses exactly 13 GETs in this order:

1. prelaunch: `/api/v1/instance-types`, `/api/v1/images`, `/api/v1/regions`,
   `/api/v1/ssh-keys`, `/api/v1/firewall-rulesets`,
   `/api/v1/firewall-rulesets/global`, `/api/v1/instances`;
2. security, after the user changes firewall/ruleset but before launch:
   `/api/v1/firewall-rulesets`, `/api/v1/firewall-rulesets/global`;
3. post-launch binding: `/api/v1/instances`;
4. termination, after the user terminates and before deleting security resources:
   `/api/v1/instances`;
5. final cleanup: `/api/v1/firewall-rulesets`,
   `/api/v1/firewall-rulesets/global`.

Every request has a durable intent and send-started ledger event. A response or closed
failure event is fsynced before advancing. An uncertain post-send outcome is never
replayed and converts the run to cleanup-only. Cleanup GETs may continue after expiry;
execution GETs cannot. Raw bodies are validated in memory and discarded. Retained
receipts contain only schema-declared fields after credential-key filtering; public
records contain only safe aliases, counts, and hashes.

Only the user may apply the private global rule, create the owned regional ruleset,
click launch once, open Jupyter, upload/download files, terminate the exact bound
instance, delete the owned ruleset, and restore the global baseline. The supervisor
implements no Lambda mutation.

The host selection is `gpu_1x_a10`, `us-east-1`, x86_64, Lambda Stack 22.04 alias
`img-0032`, family `lambda-stack-22-04`, version `22.4.5-2141`, no persistent
filesystem, key alias `fractal-lambda-codex`, and one exact owned ruleset. The
prelaunch observer requires capacity, the exact raw image/key identities and key
fingerprint, 129 cents/hour, zero nonterminal instances, and the sealed global
baseline. The security observer proves both temporary rules before launch. The
post-launch observer binds exactly one matching active instance and its immutable ID.

## Model and runtime identity

| Item | Exact binding |
|---|---|
| Provider/API base | OpenAI / `https://api.openai.com/v1/` |
| Model | `gpt-4o-2024-11-20` for all eight roles |
| Standard prices | USD 2.50/M input; USD 1.25/M cached input; USD 10.00/M output |
| SiRA commit/tree | `93fb8d72de71f9a4a13419670adeb34d93cf7acd` / `6a6d9068b94d7632d3533a3d6f013d4de6ff76e8` |
| `uv.lock` SHA-256 | `138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e` |
| Routing patch/runtime/document hashes | `4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed` / `c461dce20fea9e743135cad98b664213a393e46f35d1c1a8434212b2f0367dbb` / `8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619` |
| API service tier / pricing class | explicit request `default`; observed response must be `default` / standard |
| Platform | `linux/amd64`; Python 3.10 |
| Base image | `mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c` |
| amd64 manifest/config | `sha256:8f7d4d5ef52dbe4af81db537258ae6d15c71b86c6984dd6030dac8f34c86ebcd` / `sha256:801969079a1e0ae8c657adc45f7acac5abcc7fab846e60cd42c883ee78dded51` |
| Dependency/browser | uv 0.11.7; `uv sync --frozen --extra eval --python 3.10`; Playwright 1.39.0; Chromium revision 1084 / 119.0.6045.9 |

Current official Chat Completions documentation says an omitted tier means `auto`,
while the explicit API value `default` selects standard pricing and the response
reports the tier actually used. Every runtime request therefore sets
`service_tier="default"`; any missing or non-`default` response tier fails after the
attempt and cannot be accounted as a successful standard-price response.

The future bootstrap clones and checks the exact source/tree, stages only hash-bound
inputs, downloads the 24,933,975-byte uv wheel at SHA-256
`4e4d5e31bea86e1b6e0f5a0f95e14e80018e6f6c0129256d2915a4b3d793644d`,
pulls the image by digest, verifies its config, builds without cache or pull, and
resolves the result to one immutable image ID. It does not run `playwright install`.

Expected setup endpoints are `github.com:443`, `files.pythonhosted.org:443`,
`pypi.org:443`, `mcr.microsoft.com:443`, and registry-directed MCR blob storage.
Model metadata and workload requests use `api.openai.com:443`; the locked task has
site-dependent HTTPS egress. There is no image push.

## Exact caps

| Resource | Aggregate | Per condition / operation |
|---|---:|---:|
| OpenAI API cost | USD 4.00 | USD 2.00 |
| Model tokens | 400,000 | 200,000 |
| Model-call attempts | 77 | reactive 16; simulative 61 |
| Model metadata GET | 1 | before both conditions |
| Condition wall | 240 s | 120 s |
| Browser actions | 2 | 1 |
| Condition attempts / retries | 2 / 0 | 1 / 0 |
| Retained condition output | 209,715,200 B | 104,857,600 B |
| In-container attempt tmpfs | 134,217,728 B | 67,108,864 B |
| Remote evidence bundle | 268,435,456 B | 4,096 files maximum |
| Local/external sealed run archive | 301,989,888 B | at most 125 payload + 3 seal files; 600 s; complete expected 34 + 3 |
| Observer responses | 13,631,488 B | 1,048,576 B per GET |
| Observer ledger | 262,144 B / 96 events | 4,096 B per event |
| Provider wall/cost | 3,600 s / USD 2.00 | termination click by 3,300 s; projected USD 1.29 |
| Instance/click/filesystem | 1 / 1 / 0 | exact |
| Owned containers | 4 | browser, model, reactive, simulative |
| Docker/control calls | 128 | one shared work+cleanup meter; zero retry |
| Docker captured output | 33,554,432 B | aggregate across both runners |
| Setup transfer admission | 2,147,483,648 B | uv exact; Git/image wire metering residual |
| Runtime disk increment | 17,179,869,184 B | checked after build and every workload |
| Remote free-space preflight | 34,359,738,368 B | no persistent filesystem |

Condition containers use 2 CPUs, 4,294,967,296 bytes memory/no extra swap, 512 PIDs,
1,073,741,824 bytes shared memory, a 134,217,728-byte `/tmp`, local logs capped at one
8,388,608-byte file, five-second TERM grace, and restart `no`. Browser/model
preflights use smaller CPU/memory/PID limits. All four use a 67,108,864-byte attempt
tmpfs and immutable-ID copy-out before removal.

## Exact command and condition diff

The plan contains shell-free local materialize/observe/archive arrays and the one
remote bootstrap array. Their governing module hashes are:

- contract: `d6da182643b080e3e297716f1d65ce9c2e04d5157280c9f17aa33b82c840261c`;
- local supervisor: `9ee429b7f131079be7327186ba75013c7d5455b71802558261fbff98077e25e3`;
- local hash-first bootstrap: `0cd531ecd7584cb2d61caa3b0df8d6a60a82345c1f97fdddbd3c8aa6a16a9063`;
- remote bootstrap: `74aa58c2aacd2fc88423370c9d673fbda03faffe72f1e05de7fd4a1420d21e02`.

Container-create template hashes are browser
`fbceb0b9b055315a5664c81e60e0cd983f3ce721216ce4bc748f87c557f80aa6`,
model `4ba91c797522398b7b26fc80b06d89bbbb54481e8fc79c80e3c4c7cafb6d433a`,
reactive `a33ec29557883b9147fa491b78ee49d7468a99873563b3341971ea9727f8484b`,
and simulative `3befed62dca595636a9bd3629804663db16816822e5c2e7b4e0397f630ec08df`.

Reactive and simulative arrays differ only in container name, condition/run labels,
gate mode, source job name, and upstream mode. Task, model, seed, max step, timeout,
retry, runtime adapter, resources, network, secret mount, tmpfs, and security flags are
identical. Inner hashes are
`e2202f393a5958a4609286b21c07ba4feb1255e38d6a4dab78cf08d718f9533d`
and `0c02c8143f3c2ce14becb9ab6921363c6ccc19bd3106a31f618fd8851bea7db4`.

## Evidence, cleanup, and storage

Before release, each bounded workload container must be live and expose a nonempty
process snapshot through its immutable ID. Before removal, the container is inspected
and its tmpfs payload is copied to the fresh remote evidence root. Stop always has kill
escalation, terminal inspection, forced removal, removal proof, and zero labeled
container/network/volume residue. Success seals session JSON, source logs,
screenshots, stdout/stderr, accounting, exact commands, runtime/image/package/browser
identities, exact condition diff, normalized events, regulation decisions, compute-use
closeout, and cleanup. Failure seals every safe partial file plus a manifest and
records excluded secret/cap-exceeding counts without retaining values.

After manual download and local hash verification, the user terminates the bound
instance. The termination observer must prove it terminal or absent before the user
deletes the owned ruleset/restores the firewall. Final GETs prove ruleset absence and
baseline semantic hash
`b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764`.

The downloaded ZIP is structurally and cryptographically checked before the final
local archive is copied to
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/RUN-T07-BOUNDED-HOST-0001`
through held no-follow descriptors. It requires APFS UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, Thunderbolt/UTDM, writable/unlocked state,
Mac prewrite/retained floors 8,891,924,480/8,589,934,592 bytes, and external
prewrite/retained floors 200,350,182,605/200,048,192,717 bytes. Every destination is
read back and compared before atomic finalization; the source remains local. The
external set must include the exact local upload archive and bootstrap as
`upload-bundle/t07-bounded-repository.tar` and
`upload-bundle/t07-bounded-bootstrap.py`; a complete success is expected to contain
34 payload files plus three seal files, under the 125-payload/128-total cap.

After a run, `compute-use.json` preserves runtime wall/accelerator time, list-price
upper bound, observed API cost, and a null actual invoice. A separate repository
closeout must reconcile `CMP-0001` before interpretation or successor execution.

No repository code/configuration change is currently required before a live request.
Fresh user authorization and every dynamic identity, price, resource, secret,
freshness, storage, and termination-path check remain mandatory execution inputs.
