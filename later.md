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
signatures. Each identity moves with `set_suite`, a
[replacement](spec/identity.md#roots) of the root: an entry signed by the
old root key, carrying a signature by the new root key over the entry's
other contents, as `add_key` carries a proof of possession. Larger signatures make entries larger, which matters only for
mailbox envelopes. Those may then carry heads messages instead of entries.

## Software distribution

Applications and updates are published in public spaces by their authors.
Devices follow the publishers they trust. An update is a new file in that
space, and installing it is a local decision. No store and no special
update channel are involved. A device may prefer copies already held by its
contacts' hosts.

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
