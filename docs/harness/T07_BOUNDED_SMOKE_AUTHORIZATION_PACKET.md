# T07 bounded smoke authorization packet

Status: **blocked historical V1 authorization; superseded; never execute**

V1 stopped before its first Lambda request, secret access, mutation, or bounded private
binding write. Its plan and all `0001` run identities are burned and nonreusable. The
historical content below is retained for provenance only. The active replacement is
`T07_BOUNDED_SMOKE_V2_AUTHORIZATION_PACKET.md`; V2 also remains unauthorized.

## Exact immutable binding

| Field | Exact value |
|---|---|
| Branch | `phase-1/sira-smoke-bounded` |
| Fork / frozen parent | `397a391b736528dd1049023d629100193e823c49` |
| Reviewed implementation commit | `e3c68268ecb02375a7b3f78da0187ce1136f06c0` |
| Required execution commit | `<EXACT_FINAL_CLEAN_BOUNDED_SMOKE_PACKET_COMMIT>`; supplied by the final handoff |
| Plan ID | `PLAN-T07-BOUNDED-SIRA-SMOKE-V1` |
| Host run | `RUN-T07-BOUNDED-HOST-0001` |
| Reactive / simulative runs | `RUN-T07-BOUNDED-SIRA-REACTIVE-0001` / `RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001` |
| Plan | `containers/sira-smoke/bounded/bounded-smoke-plan-v1.json` |
| Plan bytes / SHA-256 | 55,789 / `0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f` |
| Plan schema bytes / SHA-256 | 11,572 / `225c81bb21c5a361ec7c96adcd9eca29c0953b3874c657ed78cb2dc6bea0a71d` |
| Authorization schema bytes / SHA-256 | 3,290 / `8b542cd152818304761a1bc11027a1abfa7187cf49698929fb11fedbfed13b09` |
| Private-binding schema bytes / SHA-256 | 3,415 / `39e9f8ea7205e924fef25995b6c801196b35f85473e32ce58d18ed110a857b43` |
| Observer-ledger schema bytes / SHA-256 | 3,312 / `2d9ad9e1e43d7a229ee2ebfb44af82b5f7e6234300bd9a14d1072e0a53c4ad61` |
| Evidence schema bytes / SHA-256 | 1,423 / `3f1b710ca9256696a56936a8fcbb71f9eed7fc36392579ed50ca0767df30d22e` |
| Contract module bytes / SHA-256 | 72,269 / `d6da182643b080e3e297716f1d65ce9c2e04d5157280c9f17aa33b82c840261c` |
| Local supervisor bytes / SHA-256 | 262,160 / `9ee429b7f131079be7327186ba75013c7d5455b71802558261fbff98077e25e3` |
| Local hash-first bootstrap bytes / SHA-256 | 7,276 / `0cd531ecd7584cb2d61caa3b0df8d6a60a82345c1f97fdddbd3c8aa6a16a9063` |
| Remote bootstrap bytes / SHA-256 | 143,094 / `74aa58c2aacd2fc88423370c9d673fbda03faffe72f1e05de7fd4a1420d21e02` |

The plan binds 34 implementation artifacts by exact byte size and SHA-256. A Git
document cannot contain its own final commit SHA, so the copy-ready block contains one
explicit commit placeholder. The final handoff resolves it; a future run must verify
that clean commit, ancestry from the reviewed implementation, and every artifact hash
before reading a secret or sending a request.

Repository execution permission fields remain false, the plan is `authorized: false`,
and `CMP-0001` is planned with zero actual time/cost. A fresh current-turn user message
is materialized into a mode-0600, Git-ignored, single-run authorization overlay. That
overlay is the only prospective execution authority and expires after 3,600 seconds,
the first matched pair, or the first terminal infrastructure failure.

## Future scope and exact observer order

The future scope is one manually supervised Lambda/Jupyter host, one pinned source and
image build, one no-network Chromium preflight, one exact-model metadata GET, and one
ordered reactive/simulative pair. The local observer may issue only these 13 GETs to
`https://cloud.lambda.ai`, once each with no redirect, pagination request, or retry:

1. prelaunch: `/api/v1/instance-types`, `/api/v1/images`, `/api/v1/regions`,
   `/api/v1/ssh-keys`, `/api/v1/firewall-rulesets`,
   `/api/v1/firewall-rulesets/global`, `/api/v1/instances`;
2. security before launch: `/api/v1/firewall-rulesets`,
   `/api/v1/firewall-rulesets/global`;
3. post-launch binding: `/api/v1/instances`;
4. post-termination verification: `/api/v1/instances`;
5. final security verification: `/api/v1/firewall-rulesets`,
   `/api/v1/firewall-rulesets/global`.

Each intent/send/outcome is append-only and fsynced. An unknown post-send outcome is
never replayed and converts the run to cleanup-only; termination/restoration GETs may
continue after expiry. Raw provider bodies are discarded after in-memory validation;
only schema-declared, credential-filtered receipts remain in the private ignored run
root.

Only the user applies/restores the privately bound global rule, creates/deletes the
owned regional ruleset, clicks launch once, opens Jupyter, uploads/downloads files,
and terminates the bound instance. The supervisor contains no Lambda mutation path.
The host is exactly `gpu_1x_a10`, `us-east-1`, x86_64, image alias `img-0032`
(`lambda-stack-22-04`, `22.4.5-2141`), no persistent filesystem, key alias
`fractal-lambda-codex`, and one privately bound ruleset.

## Model, source, installation, and secrets

The provider is OpenAI at `https://api.openai.com/v1/`; every SiRA role is
`gpt-4o-2024-11-20`. First-party pages retrieved 2026-08-11 list that dated snapshot
and standard prices USD 2.50/M input, USD 1.25/M cached input, and USD 10.00/M output.
The official Chat Completions reference retrieved 2026-08-12 (1,619,873 bytes,
SHA-256 `b33c4a8798d3a12f4c466c7791cdb936f47c82810d844b4c551567f0a62ac83e`)
says omission selects `auto`, while API request tier `default` selects standard
pricing and the response reports its actual tier. Every completion therefore sends
`service_tier="default"`; a missing or different response tier stops and remains
unreconciled. All metadata URL/time/byte/hash records are in the plan. Public
documentation is not account availability: the single future authenticated model GET
must return the exact ID before either condition.

SiRA is pinned to commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`, tree
`6a6d9068b94d7632d3533a3d6f013d4de6ff76e8`, `uv.lock` SHA-256
`138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e`, and routing
patch SHA-256 `4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed`.
The future build downloads the exact 24,933,975-byte uv 0.11.7 x86_64 wheel at
SHA-256 `4e4d5e31bea86e1b6e0f5a0f95e14e80018e6f6c0129256d2915a4b3d793644d`, runs
`uv sync --frozen --extra eval --python 3.10`, and uses
`mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c`
for `linux/amd64`. The image's amd64 manifest/config are pinned in the plan. It does
not run `playwright install` and does not push an image.

Expected setup endpoints are `github.com:443`, `files.pythonhosted.org:443`,
`pypi.org:443`, `mcr.microsoft.com:443`, and registry-directed MCR blob storage.
Workload/model metadata use `api.openai.com:443`; the locked browser task has
site-dependent HTTPS egress.

The only secret variable names are `LAMBDA_API_KEY` and `SIRA_API_KEY`.
`LAMBDA_API_KEY` is available only to the local in-process GET observer.
`SIRA_API_KEY` is a private mode-0600 file mounted read-only at
`/run/secrets/sira_api_key` and exported only to the SiRA child. `OPENAI_API_KEY` is
forbidden. No secret value or hash may enter argv, labels, paths, images, container
configuration, logs, screenshots, ledgers, archives, Git, or notebook content.

## Exact caps

- OpenAI: USD 4.00 aggregate/USD 2.00 each; 400,000 aggregate/200,000 each model
  tokens; 77 call attempts total (16 reactive, 61 simulative); one model metadata GET.
- Conditions: one reactive then one simulative; 120 seconds, one browser action,
  104,857,600 retained-output bytes, and one attempt each; zero retry; 240 seconds,
  two actions, and 209,715,200 retained-output bytes aggregate.
- Containers: four; 128 aggregate work-and-cleanup calls; 33,554,432 aggregate
  captured-output bytes; 67,108,864-byte attempt tmpfs each; exact per-container
  CPU/memory/swap/PID/shm/tmpfs/log/TERM limits in the plan.
- Setup/runtime: 2,147,483,648-byte setup-transfer admission, exact uv-wheel meter,
  17,179,869,184-byte incremental runtime-disk cap, and 34,359,738,368-byte remote
  free-space floor. Git/image wire bytes are not exactly metered and remain an explicit
  residual limitation; their materialization is fail-closed by the disk cap.
- Lambda: one instance, one click, zero persistent filesystems, USD 2.00 normal cost
  cap, USD 1.29 projected list cost, 3,600-second authorization/provider wall, and
  termination click by 3,300 seconds from authorization materialization.
- Observer: 13 GETs; 1,048,576 response bytes each/13,631,488 aggregate;
  262,144-byte/96-event ledger; 4,096 bytes per event; 3,600 seconds total.
- Evidence/storage: 268,435,456-byte remote evidence cap; 301,989,888-byte local and
  external archive cap; at most 125 copied payload files plus three seal files (128
  total), with 34 payload plus three seal files expected on complete success; 600
  archive seconds; Mac
  prewrite/retained floors 8,891,924,480/8,589,934,592 bytes; external
  prewrite/retained floors 200,350,182,605/200,048,192,717 bytes.

The archive destination is the approved APFS/UTDM run root under
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts`. The supervisor binds APFS
UUID `8478609D-FA37-4ED5-875D-47AE912B9151` and physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E` with held no-follow descriptors, rereads and
compares every destination, verifies SHA-256, fsyncs, atomically finalizes, retains the
local source, and permits no internal fallback.

## Ready-to-copy fresh authorization block

Replace only the exact final clean commit placeholder and, if used on another date,
the authorization reference date. Any code, plan, price, resource, firewall,
secret-channel, or storage drift requires a new reviewed packet.

```text
I authorize T07 bounded SiRA smoke V1 only on exact clean commit
<EXACT_FINAL_CLEAN_BOUNDED_SMOKE_PACKET_COMMIT> of branch
phase-1/sira-smoke-bounded, descended from reviewed implementation commit
e3c68268ecb02375a7b3f78da0187ce1136f06c0 with all 34 plan-bound artifact hashes
unchanged, using plan PLAN-T07-BOUNDED-SIRA-SMOKE-V1 at
containers/sira-smoke/bounded/bounded-smoke-plan-v1.json, 55,789 bytes, SHA-256
0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f,
host run RUN-T07-BOUNDED-HOST-0001, reactive run
RUN-T07-BOUNDED-SIRA-REACTIVE-0001, simulative run
RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001, and fresh authorization reference
AUTH-T07-BOUNDED-SIRA-SMOKE-V1-2026-08-11.

I authorize materialization of the plan's one mode-0600, Git-ignored, 3,600-second
single-run authorization overlay and private binding; preparation of the exact
tracked-only 36-member/8,388,608-byte-capped upload archive and separate reviewed
bootstrap; exactly 13 GET-only Lambda observer requests in the plan; and the user-only
temporary global-firewall restriction,
creation of one owned regional ruleset, one manual launch click for
gpu_1x_a10/us-east-1/img-0032 with no persistent filesystem, Cloud IDE/Jupyter access,
bundle/authorization/secret-file upload, evidence download, termination of the exact
bound instance, deletion of only the owned ruleset, and exact global-firewall
restoration. I authorize one pinned source/image/dependency build, one no-network
local-static-page Chromium preflight, one GET of
https://api.openai.com/v1/models/gpt-4o-2024-11-20, then SIRA-REACTIVE once followed
by SIRA-SIMULATIVE once, using gpt-4o-2024-11-20 for every role. Every Chat
Completions request must set service_tier="default" and every reconciled response
must report service_tier="default"; missing or different response tiers stop.

Caps are USD 4.00 OpenAI aggregate/USD 2.00 per condition; 400,000/200,000 model
tokens; 77 model-call attempts total (16/61); one browser action, 120 seconds,
104,857,600 retained-output bytes, and one attempt per condition; zero retry; one
Lambda instance, one launch click, zero persistent filesystem, USD 2.00 Lambda normal
cost, 3,600 seconds from authorization materialization with termination click by
3,300 seconds; 13 Lambda GETs; 2,147,483,648 setup-transfer admission bytes;
17,179,869,184 incremental runtime bytes; 268,435,456 remote evidence bytes;
1,048,576 early-failure evidence bytes; 301,989,888 local/external archive bytes;
4,096 remote evidence entries; 128 aggregate Docker lifecycle calls; and
the exact CPU/memory/PID/tmpfs/log/output/observer/storage caps in the plan.

The operator may access only LAMBDA_API_KEY through the approved nonlogging local
channel. I will supply SIRA_API_KEY only as the private mode-0600 secret file named by
the plan, containing only its raw value with an optional final newline and no
`SIRA_API_KEY=` prefix. It is created and uploaded outside notebook cells and logged
commands; its value may not enter argv, labels, paths, images, container configuration,
logs, screenshots, ledgers, archives, Git, or notebook output. OPENAI_API_KEY is
forbidden.

I authorize the exact success-or-failure evidence capture and one-way hash-verified
archive copy to the approved APFS/UTDM root, with source retention, held no-follow
identity checks, decoded ZIP/member/manifest/pair verification, exact floors, and no
internal fallback. The canonical remote output root is claimed once before authority,
bundle, plan, contract, or secret validation and is burned on any terminal failure.
The external archive must include the exact local upload archive and bootstrap.
Detected credential material or incomplete secret cleanup requires manual credential
rotation and keeps security closeout unresolved. On any stop condition, do not
retry: preserve safe evidence, remove owned containers when possible, terminate the
exact bound instance, verify terminal/nonbillable state, remove only the owned
ruleset, and restore the exact firewall baseline. Stop after the pair or first terminal
failure. This grants no pilot, training, interpretation, T08, unrelated cloud
mutation, SSH, second launch, second condition attempt, or production claim.
```

## Remaining blockers and limitations

The present blocker is the absence of that fresh authorization with the exact final
clean packet commit. Dynamic source/resource/price/model/secret/storage/freshness/user-
presence/termination checks remain fail-closed execution inputs. The seven accepted
residual limitations are manual launch not being exactly-once API-proven; practical,
not formal, descendant containment; outage-extended billing; practical rather than
exhaustive supply-chain attestation; manual nonproduction setup; non-exact Git/image
wire-byte metering; and the pair's lack of scientific power. No code or configuration
repair is currently required before a live request.
