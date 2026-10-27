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
signatures. Each identity moves with `set_suite`, in an entry signed by the
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

A space policy that rotates the epoch every few messages and deletes old
keys on every member's devices. It gives disappearing conversations to those
who want them, without imposing that on everyone. See
[decisions.md](decisions.md) D4.
