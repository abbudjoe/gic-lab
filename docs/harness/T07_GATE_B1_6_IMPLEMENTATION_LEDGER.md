# T07 Gate B1.6 implementation ledger

Status: **in progress; Gate B2a installation authority blocked**

Source contract: `T07_GATE_B1_6_DOCKER_STORAGE_QUALIFICATION.md`, SHA-256
`52d05ce39998f1a0ff81c7bbc23d936d1a61e1d709c0adafdfd07b7fb0279e60`.

Baseline: clean `phase-1/sira-smoke` commit
`e224e781e752869041c78a3e93687aaa5d8c6430`.

## Definition of done

| ID | Required outcome | Status | Evidence |
|---|---|---|---|
| T07-B16-01 | Preserve branch ancestry, Gate A/B1/B1.5 evidence, locked science, and superseded records. | met | Starting checks and locked-file hash regression. |
| T07-B16-02 | Perform no prohibited Docker, browser, network, API, secret, SiRA, cloud, or cleanup action. | met | Local source inspection, read-only host inspection, mocks, and bounded temporary fixtures only. |
| T07-B16-03 | Enforce the external max(150 GiB, 20%) floor before and after storage-producing actions. | partial | Typed exact arithmetic and boundary tests implemented; no action executed. |
| T07-B16-04 | Derive and approve a source-backed numeric Mac mini operational floor. | blocked | Only DMG and retained evidence-cap terms are exact; six required terms remain unknown. |
| T07-B16-05 | Bind exact dedicated external paths and an internal active-attempt root. | met | Typed path roles and exact constants under new `/Volumes/Macintosh HD - Data/GIC-Lab`. |
| T07-B16-06 | Verify APFS, writable/unlocked state, both UUIDs, UTDM transport, and exact mount. | met-control-plane | Structural diskutil/APFS-list parser and mismatch tests; live B2a qualification not run. |
| T07-B16-07 | Reject symlinks, path escape, internal placement, missing/renamed storage, stale guards, and fallback. | met-control-plane | Descriptor-relative `O_NOFOLLOW` traversal, exact-role validation, single-use guard token, negative tests. |
| T07-B16-08 | Record and bound the `noowners` residual risk without changing volume ownership settings. | met-design | Qualification decision; no ownership mutation. |
| T07-B16-09 | Bind currently reverified official Docker 4.85.0 build 235549 metadata. | blocked | Retained 2026-08-09 official observation only; current-turn network verification prohibited. |
| T07-B16-10 | Install only the selected build without update/version substitution. | blocked | Version-specific supported first-start/update controls are not retained locally; no install occurred. |
| T07-B16-11 | Separate user-only terms, GUI, privilege, and reconnect actions. | met-design | Distinct typed plan actors and required user-only action validation. |
| T07-B16-12 | Prove external disk placement and default internal inactivity mechanically. | met-design / blocked-live | Minimized settings, exact file/device, engine, default-path, and reconnect evidence contract; version-specific evidence source/path remains blocked. |
| T07-B16-13 | Enforce bounded stop/disconnect/remount/reopen lifecycle ordering. | met-control-plane | Typed reconnect state machine with skip/replay/identity mismatch tests. |
| T07-B16-14 | Keep bounded active evidence only on the Mac mini. | met-design | Exact internal root and inherited 67,108,864-byte cap. |
| T07-B16-15 | Close, fsync, hash, manifest, and make attempt sources immutable. | met-control-plane | Bounded local seal implementation and tests. |
| T07-B16-16 | Copy sealed evidence one-way, verify every destination hash, and retain source. | met-control-plane | Fresh staging, `O_EXCL` writes, fsync, atomic rename, verification/copy record, no deletion. |
| T07-B16-17 | Produce a fresh B2a plan with arrays, caps, zero retry, commit and SHA binding. | pending | Final plan follows the reviewed implementation commit. |
| T07-B16-18 | Reject stale combined B2 authority and separate B2a from B2b. | met-control-plane | Dedicated schema/loader, fixed superseded ID/SHA, negative tests. |
| T07-B16-19 | Produce a requirements-only B2b stub without executable authority. | pending | Required document follows. |
| T07-B16-20 | Pass focused tests, validation, full check, independent review, repairs, and post-review check. | pending | Closeout commands/results follow after review. |
| T07-B16-21 | Update all required documents, active plan, and storage policy without overstating suitability. | pending | Documentation set in progress. |
| T07-B16-22 | Commit reviewed work with a non-circular binding and leave a clean branch. | pending | Implementation commit followed by packet-binding descendant. |

`met-control-plane` means deterministic local control-plane behavior is tested. It is
not evidence that Docker, an APFS reconnect, or kernel containment worked live.

## Pre-edit gates

- Branch: `phase-1/sira-smoke`.
- HEAD: `e224e781e752869041c78a3e93687aaa5d8c6430`.
- Worktree: clean.
- Ancestry: the B1.5 commit is the exact starting HEAD.
- Focused Gate A/B1 regression:
  `PYTHONPATH=src uv run --no-sync pytest -q tests/test_sira_container.py tests/test_harness_schemas.py`
  — 84 passed.
- `make validate` — passed.

## Closeout evidence

Pending final review and binding. Gate B2a, Gate B2b, Gate C, and live T07 remain
unauthorized.
