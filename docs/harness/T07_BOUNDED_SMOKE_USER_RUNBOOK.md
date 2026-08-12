# T07 bounded smoke V2 user runbook

Status: **future user-operated procedure; unauthorized now**

Use this runbook only after a fresh authorization names the exact final clean commit
and plan below. Use the argument arrays in the plan directly; never reconstruct them as
shell strings, improvise a retry, or substitute a resource.

## Bound identities

- Plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V2`, 43,198 bytes, SHA-256
  `f0d635783d719d1c5cb5df5351eaf8f6f54e9049da1f2565e4227e66f48ef511`.
- Private security binding: alias `t07-bounded-binding-67eceae4caa9`, SHA-256
  `5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b`, 2,660
  bytes, schema `0.3.0`. Its independent locator, path, local-seal identity, and
  values remain in the protected local channel and are not derivable from the alias
  or SHA.
- Contract: SHA-256
  `fcb0b1a113b5f1c03ce123b24df9abe536b7ac561758915cdf5d340d08929ebc`.
- Local supervisor: SHA-256
  `5b2b43691288c2950ddbf9de12bf5c72d4fccf7b7a3fc04c81ea173c5f0f55a2`.
- Local hash-first bootstrap: SHA-256
  `0cd531ecd7584cb2d61caa3b0df8d6a60a82345c1f97fdddbd3c8aa6a16a9063`.
- Reviewed implementation commit:
  `a7ca7475177aee60126e39c631d61e3d9453ca85`.
- The protected human-decision seal and high-assurance baseline seal must match their
  exact published SHA-256 identities before either document is parsed; selected-field
  agreement alone is insufficient.

V1 and all `0001` bounded run identities are blocked historical evidence and must
never be replayed.

## Ordered procedure

Remain present for the whole supervised window and keep the Lambda termination
control visible. The 3,600-second authorization/provider timer begins at
materialization, not launch; terminate no later than 3,300 seconds after
materialization. Then perform exactly the plan's 23 steps:

1. Privately resolve the retained local binding and its local seal with the exact
   alias/SHA above. Supply their protected path and local-seal SHA only as the
   `${PRIVATE_SECURITY_BINDING_PATH}` and
   `${PRIVATE_SECURITY_BINDING_SEAL_SHA256}` substitutions; never print, log, or add
   either value to Git. Run the plan's `materialize` array once with the exact final
   clean execution commit and a fresh authorization reference. Before creating a run
   root, it must verify the exact local binding/seal, exact externally sealed bundle,
   directory/file modes, held volume identities, byte equality, hashes, storage
   floors, and absence of internal fallback. It then copies the verified binding and
   creates a fresh mode-0600 authorization, observer state, request ledger, and
   summary under
   `artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0002/`. Stop if that root already
   exists or any binding identity, hash, permission, storage, freshness, or floor
   check fails. Never regenerate authority from the historical L2M input.
   The exact local arrays require the repository's pinned `.venv/bin/python`; do not
   substitute macOS `/usr/bin/python3`.
2. Run `prepare_bundle` once. It must create a deterministic tracked-only USTAR
   archive with exactly 36 members: `BUNDLE_MANIFEST.json`, the plan, and all 34
   plan-bound implementation artifacts. It also emits the reviewed remote bootstrap
   separately under
   `artifacts/t07/bounded-upload/RUN-T07-BOUNDED-HOST-0002/`. The archive and
   bootstrap together are capped at 8,388,608 bytes; untracked, ignored, private,
   `.env`, `.git`, `.secrets`, and `artifacts` inputs are forbidden.
3. Run `observe_prelaunch` once. Its seven GETs must prove the exact offered
   `gpu_1x_a10`, `us-east-1`, `img-0032`, `fractal-lambda-codex`, 129-cent/hour
   price, capacity, key fingerprint, sealed global baseline, zero nonterminal
   instances, and a credible termination path.
4. In the Lambda console, apply only the privately bound temporary global IPv4 `/32`
   rule if required. Do not expose the address.
5. Create exactly the privately bound, uniquely named, same-region regional ruleset
   with its exact SSH-only rule. Do not reuse an unrelated ruleset.
6. Run `observe_security` once. Its two GETs must prove the exact temporary global
   rule and exact owned regional ruleset before launch.
7. Select exactly one `gpu_1x_a10` in `us-east-1`, image `img-0032`, no persistent
   filesystem, key `fractal-lambda-codex`, and the bound owned ruleset. Reconfirm
   price and image. Click **Launch** exactly once; never click again after ambiguity.
8. Run `observe_post_launch` once. Its one GET must bind exactly one matching active
   instance and immutable instance ID or stop for incident cleanup.
9. Run `release_bootstrap` once only after the post-launch report replays cleanly and
   the user attests that the console offered the exact bound image. The single-use
   release binds the instance observation, authorization/private binding, plan,
   execution commit, archive/manifest/bootstrap hashes, and canonical output root.
10. Open Cloud IDE/Jupyter on that exact instance. Do not use SSH.
11. Upload exactly `t07-bounded-repository.tar` to
    `/home/ubuntu/t07-bounded-repository.tar`, `t07-bounded-bootstrap.py` to
    `/home/ubuntu/t07-bounded-bootstrap.py`, the authorization to
    `/home/ubuntu/t07-bounded-authorization.json`, the release to
    `/home/ubuntu/t07-bounded-bootstrap-release.json`, and the private mode-0600
    secret file to `/home/ubuntu/.config/giclab/sira_api_key`. Created and uploaded
    outside every notebook cell and logged command, that file contains only the raw
    value assigned to `SIRA_API_KEY`, optionally followed by one newline—never an
    `SIRA_API_KEY=` prefix. It stays outside source/evidence roots, and the value never
    enters a cell, argv, label, log, screenshot, environment/configuration listing, or
    path.
12. Execute the plan's `bootstrap_argv_template` once, replacing only its declared
    placeholders. Before importing uploaded implementation code or opening the secret,
    the standalone bootstrap must verify its own hash, claim the fresh canonical root
    `/home/ubuntu/t07-bounded-output-0002`, verify the exact USTAR archive and release,
    and extract to `/home/ubuntu/t07-bounded-bundle`. That root is permanently burned
    for this run even on pre-secret failure. The bootstrap then verifies the
    source/tree, immutable patch, lock, uv wheel, digest-pinned Playwright base, final
    image ID, runtime-disk cap, and shared work/cleanup call meter.
13. Require the one no-network local-static-page Chromium lifecycle preflight to pass,
   including stop/kill/remove and zero owned residue.
14. Require the one authenticated metadata GET to return exactly
   `gpt-4o-2024-11-20`; verify price and budget boundaries before either condition.
   Every Chat Completions request must explicitly carry `service_tier="default"`,
   and every reconciled response must report `service_tier="default"`.
15. Execute `SIRA-REACTIVE` once, then `SIRA-SIMULATIVE` once. Each gets at most one
   browser action, 120 seconds, 200,000 tokens, USD 2.00 API cost, and no retry.
16. On success, seal the complete evidence. On any failure, seal the bounded
    secret-scanned normal or early-failure evidence under the already claimed root.
    Retained command events record only argv hashes, return codes, byte counts, elapsed
    time, and closed failure codes. In every case remove all four owned containers
    through immutable IDs and verify zero owned containers/networks/volumes.
17. Download the produced success or failure archive, its exact identity JSON, and
   `TERMINATE_REQUIRED.json` into the fresh local inbound root. The local verifier
   must validate canonical stored ZIP paths, the complete member/manifest/hash set,
   decoded secret absence, and—on success—the pair budget, command diff, normalized
   events, regulation decisions, and compute closeout. Do not edit or unpack over an
   existing root.
18. Run exactly one inbound verifier: `verify_inbound_complete` for a complete pair or
    `verify_inbound_failed` otherwise. Verification must finish before provider
    termination. Any actual secret derivative forces a credential-material incident
    and manual credential rotation; incomplete deletion also requires rotation.
19. Click **Terminate** for the exact bound instance regardless of workload outcome.
20. Run `observe_termination` once. Its one GET must prove the bound instance terminal
   or absent before changing the security resources.
21. Delete only the bound owned regional ruleset, and restore the exact sealed global
   baseline if it was changed.
22. Run `observe_terminal` once. Its two GETs must prove owned-ruleset absence and the
   exact global-baseline semantic hash.
23. Run exactly one local archive array: `archive_complete` only for a validated pair,
   otherwise `archive_failed`. It must use held no-follow APFS/UTDM descriptors,
   reread every destination, verify every SHA-256, fsync, atomically finalize, retain
   the local source, and use no internal fallback. The exact upload archive and
   bootstrap must appear in the external archive as
   `upload-bundle/t07-bounded-repository.tar` and
   `upload-bundle/t07-bounded-bootstrap.py`. The cap is at most 125 copied payload
   files plus three seal files (128 total); the expected complete-run set is 34
   payload files plus three seal files (37 total). Then stop; do not interpret.

## Immediate stop and incident rule

Any hard blocker stops before launch. After launch, Cloud IDE, source/bootstrap,
model/API, browser/container, budget/wall/disk/call/output, evidence download, pair
contract, observer-ledger, or archive failure ends the attempt: preserve safe evidence,
remove owned containers when possible, terminate the exact instance, verify terminal
state, and restore only the owned security resources. A provider/control-plane outage
is an incident; remain present and keep using the same manual termination control. It
does not authorize another resource or retry.

The profile expires after the first matched pair or first terminal infrastructure
failure. It authorizes no interpretation, pilot, T08, production claim, SSH, second
launch, or second condition attempt.
