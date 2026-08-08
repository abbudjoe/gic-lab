# SiRA Adapter Contract

The T04 adapter consumes the reviewed static contracts in `docs/audits/sira/` and
does not execute SiRA. `SiRACommandConfig` owns source-specific task and CLI fields;
the generic `RunPlan` continues to own authorization, identity, budgets, versions, and
artifact policy. `SiRAAdapter.build_command` requires separate pinned-source and
prospective attempt-output roots and returns only a `shell: false` `CommandSpec`.
The plan's `config_sha256` is the digest of the complete canonical SiRA configuration;
the mutable `gpt-4o` alias must keep `model_revision: null`, and dataset tasks bind the
exact audited or externally supplied dataset digest. Command construction verifies that
the source root is the clean Git top level at the audited commit, binds its non-Git
content tree and exact Git commit into the command digest, and the executor rechecks
the tree, Git top level, HEAD, and clean status immediately before launch.
The T04 FanOut pilot surface is deliberately limited to T01's two reviewed one-row
slices, their exact questions, and `data_root: data`; a caller cannot substitute an
arbitrary path or goal while reusing the audited dataset digest. FlightQA and WebArena
remain typed trace contexts so their audited structured artifacts can be validated, but
`build_command` refuses both because T01 defines no reviewed pilot command for either.

`assert_sira_matched_pair` first regenerates and exactly checks each command against its
own adapter, plan, config digest, and the caller-supplied source and attempt-output
owners. It then compares the pair. The assertion never infers either owner from the
command under test, so equal mutations on both sides cannot pass. The comparison permits
the source-declared job/mode differences plus one harness-owned output-root difference
required by T03's per-attempt evidence isolation. Any model, task, seed, limit,
executable, environment, working-directory, projection, or other drift fails.
The same exact source output directory is authorization-bound as an
`owned_output_root`; the generic executor independently requires it to be inside the
corresponding prospective attempt and rechecks it immediately before launch.

The audited CLI cannot enforce a finite total API cost or model-token maximum and has
an unbounded clustering retry loop. Those units are typed as
`unbounded_applicable`, so the adapter can render and dry-run the pair while the generic
executor refuses to launch it even if a caller later supplies authorization. A later
phase must add a real finite command-level control; changing authorization alone is not
enough. The audited agent and global text logs are written under the source checkout,
not the attempt. Both patterns are therefore explicit `unowned_output_patterns` and a
second independent hard preflight blocker. A later runtime wrapper must redirect or
atomically isolate those logs before live execution can become eligible.

Normalization accepts exactly one source-shaped session JSON in the adapter-owned
output directory. For WebArena, it additionally requires exactly one strict
`output.jsonl` row and reconciles its instance, goal, and result against the session and
task contract before emitting the canonical result. It reconciles the exact configured
goal, step limit, per-step goal copies, duplicate/prior actions, dataset instance
identity, and WebArena-only fields before emitting evidence. It copies structured
observations, source-named state, selected plan, requested actions, partial operational
outcome, and conditional WebArena metrics. Each emitted payload field carries its own
source path, rule, provenance, and availability status. Nonempty source warnings and
errors travel through a typed notice channel so the harness retains ownership of
warning/error control events.
It does not parse free-text logs or invent candidate actions, predicted futures, critic
scores, action results, scientific outcomes, GIC state, usage, or timestamps. Every
regular owned output file remains raw evidence, and ambiguous retries, malformed
records, symlinks, traversal, or condition/configuration mismatch are refused.

The committed fixture is explicitly `synthetic-contract-fixture`; it is neither
upstream evidence nor a run result. See `SCHEMA_GAP_REPORT.yaml` for the machine-readable
field contract and `DRY_RUN_EXAMPLES.yaml` for the matched non-executing pair.
