# T07 Colima/Lima candidate record

This directory contains the non-executable Gate B1.7 source-lock and decision record.
The candidate is rejected, so this directory deliberately contains no start command,
installation plan, authorization block, profile YAML, VM definition, or executable
Gate B2a plan.

`candidate-decision.json` records the exact audited artifacts and machine-checkable
blockers. `source-observations.json` retains the commit-qualified Lima-key sources and
signed Docker Engine release identities that drive the rejection. Their SHA-256
values are recorded in the Gate B1.7 decision and authorization packet.
Historical Docker Desktop plans remain outside this directory as blocked provenance.

Nothing here authorizes installing Colima, Lima, Docker, Buildx, a VM image, a
container image, or any dependency; starting a VM/container/browser; accessing a
secret; or executing either SiRA condition.
