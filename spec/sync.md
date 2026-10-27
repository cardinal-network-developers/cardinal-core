# Sync

Status: draft. Normative.

Sync makes two holders of a set of objects hold the same set. One procedure
serves every case: a person's own devices, two friends, a device and a
storage host that cannot read what it stores, and identity logs spreading
through contacts.

The procedure knows nothing about what the objects mean. It reconciles sets
of 32-byte ids. Meaning (which ids belong in a set, which are wanted) is
decided by the layer that owns the set.

## Sets

A set is named by a **label**, 32 bytes, agreed by both sides:

| Set | Label | Who may name it |
|---|---|---|
| a space's sealed entries | the space id | member devices to member devices |
| an identity log | `BLAKE3("identity log" \|\| identity id)` | everyone listed in [identity.md](identity.md#distribution), and the identity's storage hosts |
| a stored set at a host | a random label the owner chose when granting storage ([hosts.md](hosts.md#storage)) | the owner's devices and that host |
| chunks of a space held by a host | likewise | likewise |

A device MUST NOT name a set to a peer that is not entitled to it. A peer
that receives a label it does not hold, or may not reconcile with this
sender, MUST answer as if the set were empty. It MUST NOT reveal whether the
set exists.

## Range reconciliation

The algorithm is range-based set reconciliation, as in Meyer's "Range-Based
Set Reconciliation" (2023). It needs no state between sessions, does not
depend on how the sets got different, and takes a few round trips even for
very large sets.

### Fingerprints

Items are ids, ordered bytewise. The **fingerprint** of a range is

```
first16(BLAKE3(sum || varint(count)))
```

where `sum` is the sum of the ids in the range, each read as a 256-bit
little-endian integer, modulo 2^256, written as 32 bytes little-endian. Sums
can be maintained incrementally, so fingerprints of any range are cheap.

### Messages

Messages on the `sync` service are records whose key 0 is an op:

| Op | Message |
|---|---|
| 1 | reconcile: `{0: 1, 1: label, 2: ranges}` |
| 2 | want: `{0: 2, 1: label, 2: ids}` |
| 3 | objects: `{0: 3, 1: label, 2: list of object bytes}` |
| 4 | heads: `{0: 4, 1: space id, 2: sealed ids}` |

In a reconcile message, `ranges` is a
list of records, ascending, together covering all possible ids:

| Key | Field | Type |
|---|---|---|
| 1 | upper bound | bytes(32), exclusive; absent in the final range, meaning "to the end" |
| 2 | mode | 0 = skip, 1 = fingerprint, 2 = list, 3 = you lack |
| 3 | payload | fingerprint bytes(16); or a list of ids |

The initiator sends one fingerprint range covering everything, or a list if
it holds 32 ids or fewer.

For each range it receives, a side replies:

- **skip**: nothing to do for that range; reply skip.
- **fingerprint**: if its own fingerprint for the range matches, reply skip.
  If it holds at most 32 ids in the range, reply with a list of them.
  Otherwise split its ids in the range into 16 subranges of nearly equal
  count, and reply with a fingerprint for each.
- **list**: it now knows exactly which ids each side lacks in that range.
  Reply with **you lack**, listing its ids in the range that are absent from
  the received list (possibly none).
- **you lack**: record the ids as wanted. Reply skip.

Reconciliation ends when a message contains only skips. Each side then knows
the ids it lacks, and fetches them.

A message SHOULD NOT exceed 64 KiB. A side that has more to say continues in
the next message.

## Fetching objects

After reconciliation, each side requests what it lacks with `want`, at most
256 ids at a time. The holder replies with `objects`, omitting any it no
longer holds, or, as a [light holder](state.md#light-holders), holds only
by id. The receiver checks every object against its id,
and against the rules of the layer that owns the set, before storing it.

An object whose prerequisites are missing (a space entry whose parents have
not arrived, an identity entry whose parents have not arrived) is held, and
the receiver reconciles that set with the sender. Parents are named by entry
id, which a host cannot see, so missing parents are found by reconciling,
not by `want`.

A storage host accepts `objects` for a label only from the owner's devices.
That is how an owner puts objects into storage
([hosts.md](hosts.md#storage)).

## Blob transfer

Chunks are fetched by id, not reconciled, because the fetcher knows from its
own state which chunks it needs.

On the `blob` service: request `{0: 1, 1: ids}`, at most 64 ids. Reply
`{0: 2, 1: list}`, where each item is `{1: id, 2: ciphertext}` or
`{1: id, 3: 1}` meaning not held. The fetcher checks
`BLAKE3(ciphertext) == id`.

**Who is served.** Chunk ids are unguessable, and chunks are useless without
the key in a reference, so knowing an id is treated as the right to fetch
it, within limits:

- a device serves chunks to any peer it has a session with: its own devices,
  contacts, and co-members of a shared space. A reference handed to a
  contact outside any shared space ("send this file to Ben") therefore works;
- a host serves chunks to owner devices, to token holders for labels the
  owner allowed for that token, and to anyone for public labels.

A device MAY refuse requests that exceed its own rate limits.

## When to sync

- **On session open**, devices reconcile every set both are entitled to,
  starting with identity logs, so revocations travel first.
- **On write**, a device sends the new sealed entry to every online device
  of every member, as an `objects` message, if it fits in 900 bytes.
  Otherwise it sends a `heads` message. Recipients fetch what they lack.
- **Offline recipients** get the same entry or heads message in their
  mailbox ([hosts.md](hosts.md#mailbox)). A mailbox carries notice of a
  change, never bulk data.
- **Periodically**, on long-lived sessions, every few minutes, at background
  priority.

All sync traffic is **background** priority on the link
([link.md](link.md#priority)), except blob fetches that a person is waiting
for, such as opening a file, which are **interactive**.

## Sneakernet and delay-tolerant carriage

Everything in a set is a self-verifying object, so sync works without a live
session. A device can write a **bundle**: a file containing a label and
objects, optionally sealed to a recipient identity's encryption key. Carry it
on a USB stick, send it over a satellite store-and-forward link, or hand it
to a courier. The receiver imports it exactly as if the objects had arrived
by fetch. A bundle is a file holding one record: either
`{0: 12, 1: list of objects messages}`, or
`{0: 12, 2: recipient identity id, 3: sealed record}`, where the sealed
record is that list [sealed](crypto.md#sealing) to the recipient identity's
encryption key, with context `"bundle"`.

This is not a special mode. It is the same objects and the same checks,
carried by different means.
