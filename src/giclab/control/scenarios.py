"""Canonical production-coupled Category 3 shadow scenario identities."""

from typing import Final

HAPPY_PATH: Final = "happy-path"
REQUIRED_FAILURE_SCENARIOS: Final = (
    "lifecycle-unsupported",
    "metadata-expired",
    "provider-entry-replacement",
    "host-preflight-replacement",
    "condition-failure",
    "raw-export-failure",
    "finalizer-failure",
    "cleanup-interrupted-resumed",
    "provider-termination-unavailable",
    "structural-privacy-finding",
    "ambiguous-provider-call-outcome",
    "known-provider-exception",
    "response-accounting-incomplete",
    "ambiguous-task-model-send",
    "cost-token-admission-stop",
)
ALL_REQUIRED_SCENARIOS: Final = (HAPPY_PATH, *REQUIRED_FAILURE_SCENARIOS)
