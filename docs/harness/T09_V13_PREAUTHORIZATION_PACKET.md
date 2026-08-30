# T09 V13 preauthorization packet

Status: **implementation complete; local fake/offline tests complete; PR review required; unauthorized**.

```text
implementation complete
local fake/offline tests complete
PR review required
merge required
no real metadata GET
no Lambda call
pilot not executed
authorization false
```

This packet is not authorization. It creates no private overlay or run root and grants
no provider, cloud, browser, SiRA, evaluator, or scientific authority.

The repair starts from merged commit
`5253b864a3a2b288ce5cf06cd60d054b4925e5cc`, tree
`2f5c6fca38196731efb204a9a9c4778a2edc7a7c`. The root cause was the shared local
qualifier importing unversioned constants derived from the V11 pilot global. Changing
that global to V12 or V13 was rejected because it would preserve the defect. V13 uses
explicit immutable provider/plan contract selection and fresh `AUTONOMOUS-0006`
identities.

The stopped V12 Lambda cost of USD `0.3796854954083761` raises the conservative prior
from USD `33.1487895873264159` to USD `33.5284750827347920`. Against the USD `90.00`
cumulative cap, the effective maximum new total is USD `56.4715249172652080`.

The V13 plan is 18,102 bytes with SHA-256
`87fbdfdb6375b4ba39f6eed2224768619ccee6b54090e43d9c84a568d2ea1957`. The runtime
profile is 14,487 bytes with SHA-256
`58159df775f8e3a30debdc327e8be29574ec68a5c34167012866382a09b75ca4`.

The EXP-0001 science remains unchanged: SiRA
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`, dated model
`gpt-4o-2024-11-20`, service tier `default`, FanOutQA November 2023 development
snapshot, tasks `7dcbbbdc7f1120cd` and `2120afba8009bad3`, exact pinned evaluator,
counterbalanced four-attempt order, zero retries after empirical entry, and descriptive
calibration only.
