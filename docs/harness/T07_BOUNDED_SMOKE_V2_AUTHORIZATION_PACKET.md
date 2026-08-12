# T07 bounded-smoke V2 authorization packet

Status: **ready for a fresh user decision; unauthorized; do not execute from this
packet alone**

## Exact immutable binding

| Field | Exact value |
|---|---|
| Branch | `phase-1/sira-smoke-bounded` |
| Fork / frozen parent | `397a391b736528dd1049023d629100193e823c49` |
| Reviewed implementation commit | `a7ca7475177aee60126e39c631d61e3d9453ca85` |
| Required execution commit | `<EXACT_FINAL_CLEAN_BOUNDED_SMOKE_V2_PACKET_COMMIT>`; supplied by the final handoff |
| Plan ID | `PLAN-T07-BOUNDED-SIRA-SMOKE-V2` |
| Host run | `RUN-T07-BOUNDED-HOST-0002` |
| Reactive / simulative runs | `RUN-T07-BOUNDED-SIRA-REACTIVE-0002` / `RUN-T07-BOUNDED-SIRA-SIMULATIVE-0002` |
| Future authorization placeholder | `AUTH-T07-BOUNDED-SIRA-SMOKE-V2-PENDING` |
| Plan | `containers/sira-smoke/bounded/bounded-smoke-plan-v2.json` |
| Plan bytes / SHA-256 | 43,198 / `f0d635783d719d1c5cb5df5351eaf8f6f54e9049da1f2565e4227e66f48ef511` |
| Private binding alias / bytes / SHA-256 | `t07-bounded-binding-67eceae4caa9` / 2,660 / `5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b` |
| Private-binding schema version / bytes / SHA-256 | `0.3.0` / 5,425 / `ee09d8413b44dc66d1cefaad92b81f418e9e0ae0df98413a354a97ea32da350b` |
| Plan schema bytes / SHA-256 | 12,768 / `2d0bf1b934c6df81b0f9b6a9aa9e91ed6b2c61fb1641f15b55cca6038718978b` |
| Authorization schema bytes / SHA-256 | 3,293 / `cad71bc9e9ba365be30d8136d808f9ab51ed5fcfa57ee36437d730be46226dee` |
| Observer-ledger schema bytes / SHA-256 | 3,315 / `44c71d2fea9b216badca84fa867ab95dedfaa4309455dba59c72e219c5e6c6b9` |
| Evidence schema bytes / SHA-256 | 1,426 / `803d74577d6bb90daaee2b61c15c65abfff3680e4ebefea7137d81bb7d99ad49` |
| Contract module bytes / SHA-256 | 73,750 / `fcb0b1a113b5f1c03ce123b24df9abe536b7ac561758915cdf5d340d08929ebc` |
| Local supervisor bytes / SHA-256 | 297,716 / `5b2b43691288c2950ddbf9de12bf5c72d4fccf7b7a3fc04c81ea173c5f0f55a2` |
| Local hash-first bootstrap bytes / SHA-256 | 7,276 / `0cd531ecd7584cb2d61caa3b0df8d6a60a82345c1f97fdddbd3c8aa6a16a9063` |
| Remote bootstrap bytes / SHA-256 | 143,094 / `9b7cc9df569d3c9f7ed591c81737d8d8e08db501588541d9767b2df63240bb68` |

The V2 plan binds 34 implementation artifacts by exact byte size and SHA-256. A Git
document cannot contain its own final commit SHA, so the copy-ready block has one
explicit final-commit placeholder. A future execution must verify that clean commit,
ancestry from the reviewed implementation, the plan hash, all 34 artifact hashes, and
the private binding hash before reading either approved secret or sending a request.

Repository execution permissions remain false, the plan is `authorized: false`, and
`CMP-0001` remains planned with zero actual time/cost. The only prospective execution
authority is a fresh current-turn user message materialized into a mode-0600,
Git-ignored, 3,600-second single-run overlay. V1 and every bounded `0001` run identity
remain burned and nonreusable.

## Security-binding repair and private boundary

Sanitized classifications are:

- ruleset-name drift: `stale_high_assurance_name`;
- restoration-baseline drift: `materializer_baseline_bug`;
- overall cause: `both`.

The fresh binding uses schema `0.3.0` and ruleset pattern
`t07-bounded-ruleset-v1`. It binds canonicalizer/parser
`t07-firewall-canonical-v1` / `t07-firewall-response-v2`, baseline alias
`l2m-firewall-baseline-b0ef71115811` with semantic SHA-256
`b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764`, and restoration
alias `l2m-firewall-restoration-50ca7febe9f1` with payload/seal SHA-256
`50ca7febe9f160ada862371376485ea2ece11b373d25179ccd578d9c7acd42b8`.

The source and local seal are regular, no-follow, user-owned, mode 0600, outside Git,
and retained. The binding source was copied one-way into the approved APFS/UTDM bundle;
the local seal remains local. The private locator is independently generated and not
derivable from the public alias or binding SHA. The destination was fsynced, atomically
finalized, reread, and hash-verified with no internal fallback. Materialization verifies
the exact local seal and external bundle before creating any run root. Only the opaque
alias, binding bytes, binding SHA, and schema are public. The locator, paths, local-seal
identity, nonce, IPv4 `/32`, firewall values, ruleset name, decision values, and raw
provider IDs remain private.

Before generating that binding, the supervisor requires exact byte identities for the
published protected human-decision seal and high-assurance baseline seal; parsing a
field subset cannot substitute for either upstream seal hash.

## Future scope and fixed order

The future scope is one manually supervised Lambda/Jupyter host, one pinned
source/image build, one no-network local-static-page Chromium preflight, one exact
model metadata GET, and one externally assigned ordered pair:
`SIRA-REACTIVE` first, then `SIRA-SIMULATIVE`. Interpretation remains prohibited.

The local observer may issue only the 13 plan-listed GETs to
`https://cloud.lambda.ai`, exactly once each, in five ordered phases, without redirect,
pagination request, or retry. Only the user may apply/restore the privately bound
global firewall rule, create/delete the one owned regional ruleset, click launch once,
open Jupyter, upload/download fixed files, and terminate the exact bound instance.
The supervisor implements no cloud mutation path and SSH remains forbidden.

The selected public resource is `gpu_1x_a10`, `us-east-1`, x86_64, image alias
`img-0032` (`lambda-stack-22-04`, `22.4.5-2141`), key alias
`fractal-lambda-codex`, and zero persistent filesystems. Dynamic availability,
capacity, price, image, key fingerprint, firewall, no-running-instance, user-presence,
and termination-path checks remain fail-closed.

## Exact caps

- OpenAI API cost: USD 4.00 aggregate and USD 2.00 per condition.
- Model tokens: 400,000 aggregate and 200,000 per condition.
- Model calls: 77 attempts aggregate; 16 reactive and 61 simulative; one separate
  exact-model metadata GET; zero retry.
- Condition wall: 240 seconds aggregate and 120 seconds each.
- Browser actions: two aggregate and one per condition; one additional no-network
  browser-preflight action.
- Condition attempts: two aggregate and one each.
- Retained condition output: 209,715,200 bytes aggregate and 104,857,600 bytes each.
- Container/control: four owned containers; 128 aggregate work-and-cleanup lifecycle
  calls, including 48 reserved cleanup calls; 33,554,432 captured control-output bytes,
  including 8,388,608 cleanup-reserve bytes. Each container is limited to 2,000 CPU
  millis, 4,294,967,296 memory bytes, equal memory+swap, 512 PIDs, 1,073,741,824 shm
  bytes, 134,217,728 tmpfs bytes, 8,388,608 log bytes, one log file, five-second TERM,
  restart `no`, and a 120-second cleanup reserve.
- Per-condition payload/evidence: 67,108,864 tmpfs bytes plus 37,748,736 control
  evidence reserve bytes.
- Setup/runtime: 2,147,483,648 setup-transfer admission bytes;
  17,179,869,184 runtime-disk increment bytes; 34,359,738,368 remote-free floor;
  33,554,432 bootstrap-process output bytes. Only the uv wheel is exactly transfer
  metered; Git/image wire bytes remain an explicit limitation and are disk-admission
  bounded.
- Lambda: one instance, one launch click, zero persistent filesystems, USD 2.00 normal
  provider cap, USD 1.29 projected list cost, 3,600-second provider/authorization wall,
  and termination click by 3,300 seconds.
- Lambda observer: 13 GETs; 1,048,576 response bytes each and 13,631,488 aggregate;
  262,144 ledger bytes, 96 events, 4,096 bytes/event, and 3,600 seconds.
- Evidence: 268,435,456 remote bytes; 301,989,888 local and sealed bytes;
  1,048,576 early-failure bytes; 128 archive files; 600 archive seconds;
  8,388,608 upload bytes and 36 archive members.
- Storage floors: Mac prewrite/retained 8,891,924,480 / 8,589,934,592 bytes;
  external prewrite/retained 200,350,182,605 / 200,048,192,717 bytes.
- Automatic and implicit retries: zero. Cloud mutations through the supervisor: zero.

## Model, source, dependencies, and secrets

OpenAI is fixed at `https://api.openai.com/v1/` and every SiRA role is exactly
`gpt-4o-2024-11-20` with request and reconciled response service tier `default`.
Standard price identities remain USD 2.50/M input, USD 1.25/M cached input, and USD
10.00/M output. The future authenticated model GET must return the exact dated model
before either condition.

SiRA is pinned to commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`, tree
`6a6d9068b94d7632d3533a3d6f013d4de6ff76e8`, lock SHA-256
`138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e`, and routing
patch SHA-256 `4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed`.
The exact future installation uses uv 0.11.7's 24,933,975-byte pinned x86_64 wheel,
`uv sync --frozen --extra eval --python 3.10`, and the digest-pinned Playwright
1.39.0 Jammy image for `linux/amd64`. It does not run `playwright install` or push an
image. Network endpoints and immutable artifact identities remain exactly those in
the plan.

The only secret variable names are `LAMBDA_API_KEY` and `SIRA_API_KEY`.
`LAMBDA_API_KEY` is available only to the local in-process GET observer.
`SIRA_API_KEY` is supplied as a private mode-0600 file, mounted read-only at
`/run/secrets/sira_api_key`, and exported only to the SiRA child. `OPENAI_API_KEY` is
forbidden. No secret value or derivative may enter argv, labels, paths, images,
container configuration, logs, screenshots, ledgers, archives, Git, or notebook
content.

## Cleanup contract

Every success or failure must preserve safe bounded evidence; capture process and
payload evidence before removal; stop, then kill if necessary, by immutable container
ID; remove every owned container; and verify zero owned container/network/volume and
browser-process residue. The user must terminate the exact bound Lambda instance,
verify terminal/absent and nonbillable state, delete only the owned regional ruleset,
and restore the exact sealed global baseline. The local archive must verify the
inbound manifest and pair surface before termination, then copy one-way through held
no-follow APFS/UTDM descriptors, reread/hash every destination, fsync, atomically
finalize, retain the source, and prohibit internal fallback. No failure or ambiguous
send authorizes a retry or a second run identity.

## Ready-to-copy V2 authorization block

Replace only the exact final clean commit placeholder and, if used on another date,
the authorization-reference date. Any code, plan, binding, resource, price,
secret-channel, or storage drift requires a new reviewed packet.

```text
I authorize T07 bounded SiRA smoke V2 only on exact clean commit
<EXACT_FINAL_CLEAN_BOUNDED_SMOKE_V2_PACKET_COMMIT> of branch
phase-1/sira-smoke-bounded, descended from reviewed implementation commit
a7ca7475177aee60126e39c631d61e3d9453ca85 with all 34 plan-bound artifact hashes unchanged,
using plan PLAN-T07-BOUNDED-SIRA-SMOKE-V2 at
containers/sira-smoke/bounded/bounded-smoke-plan-v2.json, 43,198 bytes,
SHA-256 f0d635783d719d1c5cb5df5351eaf8f6f54e9049da1f2565e4227e66f48ef511,
host run RUN-T07-BOUNDED-HOST-0002, reactive run
RUN-T07-BOUNDED-SIRA-REACTIVE-0002, simulative run
RUN-T07-BOUNDED-SIRA-SIMULATIVE-0002, fresh authorization reference
AUTH-T07-BOUNDED-SIRA-SMOKE-V2-2026-08-11, and the protected private security binding
alias t07-bounded-binding-67eceae4caa9, 2,660 bytes, SHA-256
5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b.

I authorize materialization of that exact pre-sealed mode-0600, Git-ignored private
binding only after the operator privately supplies its protected path and local-seal
SHA through the plan's declared substitutions and the supervisor verifies the exact
local seal plus held-descriptor external bundle before creating the run root; one
fresh 3,600-second single-run authorization overlay; preparation of
the exact tracked-only 36-member/8,388,608-byte upload archive and separate reviewed
bootstrap; exactly the 13 GET-only Lambda observations in the plan; and the user-only
temporary global-firewall restriction, creation of one owned regional ruleset, one
manual launch click for gpu_1x_a10/us-east-1/img-0032 with no persistent filesystem,
Cloud IDE/Jupyter access, fixed file upload/download, termination of the exact bound
instance, deletion of only the owned ruleset, and exact global-firewall restoration.

I authorize one pinned source/image/dependency build, one no-network local-static-page
Chromium preflight, one GET of
https://api.openai.com/v1/models/gpt-4o-2024-11-20, then SIRA-REACTIVE once followed
by SIRA-SIMULATIVE once, using gpt-4o-2024-11-20 for every role and service_tier
"default" on every request and reconciled response.

Caps are USD 4.00 OpenAI aggregate/USD 2.00 per condition; 400,000/200,000 model
tokens; 77 model-call attempts total (16/61); one browser action, 120 seconds,
104,857,600 retained-output bytes, and one attempt per condition; zero retry; one
Lambda instance, one launch click, zero persistent filesystem, USD 2.00 provider
normal cost, 3,600 seconds with termination click by 3,300 seconds; 13 Lambda GETs;
2,147,483,648 setup-transfer admission bytes; 17,179,869,184 runtime-disk bytes;
268,435,456 remote evidence bytes; 301,989,888 local/external archive bytes; 128
aggregate Docker lifecycle calls; and every exact CPU, memory, PID, tmpfs, log,
output, observer, wall, and storage cap in the plan.

The operator may access only LAMBDA_API_KEY through the approved nonlogging local
channel. I will supply SIRA_API_KEY only through the exact private file channel in the
plan. OPENAI_API_KEY is forbidden. No secret value or derivative may enter argv,
labels, paths, images, container configuration, logs, screenshots, ledgers, archives,
Git, or notebook output.

I authorize the exact success-or-failure evidence capture and one-way hash-verified
archive copy to the approved APFS/UTDM root with source retention, held no-follow
identity checks, exact floors, fsync, atomic finalization, and no internal fallback.
On any stop condition, do not retry: preserve safe evidence, remove owned containers
when possible, terminate the exact bound instance, verify terminal/nonbillable state,
remove only the owned ruleset, and restore the exact firewall baseline. Stop after the
pair or first terminal failure. This grants no pilot, training, interpretation, T08,
unrelated mutation, SSH, second launch, second condition attempt, or production claim.
```

## Remaining blocker

The only authorization blocker is the absence of a fresh user message containing the
exact final clean packet commit and the completed block above. Dynamic
resource/model/price/secret/storage/freshness/user-presence/termination checks remain
execution-time hard blockers. No further code or configuration repair is known to be
required before a separately authorized live request.

No Lambda/OpenAI/public-IP request, secret access, cloud mutation, paid compute, SSH,
Jupyter, container, browser, SiRA condition, or scientific execution occurred while
preparing this packet.
