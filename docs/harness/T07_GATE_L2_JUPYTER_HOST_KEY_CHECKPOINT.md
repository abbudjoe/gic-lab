# T07 Gate L2 Jupyter host-key checkpoint

Status: **blocked design record; non-executable; unauthorized and unexecuted**

Gate L2.0 ended in `blocked-human-or-source-decision`. No authoritative supervisor,
executable plan, or instance exists, so the user must not perform this step. The
proposed V1 run/checkpoint identities below are rejected design provenance and must
not be reused. A future source-backed implementation must issue fresh identities and
instructions after a new review and authorization.

This checkpoint supplies an independent first-contact ED25519 host-key fingerprint
for exactly one future Gate L2 instance. It is not TOFU: the fingerprint comes from
inside the owned instance through the user's authenticated Lambda console/Jupyter
session, then is compared with one bounded network discovery before SSH.

## Preconditions

The future supervisor must already have:

- one authorized Gate L2 run and one immutable provider instance ID;
- an active instance with one provider-reported public IPv4;
- the global and regional SSH-only `/32` rules verified;
- a monotonic checkpoint deadline no later than 600 seconds after the wait begins;
- proof that the checkpoint path did not exist before the wait;
- one fresh 64-lowercase-hex challenge minted by the supervisor after that absence
  proof and supplied privately to the user;
- no SSH or `ssh-keyscan` attempt yet.

## Exact user-only action

1. In the authenticated Lambda console, open Cloud IDE/Jupyter for the exact owned
   instance shown by the Gate L2 supervisor.
2. In that instance's Jupyter terminal, run only:

   ```text
   sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
   ```

3. Outside Git, create
   `~/.config/gic-lab/t07/l2-host-key-checkpoint.json` as a fresh regular file owned
   by the current user with mode `0600`; do not use a symlink.
4. Set `checkpoint_challenge_nonce` to the exact challenge supplied by the supervisor;
   do not mint or reuse a different nonce. Copy the exact owned provider instance ID,
   the ED25519 `SHA256:` fingerprint, and an exact UTC observation timestamp inside
   the supervisor's current wait window. Do not paste any private value into Codex
   chat, Git, the notebook, or a shell argument.
5. Use this structure:

   ```json
   {
     "schema_version": "0.1.0",
     "checkpoint_id": "CHECKPOINT-T07-L2-0001",
     "checkpoint_challenge_nonce": "<supervisor-provided-64-lowercase-hex>",
     "run_id": "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001",
     "provider_instance_id": "<exact-owned-instance-id>",
     "algorithm": "ssh-ed25519",
     "fingerprint": "SHA256:<exact-jupyter-fingerprint>",
     "observed_at_utc": "<exact-UTC-timestamp>",
     "observation_method": "lambda-authenticated-jupyter-terminal"
   }
   ```

The governing schema is
`schemas/t07-lambda-l2-host-key-checkpoint.schema.json`, SHA-256
`92b7b97d0e56ba3299049752c32190d415ee12696e2ed916c37d15f5cd7ef97e`.

## Supervisor decision

The supervisor opens the file through a held no-follow descriptor and requires exact
owner/mode/schema/run/instance/algorithm, the one current supervisor challenge, and
an observation timestamp inside the same bounded wait. Reuse, early creation,
absence, lateness, malformed data, or mismatch performs no SSH and proceeds
immediately to exact-ID provider termination and firewall cleanup.

On a valid checkpoint, the supervisor performs at most one:

```text
/usr/bin/ssh-keyscan -T 10 -t ed25519 <owned-instance-public-ipv4>
```

The target address comes from the private owned-instance binding and is not printed
publicly. The supervisor computes the standard SHA-256 fingerprint in process and
requires exact equality. Only equality permits a fresh run-owned private
`known_hosts` file and strict SSH. Discovery mismatch, multiple keys, malformed output,
or timeout blocks SSH and triggers termination/cleanup.

The checkpoint file, fingerprint, instance ID, discovered key line, and `known_hosts`
remain private evidence. No fingerprint or raw host identity enters Git or notebook
output.
