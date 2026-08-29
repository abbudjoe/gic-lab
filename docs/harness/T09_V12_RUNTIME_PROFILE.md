# T09 V12 one-request runtime profile

V12 changes one control-plane ownership contract and no scientific field.

```text
one local authenticated metadata GET
→ canonical private receipt and semantic SHA-256
→ durable provider Phase A preparation
→ final provider Phase B receipt reread and fresh clock admission
→ immediate single Lambda transport send
→ source-bound host copy and durable offline validation
```

The local CLI accepts only a current-user-owned, single-link, mode-0600,
no-follow dotenv containing exactly one `OPENAI_API_KEY` assignment. It has one
injectable GET transport for
`https://api.openai.com/v1/models/gpt-4o-2024-11-20`; it has no retry,
redirect, pagination, completion, Lambda, browser, or scientific path.
Authorization state is exclusively reserved before the send and durably marked
consumed after the send attempt. Either state rejects replay.

The receipt is canonical JSON at an absolute fresh mode-0600 path. Held
descriptor and path identities, owner, type, link count, exact mode, bounded
size, duplicate fields, canonical bytes, all immutable bindings, and timestamp
ordering are checked. Receipt and authorization-overlay semantic hashes exclude
credentials, headers, account identifiers, and extension fields.

Provider Phase A validates immutable bindings, safely copies the exact receipt,
prepares the encoded launch request, consumes the launch capability, and fsyncs
both `launch-intent.json` and `launch-send-intent.json`. The latter records a
send intent, not a send-start event, and is nonreplayable. Phase B rereads the
retained receipt and overlay, matches the semantic SHA, samples a new clock,
admits age less than or equal to 1,800.0 seconds, and rejects greater age. Its
next effect is `transport.send()`; no filesystem write, subprocess, sleep, or
blocking local mutation occurs between successful admission and send.
Send-start and response chronology are recorded truthfully after the attempt.

The host receives only the provider-retained source-bound receipt and expected
SHA. `DURABLE_OFFLINE` checks immutable package, plan, authorization, run,
model, endpoint, one/zero/zero/zero counts, provider-entry hash, and prelaunch
ordering. It does not construct an OpenAI transport, has no fallback, and does
not re-expire a provider-admitted receipt against current wall time.

Total metadata ownership is one local GET, zero provider OpenAI requests, and
zero host OpenAI requests. This Category 1 implementation makes no live request.

