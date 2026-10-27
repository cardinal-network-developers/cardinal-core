# Spaces

Status: draft. Normative.

A **space** is the one way data is shared. It is a set of encrypted entries
that form a causal graph, with a list of member identities, their roles, and
a series of encryption keys called epochs. Files, conversations, contact
lists, settings, and public pages are all spaces. They differ only in their
**profile**, which defines what operations they contain
([profiles.md](profiles.md)).

## Entries and sealed entries

A **space entry** is the body of a [signed object](encoding.md#signed-objects)
with exactly one signature, by a device or admin key of the author.

| Key | Field | Type | Notes |
|---|---|---|---|
| 0 | kind = 4 | uint | |
| 1 | space | bytes(32) | space id; absent in genesis |
| 2 | parents | list of bytes(32) | entry ids; absent in genesis, otherwise non-empty |
| 3 | author | bytes(32) | identity id |
| 4 | author log head | bytes(32) | id of an entry in the author's identity log at the time of writing |
| 5 | ops | list of op records | applied atomically, in list order |
| 6 | time | uint | author's clock in milliseconds; display only |
| 7 | epoch | bytes(16) | id of the epoch this entry is encrypted under |
| 8 | wraps hash | bytes(32) | `BLAKE3` of the encoded wraps list, when the sealed entry carries wraps |

- The **entry id** is the id of the signed object. Parents, node ids, and
  deduplication all use entry ids.
- The **space id** is the entry id of the genesis entry.
- An entry is **atomic**: all of its ops apply or none do. Applications put
  changes that must not be seen half-done, such as a folder rename with its
  contents, or a git commit's objects, in one entry.
- Ancestor, concurrent, and log order are defined as in
  [identity.md](identity.md#entries), over entry ids.

A **sealed entry** is what is stored and transferred:

| Key | Field | Type | Notes |
|---|---|---|---|
| 0 | kind = 3 | uint | |
| 1 | epoch | bytes(16) | must equal the inner entry's field 7 |
| 2 | nonce | bytes(24) | first 24 bytes of `BLAKE3.keyed_hash(entry key, entry id)` |
| 3 | ciphertext | bytes | XChaCha20-Poly1305 of the encoded signed object |
| 4 | wraps | list of sealed records | present only when this entry distributes an epoch key |
| 5 | open key | bytes(32) | public spaces only: the epoch key in the clear |

- The **sealed id**, `BLAKE3` of the sealed entry's encoding, identifies the
  stored object. Sync between holders uses sealed ids
  ([sync.md](sync.md)); members use entry ids for everything else.
- The AEAD key is `derive("entry key", epoch key)`. The associated data is
  the encoding of the record of fields 0, 1, and 2.
- The **epoch id** is the first 16 bytes of `derive("epoch id", epoch key)`.
- A sealed entry MUST NOT exceed 256 KiB. Bulk content belongs in
  [blobs](blobs.md).
- A member MUST reject a sealed entry whose nonce is not the one derived
  from its entry id, whose inner field 7 differs from its sealed field 1, or
  whose inner field 8 differs from the hash of its sealed wraps.

So each entry has exactly one sealed form. A member who re-seals someone
else's entry produces the same bytes, not a new object to store and sync,
and cannot alter the wraps it carried.

A host sees how many sealed entries it holds, their sizes, when epochs
change, and how many wraps an entry carries. It does not see membership,
authors, structure, or content.

## Authors

An entry is **attributable** if its signing key is a device or admin key of
the author, effective at the cited head of the author's identity log.

Whether it stays valid depends on what has happened to that key since, as
the verifier knows from the author's log:

- **still effective**: valid;
- **removed in any mode**, retired or compromised: valid only if the entry
  is **witnessed**.

Retired keys are treated like compromised ones here, because a sold laptop
whose key was never wiped could otherwise write as its old owner forever,
citing an old log head. An entry by key `K` is witnessed if it is an ancestor
of, or is listed by, a valid entry of the same author that:

- is signed by another key, and cites a log head that does not contain the
  removal of `K`; or
- contains a `keep` op for `K` that lists it or one of its descendants.

A device's entries are thus kept if its own identity built on them while it
still trusted the device, or if the person chose to keep them afterwards.
The person's other devices are the only witnesses whose word counts: they are
not the thief. Other members building on an entry does not save it. A
witness must itself be valid; since a witness is always a descendant of what
it witnesses, validity can be computed from the newest entries backward.

**Witnessing is routine.** Every write by one of a person's devices
witnesses everything of theirs it has seen. Before writing a removal of a
key, in either mode, software MUST first sync each space it holds with
whatever holders it can reach, and append an empty entry, with all current
heads as parents, in each space where the removed key wrote something not
yet witnessed. A device that retires itself first has another device of the
identity, usually the one replacing it, do the same.

**Keeping after the fact.** When no device was left to witness, as after a
recovery from nothing, software offers to keep a removed device's work up to
a point the person chooses, and writes a `keep` op listing the last entries
to keep. Entries the thief wrote after that point are not ancestors of them,
so they stay invalid.

Software MUST show the person when entries are discarded for these reasons.
Validity converges as identity logs spread. Members MAY hold an entry back
until they have the author's log.

## Roles

| Role | Value | May add | May remove or downgrade |
|---|---|---|---|
| reader | 0 | | itself |
| writer | 1 | | itself |
| admin | 2 | readers, writers, admins | readers, writers; itself |
| owner | 3 | anyone | anyone |

Readers receive epoch keys and read; the only entries they write are their
own reach node, `keep` ops, and their own removal. Writers also append
application ops and rotate epochs. Owners also change policy. The author of the genesis entry is
an owner.

As in identity logs, **no member can remove another of equal role, except
owners removing owners**, so every conflict below owner has an arbiter.
Conflicts between owners [split the space](#splits).

## Control operations

Op numbers 1–31 are control operations, defined here. Op numbers 32 and above
are defined by the space's profile ([state.md](state.md) defines the shared
ones).

| Op | Name | Fields |
|---|---|---|
| 1 | `create` | 1: profile (uint or bytes(32)); 2: policy; 3: id of the space this one was [split](#splits) from, if any. Genesis only. |
| 2 | `add_member` | 1: identity id; 2: role |
| 3 | `set_role` | 1: identity id; 2: role |
| 4 | `remove_member` | 1: identity id |
| 5 | `rotate` | 1: list of `{1: epoch id, 2: key}`: the keys of every epoch this one supersedes, only if history is shared |
| 6 | `set_policy` | 1: policy |
| 7 | `keep` | 1: signing key of a removed device of the author; 2: list of entry ids by that key ([Authors](#authors)) |

**Policy** is a record:

| Key | Field | Default |
|---|---|---|
| 1 | history shared with new members | 1 (yes) |
| 2 | public: epoch keys are published in field 5 | 0 |
| 3 | rotate after this many entries in one epoch | 10000 |

## Evaluating membership

Membership follows the rules of [identity logs](identity.md#evaluating-a-log),
with members in place of keys and roles in place of powers:

- An entry is **valid** if it is attributable, authorized by the membership
  state built from its valid ancestors, and every removal or downgrade of
  its author by a strictly higher role is a descendant of it.
- A member leaving (removing itself) is a retirement: its earlier and
  concurrent entries stay.
- An entry by which an owner removes or downgrades another owner is judged
  by authorization alone. Any other entry by an owner is invalid if it is
  concurrent with a valid entry by another owner that removes or downgrades
  its author. A removed owner therefore cannot keep writing with old parents.

### Splits

A space is **split** when two concurrent valid entries, by different owners,
each remove or downgrade the other's author. Both entries stay valid, so
both owners lose their role in the original space. No rule could choose
between them: two owners who disagree about who belongs are a real
disagreement, and the protocol does not pretend to settle it.

When a member's device sees a split:

- software shows the original space read-only, with its state computed by
  the rules above, and writes nothing more to it;
- software of each owner in the split offers to create a **copy**: a new
  space whose genesis has `create` field 3 naming the original, holds as
  `create` ops the state computed as if only that owner's removal were
  valid, and adds the members that owner chooses;
- other members are offered each copy as an ordinary membership, and choose
  which to accept, or both.

A friendship in which one side was compromised should split, not be decided
by a rule. Each person keeps the history they shared.

## Epochs

Each epoch is a random 32-byte key.

### Distribution

Each entry is encrypted under the current epoch in its causal past, except
that an entry that starts a new epoch (genesis, `rotate`, or an
`add_member` that rotates) is encrypted under the epoch it starts.

An entry distributes an epoch key by carrying, in sealed-entry field 4, one
[sealed record](crypto.md#sealing) per recipient, made with that recipient
identity's current encryption key and the context `"space key" || epoch id`.
The list is in random order and names no recipients; each recipient tries
each record. The entry's field 8 binds the list.

- **Genesis** starts epoch 0, wrapped for every initial member.
- **`add_member`** wraps the current epoch key for the new member. If the
  policy does not share history, the adding entry MUST instead `rotate` and
  wrap the new key for all members.
- **`rotate`** starts a new epoch, wrapped for every current member. If
  history is shared, field 1 carries the key of every epoch it supersedes,
  that is, every epoch current in its causal past. A member holding the
  latest key can therefore walk back to every earlier one, across concurrent
  branches.

A wrap is about 1.2 KB, and an entry is at most 256 KiB, so a space whose
epochs are wrapped this way holds at most about 200 members. Larger groups
need the key tree described in [later.md](../later.md#large-groups).

### When to rotate

A writer MUST rotate, in the same entry as or before its next write, when:

- a member was removed (the removing entry itself SHOULD rotate);
- the current epoch's key was wrapped for an identity that is no longer a
  member;
- a member identity's encryption key changed since the epoch began.

A writer SHOULD rotate when the policy's entry limit is reached.

### Concurrent epochs

Concurrent rotations create several epochs. The **current epoch** is the one
started by the valid epoch-starting entry that is last in log order among
those with no epoch-starting descendants. Writers encrypt under the current
epoch. Readers keep every key they have received.

### What removal means

A removed member keeps every key it held and can read everything written
under those keys, if it can get the ciphertext. It cannot read anything
written under later epochs. You cannot unshare what was shared.

## Public spaces

A space whose policy is public publishes each epoch key in sealed-entry
field 5. Anyone who obtains the entries can read them; only members can
write. Public spaces are how people publish.

## Ephemeral messages

Typing indicators, presence, live cursors, and call signaling are not
entries. They are sent on the link's `ephemeral` service, labeled with the
space id, to members' online devices, and never stored. A device MUST NOT
send ephemeral messages for a space to a device whose identity is not a
member.

## Holding a space

A device **holds** a space if it stores its sealed entries. Holders are:

- devices of member identities, which can read it;
- hosts granted storage by a member, which cannot.

Holders reconcile with [sync.md](sync.md).

A member **accepts** a space by writing any valid entry in it, usually its
reach node. Being added is an offer, not consent: software shows "Ana added
you to Garden club" and writes nothing until the person accepts. Until an
identity accepts, it holds the space only for reading the offer, and the
rules below do not apply to it, in either direction. The adder delivers the
offer through a relationship it already has with that identity; with no
relationship, the offer never arrives.

**Members who accepted are entitled to reach each other.** Sharing a space
is consent given by whoever added the member and by the member who accepted,
so, among accepted members:

- a device MAY open link sessions with devices of every identity that is a
  member of a space it holds, for that space's sync, blobs, and ephemeral
  messages;
- member devices reconcile the identity logs of all of the space's members,
  so that authors can be checked and encryption key changes noticed;
- each member's reach node ([profiles.md](profiles.md#reach)) gives the
  others a delivery token for this space.

A device MUST NOT use a session opened through a shared space to name any
other space, or to deliver anything about any other space.
