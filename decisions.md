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

**Choice.** Validity and state are pure functions of the set of entries. No
clock, local or remote, affects what a set of entries means. Local time
affects only when software acts: when a guardian chooses to confirm a
recovery, when a device rotates a token, when a reminder appears.

**Why.** Clocks lie, drift, and do not agree across light-minutes. Worse, a
rule that depends on when a verifier first saw something gives a different
answer to a device that joins years later. The recovery waiting period is
real, but it is measured by the guardians, who then sign, so the signature
is what every verifier sees.

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


Amended by D26: owners and roots no longer remove each other.
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


Partly superseded by D24: guardians no longer withdraw; they decline to confirm.
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

Amended by D34: the recovery public key belongs to the root key.
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


Superseded by D25.
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


Superseded by D24.
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


Partly superseded by D27.
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


Superseded by D26.
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


Superseded by D28.
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

---

### D24. Guardians confirm; verifiers count signatures

**Choice.** Recovery has two guardian steps. `endorse` says a recovery is
wanted and starts each guardian's wait. `confirm`, written after the wait on
the guardian's own clock, is binding and carries the guardian's share. A
recovery is in effect when a threshold of guardians has confirmed it.
Objections double the guardians' wait and bind nothing else. Thresholds are
majorities, and guardian software never confirms two decisions that do not
know each other.

**Replaces.** Waiting periods measured by every verifier, finality by the
new root's first entry, and withdrawals (D16, D19).

**Why.** A third review showed that any rule using a verifier's own clock
gives a different answer to a verifier that joins later. A contact who
received a two-year-old recovery all at once could reject it forever.
Moving the clock to the guardians, who then sign, makes the outcome a fact
about the entries. Without withdrawals, nothing can undo a recovery later,
and releasing shares only on confirmation means no share leaves early.

**Cost.** A guardian who confirms cannot take it back; the wait is the time
to change one's mind. A stolen guardian device can sign with an old log
head, so a recovery is only as safe as a majority of guardians' devices.

Amended by D30 and D31: conflicting decisions freeze the identity, and confirmations live in the guardians' own logs.
---

### D25. Guardians approve changes to guardians

**Choice.** Every `set_recovery` after genesis is confirmed by a threshold
of the guardians it replaces, like a recovery. Each guardian set has its own
random guardian key, separate from the phrase, and changing guardians
rotates the identity's encryption key.

**Replaces.** Guardian changes that took effect after a wait measured by
each verifier (D18), and shares of a seed derived from the phrase.

**Why.** The wait was clock-dependent (D24). Approval by the old guardians
is not: a phrase thief cannot install friendly guardians, and former
guardians cannot recover with old parents without creating a visible
conflict that only both majorities can end. A guardian key per set means
former guardians cannot read data written after they were replaced.

**Cost.** Replacing guardians needs a majority of the old ones to agree.
People should name enough guardians that a majority stays reachable for
years. An identity with no guardians has no protection against a phrase
thief beyond the contest itself.

Amended by D30: a conflict between guardian decisions freezes the identity; nothing ends it.
---

### D26. Nobody at the top removes a peer

**Choice.** Roots never remove roots: a root only replaces itself, and only
a recovery changes roots otherwise. Owners never remove or downgrade owners:
an owner leaves, or succeeds the space. Above space owners stand their
identities, and above identities, their guardians.

**Replaces.** Root-against-root and owner-against-owner removal, judged by
authorization alone, and space splits (D21).

**Why.** The review showed that peer removal at the top let a removed owner
backdate a removal and erase years of another owner's work, and let a
removed root re-contest an identity after recovery. Removing the power
removes the attacks. A compromised owner is a compromised identity, which
its guardians fix; a real disagreement between owners is a parting, which
succession expresses without any rule choosing a winner.

**Cost.** An owner cannot expel a co-owner. They can only leave with the
members who follow them.

---

### D27. One kind of removal; the remover decides what to keep

**Choice.** `remove_key` has no mode. In identity logs, a removed key's
entries count only if they are ancestors of its removal, so the removal's
parents say what is kept. In spaces, a removed key's entries count only if
witnessed. Whether software witnesses before removing, for a sold device, or
asks the person, for a stolen one, is a matter of software, not protocol.

**Replaces.** Retired and compromised modes, with different validity rules
in identity logs and spaces.

**Why.** Retirement that kept concurrent entries let a sold admin laptop add
keys forever with old parents. A mode the remover chooses gives the protocol
nothing it can check; a choice of parents does.

**Cost.** A thief's work that the person's other devices built on before
the theft was noticed is kept. Before anyone noticed, it was trusted.

Amended by D33: a recovery also revokes every entry concurrent with it.
---

### D28. History is never pruned by protocol

**Choice.** State is defined over full history only. A device may run light
from its own identity's checkpoint, and fetch history from a full holder
when needed. History itself is bounded by succeeding a space.

**Replaces.** Barriers and pruning (D22).

**Why.** The review showed that a barrier written by any owner could be
forged, could change after holders had pruned, and left pruned holders
unable to evaluate membership. Every fix made the barrier more like a
successor space, so the design now says so directly: a fresh start is a new
space, chosen by its owners, and accepted by its members by joining.

**Cost.** Someone must keep full history for a space to survive the loss of
its full holders. Moving to a successor is visible to members, and late
changes to the old space must be re-applied by hand.

---

### D29. The authority rules are a program, checked by machine

**Choice.** Which identity and space entries are valid is defined by a
small stratified logic program ([model/rules.md](model/rules.md)), with a
checker, a reference evaluator, targeted scenarios for every review
finding, and a fuzzer that writes adversarial histories.

**Replaces.** Validity rules written only in prose.

**Why.** Four reviews in a row found the same kind of flaw: a set of
entries with no consistent reading, or with two. Each prose fix closed one
hole and opened a subtler one, because nobody can check rules with "not"
in them for loops by reading. A stratified program has exactly one result,
and whether a program is stratified is a mechanical check. The fuzzer found
a real flaw (D33) within minutes of running.

**Cost.** Implementers read a few dozen lines of logic beside the prose,
and the model must be kept in step with the specification.

*Amended by D35:* stratification settles that there is one answer, not that
it is the right one. The fuzzer now also checks intent.

---

### D30. What no rule can settle freezes the identity

**Choice.** Guardians who decide both ways under one policy, a root contest
with no guardians, and guardians named by one side of such a contest make an
identity **frozen**: permanently, visibly, and with no protocol way back.
The person starts a new identity, and contacts recognize it in person.

**Replaces.** Conflict rules under which neither decision was in effect,
which let a later conflict revive keys a recovery had removed, or hold an
identity hostage forever (D25); and ignoring decisions under a replaced
policy (D25), which a late confirmation could turn into undoing one.

**Why.** These are cases where no one stands above the parties. Any rule
that picked a winner could be gamed by the loser writing with old parents.
Freezing is honest, and it is monotone, so it cannot be used to undo
anything. The protocol adds capability to relationships people already
have; it need not pretend to replace them when the evidence runs out.

**Cost.** Stated plainly in [identity.md](spec/identity.md#what-recovery-cannot-do):
a colluding majority of current guardians can do anything; a thief holding
a guardian's keys casts that guardian's vote; without guardians, two holders
of the phrase freeze the identity; a phrase that was in use while the
identity had no guardians can freeze it later; former guardians acting
together on a policy they replaced can freeze it. A decision is never
switched off by a later one, so a decision made under a policy already
changed in its own past freezes the identity rather than being ignored: the
fuzzer showed that ignoring it would let a late confirmation undo a
recovery. Starting over is slow and manual,
and scammers will imitate it, so the warnings software shows must evolve
([later.md](later.md#starting-over)).

*Amended by D37, D38 and D39:* the contest rule is now stated through the
policy's controller, a decision that is evidence of misbehaving guardians is
not applied, and a frozen author's entries keep counting where others built
on them.

---

### D31. Guardians confirm in their own logs

**Choice.** `endorse` and `confirm` are entries in the guardian's own
identity log, judged as of their own causal past. A `recover` entry is
signed by the new root key it names.

**Replaces.** Confirmations written into the recovering identity's log,
signed by a guardian key checked at a head the confirmation cited.

**Why.** Judging a guardian's key at a cited head ignored the guardian's own
rules, and let one stolen guardian phrase mint keys at will. In the
guardian's own log, the guardian's revocation rules apply, the guardian's
other devices see every confirmation, and judging each one as of its own
past makes guardianship between friends who guard each other well-founded.

**Cost.** A thief who steals a guardian's device or phrase can still
confirm with parents from before the guardian removed the device, or on a
branch that does not show the guardian frozen. It is one vote per guardian,
however many keys the thief mints, and a majority of guardians is still
needed. Reversing a vote when the guardian is later frozen or loses a device
would let a recovery come undone, which is worse. The fuzzer checks this
with guardians who guard each other in pairs, cycles, and meshes, while
they are themselves contested, recovering, or frozen.

---

### D32. Roles belong to memberships

**Choice.** Each `add_member` creates a membership with a fixed role, and
every space entry names the membership it is written under. Changing a role
ends one membership and adds another in the same entry. `set_role` is gone.

**Replaces.** Roles held by identities and changed in place.

**Why.** With roles held by identities, the role an entry was written under
depended on which role changes were valid, which depended on roles: a loop.
Fixed roles per membership make the layers by role static. They also fix
two review findings: adding an existing member can no longer demote them,
and a removed member can be added again and write.

**Cost.** Sixteen bytes per space entry, and a new membership id after every
change of role.

*Amended by D40:* only a membership's own identity can leave it.

---

### D33. A recovery revokes work done without knowledge of it

**Choice.** Every entry concurrent with a recovery in effect is invalid,
whoever signed it, including entries by keys the recovery keeps.

**Replaces.** Recoveries that kept the concurrent work of kept keys.

**Why.** The fuzzer found that a thief holding a key the recovery kept
could add keys with old parents that survived the recovery. A recovery is a
reset to a point the guardians chose; work that did not know about it has
no claim to survive it.

**Cost.** Honest work done on a kept device during the waiting period, by a
device that had not yet seen the recovery, is discarded. Devices sync the
pending recovery during the wait, so this is rare.

*Amended by D38:* this applies to recoveries that are applied, not to those
that only freeze the identity.

---

### D34. The recovery key belongs to the root

**Choice.** The recovery public key is published with the root key, in its
`add_key` or `recover`. A new phrase brings its recovery key into effect at
once.

**Replaces.** The recovery public key in `set_recovery`, which after
genesis needs guardians' confirmation.

**Why.** A review showed that after a phrase was exposed, new encryption
keys were sealed to the old phrase until guardians confirmed a policy
change, or forever without guardians. The recovery key is the root's own
secret, so it needs no one's approval.

**Cost.** None beyond moving a field.

---

### D35. The fuzzer checks intent, not only determinism

**Choice.** Besides one answer for any set of entries, the fuzzer checks
what the answer should be: guardians following the software rules never
freeze an identity; an honest owner keeps its membership and everything it
wrote; removals go strictly down in power; a key removed by a recovery
gains nothing; nobody can invalidate a member of equal or higher role, and a
non-member cannot affect anyone; freezing an author keeps what others built
on it. Histories include honest actors whose software follows the rules,
thieves, and strangers. Determinism is also checked across Python hash
seeds, in separate processes. Each fix was checked by putting the flaw back
and watching the fuzzer find it.

**Replaces.** A fuzzer that checked only determinism, monotonicity, and two
structural properties.

**Why.** A cold review of the program (V1–V11) found that the machinery for
one answer worked, but the answer was wrong in ways no property looked for:
anyone could end an owner's membership; a stolen phone could erase its
owner's history; a key's power depended on hash order; guardians obeying
the rules could freeze an identity. Each of these is a statement about
intent, and each is now a property.

**Cost.** A slower fuzzer. The intent properties are themselves claims that
can be wrong or incomplete; what they leave out is listed in
[model/README.md](model/README.md).

---

### D36. Guardians confirm in a chain

**Choice.** Guardian software confirms decisions under one policy only in a
chain: each new one descends from every one it already confirmed, and those
that are changes of the policy must be dead, meaning that more than *n − t*
guardians have confirmed decisions concurrent with them.

**Replaces.** A rule that let a guardian confirm a change after confirming a
decision that descended from it, so guardians each obeying it could freeze
an identity; and that left a split vote between two changes deadlocked
forever.

**Why.** Two decisions that freeze an identity both need a majority, so some
guardian confirms both. The chain rule stops that while both could still
take effect, using only what the guardian knows for certain: its own log.
Deadness lets guardians move on from a split, because a dead change can
never reach its threshold again.

**Cost.** Moving on from a split needs enough of the other guardians'
confirmations to prove the split dead. With an odd number of guardians, the
ones who have not voted must break it.

---

### D37. A policy without guardians names its controller

**Choice.** A `set_recovery` that drops every guardian names, in field 8,
the root that may change the policy afterwards. The genesis root controls
the genesis policy. A root that replaced the controller in turn also
controls it.

**Replaces.** Any root "before revocation" may change a policy without
guardians, computed by a parallel set of rules.

**Why.** A review showed that a root removed by a recovery could, once the
guardians later agreed to drop themselves, name its own guardians and take
the identity. Who controls the policy is now fixed by the shape of entries,
which is also what keeps decisions monotone, and the parallel rules are
gone.

**Cost.** A field, and a change that drops guardians without naming a
controller leaves the policy unchangeable.

---

### D38. Evidence of misbehaving guardians freezes, but is not applied

**Choice.** A decision that is evidence of guardians deciding both ways
stays in effect, so nothing later undoes a decision, but it is not applied:
a recovery among them removes no keys and revokes nothing.

**Replaces.** Applying such decisions and freezing.

**Why.** Former guardians acting on a policy they had agreed to replace
could, by backdating a recovery, remove every key of the identity, which
destroyed spaces for everyone the identity had shared with. Freezing is
enough.

**Cost.** None found.

---

### D39. A frozen author's entries count as far as others built on them

**Choice.** A space is evaluated once as if no author were frozen. A frozen
author's entries then count if they are in the causal past of a valid entry
by an author who is not frozen. Software does not build on entries of an
author it knows to be frozen.

**Replaces.** Rejecting every entry of a frozen author.

**Why.** Those who can freeze an identity (former guardians, an old phrase)
could otherwise destroy every space the identity created or added people
to, including everyone else's work. What others built on was written before
they knew; nothing new counts. Only valid members keep a frozen author's
entries, so a stranger cannot.

**Cost.** A second evaluation of a space whose members include a frozen
identity. A frozen author's last entries that nobody built on are lost.

---

### D40. Only a membership's own identity leaves it, and leaving voids only its own key's concurrent work

**Choice.** A leave or `succeed` counts only if written by the membership's
own identity, under that membership, after its creation, with a signature
that counts. Around a leave, only entries signed by the same key are void.

**Replaces.** A leave that any author's entry could write by naming the
membership, and that voided everything concurrent with it.

**Why.** A review showed that anyone, even a non-member, could end an
owner's membership and with it the whole space; and that a stolen phone
could backdate its owner's `succeed` and erase the owner's history. Same-key
voiding still stops the device that left from writing on by backdating.

**Cost.** A member's other devices can write concurrently with a leave they
had not seen, and those entries stand.

---

### D41. A key is named once, and removals go down in the rules

**Choice.** An `add_key` of a key already named in its causal past, or a
`recover` naming one as its new root, is invalid. A key's power is the one
its first `add_key` gives it; a key first named at two powers concurrently
never counts. The proof of possession covers the power. The rules, not the
input facts, check that a removal goes strictly down.

**Replaces.** Power read from whichever `add_key` came first in a hash
table's iteration order, and a proof that could be replayed at another
power.

**Why.** A review showed that a stolen admin could re-add an honest admin as
a device by replaying its proof, and then remove it, and that whether this
worked depended on Python's hash seed. Fixing power by the entries' shape
removes both.

**Cost.** A device that returns after removal needs a new key.

---

### D42. The core is frozen; extensions are named by hash

**Choice.** The small-integer kinds, ops, and fields are one frozen base
document, named by its hash. Everything new is an extension, named by the
hash of its document and used in place of a number. Each extension is
critical or ignorable. A verifier that meets a valid entry using a critical
extension it does not know stops trusting that log from there on, and says
so. Identities and spaces declare what they speak with `set_protocol`, which
replaces `set_suite`. Devices adopt extensions endorsed by publishers their
person follows ([evolution.md](spec/evolution.md)).

**Replaces.** A registry of core kinds that someone would have to keep, and
`set_suite`.

**Why.** Once the project is open, nobody should be its arbiter. Numbers
need a registrar; hashes do not. Two communities extending the core
independently must never give one number two meanings, because the result
would be identity logs that are valid in one place and invalid in another,
with no one told. Hash names make collisions impossible and disagreement
visible.

**Cost.** Thirty-two bytes per extension op. Agreement on validity holds
among verifiers that know the same extensions, not across all of them; one
that knows less accepts less, and says so.

---

### D43. Applications hold no keys; agents hold their own

**Choice.** On each device one Cardinal service holds keys, logs, and
spaces. Applications reach only the spaces the person grants them, by
choosing in a picker the service draws, and see members as opaque handles.
Their writes are signed by the device, as the person. An application that
must act on its own is an agent: its own identity, a member only where
added, shown as its principal's agent when the principal added it
([apps.md](spec/apps.md)).

**Replaces.** Nothing in this specification; it completes D12, which
dropped scopes and said apps could be given their own identity.

**Why.** The question is what a poorly trusted application, such as a
mini-game with friends, can learn. Scopes answered inside the protocol, at
great cost. The powerbox answers at the boundary the person can see, and
the protocol only ever sees an identity writing to a space. Friends connect
through the ordinary co-member rules, so nothing new is needed for the game
to be played together. Most applications never hold a key, so they cannot
leak one.

**Cost.** Isolation is only as good as the platform's sandbox. Agents that
verify entries learn their co-members' identity logs.

---

### D44. Reveal a field only to those who need it, only when it is used

**Choice.** The identity log names guardians only by salted commitments; a
guardian is revealed only by its own `endorse` or `confirm`, which carries
the salt. Device names are not in the log at all. Identity entries carry no
time. A [table](architecture.md#who-sees-what) states what each party sees.

**Replaces.** Guardian identity ids in `set_recovery`, visible to everyone
the log was synced with; the display label in `add_key`; and a time on every
identity entry.

**Why.** Metadata invites attacks outside the protocol. Anyone who wants to
take an identity by force goes after its guardians; anyone tracking a person
learns from when they change devices. Hiding these is not a cryptographic
guarantee, since a guardian can always be found some other way, but it
stops many attacks from starting. Verification never needed them: a
commitment is checked when the guardian acts, which is the only time its
identity matters.

**Cost.** Confirmations must be delivered with the guarded identity's log,
since verifiers no longer know which guardians' logs to fetch. The number of
guardians and the threshold stay visible.

---

### D45. Copies are counted by what was seen, not by what was claimed

**Choice.** Software counts a holder as a copy only after random chunk
checks through the ordinary `blob` service. A holder that fetches a chunk
stops counting until it passes checks again, so a rebuild after a disk
failure needs no declaration. Holders that fetch the same chunks
repeatedly stop counting. Redundancy targets, place labels, and archives
are left to [later.md](later.md#redundancy-targets-and-archives).

**Replaces.** The account space's record of which devices and hosts hold
copies, taken as the count.

**Why.** "N copies, survives N-1 failures" assumes the copies are real and
fail independently, and neither can be verified without owning the
hardware. A count of copies seen recently is something software can
measure and state honestly. Checks look like ordinary requests, so a
holder cannot keep only what is checked, and counting by observation makes
an honest rebuild and a missing copy the same thing: not held right now.

**Cost.** A holder that relays chunks from a third party, or two holders on
one disk, still pass. Catching deliberate deceit is left to the people
involved. Checks cost a little bandwidth.

Amended by D46: fetching no longer stops a holder counting, and counting
copies is guidance, not a requirement.

---

### D46. Only a missing chunk fails a holder

**Choice.** Counting copies is guidance: each device chooses how far to
look, from trusting the account space's record, to spot checks, to looking
for anomalies such as answers slower than the holder's round trip. Spot
checks are the reasonable default. A holder fails only by not producing a
chunk it should keep, or producing a wrong one. Fetching, once or
repeatedly, is never held against it.

**Replaces.** D45's rules that a holder that fetches stops counting until
it passes checks after a wait, and that one fetching the same chunks
repeatedly stops counting.

**Why.** A check is an ordinary request, so a device cannot tell another
holder's check of it from a fetch: two holders checking each other would
reset each other forever. Working around that took allowances by volume,
waits, and rechecks during checks, and none of them caught a holder set on
cheating. What matters is whether the chunk is there, and a check sees
that directly: a rebuilding holder fails while chunks are missing and
passes once it has them, still with nothing declared. Catching deceit pays
off only once holders cannot be trusted. Until then, checks find accidents
and show the state of the data from tests rather than assumptions.

**Cost.** A holder that keeps nothing and fetches each checked chunk from
elsewhere as it is asked passes. It passed under D45 too, by relaying.

---

### D47. Paths kept on one device are listed in a file

**Choice.** A `.cardinalignore` file in a folder lists, in gitignore
syntax, paths that each device keeps to itself and never writes to the
space ([profiles.md](spec/profiles.md#paths-kept-on-one-device)).

**Replaces.** The files profile's folder field 1, a list of glob patterns
stored on the folder node, which no implementation used.

**Why.** A file is easier to reason about: it is seen and edited with any
editor, it comes along when a folder is copied in, and its syntax is one
people already know. Patterns in a node field are invisible, need a
command to see or change, and would have needed a syntax of their own.

**Cost.** The sync engine reads a file's content to decide what to sync.
Files under 1 KiB are stored inline in entries, so every device holding
the state has them; a larger one is read once its chunks are here.

---

### D48. Every device carries the news

**Choice.** A device that writes to a set, or stores objects new to it, tells
a few peers entitled to the set, and they do the same
([sync.md](spec/sync.md#notices)). Which peers and how many is each device's
own choice. In a large space a device keeps sessions with its own devices and
about six others, chosen at random. A writer deposits in the mailboxes of at
most about eight offline members per write, and not again for a member until
it has heard from them. `heads` works for any set, and devices ignore `sync`
ops they do not know.

**Replaces.** The rule that a writer sends each entry to every online device
of every member, and to the mailbox of every offline one; the rule that all
sync traffic is background; and the step of token rotation in which each
member deposits its reach node with each other member.

**Why.** Fan-out from the writer costs the writer in proportion to the space,
and fails when the writer cannot reach someone that others can. Passing news
on costs each device the same small amount, and gives every device several
paths. Sets already say what is new, so a notice stops by itself, with no hop
count or message ids. Reconciling already guarantees convergence, so notices
only have to be fast, not reliable, and one `heads` message covers everything
before it, so a later notice repairs a lost one. All of this adds no message
type: `heads`, `want` and `objects` were there.

Simulated with 600 devices (200 members with 3 each), each opening 6 sessions
and telling up to 8 peers: a notice reaches 100% of them in about 6 hops, and
99.99% of live devices when a fifth are silent, for about 6 notices per
device. With 3 sessions each, the worst run reached only 0.2%, when a writer's
neighbours were all silent, so "a few" means about six. A writer that had
sent 600 messages sends 8.

A device does not announce an object before its parents, and while it holds
an object for missing parents, any notice for that set sends it back to
reconcile. Without these, a device that reconciled too early, with a peer
still fetching the parents, ignored the next notice, because it named an object
already held, and waited minutes for the periodic reconcile. The stress test
showed this happening before there was any forwarding.

A rule that every device deposits for a few offline members would have been
worse than the old one: 150 online devices each making 8 deposits is 1,200 per
write. Someone offline is in no hurry, and needs only one waiting notice, so
only the writer deposits, and only until it has heard from them.

**Cost.** A device hears most news several times, which is the price of not
coordinating, though each copy is tiny. News takes several hops instead of
one, so a space of many members is a little slower to reach everyone than a
direct send to a device that was reachable. A member of a large space who
returns when nobody else is online sees only that something changed, until
someone is. Notices are interactive, so a peer could misuse that class, but
only on its own session.

**Left open.** Live streams ([later.md](later.md#live-streams)) need their
own sequence, a way to find peers without a member list, and agreements with
deadlines. Nothing here stands in their way: the duty to pass news on is
stated for any set, fan-out and peer choice are local, no field ties a notice
to a space or a member list, and a new notice op is ignored by older devices.

