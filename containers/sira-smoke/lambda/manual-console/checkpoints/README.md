# Gate L2M checkpoint templates

These 13 files are inert public user-action templates. They are not valid checkpoints and grant
no authority: angle-bracketed values must come from the ignored, sealed private run
binding, and every file must be freshly created mode `0600` inside its observer-issued
300-second challenge window.

The user must never add a raw provider ID, source IPv4, public-key fingerprint,
Jupyter URL/token, secret, or private path. The observer validates and consumes each
checkpoint once through the held no-follow reader and fsync-backed consumption ledger.
The offeredness checkpoint precedes every mutation; launch configuration selection
precedes launch-window arming; bundle upload precedes the one qualification command.
Instance binding and terminal-state verification are observer-only durable journal
receipts, so they deliberately have no user checkpoint template.

Templates remain deliberately non-schema-valid until their private placeholders and
current timestamp are filled during a separately authorized run.
