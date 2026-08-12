# T07 bounded-smoke security-binding repair

Status: **repair complete; V2 execution remains unauthorized**

## Bound starting evidence

- Branch: `phase-1/sira-smoke-bounded`.
- Required starting commit: `36cfda4ea19ea4d4735d1caeba7f7e4797a769ae`.
- Preserved V1 plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V1`, 55,789 bytes,
  SHA-256 `0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f`.
- Reviewed V1 implementation ancestor: `e3c68268ecb02375a7b3f78da0187ce1136f06c0`.
- All 34 V1 artifact bindings and all five locked scientific hashes revalidated.
- No V1 local run, upload, remote, or external attempt root exists. The V1 plan and
  run identities remain burned and nonreusable.

The retained protected artifact was the earlier L2M materialization input, not a V1
bounded private binding: V1 stopped before `private-binding.json` could be created.
That historical input remains byte-identical, regular, no-follow, Git-ignored, and
read-only mode 0400. Mode 0400 is stricter than the old input's write-protection need;
the new V2 binding itself is mode 0600 as required. No historical artifact was
rewritten or deleted.

## Sanitized adjudication

| Surface | Observed structure | Required V2 structure | Closed classification |
|---|---|---|---|
| Owned ruleset name | String carrying the earlier high-assurance/L2M naming track | `giclab-t07-bounded-` plus exactly 12 lowercase hexadecimal characters derived from a fresh nonce | `stale_high_assurance_name` |
| Restoration baseline | The V1 supervisor hashed normalized rules with a raw/omitted `port_range` representation | The authoritative `t07-firewall-canonical-v1` presence document (`present` plus value, or `absent`) | `materializer_baseline_bug` |

Overall cause: **`both`**. The retained input belongs to the prior naming/binding
track, while the materializer independently duplicated the canonicalizer incorrectly.
The generated V1 bounded name would have matched its regex; the generic V1 failure was
caused by the canonicalizer defect. No provider, key, endpoint, or private value was
inferred to be at fault.

## Minimal repair

The V2 supervisor now:

1. computes firewall semantic hashes using the exact authoritative canonical document
   and has a parity regression against the frozen canonicalizer;
2. verifies the exact published protected-decision and high-assurance baseline-seal
   file hashes before parsing them;
3. keeps the canonical semantic baseline SHA and restoration-payload seal in separate,
   schema-required fields and rejects swaps;
4. generates the bounded name and opaque binding alias from separate domain-separated
   hashes of one fresh 128-bit random nonce, plus an independent 128-bit private
   locator whose value cannot be derived from either public identity;
5. rejects prior-track, malformed, stale, wrongly versioned, or hash-drifted bindings;
6. materializes only the already sealed exact V2 binding after verifying its private
   local seal and exact held-descriptor external bundle before creating a run root;
7. requires the supplied source and local seal to be regular, no-follow, user-owned,
   mode 0600, under the exact Git-ignored private-binding root, and addressed through
   the independent locator rather than the public alias or binding hash;
8. verifies destination modes, exact copy/seal records, pre/post volume identity,
   source/destination equality, retained floors, and absence of internal fallback;
9. cleans only the exact owned incomplete local/external transaction on failure while
   preserving every pre-existing destination; and
10. requires the execution commit to descend from exact reviewed implementation commit
   `a7ca7475177aee60126e39c631d61e3d9453ca85`.

No scientific logic, provider lifecycle, model route, budget, deferred limitation, or
cleanup policy changed.

## Fresh private V2 binding

Public-safe identity only:

- Alias: `t07-bounded-binding-67eceae4caa9`.
- SHA-256: `5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b`.
- Bytes: 2,660.
- Schema version: `0.3.0`.
- Ruleset pattern: `t07-bounded-ruleset-v1`.
- Baseline: `l2m-firewall-baseline-b0ef71115811`, semantic SHA-256
  `b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764`.
- Canonicalizer/parser: `t07-firewall-canonical-v1` /
  `t07-firewall-response-v2`.
- Restoration: `l2m-firewall-restoration-50ca7febe9f1`, payload/seal SHA-256
  `50ca7febe9f160ada862371376485ea2ece11b373d25179ccd578d9c7acd42b8`.

The fresh local binding and local seal are regular, no-follow, user-owned, mode 0600,
outside Git, and retained. Their private locator is independent of and not derivable
from the public alias or binding SHA. The one-way external bundle was written through
held no-follow descriptors to the approved APFS/UTDM archive, fsynced, atomically
finalized, reread, and verified byte for byte and by SHA-256. No internal fallback
occurred. The private locator, paths, local-seal identity, nonce, CIDR, rule values,
ruleset name, decision values, and provider IDs are deliberately absent from this
record.

## Boundary

This turn made zero Lambda, OpenAI, public-IP, or other external request; read no API
key; made no cloud or console mutation; allocated no paid compute; and used no SSH,
Jupyter, container, browser, SiRA condition, or scientific execution. V2 remains
`authorized: false` pending a new exact-commit authorization.
