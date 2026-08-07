# Phase 0 — GIC Research Bootstrap Package v0.1

Status: **successful**

Started: 2026-07-15

## Source contract

The authoritative contract for this phase is the user's 2026-07-15 instruction beginning “Use the attached ChatGPT conversation as historical design context” and ending “Do not proceed to prototype reproduction without explicit approval.” The attached conversation is historical and non-authoritative.

## Target contract

Produce a zero-GPU, zero-cloud-mutation, public research bootstrap for evaluating GIC, SiRA, and SR²AM. The repository must expose explicit research, provenance, experiment, artifact, validation, and publication contracts without claiming that any prototype or result has been reproduced.

## Scope

In scope: repository doctrine, documentation, plans, schemas, manifests, CPU-safe validation tooling and tests, a Quarto notebook, CI/Pages workflows, source reading artifacts, and the historical handoff summary.

Out of scope: cloud provisioning or mutation, Lambda credential access, paid compute, checkpoint downloads, files larger than 1 GB, prototype or benchmark execution, training or fine-tuning, and Phase 1 protocol approval.

## Definition of done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| DOD-01 | A concise root `AGENTS.md` maps the repository, states authority, lists commands, and encodes scientific-integrity and versioning rules. | File inspection plus documentation-link validation. | met |
| DOD-02 | All ten required repository policy/research documents exist, are cross-linked, distinguish facts from estimates, and record ambiguities. | Required-path validator and link check. | met |
| DOD-03 | The execution-plan system is self-contained, and this plan records DoD, implementation mapping, progress, decisions, and evidence. | `docs/PLANS.md` and this ledger. | met |
| DOD-04 | The experiment registry, `EXP-0000` template, and experiment/artifact/transition JSON Schemas exist with typed invariants and validation tests. | Schema validation tests and CLI validation. | met |
| DOD-05 | Model, dataset, source, artifact, and compute manifests carry version/revision, commit, SHA-256, license, provenance, storage, and verification fields without invented values. | Manifest validator and tests. | met |
| DOD-06 | A searchable Quarto notebook provides status, research, experiment registry, weekly notes, decisions, failure analyses, and explicit result-status semantics. | Successful local `quarto render notebook`. | met |
| DOD-07 | A uv-managed Python package provides formatting, linting, typing, tests, validation, and one parity command for all local checks. | `make check` and `uv.lock`. | met |
| DOD-08 | Reading artifacts include a human template, a source-pinned manifest, and an agent draft with exact references and every interpretation marked unverified pending human review. | Required-path/content validation and source audit. | met |
| DOD-09 | The initial conversation summary is concise, historical, non-authoritative, and includes decisions, rationale, assumptions, rejected alternatives, resource estimates, and unresolved questions. | Handoff document inspection. | met |
| DOD-10 | CI and GitHub Pages workflows are present, syntactically valid, and use the same repository checks/site build as local execution. | Workflow parser plus workflow inspection. | met |
| DOD-11 | Repository hygiene prevents credentials and large research artifacts from being committed; license selection remains explicitly open. | Ignore-rule, secret-pattern, large-file, and policy checks. | met |
| DOD-12 | The complete local smoke, independent spec-conformance review, post-review smoke, and Phase 0 evidence run pass; all DoD statuses are final. | Command transcripts summarized below and reviewer result. | met |

## Implementation mapping

| Work package | Mapped DoD |
|---|---|
| Doctrine, charter, policies, handoff, and plans | DOD-01, DOD-02, DOD-03, DOD-09, DOD-11 |
| Schemas, registry, manifests, validation package, and tests | DOD-04, DOD-05, DOD-07 |
| Notebook, styles, CI, and Pages | DOD-06, DOD-10 |
| Source audit and reading artifacts | DOD-08 |
| Smoke, review, fixes, rerun, and ledger closeout | DOD-12 and every mapped item |

## Success criterion

`make check` must pass locally, including a real Quarto render, with no secrets or oversized files detected. A subagent must classify every DoD item as met and return no unresolved valid finding. The post-review `make check` must also pass. Phase 0 then stops without beginning prototype reproduction.

## Progress log

- 2026-07-15: Confirmed the selected repository root was empty and had no repository-local doctrine.
- 2026-07-15: Read the `assembly` skill, extracted this DoD before implementation, and confirmed that no cloud/GPU action is authorized or required.
- 2026-07-15: Began primary-source and bootstrap-contract audits in parallel. No repository or cloud mutation was delegated.
- 2026-07-15: Initial Python smoke stopped at `ruff format --check`; seven Python files required deterministic formatting. No later gate was credited.
- 2026-07-15: Formatting was applied; the rerun then exposed four overlong generated-content/source lines at the lint gate. Those source lines were wrapped before another full rerun.
- 2026-07-15: Formatting and linting passed; strict mypy then found the package contract incomplete because `py.typed` was missing. Added the PEP 561 marker rather than weakening type checks.
- 2026-07-15: The next type gate exposed missing `jsonschema` stubs and PyYAML's YAML 1.1 coercion of the GitHub Actions `on` key. Added typed stubs and changed the shared loader to YAML 1.2 boolean semantics instead of special-casing workflow keys.
- 2026-07-15: Unit tests reached repository validation and exposed two integration contracts: an empty `.env.example` line crossed a newline in the secret regex, and generated notebook links were checked before generation. Restricted assignment whitespace to a line and made validation generate canonical public views before checking links.
- 2026-07-15: The real site gate required Quarto. Homebrew fetched v1.9.38 but its package installer required an unavailable interactive administrator password. Switched to the official portable v1.9.38 release in ignored `.tools/` storage and taught `make site` to prefer it without changing the CI contract.
- 2026-07-15: `make check` first completed, but render logs showed Quarto skipped underscore-prefixed `_generated/`, so generated navigation targets were absent. Reclassified the site smoke as failed, moved deterministic views to `notebook/generated/`, and added a post-render HTML/link validator.
- 2026-07-15: The first clean rerun after adding rendered-link tests stopped at lint because the new test annotation lacked its `Path` import. Restored the explicit import and restarted the full gate.
- 2026-07-15: The complete pre-review gate passed and rendered twelve linked notebook pages. Visual QA in the in-app browser confirmed coherent navigation and correct zero-run status/experiment views.
- 2026-07-15: Independent spec review found no hard-constraint or scientific-integrity violation, but rejected closeout for five contract gaps: typed manifest/compute entry enforcement, an absolute local path in a public log, the exact `confirmed` evidence label, public reachability of falsification notes, and the unfinished assembly ledger.
- 2026-07-15: All five review findings were fixed with typed schemas, regression tests, public-site projection, path removal, and explicit evidence semantics. The same reviewer returned a clean rereview with DOD-01 through DOD-11 met and only the deliberately sequenced closeout work remaining.
- 2026-07-15: The first post-review smoke failed at strict mypy because the editable package's `.pth` file had acquired a macOS hidden flag and Python therefore skipped it. A nominal frozen sync considered the environment current, exposing that `make check` did not reconstruct its own import contract.
- 2026-07-15: Changed the parity gate to deterministically reinstall the local `giclab` package from the frozen environment before validation and removed the now-duplicated explicit sync step from CI/Pages workflows. This fixes the bootstrap contract rather than weakening typing or manually clearing a filesystem flag.
- 2026-07-15: A rereview correctly found that the advertised `make setup` still used the old nominal sync, leaving two environment control paths with different guarantees. Unified `make setup` and `make check` on one canonical deterministic `sync` target.
- 2026-07-15: The next rereview returned clean with DOD-01 through DOD-11 met. The only remaining work is the deterministic local evidence run and mechanical state/ledger closeout.
- 2026-07-15: The deterministic Phase 0 evidence run passed. A GPU/model scout is not applicable to this zero-compute documentation/control-plane phase, so no 1024-step or equivalent model run was attempted.
- 2026-07-15: Closed the project state as `successful`, ended the zero-use compute period, and marked every DoD item `met`. Phase 0 stops here.

## Decision log

- 2026-07-15: Treat this entire Phase 0 package as one assembly item; no Phase 1 work may begin inside it.
- 2026-07-15: Use the user's explicit Phase 0 instruction as the source contract and retain the attached conversation only as historical rationale.
- 2026-07-15: Record unknown hashes, commits, licenses, and revisions as `null`/unverified rather than fabricating provenance.
- 2026-07-15: Use `confirmed` for evidence that meets a predeclared confirmatory contract; keep `confirmatory` as the study-stage adjective and state that confirmation is scope-bound.
- 2026-07-15: A clean check must rebuild the local package import surface from the lock; a warm editable environment is not accepted as an implicit precondition.
- 2026-07-15: Environment construction has one owner: the canonical `sync` target. Setup, checks, and CI must not carry overlapping sync policies.
- 2026-07-15: Assembly scout requirement is `not applicable` for Phase 0 because the authoritative contract forbids model/prototype/GPU execution; the deterministic local parity gate is the phase evidence run.

## Evidence log

- Initial smoke: `uv lock && uv sync --all-groups --frozen && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest` — **failed** at formatting; seven files listed, later commands did not run.
- Pre-review gate: `rm -rf _site && make check` — **passed**; lock was current, formatting/linting and strict typing passed, 12 tests passed, repository validation passed, Quarto 1.9.38 rendered 12 pages, and rendered-link validation passed.
- Visual QA: served `_site` on loopback and inspected home, generated status, and generated experiment views in the in-app browser — **passed**; no prototype or experiment result was presented.
- First independent spec-conformance review — **changes required** on five findings listed in the progress log; no hard-constraint or scientific-integrity violation found.
- First rereview: independent reviewer classified DOD-01 through DOD-11 `met`, DOD-12 `partial` only for the sequenced post-review smoke/closeout, and returned **clean**.
- First post-review smoke: `rm -rf _site && make check` — **failed** at `uv run mypy` with `Can't find package 'giclab'`; no later gate was credited. Investigation found Python skipping a hidden editable-package `.pth` file.
- Second rereview — **changes required** because `make setup` still used the brittle nominal sync while `make check` used deterministic reinstall; no other finding remained.
- Recovery evidence: with the editable `.pth` deliberately marked hidden, `make setup` rebuilt the package and a fresh import succeeded; after marking it hidden again, `rm -rf _site && make check` rebuilt it and passed every gate.
- Final independent rereview — **clean**; DOD-01 through DOD-11 were classified `met`, with DOD-12 pending only this evidence/closeout sequence.
- Phase 0 evidence run: `rm -rf _site && make check` — **passed**; lock current, canonical package reinstall completed, formatting/linting passed, strict typing passed, 16 tests passed, repository validation passed, Quarto 1.9.38 rendered 13 pages, and rendered-link validation passed.
- Resource evidence: `manifests/compute.yaml` records zero cloud mutations, accelerator hours, paid cost, prototype runs, benchmark runs, and training runs for the closed Phase 0 period.
- Scout: **not applicable by source contract**; no cloud, model, prototype, benchmark, or training operation was authorized or performed.

## Next permitted phase

Phase 0.5 may audit and reconcile sources, licenses, and the human reading before any model-serving or benchmark work. It requires explicit user approval after this plan is successful.
