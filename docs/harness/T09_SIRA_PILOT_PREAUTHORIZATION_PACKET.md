# T09 SiRA pilot preauthorization packet

Status: **statically complete and ready for a fresh exact authorization; unauthorized**

Plan authorization remains `false`. This packet records the immutable package a
later current-turn authorization must name. It is not itself authority to run the
dynamic preflight, create or mutate cloud resources, read a provider credential,
contact OpenAI, start a browser, run SiRA, or execute a FanOutQA task.

## Immutable package

| Field | Frozen value |
|---|---|
| Plan | `PLAN-EXP0001-PILOT-V2` |
| Plan path | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml` |
| Plan bytes / SHA-256 | `4710` / `e39cab555ff07ce3e99215f6cf46eb49a0de7cc37268481fa2e4e22addb6ac05` |
| Reviewed implementation ancestor | `06cf17023380b206302082293f87e9b0d84e0e72` |
| Final clean package commit | Supplied as the exact terminal commit in the T09 handoff; it must be a descendant of the reviewed ancestor and is checked at execution |
| Execution contract | `contracts/T09_PILOT_EXECUTION_CONTRACT.json`; SHA-256 `6af4987662e5edd848e8de672d9d8909cd886376e2986bb18a18fb18e5b4f4f0`; 16,405 bytes |
| Four-command package | `contracts/T09_PILOT_COMMAND_MANIFESTS.json`; SHA-256 `89790864c705cc8add130c0f92ffeff087f6fefb3aee36e76bc3b958fa3bfdec`; 18,532 bytes |
| Dataset contract | SHA-256 `adc2b2531d322ee9013cff2fd049c2f45e1098901f95cc1122fa57c013280389` |
| Evaluator contract | SHA-256 `bc019781ab4468a51bcf6f76ac937ea81334d70281f476504b5693df57178a6a` |
| Runtime identity | SHA-256 `db3041caf860a0e5e383c8c2b71cee7cb43ef8b480bbcca7aca209928520674c` |

The host runner requires its `--package-commit` to equal the checked-out clean Git
HEAD, verifies that the reviewed implementation commit is its ancestor, and verifies
the selected runtime, evaluator, preflight, host, and generator bytes by reading them
from that reviewed ancestor. A documentation-only post-implementation commit cannot
silently replace reviewed execution code.

## Scientific, data, evaluator, and order bindings

- Experiment `EXP-0001`; calibration only.
- SiRA commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Every model role uses `gpt-4o-2024-11-20`, requested service tier `default`, with no
  fallback and no implicit provider retry.
- Dataset is the archived November 2023 FanOutQA development split: pinned SiRA Git
  blob `76ad1feb689b754bfe4e5e24d3ea371b647efa67`, file SHA-256
  `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`.
- Task A is `7dcbbbdc7f1120cd`; Task B is `2120afba8009bad3`.
- Attempt order is Task A reactive, Task A simulative, Task B simulative, Task B
  reactive. Seed `42`, task records, and order are frozen before empirical entry.
- The evaluator is the exact SiRA FanOutQA evaluator at the SiRA commit, evaluator
  SHA-256 `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79`,
  with its complete locked dependency/asset closure. It has no judge model, prompt,
  provider access, or alternate scoring path. Primary score is exact upstream
  `acc_loose`.

The four frozen argv hashes, in attempt order, are
`ad2dc769d52eb9349a8a8a093fb706ab3f78aa1a06d467e0e13d970fac3d43b5`,
`f71a33d391c10a128335fc4e1b9620c056669929ce678ec391e15fecc4a77ad3`,
`75c2149f4c39d0d6aa73b44cd8a5e1ab3e30551cf831299a11e9fa6f53d39527`,
and `4f3b06547278254c688e482ccfc51b299e4210c9f4606cefff642eeb14636d84`.
Both machine pair diffs are valid. Within each task pair the task, model, runtime,
tools, 30-step maximum, timeouts, evaluator, instrumentation, evidence handling, and
budgets are equal. Only the source-declared treatment, run/order identity,
condition-owned path, and later realized events may differ.

## Runtime and budgets

The selected runtime is the T07 pragmatic x86_64 Linux runtime: Python 3.11.14,
container image
`sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`,
Playwright 1.39.0, Chromium revision 1084, and model/service tier above. Pilot,
preflight, and evaluator containers request no GPU and set `CUDA_VISIBLE_DEVICES`
empty. The A10 remains a convenient qualified host allocation; no GPU acceleration
is claimed.

Expected planning use is:

| Scope | Model calls | Tokens | Browser actions | OpenAI USD | Lambda USD | Total USD |
|---|---:|---:|---:|---:|---:|---:|
| Reactive attempt | 72 | 87,948 | 18 | 0.254970 | 0.258000 | 0.512970 |
| Simulative attempt | 90 | 120,636 | 18 | 0.471015 | 0.258000 | 0.729015 |
| One pair | 162 | 208,584 | 36 | 0.725985 | 0.516000 | 1.241985 |
| Four attempts | 324 | 417,168 | 72 | 1.451970 | 1.032000 | 2.483970 |

Hard per-attempt caps are 1,155 model-call attempts, 1,000,000 total tokens, USD 10
OpenAI, 30 task browser actions, 30 seconds per action, 3,600 condition-wall seconds,
2 GiB output, 1.0 A10 allocation-hour, and USD 1.29 Lambda allocation. Hard pair wall
is 7,200 seconds. Hard pilot caps are four attempts, zero retry after empirical entry,
4,620 model-call attempts, 4,000,000 tokens, 120 task browser actions, 14,400 total and
Lambda seconds, 12 GiB disk, USD 40 OpenAI, 4 A10-hours/USD 5.16 Lambda, and USD 45.16
combined. Counters reserve calls/actions before the operation, persist aggregate use,
reconcile returned receipts, and fail closed on an unreconciled call or any cap.

## Automatic first-pair checkpoint

Task B proceeds without another authorization only if both Task A attempts have
valid reconstructable evidence, both exact evaluator runs succeed, the pair remains
matched, no credential or cleanup issue occurred, and use is strictly below 2,310
calls, 2,000,000 tokens, 60 browser actions, 7,200 wall seconds, USD 20 OpenAI, USD
2.58 Lambda, and USD 22.58 combined. Projected four-attempt cost must remain no more
than USD 45.16, and no severe floor/ceiling result may make Task B incapable of adding
calibration value. Any failed criterion persists `stop-before-task-b`, preserves Task
A evidence, performs cleanup, and forbids Task B. This is a calibration stop rule,
not an unbiased sampling claim.

## Evidence, cleanup, and release restrictions

Each attempt must retain the exact task/pair/order/command/config/commit/runtime/model
identity; timestamps and process exit; every available provider call receipt with
role, lineage, usage and requested/returned tier; requested actions and post-action
results; session, answer, screenshots, stdout/stderr and normalized events;
regulation-decision assignment; exact evaluator input/output and score; orthogonal
artifact/completion/answer/evaluator/condition states; hashes/sizes; and cleanup.
Unavailable H2K fields remain explicitly unavailable.

Credentials, Jupyter URLs/tokens, API/cloud secrets, private IP/CIDR values, and
unrelated account/provider identifiers are structurally excluded. An authorized run
must destroy the exact secret channel, close browser and condition containers,
terminate the exact owned provider resource, and retain a final provider receipt
showing zero Lambda instances. A nonzero resource count or ambiguous ownership is a
failed closeout, not permission to delete an unrelated resource.

The FanOutQA data are CC-BY-SA-4.0. Raw task/reference material, responses, traces,
and screenshots remain private and access controlled. Public raw release is blocked
pending attribution/share-alike, third-party-content, privacy, and redaction review.
That publication-only restriction does not block an exactly authorized private run.

Report only descriptive task-level calibration results. Do not estimate an effect or
variance, test significance, claim condition superiority, pass/fail `EXP-0001`, or
draw H2K/GIC architectural conclusions.

## Ready-to-copy authorization form

The T09 final handoff supplies the exact value for `<FINAL-CLEAN-PACKAGE-COMMIT>`.
Copy the block only after substituting that value and independently confirming the
current-turn cloud/spend authorization remains intended:

```text
I authorize one execution of the private, access-controlled EXP-0001 SiRA calibration
pilot PLAN-EXP0001-PILOT-V2 from clean GIC Lab commit
<FINAL-CLEAN-PACKAGE-COMMIT>, whose reviewed implementation ancestor is
06cf17023380b206302082293f87e9b0d84e0e72. I bind pilot.yaml at 4,710 bytes and
SHA-256 e39cab555ff07ce3e99215f6cf46eb49a0de7cc37268481fa2e4e22addb6ac05,
execution contract SHA-256
6af4987662e5edd848e8de672d9d8909cd886376e2986bb18a18fb18e5b4f4f0, and command
package SHA-256 89790864c705cc8add130c0f92ffeff087f6fefb3aee36e76bc3b958fa3bfdec.

The authorized sample is exactly FanOutQA development revision
76ad1feb689b754bfe4e5e24d3ea371b647efa67, tasks 7dcbbbdc7f1120cd and
2120afba8009bad3, ordered Task A reactive then simulative and Task B simulative then
reactive, with gpt-4o-2024-11-20/default for every role, SiRA commit
93fb8d72de71f9a4a13419670adeb34d93cf7acd, and the exact pinned upstream evaluator.

I authorize expected total spend USD 2.483970 and hard aggregate spend no more than
USD 45.16: OpenAI no more than USD 40 and Lambda A10 allocation no more than 4 hours
or USD 5.16. Per attempt I authorize at most 1,155 model calls, 1,000,000 tokens,
USD 10 OpenAI, 30 browser actions, 3,600 wall seconds, and 2 GiB output; aggregate
limits are four attempts, zero retry, 4,620 calls, 4,000,000 tokens, 120 actions,
14,400 wall/Lambda seconds, and 12 GiB disk. Pair wall is 7,200 seconds.

After Task A, continue automatically to Task B only if both attempts have valid
reconstructable evidence, evaluator and pair checks pass, there is no credential or
cleanup issue, all strict first-pair thresholds pass, projected total remains at or
below USD 45.16, and Task B can still add calibration value. Otherwise stop before
Task B, preserve evidence, and clean up.

Retain the exact private evidence contract, structural redactions, cleanup receipts,
and explicit unavailable fields. Raw licensed/private material may not be publicly
released. Terminate the exact owned provider resource and verify zero Lambda
instances at closeout. This authorization is for calibration only and authorizes no
effect, variance, significance, superiority, EXP-0001, H2K, or GIC conclusion.
```
