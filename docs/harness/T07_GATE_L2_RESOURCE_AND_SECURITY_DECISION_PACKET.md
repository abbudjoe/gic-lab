# T07 Gate L2 resource and security decision packet

Status: **inventory-evidence-insufficient; blocked; non-executable; unauthorized**

Date: 2026-08-10

This is an account-bound decision packet, not a Gate L2 plan or authorization. It
contains no launch request, provider mutation array, raw provider image ID, selected
resource, secret, public IP, or ready-to-copy authorization block. Gate L2, paid
compute, cloud mutation, SSH, and prototype execution remain false.

## Evidence binding

The packet consumes only the immutable, externally sealed Gate L1 inventory for
`RUN-T07-L1-LAMBDA-INVENTORY-0003`:

- inventory SHA-256:
  `022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933`;
- request-ledger SHA-256:
  `1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707`;
- canonical schema-extension report, 1,863 B, SHA-256:
  `20f035039e633e5ef81c544f439b8fac6dc08ee4dafce1eacd2646df0e3a9263`;
- external `SEAL.json` SHA-256:
  `3347b8d03d0f937111de92ef79286c7fbcb02027f652f35ba42ac337cf8f7bd5`;
- external `COPY_RECORD.json` SHA-256:
  `76d8511282962cb6fdc4f72a63eaf41e7e63239acb9fa38e030f51057cb8a0e7`.

All seven inventory outcomes were HTTP 200 and schema-valid, source and archive bytes
matched, and zero running instances were observed. Price, capacity, firewall state,
keys, and running instances are observations from that run, not launch-time facts.

## Resource candidates

The repaired image projection yields six qualifying tuples under the fixed Gate L0
policy. Every tuple uses `gpu_1x_a10`, x86_64, 30 vCPU, 200 GiB RAM, 1,400 GiB root
storage, one GPU, no persistent filesystem, the approved `gpu-base-22-04` family, and
an observed list price of USD 1.29/hour.

The policy-ranked first three are:

| Rank | Type | Region | Image alias | Image version | Observed price |
|---:|---|---|---|---|---:|
| 1 | `gpu_1x_a10` | `us-east-1` | `img-0062` | `22.4.5-1459` | USD 1.29/hour |
| 2 | `gpu_1x_a10` | `us-east-1` | `img-0101` | `22.4.5-1722` | USD 1.29/hour |
| 3 | `gpu_1x_a10` | `us-east-1` | `img-0111` | `22.4.5-2141` | USD 1.29/hour |

The three alternates are the same aliases and versions in `us-west-1`, in alias
order. No tuple is selected or authorized. The one-hour list-price cap for each is
129 cents; the future provider-compute hard ceiling remains 200 cents. A future
launch gate must freshly revalidate price, capacity, image availability, and zero
running instances immediately before mutation. `us-south-1` is not automatically
selectable.

The complete matrix and all 23 excluded instance types with their exact reason lists
are in
`docs/harness/evidence/T07_RUN_0003_POSTRUN_ADJUDICATION.json` and validate against
`schemas/t07-lambda-resource-candidate-matrix.schema.json`.

## SSH-key evidence

The sealed inventory retained the three account key names below but deliberately
dropped their public-key bodies. Consequently no account fingerprint exists to
compare with the local public fingerprints. `evidence_unavailable` is not a negative
match.

| Lambda key name | Local fingerprint match | Matching local path | Same-stem private file |
|---|---|---|---|
| `aic-codex-lambda` | `evidence_unavailable` | unavailable | unavailable |
| `codex-fawx-20260527` | `evidence_unavailable` | unavailable | unavailable |
| `fractal-lambda-codex` | `evidence_unavailable` | unavailable | unavailable |

Only local `.pub` bytes and same-stem filesystem metadata were inspected:

| Local public-key path | Algorithm | Standard fingerprint | Mode | Same-stem private file by metadata |
|---|---|---|---:|---|
| `~/.ssh/fractal_lambda_ed25519.pub` | `ssh-ed25519` | `SHA256:jZS7ZqMUWT/mUf/2J80DuXvKlOIvRSKjSlc+qaVUycU` | `0644` | yes |
| `~/.ssh/google_compute_engine.pub` | `ssh-rsa` | `SHA256:rPdA5jGuJ1LbCcepfOS4qOaGqBtgiFAjpVVfLYKgndY` | `0644` | yes |
| `~/.ssh/id_ed25519.pub` | `ssh-ed25519` | `SHA256:v/BRQtLI4irTS9DzfsHfGlMy7IHlZvd6WhF3Qa/IGVo` | `0644` | yes |
| `~/.ssh/id_ed25519_github.pub` | `ssh-ed25519` | `SHA256:znqRTXzIMkq7nYkZfJPPfoh4QrOUiuPVuk+06kGA56g` | `0644` | yes |
| `~/.ssh/jarvis_tailscale.pub` | `ssh-ed25519` | `SHA256:ESvp3ohE6ZYWkB1nxg7EDfbaJmcWwZneb9LvN/cfAd0` | `0644` | yes |
| `~/.ssh/prime_codex_rsa_20260517.pub` | `ssh-rsa` | `SHA256:34/DLwx96bxIRXJwj3JsS9izW3rmcrCbL8SdjONhfm0` | `0644` | yes |
| `~/.ssh/real2sim_codex_ed25519.pub` | `ssh-ed25519` | `SHA256:omJTSzs1UVrzRxFW9pCbWKAtXSnYwYExi2tMxOj1tX8` | `0644` | yes |

All local files were owned by the current user. Private-key bytes were not read, no
agent was invoked, and no SSH operation occurred. There is no SSH-key recommendation.
Resolving this fact requires either independently verified account public-key
fingerprints supplied by the user or a fresh, reviewed, separately authorized minimal
read-only evidence plan. This turn authorizes neither.

## Global firewall assessment

The effective global ruleset is not a strict qualification firewall:

| Ordinal | Protocol | Port range | Source scope | Classification | SSH | Non-SSH exposure |
|---:|---|---|---|---|---|---|
| 1 | TCP | 22–22 | single IPv4 | SSH | yes | no |
| 2 | TCP | 49100–49100 | single IPv4 | custom network | no | yes |
| 3 | UDP | 47998–47998 | single IPv4 | custom network | no | yes |
| 4 | TCP | 8210–8210 | single IPv4 | custom network | no | yes |

Actual source addresses and free-form descriptions are omitted. A new per-instance
SSH-only ruleset cannot neutralize these rules because per-instance rules are
additive to global rules and are attached only at launch.

Run 0003 also observed **no regional/per-instance ruleset**. D-020 and the Gate L0
host decision require at least one same-region, strictly TCP/22-only ruleset for the
launch. A future gate must therefore either (a) separately authorize creation,
approval, launch-time attachment, and post-termination deletion of one T07-owned
same-region ruleset while also making the global rules strict, or (b) record an
explicit reviewed governance decision superseding that regional-ruleset requirement.
This packet selects neither path. The regional ruleset is additive defense; it never
substitutes for strict global rules.

The preferred future design candidate is temporary global-rule replacement, but it
is blocked until the user supplies both:

1. this exact attestation: “I attest that no other Lambda workspace resource depends
   on the current global inbound rules during the T07 qualification window”; and
2. the exact current public IPv4 placeholder
   `<USER_APPROVED_PUBLIC_IPV4/32>` through a reviewed input channel.

The future plan must first freshly prove zero running instances account-wide, then
snapshot the original GET response byte-for-byte, schema-validate it, durably seal it
under a run-owned path with file and directory fsync/readback evidence, and bind the
response, normalized rules, and seal by SHA-256. It must replace the rules with exactly
one inbound TCP/22 rule from the approved `/32`, verify the exact replacement by GET,
and bind the immutable launched instance identity. Qualification completion or any
failure while that instance exists must enter `instance-termination-required`;
provider-terminal evidence for that same identity is mandatory before restoration.
Only then may the exact original normalized rules be restored and verified by GET.
Any failure after mutation arms this fail-closed lifecycle. Restore failure is a
high-severity incident and forbids another launch. The alternatives remain permanent
user cleanup or no launch.

The crash-recovery source is the private raw response artifact itself—not merely its
digest. The future writer must create both the run-owned
`firewall-snapshot/original-global-firewall-response.json` artifact and its
`ORIGINAL_GLOBAL_FIREWALL_SEAL.json` through the exact
`artifacts/t07/lambda/gate-l2/<fresh-run>/` repository-contained,
held-no-follow directory chain with exclusive dirfd-relative writes, bounded bytes,
file and directory fsync, and exact post-fsync readback. The seal must name and hash
the raw artifact. Missing, replaced, or tampered snapshot/seal evidence blocks the
first mutation and also blocks restoration from being falsely declared complete.

## Host-key trust decision

The preferred method is independent authenticated-channel verification. After a
separately authorized future launch, the user must open the authenticated Lambda
console or Jupyter terminal, obtain the host's ED25519 host-key fingerprint from
inside the instance, and return it as a current-turn decision. A future bounded
discovery result may then be compared before first login using
`StrictHostKeyChecking=yes` and a fresh run-owned `known_hosts` file.

Trust on first use is not the default. It would require explicit approval as a bounded
governance relaxation under the verified `/32` firewall. No SSH/no launch remains
available.

## Exact blockers and decisions

An executable Gate L2 plan is prohibited until all of these are non-null:

1. matchable account SSH public-key evidence and exactly one user-approved key;
2. exactly one user-approved type, region, and image alias after fresh revalidation;
3. the global-firewall option and the dependency attestation above;
4. the exact user-approved public IPv4 `/32` when temporary replacement is used;
5. the host-key verification method;
6. fresh preflight proof of zero running instances account-wide;
7. a separately authorized same-region strict TCP/22 T07 ruleset lifecycle, or an
   explicit reviewed supersession of the D-020/Gate L0 regional-ruleset requirement;
8. exact raw provider IDs resolved privately from the sealed, projection-validated
   alias map;
9. exact firewall snapshot/replacement/verification/instance-termination/restore and
   incident contracts;
10. exact budget, evidence-transfer, containment, cleanup, and immutable-ID provider
   termination contracts;
11. a new clean-commit-bound plan and separate current-turn user authorization.

The terminal state is `inventory-evidence-insufficient`. The image verifier and
candidate matrix are repaired, but absent account public-key evidence prevents the
required local/account fingerprint match. This packet does not authorize Gate L2,
Gate L3, Gate L4, the pilot, cloud mutation, paid compute, SSH, or any experimental
execution.
