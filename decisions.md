# Decisions

Each entry records a choice, what it replaced, and what it costs. When a
decision is revisited, add a new entry rather than editing the old one.

The previous drafts are in `../tools/specs`. They are referred to here as
"the drafts."

---

### D1. Everything shared is a space

**Choice.** Files, messages, contacts, settings, groups, and public pages
are all spaces: encrypted causal logs with members, epochs, and one merge
model.

**Replaces.** The drafts' separate volumes, announcements, Double Ratchet
messaging, mailbox-specific notices, and the sender-key group design.

**Why.** "I don't want to decide how to share" is a requirement on the
architecture, not the interface. If messages and files travel by different
mechanisms, an interface must eventually expose the difference. One
mechanism also means one implementation of offline editing, merge, history,
membership, revocation, and backup, instead of five.

**Cost.** Spaces are heavier than a chat protocol for a single message:
signatures and a causal graph per entry. On modern devices this is
negligible.

---

### D2. Identity is a log, named by its first entry

**Choice.** An append-only, hash-linked log of signed operations. The name
is the hash of the genesis entry, not a key.

**Replaces.** Per-scope certificates with highest-sequence-wins.

**Why.** Highest-sequence-wins is a rotation rule, not a delegation rule,
and it fails under partition: two devices that rotate apart produce
incomparable states, and a thief can always count higher. A causal log makes
concurrency visible, gives a deterministic rule for revocation that holds
regardless of who saw what first, and turns key theft into a **detectable
fork**. A fork is evidence that friends can act on. That is what makes
social recovery possible at all.

**Cost.** Evaluating a log is more work than checking a certificate chain.
Logs are small, a few dozen entries in a lifetime, so this is a non-issue.

---

### D3. Spaces belong to identities; identities hold one encryption key

**Choice.** Space keys are wrapped to member identities, not to member
devices. An identity's devices share its encryption key.

**Replaces.** Per-device fan-out ("Model B" sessions per device pair).

**Why.** Adding a phone should not require every friend and every group to
do something. With per-device wrapping, each new device changes every space
you belong to, and every member learns your device count. With
per-identity wrapping, adding a device touches only your own log.

**Cost.** A stolen device holds the identity encryption key until rotation.
Removal therefore triggers rotation of the identity key, and of every
space's epoch at its next write. A thief with a stolen, still-unlocked
device can read what was already on it, which is true under every design.

---

### D4. No Double Ratchet

**Choice.** Forward secrecy on the wire comes from the link handshake and
its periodic post-quantum rekey. Stored data is protected by epoch rotation.
There is no per-message ratchet.

**Replaces.** The drafts' Signal-style Double Ratchet sessions per device
pair.

**Why.** The ratchet protects against a specific threat: a server keeps
ciphertext, and an attacker later steals a device's long-term key. In this
design:

- ciphertext on the wire is protected by ephemeral link keys, which are
  discarded;
- ciphertext at rest is on the person's own devices or with their chosen
  hosts, and the person *wants* their history readable on their next
  device;
- a stolen device yields its stored plaintext no matter what the protocol
  does.

A ratchet that is forward-secret against the person's own future devices
works against goal 5, "stop caring which device has what." It is the main
reason multi-device history has been so poor in ratcheted messengers.
Post-compromise recovery is still achieved, by removing the device and
rotating.

**Cost.** Envelopes waiting in a mailbox are encrypted under the space's
epoch key, not a one-time key. If a member's device is compromised before
the next rotation, envelopes still waiting could be read. Mitigation:
rotation on every removal and by entry count, and short mailbox retention.
A future "ephemeral" policy could rotate the epoch per batch of messages and
delete old keys, for people who want disappearing conversations.

---

### D5. Entries are signed, not deniable

**Choice.** Every space entry carries an Ed25519 signature from the author's
device.

**Replaces.** The drafts' deniable, MAC-authenticated messages.

**Why.** In spaces with more than two members, only signatures prove
authorship among members. And the project's founder wants every person to
be able to stand behind their words. Members of a space can prove to a third party what
another member wrote, but only by revealing the space's content, which they
could do anyway.

**Cost.** No cryptographic deniability. People who need it face a threat
model this project lists as a non-goal.

---

### D6. A new encoding, smaller than any profile of an old one

**Choice.** One binary encoding with six types, in which every value has
exactly one encoding, and records preserve unknown fields. Auditability
comes from a canonical text rendering in tools.

**Replaces.** Hashable String, Hashable String Bundles, the Binary Format
layout language, and hash-identified layout documents: four specifications
and two representations per concept.

**Why.** Canonical bytes are required for signatures. Unknown-field
preservation is required for partition tolerance: a device that has been
away for a year must not destroy data written by newer software. A
text-first wire format made every structure exist twice, and its layout
language could not express the formats it named, so prose did the real work
anyway.

**Cost.** A text editor alone no longer shows a document. A twenty-line tool
does.

---

### D7. A purpose-built link instead of QUIC or TLS

**Choice.** A WireGuard-style handshake with ML-KEM, roaming by index,
silence by MAC, and a small stream and datagram layer with three priority
classes.

**Replaces.** The drafts' Noise IK sessions over a minimal UDP profile, and
the option of overt QUIC transports.

**Why.** The drafts were right to use Noise. They lacked streams, flow
control, congestion control, priorities, and roaming, which every real
deployment needs. QUIC provides those, but brings certificate authorities,
in-band negotiation, visibility to scanners, and a specification larger than
this entire project. Writing the needed 10% is smaller and fits better.

**Cost.** A congestion controller and loss recovery are real engineering,
and must be tested against real networks. The specification states required
behavior, not an algorithm, so implementations can borrow proven ones.

---

### D8. Post-quantum key agreement from day one

**Choice.** ML-KEM-768 is mixed into the handshake, the sealing
construction, and a mandatory in-session rekey.

**Why.** Personal archives last decades. Traffic recorded today will be
decrypted by whoever eventually breaks X25519. Signatures stay Ed25519
because forging them later does not expose the past, and the identity log can
change suites when that matters.

**Cost.** Handshakes fill a full 1232-byte packet. Invitations cannot carry
an ML-KEM key, so first contact relies on the invitation secret, plus an
immediate rekey.

---

### D9. Content-defined chunks, encrypted convergently within a space

**Choice.** FastCDC chunk boundaries, per-epoch convergence secrets, and
references that carry the key.

**Replaces.** The drafts' fixed power-of-two chunks with epoch-derived keys.

**Why.** Editing the middle of a large file should transfer only what
changed. That is what makes this a replacement for rsync. Convergence within
a space deduplicates. Carrying the key in the reference makes sharing a
single file trivial and gives blind hosts a way to verify chunks.

**Cost.** Members of a space can tell whether a known file is in that space.
They are members, so they could also simply look.

---

### D10. One reconciliation protocol for everything

**Choice.** Range-based set reconciliation over object ids, with fetch by
id.

**Replaces.** The drafts' per-writer version heads with a twelve-record
limit per message.

**Why.** It works the same for devices that can read the data and for hosts
that cannot. It needs no per-peer state, and it costs a few round trips even
for millions of objects.

---

### D11. One host role, with several services

**Choice.** Mailbox, rendezvous, relay, and storage are services of one role,
under one grant.

**Replaces.** The drafts' separate mailbox and cache-host roles, and their
separate grant documents.

**Why.** In practice the same always-on device does all four. One grant, one
token scheme, one place in the account space.

---

### D12. No scopes

**Choice.** Authority is expressed as powers in identity logs and roles in
spaces. Application data is typed by profile and kind.

**Replaces.** The drafts' scope tree, read and write scope documents,
per-device scope documents, and frozen suite scope hashes.

**Why.** Scopes were a general capability mechanism, and almost every use
turned out to be one of two things: which devices speak for me, and who may
read or change this data. Both now have direct representations. The cost of
the general mechanism showed in per-device scope documents, per-volume
per-device certificates, and frozen descriptions that no longer describe
what they name.

**Cost.** Fine-grained capabilities, such as "this app may write only this
folder," are not expressible in the core. They can be expressed by giving
the app its own identity and its own space membership, which is cleaner.

---

### D13. Kept from the drafts

These were right, and survive essentially unchanged:

- the principles: no special nodes, no special codes, design for trust,
  physics as the limit of promises, the nomad test;
- consent before delivery, and the small unsolicited unit (the CMU), with
  bulk always pulled;
- delivery tokens with per-token quotas, and "a full mailbox refuses";
- silence to strangers (the drafts' "covert endpoints");
- offline root, per-device keys, mnemonic recovery;
- the physics rule for revocation;
- multicast DNS for local discovery;
- invitations as the start of every relationship.

---

### D14. Physical time is used only locally

**Choice.** No protocol decision depends on another party's clock. The only
use of time with security meaning is the recovery waiting period, measured
by each verifier's own clock.

**Why.** Clocks lie, drift, and do not agree across light-minutes. A waiting
period measured locally means the same thing everywhere: this verifier has
had this long to notice.

---

### D15. Removal authority is strictly hierarchical

**Choice.** No key can remove a key of equal power (except roots removing
roots), and no space member can remove one of equal role (except owners
removing owners). Most devices are device power; one or two home devices are
admins; admins are removed only by the root or by guardians.

**Replaces.** The first draft of this specification, which let admins remove
each other and resolved conflicts by removing both sides.

**Why.** A reviewer showed that equal-power removal can be backdated: a
revoked admin writes a removal with old parents, and it is structurally
identical to a genuine concurrent removal. No rule without trusted time can
tell them apart, so any rule either lets the attacker win races or lets them
grief forever. A strict order gives every conflict below the top a higher
arbiter, and there backdating gains nothing. At the top, roots and owners,
backdating is still possible; D21 says what happens then.

**Cost.** Losing an admin device requires the recovery phrase or guardians.
Losing a phone, the common case, does not.

---

### D16. Guardians decide recoveries; owners can only delay them

**Choice.** Recovery is a `recover` entry plus separate guardian
endorsements. The owner's devices can object, which doubles the waiting
period and alerts guardians, but only guardians can withdraw.

**Replaces.** The first draft's veto, which a thief holding the phrase could
always use, and which made the outcome depend on arrival time.

**Why.** The entire point of guardians is to decide between two parties who
hold the same secret. A veto handed that decision back to whoever holds the
secret. Separate endorsement entries also sync like any other entry, which
multi-signature objects did not.

---

### D17. The phrase is a key pair, not a symmetric key

**Choice.** The recovery phrase yields a hybrid key pair. Its public half is
in the identity log; recovery wraps are sealed to it.

**Replaces.** A symmetric recovery data key, under which every new
encryption key was wrapped.

**Why.** A reviewer showed that an admin device writing a new encryption key
had to hold the symmetric key, so a thief who stole an admin could read
every future key from the public log. With a key pair, any admin can seal
to the phrase, and only the phrase can open.

**Cost.** One ML-KEM key in the log, and one more seeded key derivation.

---

### D18. Changing guardians waits as long as a recovery

**Choice.** A new guardian set takes effect at each verifier only after the
old delay has passed there, and the old guardians are alerted.

**Replaces.** Guardian changes that took effect at once, judged by each
recovery's causal past.

**Why.** Judging by causal past let replaced guardians recover forever with
old parents. Judging by the latest policy alone would let a phrase thief
install friendly guardians and recover at once. A waiting period gives the
old guardians the same chance to act that recovery gives the owner.

**Cost.** Changing guardians takes a week by default.

---

### D19. Recoveries become final

**Choice.** A recovery is final once its new root writes a valid entry.
Later withdrawals and removals of endorsing devices are ignored. Objections
double the delay only once.

**Replaces.** Recoveries that could be undone at any time by a withdrawal,
and delays that could be doubled without limit.

**Why.** Without finality, a guardian device stolen years later could undo
a recovery and revive the thief's keys. Without a limit, repeated objections
were a veto by another name, which D16 removed.

**Cost.** A guardian who changes their mind after the delay is too late.
The delay is the time to change one's mind.

---

### D20. Removed devices' work is kept only if the owner witnessed it

**Choice.** In spaces, an entry by a removed key, retired or compromised, is
valid only if another of the author's devices built on it while still
trusting the key, or the author later listed it in a `keep` op. Software
witnesses every space before writing a removal.

**Replaces.** A rule that kept retired keys' entries unconditionally, and
kept compromised keys' entries only if witnessed, with no routine witnessing.

**Why.** Unconditional trust in retired keys let a sold laptop write as its
old owner forever. Witnessing without routine meant that marking a phone
lost could discard months of its honest messages. Routine witnesses make the
common case lose nothing, and `keep` covers recovery from nothing.

**Cost.** One small entry per space on each removal. Work a device did that
no other device saw, and that the person does not choose to keep, is lost.

---

### D21. At the top, conflicts go to people

**Choice.** A contest between roots of an identity ends only by recovery,
decided by guardians. A conflict between owners of a space splits it: the
original becomes read-only, and each owner may make a copy.

**Replaces.** The claim that a root could end a contest by removing the
others, and that an owner could settle an owner conflict.

**Why.** D15 gives every conflict below the top an arbiter. At the top there
is none, and any rule would let one side win by writing entries with old
parents. Guardians exist for exactly this in identities. In a space, two
owners who each removed the other genuinely disagree, and the honest outcome
is that each keeps what they shared.

**Cost.** A space can split, which software must present clearly. A thief
with the phrase can force the owner to involve guardians.

---

### D22. Prunable checkpoints are barriers

**Choice.** An owner's prunable checkpoint fixes the state at its frontier
for every holder. Later entries apply on top of it, and everything before it
counts as their ancestor.

**Replaces.** Pruning with skeletons, which claimed that pruned and full
holders computed the same state.

**Why.** A reviewer showed that late entries concurrent with the frontier
could reorder moves, block deletes, or change validity in ways only a full
holder could compute. Changing the rule for everyone, not just for pruned
holders, makes agreement exact.

**Cost.** A device that was offline across a barrier has its concurrent
changes applied after the checkpoint's state, rather than interleaved. A late
removal cannot invalidate entries the checkpoint already included.

---

### D23. Encryption keys form a chain

**Choice.** Each new identity encryption key carries every key it replaces,
sealed to itself.

**Replaces.** Wrapping only the current key for new devices and recovery.

**Why.** Spaces rotate only at their next write, so an idle space can stay
under an old key for years. Without a chain, a new or restored device could
not read it, and a guardian whose own key had changed could not open their
share.

**Cost.** About 1.2 KB per replaced key, per key change, in the identity log.
