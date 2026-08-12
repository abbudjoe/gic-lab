# T07 bounded smoke V3 user runbook

Status: **future user-operated procedure; unauthorized now**

Use this runbook only after a fresh authorization names the exact final clean commit
and the exact V3 plan below. Use only the plan's fixed argument arrays; never
improvise a retry, alternate resource, or alternate secret source.

## Bound identities

- Plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V3`, 51,401 bytes, SHA-256
  `30e83897c476dbd403a55d9d128636443f9df8a787ef903665ece083e3e41a53`.
- Host/reactive/simulative runs: `RUN-T07-BOUNDED-HOST-0003`,
  `RUN-T07-BOUNDED-SIRA-REACTIVE-0003`, and
  `RUN-T07-BOUNDED-SIRA-SIMULATIVE-0003`.
- Private security binding: alias `t07-bounded-binding-67eceae4caa9`, 2,660 bytes,
  SHA-256 `5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b`,
  schema `0.3.0`. Its locator, path, local-seal identity, and private values stay in
  the protected local channel.
- OpenAI source schema: 4,411 bytes, SHA-256
  `38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4`;
  parser `giclab-strict-non-shell-dotenv-v1`; selected assignment
  `OPENAI_API_KEY`; no provider fallback and no user-managed `SIRA_API_KEY` file.
- Contract/supervisor/hash-first-bootstrap/remote-bootstrap SHA-256:
  `2ef4af297f7d1b8a577d9d6a970d5e678f4e852cd10c4dfa55fd836640f18e43`,
  `ae04aa08503366ac63fdd8a05553d63aa1ff5d6566d1cce3aafe69aa7410cc04`,
  `caa99fe938a3cb0ce67d6dae1e36866abf26f6cf72c109d1ae3ca2f2ea8e7c4d`,
  and `95b83f3ad23498f18cdb8efa90b0661713bf036f06a532ee5edb22f3fe065c4c`.
- Reviewed implementation ancestor:
  `a7ca7475177aee60126e39c631d61e3d9453ca85`.

V1/`0001` and V2/`0002` are blocked historical evidence and must never be
replayed. The protected human-decision and high-assurance baseline seals must match
their exact published hashes before either document is parsed.

## Secret-channel boundary

The Lambda observer receives only `LAMBDA_API_KEY` through its nonlogging local
channel. The OpenAI channel receives the exact repository-external `.env` path only
as private `${OPENAI_DOTENV_FILE}`. It opens that exact path through held no-follow
descriptors and strictly selects one plain, unquoted `OPENAI_API_KEY=...` assignment.

The supervisor automatically writes only the selected bytes to one fresh mode-0600
local upload file. The user uploads that filtered file—not `.env`—to
`/home/ubuntu/.config/giclab/openai_provider_key`. Local cleanup destroys the exact
device/inode before any release can be issued. The metadata child later receives
`OPENAI_API_KEY` directly; each SiRA condition child receives the same bytes only as
an ephemeral `SIRA_API_KEY` alias. `LAMBDA_API_KEY` reaches neither. No key or key hash
may enter a command line, notebook cell, environment/configuration record, label,
image, path, log, screenshot, ledger, archive, Git file, chat, or public output.

## Exact 29-step procedure

Remain present for the complete supervised window and keep Lambda's termination
control available. The 3,600-second timer starts at authorization materialization;
click termination no later than 3,300 seconds.

1. Privately resolve the retained binding and local seal. Supply only their protected
   path/SHA substitutions to `materialize`, plus the exact final clean commit and
   fresh authorization reference. The verifier must establish binding, external
   bundle, Git, storage, permission, and freshness identities before creating the
   V3 run root.
2. Run `prepare_bundle` once. It creates a deterministic tracked-only USTAR archive
   with exactly 36 members—manifest, V3 plan, and 34 implementation artifacts—and a
   separate reviewed bootstrap. The archive plus bootstrap stay within 8,388,608
   bytes. `.env`, the temporary credential, Git metadata, ignored/private files, and
   prior artifacts are excluded.
3. Run `observe_prelaunch` once. Its seven GETs must prove resource offeredness,
   129-cent/hour price, capacity, key fingerprint, sealed firewall baseline, zero
   nonterminal instances, and a credible termination path.
4. **User checkpoint:** in Lambda console, apply only the privately bound temporary
   global IPv4 `/32` restriction if required. Do not disclose the value.
5. **User checkpoint:** create exactly the privately bound unique regional ruleset
   with its exact SSH-only rule. Do not reuse another ruleset.
6. Run `observe_security` once. Its two GETs must verify both exact security controls.
7. **User checkpoint:** select one `gpu_1x_a10` in `us-east-1`, image `img-0032`, key
   `fractal-lambda-codex`, no persistent filesystem, and the bound ruleset. Reconfirm
   price/image and click **Launch** exactly once.
8. Run `observe_post_launch` once to bind one matching active instance and immutable
   provider ID.
9. **User checkpoint:** open Cloud IDE/Jupyter for only the bound instance. Do not use
   SSH.
10. **User checkpoint:** in its terminal, execute only the plan's fixed
    `remote_parent_prepare_argv`, followed by every
    `remote_parent_verify_argvs` array. Require current-user ownership, stdout mode
    `700`, canonical stdout `/home/ubuntu/.config/giclab`, and both `test ! -e` and
    `test ! -L` success for the final credential path. Stop before local secret access
    if the parent hierarchy is redirected or the target already exists.
11. Run `materialize_openai_secret` once with the exact private `.env` path as
    `${OPENAI_DOTENV_FILE}`. Never print the path or value in Jupyter or chat.
12. **User checkpoint:** upload exactly the repository archive, reviewed bootstrap,
    authorization, and generated filtered runtime file to their fixed paths. Do not
    upload the complete `.env` and do not upload a bootstrap release yet.
13. **User checkpoint:** run only `remote_file_prepare_argv`, then every
    `remote_file_verify_argvs` array. Require a regular non-symlink file, current-user
    ownership, and exact stdout mode `600`. Do not read or display the file.
14. Run exactly one local secret closeout operation. If upload and permission
    qualification are confirmed, run `cleanup_openai_secret`. If upload definitely
    did not occur, run `abort_openai_secret_not_uploaded`; if the outcome or remote
    metadata is uncertain, run `abort_openai_secret_unknown`. Every path must destroy
    the exact local device/inode and fsync its receipt. Either abort path prohibits
    release; the unknown path requires credential rotation.
15. Only after the positive-upload cleanup receipt passes, run `release_bootstrap`
    once with exact console image attestation.
16. **User checkpoint:** upload only the newly issued exact bootstrap-release file to
    its fixed path. Do not run bootstrap yet.
17. Run `attest_bootstrap_release_upload` once. Receipt failure after an attempted
    upload is an unknown remote outcome, never proof of non-upload.
18. Execute `bootstrap_argv_template` once. It verifies its own hash before importing
    uploaded code, claims `/home/ubuntu/t07-bounded-output-0003`, verifies/extracts
    the bundle, and validates source, dependencies, image, budgets, release, and held
    secret-file identity.
19. Require the one no-network local-static-page Chromium lifecycle preflight,
    removal, and zero-residue checks to pass before the credential is read.
20. Require one authenticated metadata GET to return exactly
    `gpt-4o-2024-11-20`. The metadata child receives only `OPENAI_API_KEY`; every Chat
    Completions request and reconciled response must report `service_tier="default"`.
21. Execute `SIRA-REACTIVE` once, then `SIRA-SIMULATIVE` once. Each condition receives
    only the ephemeral `SIRA_API_KEY` alias and has one browser action, 120 seconds,
    200,000 tokens, USD 2.00, one attempt, and zero retry.
22. Seal success or the maximal safe failure prefix. Scan untrusted bytes before any
    hash/retention, destroy the remote secret, remove all owned containers by immutable
    ID, and prove zero owned container/network/volume/browser residue.
23. **User checkpoint:** download the complete or failed evidence ZIP, exact identity
    JSON, and `TERMINATE_REQUIRED.json` into the fresh local inbound root.
24. Run one matching inbound verifier before provider termination. Any credential
    representation, unknown workload/accounting outcome, or incomplete cleanup stays
    unresolved and requires the typed response.
25. **User checkpoint:** click **Terminate** for the exact bound instance regardless
    of workload outcome.
26. Run `observe_termination` once and require terminal/absent provider evidence.
27. **User checkpoint:** delete only the owned regional ruleset and restore the exact
    sealed global baseline if changed.
28. Run `observe_terminal` once to prove ruleset absence and exact restoration.
29. Run `archive_complete` only for a validated pair; otherwise run `archive_failed`.
    Copy one way through held no-follow APFS/UTDM descriptors, reread/hash each
    destination, fsync, atomically finalize, retain the source, and use no internal
    fallback. The cap remains 125 payload plus three seal files; a complete V3 run has
    exactly 39 payload plus three seal files, including four nonsecret local-secret
    lifecycle receipts and the two reviewed upload artifacts, but never the temporary
    credential or a derivative. Then stop.

## Immediate stop and incident rule

Any hard blocker stops before launch. After launch, any console, upload, secret,
release, bootstrap, model/API, browser/container, budget, wall, disk, call, output,
evidence, observer, cleanup, or archive failure ends the attempt. If the local secret
exists, use only the typed identity-bound cleanup/abort capability even after expiry
or repository drift. Preserve safe evidence, remove owned containers where possible,
terminate the exact instance, verify terminal/nonbillable state, remove only the owned
ruleset, restore the exact baseline, and do not retry. Unknown release-upload or
remote-bootstrap outcomes keep OpenAI usage unreconciled; exact instance termination
can prove destruction but cannot fabricate missing billing/evidence.

The profile expires after the first matched pair or first terminal infrastructure
failure. It authorizes no scientific interpretation, pilot, T08, production claim,
SSH, second launch, or second condition attempt.
