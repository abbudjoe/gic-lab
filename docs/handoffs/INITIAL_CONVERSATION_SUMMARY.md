# Initial Conversation Summary

Status: **historical and non-authoritative**

This document summarizes the attached ChatGPT discussion that motivated the repository. It is not a project specification, source citation, spending authorization, or empirical record. Current control authority resides in `AGENTS.md`, approved repository decisions/policies, and the active execution plan; scientific claims must be checked against pinned primary sources.

## Decisions and rationale carried into Phase 0

- Start with a digital, instrumented agent and preserve substrate-neutral interfaces; consider simulated and physical embodiment only after robust digital evidence. Digital environments offer better observability, replay, reset, counterfactual execution, and rollback.
- Reproduce released SiRA and SR²AM mechanisms before major architectural extension, but do not require exhaustive 30B/RL replication before testing a causal hypothesis.
- Treat SiRA as the external modular simulative-planning reference and SR²AM as the learned/internalized planning-regulation reference. Full GIC remains broader than either.
- Begin scientific innovation once a stable, cost-controlled causal baseline exists, not after perfect benchmark-score reproduction.
- Prioritize multi-goal persistence and calibrated identity before autonomous weight changes; introduce a separately evaluated world model before relying on simulated experience for learning.
- Begin continual learning with versioned adapters, independent evaluation, canary promotion, and rollback; keep terminal goals, permissions, safety boundaries, evaluator roots, and rollback outside unrestricted self-modification.
- Use one public monorepo with a generated Quarto lab-notebook site, while keeping raw private notes and large artifacts outside Git.
- Communicate publicly through durable notebook updates and selective social summaries rather than treating daily X posts as the scientific record.

## Working hypotheses from the discussion

- Existing transformer backbones may be sufficient neural primitives for GIC, but a learned control architecture, persistent typed state, distinct training objectives, and an execution substrate are still required.
- The scientifically important boundary may be learned versus hard-coded, persistent versus stateless, calibrated versus narrative, and outcome-trained versus prompted—not merely “inside” versus “outside” one checkpoint.
- The strongest early contribution may be a controlled map of when learned regulation and future-state prediction improve decisions, including negative or inconclusive results.

These remain interpretations pending the human/source reconciliation.

## Provisional implementation sequence

1. Bootstrap research control infrastructure.
2. Audit exact papers, repositories, checkpoints, licenses, and execution requirements.
3. Reconcile an independent human reading with the agent claim extraction.
4. Run CPU/mock contract tests.
5. With explicit approval, perform one 8B model-serving smoke.
6. Pilot reactive, always-plan, and regulated-plan comparisons.
7. Freeze a reference baseline before one isolated extension.

## Historical resource estimates

The conversation discussed—not verified or authorized—the following planning ranges:

- one 8B agent/checkpoint as the initial scale, with a matched 8B base control;
- no foundation-model pretraining from scratch;
- about 100–200 development tasks, 400–800 confirmatory unique tasks, and 1,500–4,000 total trajectories across conditions/repetitions;
- optional SFT pilots of roughly 800–3,200 structured examples;
- roughly 200–400 H100-equivalent GPU-hours for the first reproduction/baseline envelope;
- an indicative USD 2,500 compute authorization envelope, with about USD 4,000 of Lambda credits reported as available;
- approximately 750 GB of local project storage as workable for Phase 0/8B adapter work, with stricter retention or later expansion for full training;
- full 8B or 30B RL reproduction as materially beyond the initial envelope.

Prices, credits, hardware availability, checkpoint sizes, and provider terms are time-sensitive and must be reverified before an approved run.

## Assumptions

- The first environment will be digital and sufficiently instrumented to compare predicted with observed transitions.
- Public communication and a navigable site are desired.
- Large artifacts will use external storage with hashes/manifests.
- The user will complete additional independent reading before approving the first scientific protocol.
- The project may use rented GPU resources later, but Phase 0 has a zero-paid-compute contract.

## Rejected or deferred alternatives

- Training a foundation model from scratch: deferred as unnecessary for the initial architectural question.
- Starting with 30B RL reproduction: deferred because cost and confounding are too high before a causal baseline.
- Starting with physical robotics: deferred because it changes perception, control, safety, data, and evaluation simultaneously.
- Starting with autonomous core-weight updates: deferred until manual reversible adaptation and independent promotion/rollback are reliable.
- Using X as the research record: rejected in favor of a durable public notebook plus selective distribution.
- Splitting code and notebook into separate repositories immediately: deferred until governance or release cadence requires it.

## Unresolved questions

The final repository licenses, public identity/domain, first causal hypothesis, benchmark subset, matched-budget definition, external services, data-release policy, Lambda credit terms, and Phase 1 authorization remain open. Canonical open items live in `docs/OPEN_QUESTIONS.md`.
