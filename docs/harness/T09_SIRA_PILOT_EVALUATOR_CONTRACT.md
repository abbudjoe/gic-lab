# T09 SiRA pilot evaluator contract

Status: **exact upstream evaluator pinned and offline-validated**

Machine authority:
`experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_EVALUATOR_CONTRACT.json`

## Identity and execution path

The only authorized evaluator is SiRA's FanOutQA evaluator at commit
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`. T09 copies its files byte-for-byte into
the offline fixture tree for reproducible testing; the wrapper verifies these hashes
before evaluation:

| Source file | SHA-256 |
|---|---|
| `evaluation/fanout/evaluator.py` | `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` |
| `evaluation/fanout/run.py` | `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` |
| `evaluation/fanout/utils/helpers.py` | `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` |
| `evaluation/fanout/utils/models.py` | `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` |
| `evaluation/fanout/utils/norm.py` | `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` |

The evaluator is Apache-2.0 licensed. It uses no judge model, judge prompt, provider
call, or nondeterministic field. The wrapper accepts exactly one retained session for
one exact task row, invokes the pinned code unchanged, validates the output, and
retains the input/output. Duplicate evidence fails closed. A more convenient scoring
implementation may not be substituted.

## Materialized environment

Python is 3.11.14. The direct evaluator packages are `ftfy==6.3.1`,
`rouge-score==0.1.2`, `spacy==3.8.11`, `tqdm==4.67.3`, and
`en-core-web-sm==3.8.0`, all fixed by `uv.lock`. The English model wheel SHA-256 is
`1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85` and its
package license is MIT. Its declared training provenance includes OntoNotes 5.0
(`LDC2013T19`), ClearNLP conversion, and WordNet 3.0; none of those source corpora is
redistributed by this project.

The machine contract enumerates every transitive package/version/license. The
important direct licenses are Apache-2.0 (`ftfy`, `rouge-score`), MIT (`spaCy` and
the model package), and MIT/MPL dual terms (`tqdm`). The preflight verifies the lock,
file hashes, installed versions, imports, and English-model load in a network-disabled
container. Initial dependency materialization may use only the pinned public package
sources; neither stage makes a model/provider request.

## Scoring rules

The reference `answer` may be a FanOutQA list, dictionary, Boolean, or scalar. The
evaluator extracts text from the final session-history action by its upstream
`send_msg_to_user(...)` slicing rule. Its normalization order is lowercase, ftfy text
repair, comma removal inside numbers, `en_core_web_sm` lemmatization, selected
punctuation removal, and whitespace collapse.

The pilot's normalized task score is exact upstream `acc_loose`: the fraction of
reference dictionary keys and values found using upstream word-boundary matching.
`acc_strict` is one only when all reference strings are found. ROUGE-1, ROUGE-2, and
ROUGE-L F scores are retained as secondary evaluator provenance. All evaluator
outputs are deterministic for fixed exact task/session bytes and this environment;
the model/browser attempt producing the answer remains nondeterministic.

The output conforms to `schemas/t09-sira-pilot-score.schema.json` and separates
answer production, task completion, evaluator validity/failure code, normalized score,
and exact upstream output. An evaluator exception or cardinality/hash/schema failure
produces `evaluator_valid: false` and `score: null`; it is never converted to a
scientific zero.

## Frozen evaluator behavior

The exact implementation has two task-specific behaviors that must be retained and
reported rather than repaired:

- Task A: an ordinary fully correct prose fixture scores 0.9, while a capitalization
  and punctuation normalization fixture scores 1.0. The difference comes from
  context-sensitive lemmatization of “Drew.”
- Task B: a fully correct six-film/six-currency-value fixture scores 0.5. Normalized
  reference values begin with `$`, and the evaluator's exact word-boundary regular
  expression cannot match that leading symbol. The effective task ceiling is 0.5.

These are offline fixture results about evaluator behavior, not pilot outcomes. Scores
are therefore reported at task level only; no cross-task effect or superiority
estimate is authorized.

## Offline fixture result

`tests/test_t09_sira_pilot.py` covers clearly correct (0.9), clearly incorrect (0.0),
partial (0.3), malformed output (score 0.3 but no valid answer/completion), missing
answer (0.0, incomplete), evaluator exception (invalid/null), duplicate evidence
(invalid/null), normalization edge (1.0), and Task B's correct fixture (0.5). All pass
offline with the exact evaluator and no model, provider, browser, SiRA condition, or
FanOutQA task execution.
