# T07 Gate L2 launch-recovery human decision packet

Status: **manual-console-launch-required; automated decision path retired; Gate L2
unauthorized**

Date: 2026-08-10

This packet preserves the private-decision surface designed for the now-terminated
automated API-launch path. It does not ask the user to materialize that decision and
does not authorize Lambda access, firewall mutation, instance launch/termination,
paid compute, SSH, container use, model/browser/SiRA work, or scientific execution.

## Preserved, non-authorizing decision surface

The repository template is:

`containers/sira-smoke/lambda/T07_L2_LAUNCH_RECOVERY_DECISION_TEMPLATE.json`

The private destination is:

`~/.config/gic-lab/t07/l2-launch-recovery-decision.json`

Codex did not create or edit that file. The repository template remains deliberately
invalid and records the fields the automated design would have required:

```text
approve_unique_marker_discovery
approve_terminate_all_exact_full_marker_matches
approve_no_launch_retry_after_possible_send
approve_manual_console_fallback
acknowledge_provider_control_plane_outage_residual_risk
manual_console_fallback_operator = user
manual_console_response_window_seconds = 900
decision_nonce
```

If the retired design had been eligible, a completed file would have needed to be a
current-user-owned, no-follow regular file, validate against
`schemas/t07-lambda-l2-launch-recovery-decision.schema.json`, and receive a separate
private seal. It was not materialized. The user should not create it now: no value in
that file closes the missing authoritative supervisor/watchdog composition.

## Exact residual-risk acknowledgment

The Lambda API does not document launch idempotency. A unique name/hostname/tag marker
plus prelaunch zero-match check and exact-ID discovery provides strong ownership
evidence but cannot guarantee cleanup during a prolonged Lambda API and console
outage, Mac power/network loss, or simultaneous supervisor/watchdog failure. In those
cases a billable instance may remain until control-plane access is restored.

Approving the preserved template would not authorize Gate L2 and would not make the
automated design executable. There is no executable plan ID, path, byte count,
SHA-256, or authorization block.

## Historical meaning of each field

| Field | Exact effect |
|---|---|
| `approve_unique_marker_discovery` | Allows full-conjunction list/detail discovery after the only launch send; partial markers remain untouchable |
| `approve_terminate_all_exact_full_marker_matches` | Allows exact-ID termination of up to four independently detail-revalidated full matches if the provider anomalously duplicates one launch |
| `approve_no_launch_retry_after_possible_send` | Burns the marker and run identity at send-started, even if no response is observed |
| `approve_manual_console_fallback` | Requires the user to inspect the Lambda console for the exact private marker during the 900-second incident window |
| `acknowledge_provider_control_plane_outage_residual_risk` | Accepts that automated cleanup and the USD 2.00 nominal ceiling cannot be guaranteed during the enumerated outage/failure cases |

These meanings remain provenance only. No combination of fields is accepted as
execution authority.

## Current disposition

The exact terminal state is `manual-console-launch-required`. Independent review found
that the fake-tested supervisor and watchdog pieces are not an authoritative live
recovery boundary. The template remains fail-closed with every approval `false` and
an invalid nonce placeholder. It must not be used to authorize the rejected automated
path.

A future human-operated console-launch proposal, if the user requests one, needs a
new contract, fresh plan/run identities, and fresh current-turn authorization. No
account request, secret access, mutation, paid compute, SSH, browser, container,
model, SiRA, or scientific execution occurred.
