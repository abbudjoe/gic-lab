# T09 V11 stopped model-metadata contract conflict

V11 is immutable operational provenance, not an empirical attempt. Its
Category 3 transaction completed exactly one authenticated OpenAI model
metadata GET and six read-only Lambda GETs. It made zero Lambda launch POSTs,
incurred zero paid Lambda cost, made zero task model calls or browser actions,
and materialized zero empirical attempts. No credential was exposed.

The transaction stopped before Lambda launch because the external pre-Lambda
control plane owned the one-request allowance while the bound host runtime
would call `model_metadata_preflight()` again during runtime qualification.
Allowing two GETs would have contradicted the frozen contract, so V11 was
stopped rather than reauthorized.

The retained private conflict evidence is preserved by exact identity only:
2,939 bytes and SHA-256
`03a3de457592b2d1e33e3c703d1ffd44abe13bcd8c99b597ac2822d1eef997be`.
Credential material and the private filesystem location are intentionally not
copied into public artifacts. The stopped transaction is not reinterpreted as
an empirical attempt, and its authorization, plan, and run identities are not
reused.

The successor repair preserves one request and changes ownership, not the
scientific contract: the local gate seals a canonical receipt, the provider
binds its semantic SHA-256 before any Lambda POST, and the host validates it
offline.
