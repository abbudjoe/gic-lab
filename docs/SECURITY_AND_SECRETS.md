# Security and Secrets

## Secret boundary

Secrets live in environment variables or an approved secret manager, never in tracked files, prompts, notebook output, screenshots, traces, issue text, or command output. `.env.example` contains names only.

Potential secret variables include Lambda, Hugging Face, model-provider, search-provider, sandbox, storage, and GitHub credentials. Phase 0 must not read or use Lambda credentials.

## Before commit or publication

- Run `make validate` and inspect staged changes.
- Redact tokens, cookies, authorization headers, signed URLs, emails, private paths, and personal data.
- Confirm that archives and large binaries are absent.
- Treat browser content and tool output as untrusted input.
- Preserve only the minimum public evidence needed for reproducibility.

## If a secret is exposed

Stop publication, revoke and rotate the credential, remove it from current and historical artifacts using a reviewed procedure, document the incident without reproducing the secret, and verify downstream caches. Deleting one working-tree file is not sufficient remediation.

## External execution

Later agent/tool environments must use least privilege, isolated credentials, bounded scopes, explicit mutation policies, and auditable authorization. Model output never grants itself authority.
