# T07 bounded smoke user runbook

Status: **future user-operated procedure; unauthorized now**

Use this runbook only after a fresh authorization names the exact final clean commit
and plan below. Use the argument arrays in the plan directly; never reconstruct them as
shell strings, improvise a retry, or substitute a resource.

## Bound identities

- Plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V1`, 48,677 bytes, SHA-256
  `f469d25e3527a5f0bc678a52d458ec29dcb3d27342f045ed54f1ff0c18e813d3`.
- Contract: SHA-256
  `bed93df0df4f9ece7a90ca713385bf6f2ea0e37b2fa618236bc563d612660d82`.
- Local supervisor: SHA-256
  `ab206d00bbd8e7ba8fe69e1c08de350184bab5c821ecaa526efeb2ba23e69951`.
- Local hash-first bootstrap: SHA-256
  `bab1a3f59dccc8becbe372d2a2c7d92643164cefc86ed6659d8dceba0ba82f6c`.
- Reviewed implementation commit:
  `4c15b8aaf61a260dbdc0063538a2d8500ac95a45`.

## Ordered procedure

1. Remain present for the whole supervised window. Keep the Lambda termination
   control visible and credible. The 3,600-second authorization/provider timer begins
   when the local authorization is materialized, not at launch; plan to click
   terminate no later than 3,300 seconds after materialization.
2. Run the plan's `materialize` array once with the exact final clean execution
   commit and fresh authorization reference. It must create a fresh mode-0600
   authorization, private binding, observer state, request ledger, and summary under
   `artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0001/`. Stop if that root already
   exists or any identity, hash, permission, storage, freshness, or floor check fails.
   The exact local arrays require the repository's pinned `.venv/bin/python`; do not
   substitute macOS `/usr/bin/python3`.
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
9. Open Cloud IDE/Jupyter on that exact instance. Do not use SSH.
10. Upload the exact repository bundle, the mode-0600 authorization JSON, and the
    mode-0600 secret file to the plan's fixed paths. The secret file contains only
    `SIRA_API_KEY`, stays outside source/evidence roots, and never enters a cell,
    command, environment assignment, label, log, screenshot, or path.
11. Execute the plan's `bootstrap_argv_template` once, replacing only its declared
    placeholders with the exact plan, contract, authorization, and execution-commit
    hashes. The bootstrap must verify the source/tree, immutable patch, lock, uv wheel,
    digest-pinned Playwright base, final image ID, runtime-disk cap, and shared
    work/cleanup call meter.
12. Require the one no-network local-static-page Chromium lifecycle preflight to pass,
    including stop/kill/remove and zero owned residue.
13. Require the one authenticated metadata GET to return exactly
    `gpt-4o-2024-11-20`; verify price and budget boundaries before either condition.
14. Execute `SIRA-REACTIVE` once, then `SIRA-SIMULATIVE` once. Each gets at most one
    browser action, 120 seconds, 200,000 tokens, USD 2.00 API cost, and no retry.
15. On success, seal the complete evidence. On any post-root failure, seal the bounded
    secret-scanned partial evidence. In either case remove all four owned containers
    through immutable IDs and verify zero owned containers/networks/volumes.
16. Download the produced success or failure archive, its exact identity JSON, and
    `TERMINATE_REQUIRED.json` into the fresh local inbound root. The local verifier
    must validate canonical stored ZIP paths, the complete member/manifest/hash set,
    decoded secret absence, and—on success—the pair budget, command diff, normalized
    events, regulation decisions, and compute closeout. Do not edit or unpack over an
    existing root.
17. Click **Terminate** for the exact bound instance regardless of workload outcome.
18. Run `observe_termination` once. Its one GET must prove the bound instance terminal
    or absent before changing the security resources.
19. Delete only the bound owned regional ruleset, and restore the exact sealed global
    baseline if it was changed.
20. Run `observe_terminal` once. Its two GETs must prove owned-ruleset absence and the
    exact global-baseline semantic hash.
21. Run exactly one local archive array: `archive_complete` only for a validated pair,
    otherwise `archive_failed`. It must use held no-follow APFS/UTDM descriptors,
    reread every destination, verify every SHA-256, fsync, atomically finalize, retain
    the local source, and use no internal fallback. The 128-file maximum is exactly
    125 copied payload files plus three seal files. Then stop; do not interpret.

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
