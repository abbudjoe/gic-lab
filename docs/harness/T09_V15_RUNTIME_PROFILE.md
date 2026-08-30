# T09 V15 replacement-normalization runtime profile

Every V15 consumer selects the exact provider contract through
`--provider-contract V15` or the exact plan-ID resolver. There is no current, latest,
or implicit default, and V3 through V14 remain immutable historical contracts.

The provider-entry-failed-preempirical replacement contract has two equivalent
authority layouts:

- The direct closed-launch root contains the entry source, provisional-closeout
  source, provisional owner, closed-owner receipt, and durable cleanup journal.
- The successor retains that complete closure below
  `slot2-eligibility-source/`, with a deterministic outer `source-manifest.json`;
  the successor's own `entry-source/` remains separate.

One resolver validates either layout and reconstructs the same semantic eligibility.
The typed normalizer performs held/no-follow copying, exact byte and manifest checks,
and retained semantic revalidation before credential loading, provider traffic, or
launch-capability consumption. This applies to every closed slot below the bounded
eight-launch ceiling. Partial, unsafe, cross-version, cross-slot, changed, or
over-budget evidence fails closed.

Eligibility history is immutable and typed. A first closed slot publishes the
unsuffixed receipt. When that receipt is already bound into a replacement launch, the
newly closed slot publishes `replacement-launch-eligibility-slot-<N>.json` after
verifying the predecessor hash and exact launch capability. Current-receipt selection
uses the source-grounded entry or provisional slot and rejects duplicates, gaps,
cross-identity evidence, and filename/document disagreement. Repeated-slot host
closeout retains the authority that admitted its entry so the next launch can
reconstruct the complete source chain.

A terminal host-preflight closeout may be called again. The resume path revalidates the
retained host source, closeout receipt, cleanup-journal prefix, and exact eligibility;
it loads no credential, sends no provider request, repeats no cleanup mutation, and
rewrites no immutable evidence. Eligibility publication failure blocks replacement
without regressing verified provider absence or restored security.

V15 preserves the V14 cleanup lifecycle classifier and byte-identical handoff resume,
the sole local metadata GET and 1,800-second final-transport freshness boundary,
mixed-dotenv selection, zero automatic retries, exact launch ordering, delayed cidfile
handling, core suppression, provider-call accounting, exact-resource cleanup, and
offline host receipt validation. The prior verified closeout remains authoritative if
replacement normalization fails.

All V15 flags are false. No live qualification or scientific execution has occurred.
