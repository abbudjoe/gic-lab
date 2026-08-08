# Open Questions

Unresolved items are recorded here instead of being silently decided during implementation.

## Must resolve before licensed reuse or formal publication

- **OQ-001 — Repository licenses:** Choose separate or compatible licenses for source code and authored research content. The repository is publicly visible, but no reuse license is granted until this is resolved.
- **OQ-002 — Public identity/contact:** Decide the author name, contact address, and citation metadata for formal publication.
- **OQ-003 — Custom domain:** Decide whether the public notebook should remain at its GitHub Pages URL or use a custom domain.

## Resolved publication infrastructure

- **OQ-011 — Pages activation:** Resolved 2026-08-06. GitHub Pages uses GitHub Actions and the first deployment passed at <https://abbudjoe.github.io/gic-lab/>.
- **Repository hosting:** Resolved 2026-08-06. The public canonical repository is <https://github.com/abbudjoe/gic-lab>.

## Phase 1 artifact-execution dispositions

- **OQ-004 — Primary hypothesis:** Resolved for EXP-0001 on 2026-08-08. The locked exploratory comparison is exactly SiRA simulative versus matched reactive behavior.
- **OQ-005 — Upstream execution pins:** Resolved for the first SiRA smoke: use a clean external workspace at the pinned SiRA commit, bind its filesystem/tree identity before authorization materialization, and do not vendor or add a submodule during T07.
- **OQ-006 — Evaluation subset:** Resolved for EXP-0001. The smoke is one locked open-ended query pair; the later pilot is two preregistered FanOutQA pairs with fixed order, estimand, retry, exclusion, and validity rules.
- **OQ-007 — Budget equivalence:** Bounded for EXP-0001. Report tokens, model calls, tool calls, browser actions, wall time, and dollars per condition; do not claim matched-budget mechanism attribution until separate controls exist.
- **OQ-008 — External services:** Bounded for the SiRA smoke by the declared OpenAI model substitution and pinned local browser stack. The exact provider/model still requires current-turn authorization, and T07 must stop if runtime identity, privacy, or finite budget enforcement cannot be verified. Later SR²AM service selection remains a T11 gate.

## Must resolve before public evidence release or later paid compute

- **OQ-009 — Data release:** Decide which traces can be public and what redaction/licensing is required. This blocks public raw-trace release, not access-controlled smoke capture.
- **OQ-010 — Lambda credits:** Verify the specific credit terms and expiry before planning Lambda spend. This is a T11/T12 gate and does not authorize credential access or block the local/API SiRA smoke.

## Must resolve before later GIC architecture work

These questions do not block the first SiRA artifact execution. They become blockers
when later work implements, extends, or makes scientific claims about the affected GIC
architecture contracts.

- **OQ-012 — Configurator state contract:** Resolve whether cached plan `c_(t-1)` is an explicit configurator input, as in §2.5, or must be encoded inside belief, as implied by §5.2 and Equation 7.
- **OQ-013 — Theorem 2 reward bound:** Determine whether the theorem intends nonnegative rewards or `|r| <= R_max`; the statement gives only an upper bound while Appendix B uses absolute Simulation-Lemma bounds.
- **OQ-014 — Critic ownership:** Decide whether the first GIC implementation treats the separately pretrained critic as an explicit planner dependency, a planner submodule, or an external evaluator without mislabeling it as a seventh paper factor.
- **OQ-015 — Multiple terminal goals:** The paper formalizes one exogenous `g` but discusses competing objectives. Define authority, conflict, and safety semantics before extending the architecture to a terminal-goal portfolio.

## Nonblocking Phase 0 choices

- The notebook uses static pages rather than executable analysis cells in Phase 0.
- Python 3.11 is the initial tooling floor.
- Unknown manifest facts remain `null` with an explicit verification state.
