# T07 bounded smoke execution plan

Status: **executable design; unauthorized; no external execution performed**

## Immutable identity

| Field | Exact value |
|---|---|
| Parent/fork commit | `397a391b736528dd1049023d629100193e823c49` |
| Frozen milestone | annotated tag `t07-high-assurance-infrastructure-v1` |
| Branch | `phase-1/sira-smoke-bounded` |
| Reviewed implementation commit | `4c15b8aaf61a260dbdc0063538a2d8500ac95a45` |
| Plan ID | `PLAN-T07-BOUNDED-SIRA-SMOKE-V1` |
| Host run | `RUN-T07-BOUNDED-HOST-0001` |
| Reactive run | `RUN-T07-BOUNDED-SIRA-REACTIVE-0001` |
| Simulative run | `RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001` |
| Plan path | `containers/sira-smoke/bounded/bounded-smoke-plan-v1.json` |
| Plan bytes / SHA-256 | 48,677 / `f469d25e3527a5f0bc678a52d458ec29dcb3d27342f045ed54f1ff0c18e813d3` |
| Plan schema SHA-256 | `be96e9e729f2930780d80c343eba68b70c23a9fb61ef0c0b6dc47c3e5903450e` |
| Authorization schema SHA-256 | `4821844cf2e7ba540ce1b5fea97ca7d61f926b8a22b2d11260858b5741434879` |
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
| Routing patch/runtime/document hashes | `4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed` / `894783a47c19efc5e141a90a4dd63920b9440e1ef231aad5b2738b1f524bbbcd` / `8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619` |
| Platform | `linux/amd64`; Python 3.10 |
| Base image | `mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c` |
| amd64 manifest/config | `sha256:8f7d4d5ef52dbe4af81db537258ae6d15c71b86c6984dd6030dac8f34c86ebcd` / `sha256:801969079a1e0ae8c657adc45f7acac5abcc7fab846e60cd42c883ee78dded51` |
| Dependency/browser | uv 0.11.7; `uv sync --frozen --extra eval --python 3.10`; Playwright 1.39.0; Chromium revision 1084 / 119.0.6045.9 |

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
| Local/external sealed run archive | 301,989,888 B | 125 payload + 3 seal files; 600 s |
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

- contract: `bed93df0df4f9ece7a90ca713385bf6f2ea0e37b2fa618236bc563d612660d82`;
- local supervisor: `ab206d00bbd8e7ba8fe69e1c08de350184bab5c821ecaa526efeb2ba23e69951`;
- local hash-first bootstrap: `bab1a3f59dccc8becbe372d2a2c7d92643164cefc86ed6659d8dceba0ba82f6c`;
- remote bootstrap: `9a90c8285350f64e27b7652d3e45c0c04c6530210b26f67afc095f3145f81dc7`.

Container-create template hashes are browser
`af86b7d3b9407f7e5f04c253d49fe7a94f5af77543b17c159a3482becb067b88`,
model `eb5a7c049fe1472e42c9ffd7804d3267b1ad635658a9e5cbf38d375af7e548ca`,
reactive `ab30886c8c4c60ae80163495fd07f93e952f21be3dc385553de298c569815582`,
and simulative `180ec0f4e81882553690fab85d6689dc8f7cca24fdc4c6b6d8fc88ac41626c1b`.

Reactive and simulative arrays differ only in container name, condition/run labels,
gate mode, source job name, and upstream mode. Task, model, seed, max step, timeout,
retry, runtime adapter, resources, network, secret mount, tmpfs, and security flags are
identical. Inner hashes are
`97ddc61a5ea0ace089ed620b9579aff40317dd7cef2e81802d18771294ecd2cb`
and `f6edc9b65add534cda1556f7095a1befe484846ceb14ce618c8f16a3e33daa39`.

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
read back and compared before atomic finalization; the source remains local.

After a run, `compute-use.json` preserves runtime wall/accelerator time, list-price
upper bound, observed API cost, and a null actual invoice. A separate repository
closeout must reconcile `CMP-0001` before interpretation or successor execution.

No repository code/configuration change is currently required before a live request.
Fresh user authorization and every dynamic identity, price, resource, secret,
freshness, storage, and termination-path check remain mandatory execution inputs.
