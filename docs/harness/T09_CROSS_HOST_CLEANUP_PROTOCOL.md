# T09 cross-host cleanup publication protocol

This is a shared cleanup extension. It creates no provider effect registration,
V17 package, live authority, empirical execution, spending, or scientific result.

## Namespace and source ownership

`RemoteRoot` represents a canonical absolute POSIX provider namespace. It has no
controller filesystem operations. `RemoteCleanupBinding` binds the accepted
provider contract, plan/run, source commit/tree and optional candidate digest,
provider identity/launch ordinal, accepted entry and transfer receipts, root
semantic identity, immutable cleanup handoff, attempt, original controller deadline,
initial finite transport duration, random session nonce, and exact helper SHA-256.

The production controller derives this binding from its accepted transfer state.
A snapshot helper must match the accepted source closure; an ordinary source helper
must match the accepted Git commit. The observer checks the exact helper bytes
before opening the namespace. A resumed retained controller reuses its original
binding and authority. A new session gets a fresh nonce and cannot consume the
prior session's frames. No state is reconstructed from an effect's claim of success.

External effects require this namespace after accepted host transfer. Historical
deterministic local-carrier fixtures retain their local protocol. A separate offline
namespace must be supplied explicitly before transfer and must be disjoint from the
controller root in both directions. Absence of an accepted transfer/root preserves
pre-transfer cleanup. An effect cannot choose that fallback after remote transfer.

## Wire compatibility and finite transport

The new wire form is explicitly named `cross-host-cleanup/1.0.0`. It uses the existing
`CleanupOutputChannel` nonblocking framing primitives, with no daemon, listener, or
budget service. Its `exchange` operation does not reinterpret legacy local messages.
`CleanupOutputBinding`, its document form and the existing local request/response
forms remain unchanged. The channel's binding interface now admits either explicit
binding type; each server still validates its own exact handshake.

`CrossHostCleanupExecutionRequest` and `CrossHostCleanupExecutionReceipt` are explicit
extension types with a cleanup protocol discriminator. Legacy request/receipt fields
and their hashing remain unchanged. Thus the existing effect protocol `2.0.0` is
not redefined: historical effects receive their original forms, and a cross-host
consumer must explicitly consume the versioned extension and return its receipt.
A legacy receipt cannot satisfy a required remote reconciliation.

Frames are canonical sorted compact JSON, prefixed by a four-byte big-endian length.
The schema is `schemas/t09-remote-cleanup-protocol.schema.json`; causal checks remain
in the typed authority. Maximums are 16,384 bytes per frame, 16,384 events, 64 MiB
of transcript, 4,096 traversal entries, and 16 member components. Inventories use
one sorted member per frame, with exact count/bytes/digest termination. An empty or
maximum-size before/after census fits the event contract; additional operations
still consume the finite event allowance. Any exceeded bound aborts without truncation.

Every response binds the transaction identity and sequence. Denial is explicit and
terminal. Successful responses also carry the controller's remaining duration.
Provider clocks need not share the controller's epoch: the helper clamps its local
deadline to the minimum of its existing limit and local request-send-start plus that
remaining duration. Return transit therefore cannot renew authority. The initial
transport window is finite; no file write occurs before the authenticated grant.
The controller checks its original deadline before and after each event. Provider
verification timestamps are provider-domain observations, not controller timestamps.
The retained transport must own launch, disconnect handling, and bounded teardown.

## Publication and accounting state

The typed sequence is hello → before census → publications → after census → close
→ acknowledged. Snapshot reuse, member-after-end, duplicate/reordered sequence,
wrong binding, and acknowledgement-before-close all abort.

A grant binds sequence, member path, writer role, create/append/replace/remove
operation, maximum bytes, initial identity, and original deadline. The controller's
`_reserve_cleanup_publication` consumes the existing cleanup reserve. It has one
lock and one accountant for local and remote callers. The helper owns no policy cap.

Creates bind a fresh zero-size opened inode before writing. Replacements additionally
bind an admitted fresh temporary inode. Appends preserve the existing inode.
Removal and replacement report the exact retired identity and bytes. Successful
writes report actual syscall counts. A partial publication may consume less than
its grant, but the difference is never refunded. Interrupted temporaries remain in
the provider namespace and the grant remains consumed and unresolved.

The helper holds and checks the root, resolves components no-follow, revalidates
parent names against held descriptors, rejects unsafe owner/mode/device/type/link
identities, and verifies the final named inode. Census reads metadata only. Selected
evidence export is a separate explicit byte-copy operation; a local copy proves
only its own publication.

## Reconciliation and continuation

The controller builds an expected inventory from the bound before census and the
verified lease transitions. The terminal census must exactly equal that inventory,
with unique member and occupied inode identities. It rejects unadmitted new/changed
members, omitted publications, impossible fresh inode reuse, incomplete census,
wrong retirements, and unexplained byte deltas. The private result distinguishes
all retirements, replacement retirements, total removals, baseline removals, actual
writes, and added/changed/removed members. Its transcript digest names its exact
observation prefix rather than implying that it covers later close frames.

The controller independently reconciles local inventory and revalidates local inode
publications. Both namespace results precede its existing zero/security receipt
checks. The remote receipt digest must equal the controller authority's result;
a package-generated boolean or digest alone is insufficient.

Disconnect, final acknowledgement loss, or ambiguity retains consumed grants and
unresolved state. An interruption may resume using the same binding, original
deadline and reserve only when no local lease or namespace change occurred and the
remote session is either unused or already completely reconciled. This prevents
interrupted local output from becoming a new accepted baseline. Partial or
unadmitted local output makes the session unresolved even before the remote
handshake. An unresolved session is rejected before another effect invocation;
it cannot be restarted as a fresh successful census. Later non-cleanup entry remains
blocked after campaign admission denial or unresolved remote cleanup, including
access to an already cached condition accountant. Cleanup reserve remains available
for necessary closeout, without renewing remote authority. Public control projections expose counts,
disposition and evidence hashes; remote paths, provider topology, UID/device/inode
observations and complete inventories remain private runtime evidence.

## Trust boundary and evidence limits

This is not cryptographic remote attestation. Production relies on exact reviewed
helper/effect/control source, accepted host/transfer/root binding, authenticated
retained transport, canonical replay-resistant messages, and bounded observation.
A controller cannot inspect a remote kernel independently through this protocol.
The offline tests use a real retained helper process and separate directory B;
the harness independently inspects B to compare its census. B is not a real host.
Historical PR #15 local-carrier tests remain local evidence. No live adapter or
scientific experiment is executed by this repair.
