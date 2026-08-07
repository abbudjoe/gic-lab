# GIC Agent Claim Extraction Draft

Status: **reconciled against the independent human reading and hash-pinned GIC v1 source**

This document preserves the original agent extraction and now records its disposition against the independent human reading. Source metadata is independently pinned in `manifests/sources.yaml`; the primary source remains authoritative. Reconciliation does not make any paper claim a locally reproduced result or approve a Phase 1 protocol.

Citation convention: 1-based PDF page, section, and equation/theorem/figure when available. Source: `SRC-GIC-PAPER`, *Critique of Agent Model*, arXiv `2606.23991v1`.

## Extracted claims

| ID | Agent interpretation | Exact source | Source evidence boundary | Review status |
|---|---|---|---|---|
| GIC-01 | Agency is distinguished by endogenous goal, identity, decision, regulation, and learning structures rather than external scaffolding. | Abstract, PDF p. 1; §2, PDF pp. 4–8 | Philosophical/design thesis; not empirically established by the definition itself. | reconciled: H-GIC-000 |
| GIC-02 | GIC has six agent factors: belief encoder `h`, goal decomposer `δ`, identity evolver `ι`, configurator `κ`, simulative planner `π_f`, and actor `α`. | §5.2, PDF pp. 24–26; Fig. 8; Eqs. (7)–(8) | Formal architectural proposal. | reconciled: H-GIC-001 |
| GIC-03 | The factorization fixes conditional variables, not internal neural implementation; structured attention is suggested while detailed end-to-end design is deferred. | §5.2, PDF p. 26, immediately after Eqs. (7)–(8) | Explicitly underspecified/future work. | reconciled: H-GIC-002 |
| GIC-04 | A persistent externally supplied goal `g` is decomposed into ordered, revisable active subgoals `g_t`. | §4.1, PDF pp. 11–12; Fig. 3; §5.2, PDF p. 25 | Proposed; companion prototypes do not establish persistent long-duration goal decomposition. | reconciled: H-GIC-003 and H-GIC-020 |
| GIC-05 | Identity is a fast-updating self-model of capabilities, constraints, affordances, and relationships, distinct from slow parameter learning. | §4.2, PDF pp. 12–14; Theorem 1; Eq. (5); Fig. 4; §5.2, PDF p. 25 | Proposal plus a conditional theorem; no empirical identity-evolution prototype. | reconciled: H-GIC-004 and H-GIC-005 |
| GIC-06 | The configurator selects plan, continue/revise-plan, direct-action, and potentially goal, identity, or learning routines. | §4.4, PDF pp. 17–19; Theorem 3; Eq. (6); Figs. 6–7; §5.2, PDF p. 25 | Planning regulation is partially demonstrated by SR²AM; goal/identity/learning routing remains proposed. | reconciled: H-GIC-008 and H-GIC-009; cached-plan input remains open |
| GIC-07 | Simulative planning proposes actions, predicts future states, evaluates them through a critic, and selects plans under uncertainty. | §4.3, PDF pp. 14–17; Theorem 2; §5.2, PDF pp. 25–26; Fig. 8 | Browser/language-space variants are reported by SiRA and SR²AM; the full grounded uncertainty-calibrated contract is not. | reconciled: H-GIC-006 and H-GIC-007 |
| GIC-08 | The actor supplies fast System-I execution conditioned on belief and plan. | §5.2, PDF p. 25; Eqs. (7)–(8) | Language/tool actions are represented in companion work; general multimodal/embodied behavior remains proposed. | reconciled: H-GIC-019 |
| GIC-09 | The world model is not an agent factor: its parameters are disjoint, it is trained for predictive fidelity, and reward gradients do not update it. | §4.3, especially Theorem 2 discussion on PDF p. 16; §4.5, PDF pp. 21–22; §5.2, PDF p. 26 after Eqs. (7)–(8) | Central proposed contract; neither SiRA nor SR²AM uses a separately prediction-trained world model. | reconciled: H-GIC-010 |
| GIC-10 | Continual learning is represented by `θ_(t+1) ~ p_λ(· | θ_t, D_μ, D_f)` and may be scheduled by the configurator. | §2.6, PDF pp. 7–8; §4.5, PDF pp. 19–22; Theorem 4; §5.3, PDF pp. 26–27 | `λ` is an abstraction, not an implemented update mechanism. | reconciled: H-GIC-011 and H-GIC-012 |
| GIC-11 | The proposed training program has component pretraining, simulative RL, and real-world deployment/refinement phases. | §5.3, PDF pp. 26–27 | Proposed program, not a completed full-GIC training run. | reconciled: H-GIC-017 |
| GIC-12 | Deployment is persistent rather than request-resetting, with cached plans, goal revision, identity updates, and interleaved learning. | §5.4, PDF pp. 27–28 | Proposed. | reconciled: H-GIC-018 |
| GIC-13 | Evaluation should cover Performance, Efficiency, and Growth (PEG). | §5.5, PDF pp. 28–29 | Paper states companion work provides initial Performance/Efficiency evidence; Growth remains future work. | reconciled: H-GIC-015 |
| GIC-14 | Training data should include observation-only, reward-labeled, action-labeled, and long-horizon goal-annotated trajectories. | §5.6, PDF p. 29 | Data proposal, not a released complete dataset contract. | reconciled: H-GIC-016 |
| GIC-15 | Terminal goal `g` is exogenous and generated subgoals remain instrumental; the formalization contains one `g`. | §5.7, PDF pp. 29–31; Eqs. (7)–(8) | Proposed safety boundary; native multiple terminal goals are not specified. | reconciled: H-GIC-020, with H-GIC-003 and H-GIC-014 |
| GIC-16 | Modularity makes failures attributable and sufficiently trained components drive harmful behavior toward zero absent a bad terminal goal. | §5.7, PDF pp. 29–31 | Safety argument, not empirical safety evidence. | reconciled: H-GIC-013 and H-GIC-014 |

## Reconciliation outcome

The human matrix uses finer claim granularity than this extraction: it separates each conditional theorem from the architectural mechanism and empirical applicability claim surrounding it. It also adds explicit falsification contracts. The agent extraction contributed three claims that were not initially isolated in the human matrix: the endogenous-agency thesis, the actor role, and the single exogenous terminal-goal boundary. All three are now represented as H-GIC-000, H-GIC-019, and H-GIC-020.

Material source issues retained after reconciliation:

- §2.5 conditions the configurator on cached plan `c_(t-1)`, while §5.2 and Equation 7 omit that input despite retaining continue/revise-plan behavior.
- Theorem 2 states only an upper reward bound, while Appendix B invokes absolute Simulation-Lemma bounds that appear to require nonnegative or absolute-bounded rewards.
- Figure 8 and §5.3 expose a separately trained critic, but the six-factor equations do not make the critic a seventh factor or explicit planner input.
- The formal model contains one exogenous terminal goal, while §2.5 mentions prioritizing competing objectives without defining a goal portfolio.

## Theorem caution

These cautions were retained after human and source reconciliation:

- **Theorem 1:** assumes identity revisions improve the self-model/decisions and slow updates are monotone; it does not demonstrate an identity updater.
- **Theorem 2:** assumes bounded world-model total-variation error and selective fallback to a baseline within an error margin; it does not establish that language predictions satisfy those assumptions.
- **Theorem 3:** gives a horizon bound under reward-aligned cost and discounted finite-horizon model-predictive control; it does not validate a learned configurator.
- **Theorem 4:** gives a simulation-error-dependent value bound; it does not demonstrate self-scheduled continual learning.

## Companion boundary

Reconciled conclusion: SiRA is best treated as the externally modular System-II reference, SR²AM as the learned/internalized System-I+II+III planning reference, and full GIC as a proposal. Neither companion establishes persistent identity, a separate prediction-trained world model, configurator-directed deployment learning, Growth evaluation, or full multimodal/embodied GIC.

## Questions carried forward

1. **Internalization:** unresolved empirically. The paper defines an architectural and philosophical distinction, but a behavioral claim requires matched learned-internal, external, and hybrid controls.
2. **Theorem applicability:** unresolved empirically. The conditional proofs do not show that learned open-world components satisfy their assumptions, and Theorem 2 has a reward-bound ambiguity recorded above.
3. **One terminal goal:** resolved as the paper's formal and safety contract, not as evidence that it is sufficient or the only possible architecture. Native multiple-terminal-goal semantics remain unspecified.
4. **Typed versus latent state:** remains an implementation and experimental-design decision. The first experiment should expose typed states needed for causal intervention and attribution rather than treating external representation as a disqualifier by definition.
5. **First causal test:** intentionally unresolved. Reconciliation may recommend candidates, but selecting and approving the Phase 1 hypothesis requires a separate decision.
