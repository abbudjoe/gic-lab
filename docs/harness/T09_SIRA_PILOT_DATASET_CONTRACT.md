# T09 SiRA pilot dataset contract

Status: **frozen for `PLAN-EXP0001-PILOT-V2`**

Machine authority:
`experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_DATASET_CONTRACT.json`

## Dataset identity

The pilot uses the archived November 2023 FanOutQA development snapshot. The official
FanOutQA file `fanoutqa/data/fanout-final-dev-nov23.json` at repository commit
`989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33` is byte-identical to the pinned SiRA
file `data/fanout-final-dev.json` at commit
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`.

| Field | Frozen value |
|---|---|
| Dataset ID | `DATA-SIRA-FANOUTQA-DEV` |
| Split | `development` |
| SiRA Git blob revision | `76ad1feb689b754bfe4e5e24d3ea371b647efa67` |
| File SHA-256 | `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288` |
| Bytes / records | 1,177,174 / 310 |
| Dataset license | CC-BY-SA-4.0 |
| License SHA-256 | `4e0fd171b79f997e1fb13111149135af19fb91028388746eda82cfee615b553c` |
| FanOutQA code license | MIT |

The exact source file is loaded and hashed before execution. A mismatch fails
preflight before empirical entry.

## Selection and exclusion

The rule is to preserve the first two records already proposed before T07/T08, with
seed 42 and no condition-outcome knowledge. T07 used only the README smoke query; T08
was offline, so neither task was empirically used for development or debugging. The
public history does not establish whether upstream authors ever used either development
row for debugging, so that field remains `unknown`; no GIC Lab use is hidden. The tasks
exercise different aggregation structures and are available from public sources without
required private data.

A record was eligible only if the pinned SiRA FanOut loader accepts it, it requires no
unavailable/disallowed private data, it can be attempted under the predeclared
30-browser-action limit, and it was not already used empirically for development or
debugging. Failure to complete within 30 actions is not a reason to replace a record.
No outcome-adaptive task substitution or exclusion is permitted.

## Frozen records

### Task A

- Stable ID: `7dcbbbdc7f1120cd`; source slice `[0,1)`.
- Text: “What is the batting hand of each of the first five picks in the 1998 MLB
  draft?”
- UTF-8 text SHA-256:
  `153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b`.
- Canonical reference SHA-256:
  `fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de`.
- Canonical complete-record SHA-256:
  `cc5c3fdeea2c1f58b6160175bd3104dbea40c290ea8b390d29413e6410d97e15`.
- Pair: `PAIR-EXP0001-PILOT-V2-TASK-A`; reactive then simulative.

### Task B

- Stable ID: `2120afba8009bad3`; source slice `[1,2)`.
- Text: “What were box office values of the Star Wars films in the prequel and
  sequel trilogies?”
- UTF-8 text SHA-256:
  `9b2b443898959b28c7408ed1ff56ebd332c9e7f2142657c11c7d09aa507ba66e`.
- Canonical reference SHA-256:
  `2ee9d892e24441d5f5bbf31b7616c1ade5977af26d22e4020f92a162fa23becb`.
- Canonical complete-record SHA-256:
  `5f5a8ad5353b839def2ffc968c36c4314bb830f11f10268f410faa37690bc129`.
- Pair: `PAIR-EXP0001-PILOT-V2-TASK-B`; simulative then reactive.

The two-row local test fixture contains only these exact canonical records and hashes
to `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9`.
It exists for evaluator testing, not as an alternative dataset release.

## Retention and release

The dataset license permits the planned research use. Task text, reference answers,
raw responses, browser traces, and screenshots are retained privately under access
control. Public raw release is blocked pending CC-BY-SA attribution/share-alike,
third-party site-content, privacy, and structural-redaction review. That is a
publication-only blocker. It is separate from the material provider-lifecycle blocker
that currently prevents any pilot authorization or execution.
