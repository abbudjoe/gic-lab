# T09 V12 runtime profile

V12 uses the same scientific package and pair command semantics as V11 with
fresh unauthorized identities. Its model-metadata control-plane contract is:

```text
local pre-Lambda request: 1
provider launch request: 0
host runtime request: 0
receipt required: true
receipt replay allowed: false
```

The host receives the provider-bound receipt and expected semantic SHA-256.
It validates the exact V12 package, plan, host, authorization, model endpoint,
counts, and pre-launch timestamp ordering offline, then writes an
acknowledgement containing only safe identity/count fields and the receipt
hash. It has no fallback to the historical network preflight.

V12 remains `authorized: false`, `execution_allowed: false`,
`cloud_mutation_allowed: false`, `paid_compute_allowed: false`,
`live_qualification_performed: false`, and `pilot_executed: false`.
