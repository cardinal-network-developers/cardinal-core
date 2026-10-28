# Later

Designed for, not specified. Each item says how it fits the five concepts,
so that nothing in the core needs to change to add it. If an item turns out
to need a core change, that is a signal to reconsider the item or the core.

## Live handoff and compute

**Goal.** Leave a program running on the laptop and continue at the
desktop. Use the combined compute of your devices, and what friends lend,
without thinking about it.

**Fit.** Most of the first goal comes for free: an application that keeps
its state in a space is already current on every device. True live handoff
of a running process needs a portable execution format whose entire state
can be captured: memory, open streams, and pending work. That state can be
stored as a blob and resumed elsewhere.

The direction: applications are packages published in spaces (content-
addressed, signed by their publisher's identity), compiled to a small,
deterministic virtual machine with no ambient authority. A program can reach
only the spaces and services it was handed. Determinism makes checkpointing
exact and lets work be verified by re-running it on a second machine. The
existing `../cardinal_vm` experiment is the place to start that work. Its
interface to the rest of the system is narrow: read and write spaces, open
link channels, and nothing else.

Pooled compute is a profile: a job space where an identity posts work
(input blobs, a program reference), devices with spare capacity take it, and
results are blobs. Trust comes from whose devices you accept work from, and
optionally from duplicate execution.

## Commerce

**Goal.** Buy cucumbers from a neighbor, or pay a creator, without an
intermediary watching or able to refuse.

**Fit.** An application and a profile, never the core. Offers, orders, and
receipts are signed entries in a relationship space. Settlement is
pluggable: ordinary bank transfers referenced in a receipt; mutual credit
between people who trust each other (IOUs routed along chains of
relationships, settled occasionally); or a token issuer such as GNU Taler,
which gives the buyer privacy while keeping the seller's income visible to tax
authorities. The core needs nothing more than what it already provides:
signed, durable, mutually held records.

## Large groups

Wrapping each epoch key once per member costs about 1.2 KB per member per
rotation, and an entry holds at most 256 KiB, so the current design stops at
about 200 members ([spaces.md](spec/spaces.md#distribution)). Beyond that, a
tree of keys in the style of MLS (RFC 9420) reduces rotation to logarithmic
cost and fits in an entry.
It would change how epoch keys are distributed inside a space, and nothing
else.

## Post-quantum signatures

When forging Ed25519 becomes plausible, a new suite adds ML-DSA or SLH-DSA
signatures, as a new base protocol ([evolution.md](spec/evolution.md)).
Each identity moves with a [replacement](spec/identity.md#roots) of the
root carrying `set_protocol`: an entry signed by the old root key, carrying
a signature by the new root key over the entry's other contents, as
`add_key` carries a proof of possession. Larger signatures make entries larger, which matters only for
mailbox envelopes. Those may then carry heads messages instead of entries.

## Software distribution

Applications and updates are published in public spaces by their authors.
Devices follow the publishers they trust. An update is a new file in that
space, and installing it is a local decision. No store and no special
update channel are involved. A device may prefer copies already held by its
contacts' hosts. Protocol extensions travel the same way, through
[protocol publishers](spec/evolution.md#who-decides-which-extensions-to-adopt);
what remains to specify is the layout of a publisher's space and how a
device matches implementations to extension names.

## Agents that stand on their own

Today an agent's trust beyond its keys comes from the humans who vouch for
it, and its guardians are its principals ([apps.md](spec/apps.md#agents-normative-where-marked)).
A person can protect their keys physically and meet their friends; an agent
can do neither. If agents come to run on hardware that binds a key to one
agent and attests to it, such as a dedicated chip per agent, an agent could
hold an identity whose root it protects itself. That would be an
[extension](spec/evolution.md) defining a new kind of key and what its
attestation proves. Until then, agents are vouched for, not trusted on
their own.

## Search and discovery

Finding people and public spaces without global names happens through the
graph: friends' public spaces link to others, and introductions connect
people. A directory is just a public space someone curates, and is only as
trusted as its curator. None of this is protocol.

## Ephemeral conversations

A space policy under which the space is
[succeeded](spec/spaces.md#succession) every few days, carrying nothing
forward, and every member's devices delete the old space and its keys. It
gives disappearing conversations to those who want them, without imposing
that on everyone. What remains to specify is the policy field and how
members' software agrees on the schedule. See
[decisions.md](decisions.md) D4.

## Redundancy targets and archives

**Goal.** A space states how well its data should be kept, such as "three
copies in two places, one away from home", and software reports how well
that is met. An organization keeps an off-site archive that never deletes.

**Fit.** Copies are already counted by what was seen
([blobs.md](spec/blobs.md#counting-copies)); this adds a target to measure
against. Everything here is guidance to devices and changes no validity
rule.

- **Targets in observed terms.** New [space policy](spec/spaces.md) fields:
  minimum copies seen, minimum distinct places, longest time between
  checks, and how long to keep chunks of old versions (all, a period, or a
  thinning schedule of hourly, then daily, then monthly).
- **Places are labels, not measurements.** No protocol can tell whether two
  holders share a disk or a flood plain. The person who arranges the
  holders labels them ("home", "Mom's house", "paid host"), and targets
  count distinct labels. The assumption is stated where it can be seen and
  corrected.
- **Reports are history, not forecasts.** "Two or more copies 99.6% of the
  last 30 days; one copy for 3 hours on Oct 12 while the NAS rebuilt."
  Time without a working copy depends on how fast failures are noticed (the
  check interval) and how fast copies are rebuilt, and both are measured.
- **A probability of loss**, if shown at all, is an application's what-if:
  published failure rates per kind of device and per place, updated by the
  person's own history (which barely moves them: never having had a disk
  fail says little), combined with measured detection and repair times. Its
  absolute numbers are fragile; its comparisons ("an off-site copy cuts the
  estimate a hundredfold") are not. It is never a promise.
- **Blind archive.** A host that holds a space's entries and chunks without
  its keys, never deletes, and verifies everything by hash. It cannot read
  what it keeps; restoring goes through a member. The entry history is
  already a complete record, so the archive is git-like for free. An
  archive that can read, for compliance, is a member, and members should
  see that it exists.
- **Deletion is a promise.** Any member can keep a copy, so a short
  retention target is cooperative, as [ephemeral conversations](#ephemeral-conversations)
  are. A space that archives forever should say so to members before they
  write.

What remains to specify: the policy fields, the place labels, and whether
holders of a shared space make themselves known to all members or only to
its owners, since a list of holders is a list of machines to seize.

## Starting over

Some losses are beyond recovery: the words are gone, no device survives,
and the guardians cannot reach a threshold, or the identity is
[frozen](spec/identity.md#frozen-identities) because the evidence cannot say
who is who. Physics offers no proof of
who the person is, so the protocol offers none either. The person starts a
new identity, and each contact replaces the old one by hand, after checking
by whatever human means they trust.

The core already allows the essentials: a contact can mark an identity as
no longer trusted in their account space, and any member can copy a space's
current state into a new space with new members. What remains is tooling to
make the process bearable:

- a "replaced by" note a contact can attach to the old identity, so their
  devices show the new one wherever the old one appeared;
- offering to re-share, into new spaces, the data contacts held in common
  with the old identity;
- if the person still has a working device of a fully compromised
  identity, exporting their own data from it and importing it under the new
  one.

The corner cases are many. None needs protocol support beyond what exists,
and none should be automated so far that a thief could use it.

The warnings software shows when a contact asks to be replaced
([experience.md](experience.md#things-that-go-wrong)) are a starting point.
Scammers will find tactics no one has thought of yet, and the wording, the
friction, and the checks software asks for must change as those tactics
become known.
