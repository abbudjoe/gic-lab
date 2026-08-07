# Falsification Notes

These notes convert architectural enthusiasm into tests that could change the project direction. They are not approved protocols.

| Claim | Falsifying or weakening observation | Important alternative explanation | Minimum control |
|---|---|---|---|
| Learned regulation is useful. | It fails to improve success at matched cost or cost at matched success relative to a simple rule router. | Router sees weaker state, or model was not trained for routing. | Identical backbone, tools, observations, and total budget; random/router ablations. |
| Structured future-state planning is useful. | Equal-token unstructured reasoning matches it and shuffling predicted futures does not change action quality. | Candidate generation, not prediction, is the true bottleneck. | Fix candidates and critic; vary only prediction structure/content. |
| Language-space outputs function as a world model. | Predictions do not beat frequency/null baselines on observed transitions or are uncalibrated. | State representation omits the evaluated signal. | Predeclare typed transition targets and calibration metrics. |
| A separate world model improves agency. | Better prediction loss does not change selected actions or task success. | Planner/critic ignores the model; candidates rarely differ. | Measure action-selection sensitivity and critic ranking, not loss alone. |
| Persistent identity improves decisions. | Identity conditioning degrades calibration or creates persistent erroneous avoidance. | Updater receives biased outcomes. | Frozen policy, structured capability state, identity/no-identity and oracle-identity controls. |
| Multi-goal state improves long-horizon work. | An external queue matches it, or explicit portfolio state increases interference. | Benchmark rewards bookkeeping rather than planning. | Same tasks/resources; include unrelated goals, shared subgoals, interruptions, and conflicts. |
| Autonomous adapter learning supports growth. | Target gains are offset by retention, calibration, or safety regressions. | Evaluator overfits candidate data or is policy-coupled. | Independent evaluator, held-out retention suite, immutable rollback, and externally scheduled control. |

For every confirmatory experiment, state in advance what result would count as support, no support, mixed evidence, invalidation, or an infrastructure-invalid run.
