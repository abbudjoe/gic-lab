# Open Questions

Unresolved items are recorded here instead of being silently decided during implementation.

## Must resolve before public release

- **OQ-001 — Repository licenses:** Choose separate or compatible licenses for source code and authored research content. No repository license has been selected.
- **OQ-002 — Public identity/contact:** Decide the author name, contact address, citation metadata, and project URL to publish.
- **OQ-003 — Hosting:** Confirm GitHub organization/repository name, Pages URL, and whether a custom domain is desired.
- **OQ-011 — Pages activation:** After a remote exists, enable GitHub Pages with GitHub Actions as its source and verify the first deployment. Phase 0 validates the workflow locally but cannot claim a live deployment.

## Must resolve before Phase 1 compute

- **OQ-004 — Primary hypothesis:** Select the first single causal comparison after the human/source reconciliation.
- **OQ-005 — Upstream execution pins:** Review the pinned source commits and decide whether to vendor patches, use submodules, or clone into external workspaces.
- **OQ-006 — Evaluation subset:** Choose task families, sample sizes, repetitions, exclusion rules, and statistical estimand.
- **OQ-007 — Budget equivalence:** Define how tokens, model calls, tool calls, latency, and GPU time will be matched or reported.
- **OQ-008 — External services:** Choose search, browser summarization, sandbox, and judge providers; review costs, licenses, privacy, and version stability.
- **OQ-009 — Data release:** Decide which traces can be public and what redaction/licensing is required.
- **OQ-010 — Lambda credits:** Verify the specific credit terms and expiry before planning spend. No credential access is authorized.
- **OQ-012 — Configurator state contract:** Resolve whether cached plan `c_(t-1)` is an explicit configurator input, as in §2.5, or must be encoded inside belief, as implied by §5.2 and Equation 7.
- **OQ-013 — Theorem 2 reward bound:** Determine whether the theorem intends nonnegative rewards or `|r| <= R_max`; the statement gives only an upper bound while Appendix B uses absolute Simulation-Lemma bounds.
- **OQ-014 — Critic ownership:** Decide whether the first GIC implementation treats the separately pretrained critic as an explicit planner dependency, a planner submodule, or an external evaluator without mislabeling it as a seventh paper factor.
- **OQ-015 — Multiple terminal goals:** The paper formalizes one exogenous `g` but discusses competing objectives. Define authority, conflict, and safety semantics before extending the architecture to a terminal-goal portfolio.

## Nonblocking Phase 0 choices

- The notebook uses static pages rather than executable analysis cells in Phase 0.
- Python 3.11 is the initial tooling floor.
- Unknown manifest facts remain `null` with an explicit verification state.
