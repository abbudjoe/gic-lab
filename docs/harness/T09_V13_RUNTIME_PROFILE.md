# T09 V13 explicit pilot-contract runtime profile

Every active pilot identity consumer resolves one exact retained provider contract by
`provider_contract(version)` or `provider_contract_for_plan_id(plan_id)`. There is no
active/current/latest/default contract.

The local finalizer qualifier requires exactly one selector:

```text
--provider-contract V13
or
--plan-id PLAN-EXP0001-PILOT-V13
```

The selected contract owns the plan, host, attempt order, evaluator runs, image and
local-finalizer qualifications, frozen manifest, execution contract, command manifest,
control root, and evidence identities. A selected contract cannot consume another
version's execution contract, command package, authorization prefix, or metadata
receipt. V11 and V12 remain exact historical contracts rather than defaults.

V13 preserves the one-request architecture:

```text
one local authenticated metadata GET
→ canonical private receipt
→ provider final transport-boundary freshness admission
→ immediate Lambda transport
→ durable offline host validation
```

The request count is one local, zero provider, and zero host; freshness is inclusive
through 1,800.0 seconds at the provider final transport boundary; host current-time
expiry is disabled; retries are zero. This Category 1 task performs none of those live
operations.
