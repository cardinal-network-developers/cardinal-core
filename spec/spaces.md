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
| 9 | membership | bytes(16) | id of the author's [membership](#memberships) this entry is written under; absent in genesis and in entries of only `keep` ops |

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

**Validity and state are pure functions of the set of entries**, together
with the identity logs of the space's members. Every member that holds the
same entries and logs computes the same membership, epochs, and state,
whatever order things arrived in and whatever its clock says. The normative
rules are the `space` program in [model/rules.md](../model/rules.md), which
is [stratified](identity.md#evaluating-a-log) like the identity rules.

The first layer decides whether an entry's signature **counts as its
author's**. It depends only on the author's identity log, never on who is a
member, so it cannot loop through membership:

- the signing key must be a device or admin key of the author, in effect at
  the cited head of the author's identity log, as
  [evaluated](identity.md#evaluating-a-log) from the whole log the verifier
  holds. A key whose adding entry is invalid was never added;
- if the key has since been removed, the entry must be **witnessed**;
- if the author is [frozen](identity.md#frozen-identities), the entry
  counts only if others built on it: evaluated as if no author were frozen,
  its signature counts and it is in the causal past of a valid entry by an
  author who is not frozen. What a frozen author wrote before anyone knew
  stands, with everything others built on it; nothing new does. This is the
  one place the rules evaluate the space twice, once as if no one were
  frozen and once for real, which cannot loop. Software MUST NOT build on
  entries of an author it knows to be frozen.

A key may have been sold, broken, or stolen; the space cannot tell which,
and a sold laptop whose key was never wiped could otherwise write as its old
owner forever, citing an old log head. An entry by key `K` is witnessed if
it is an ancestor of, or is listed by, an entry of the same author whose
signature counts and that:

- is signed by another key, and cites a head that does not contain the
  removal of `K`; or
- contains a `keep` op for `K` that lists it or one of its descendants.

A device's entries are thus kept if its own identity built on them while it
still trusted the device, or if the person chose to keep them afterwards.
The person's other devices are the only witnesses whose word counts. Other
members building on an entry does not save it. An entry of only `keep` ops
needs no membership, so a person can keep their old work in a space they
have since left, or after a recovery that kept none of their keys.

**Witnessing is ordinary.** Every write by one of a person's devices
witnesses everything of theirs it has seen. That includes, unavoidably,
anything a thief wrote with a stolen device before the person noticed: until
then the person's own devices trusted it. Software therefore treats removals
in two ways, which differ only in what the software does, not in the
protocol:

- **Retired** (sold, replaced, broken): before writing the removal, software
  syncs each space it holds with whatever holders it can reach, and appends
  an empty entry, with all current heads as parents, in each space where the
  device wrote something not yet witnessed. Nothing honest is lost.
- **Lost or stolen**: software witnesses nothing. It shows the person the
  device's unwitnessed entries in each space, and writes a `keep` op for
  those the person recognizes, up to the point they choose.

Entries a thief wrote after that point are not ancestors of what is kept, so
they stay invalid.

Software MUST show the person when entries are discarded for these reasons.
Validity converges as identity logs spread. Members MAY hold an entry back
until they have the author's log.

## Memberships

Roles belong to **memberships**, not to identities. Each `add_member` op
creates a membership: one identity, one role, fixed for the membership's
life. Its id is the first 16 bytes of `BLAKE3(entry id || varint(i))`,
where `i` is the position of the op in its entry, as for
[node ids](state.md#nodes). The genesis creates its author's membership, as
owner, the same way from its `start` op. Every entry names, in field 9, the
membership it is written under.

- **Ending** a membership is `remove_member` with its id. A member may end
  its own membership at any time: that is leaving. Only the membership's own
  identity can leave it: the entry must be written by that identity, under
  that membership, in the membership's causal future, with a signature that
  counts.
- **Changing a role** is ending one membership and adding another for the
  same identity, in the same entry.
- **Adding someone who is already a member** creates a second membership. It
  changes nothing about the first, so it cannot be used to demote anyone.
- An identity may be added again after its membership ended.

| Role | Value | May add | May end |
|---|---|---|---|
| reader | 0 | | its own |
| writer | 1 | | its own |
| admin | 2 | readers, writers, admins | readers', writers'; its own |
| owner | 3 | anyone | admins', writers', readers'; its own |

Readers receive epoch keys and read; the only entries they write are their
own reach node, `keep` ops, and their own leaving. Writers also append
application ops and rotate epochs. Owners also change policy and protocol, and
[succeed](#succession) the space.

As in identity logs, **no member can end the membership of another of equal
role**. Owners cannot remove owners. Every conflict has a higher arbiter, and
above the owners stand their identities: a compromised owner device is
removed in the owner's identity log, and a compromised owner identity is
recovered by its guardians, or frozen. Owners who disagree with each other do
not fight inside the space; any of them can [succeed](#succession) it with
the members they choose.

## Control operations

Op numbers 1–31 are control operations, defined here. Op numbers 32 and above
are defined by the space's profile ([state.md](state.md) defines the shared
ones).

| Op | Name | Fields |
|---|---|---|
| 1 | `start` | 1: profile (uint or bytes(32)); 2: policy; 3: id of the space this one [succeeds](#succession), if any; 4: initial state: [blob reference](blobs.md#references) to a [canonical state](state.md#canonical-state); 5: [protocol record](evolution.md#declaring-what-you-speak). Genesis only. |
| 2 | `add_member` | 1: identity id; 2: role. Creates a [membership](#memberships). |
| 3 | | reserved |
| 4 | `remove_member` | 1: membership id |
| 5 | `rotate` | 1: list of `{1: epoch id, 2: key}`: the keys of every epoch this one supersedes, only if history is shared |
| 6 | `set_policy` | 1: policy |
| 7 | `keep` | 1: a removed signing key of the author; 2: list of entry ids by that key ([Authors](#authors)) |
| 8 | `succeed` | 1: id of the successor space ([Succession](#succession)) |
| 9 | `set_protocol` | 1: [protocol record](evolution.md#declaring-what-you-speak). Owners only. |

**Policy** is a record:

| Key | Field | Default |
|---|---|---|
| 1 | history shared with new members | 1 (yes) |
| 2 | public: epoch keys are published in field 5 | 0 |
| 3 | rotate after this many entries in one epoch | 10000 |

## Evaluating membership

After authors, the rules work in layers by role, from owners down to
readers:

- An entry is **valid** if its signature counts as its author's, its
  membership was created by a valid entry in its causal past, its ops are
  allowed to that membership's role, and its membership had not ended in its
  causal past.
- An entry **concurrent with the end of its membership** is invalid, unless
  the end was a change to a lower role and the entry's ops are allowed to
  the new role. So a demoted admin's concurrent messages stand, and their
  concurrent `add_member` does not.
- A membership's end counts only if it was written by a valid entry of a
  strictly higher role, or by the member leaving. Because every end comes
  from a higher layer, these rules never loop, and backdating gains nothing
  at any role: an entry written with old parents after an end is concurrent
  with it.
- **Leaving** voids what descends from it, and, of what is concurrent with
  it, only entries signed by the same key. A stolen phone that backdates its
  owner's leave or `succeed` cannot erase what the owner's other devices
  wrote; and a member who leaves cannot keep writing with that device by
  backdating.
- **Ending an admin's membership**, including lowering its role, voids its
  concurrent `add_member` ops, and so the memberships they created and
  everything written under them. Keeping them would let a lowered admin
  backdate additions forever. Software MUST warn the person lowering or
  removing an admin when this discards members, and offers to add them
  again; their software re-applies their discarded work as changes to
  re-apply.

## Succession

A space can be **succeeded** by a new one. Succession is how a space starts
fresh, how a history is bounded, and how owners part ways.

An owner writes `succeed`, naming a successor space it has created. The
successor's genesis has `start` field 3 naming the old space and field 4
holding the old space's state, computed from the `succeed` entry's causal
past, as its initial state. Node ids carry over, so references into the old
state still resolve. In the successor, the genesis counts as descending from
every entry whose values it carries, so the first `set` of a carried field
settles any conflict carried with it.

A member who holds the old space MUST check that the initial state is what
it computes at the `succeed` entry, and MUST NOT accept the successor if it
is not. A member who does not hold the old space cannot check, so software
shows carried content as carried over by the successor's creator, not as
written by its original authors. The successor's members, roles, and policy are whatever
its genesis says. Its history starts at genesis; the old space's history
stays where it is, for those who keep it.

A `succeed` is the owner leaving the old space, with a forwarding address:

- If owners remain, the old space continues among its remaining members.
  Members of the old space are offered the successor if its genesis added
  them, and may belong to both.
- After a `succeed`, an entry that descends from it and has no owner
  membership in effect in its causal past is invalid: once its last owner
  has left, the old space is **closed**. Entries
  concurrent with a `succeed`, written by members who had not seen it, stay
  valid in the old space. Software shows them in the successor as changes to
  re-apply, like any conflict, and never applies them silently.

So:

- **Start fresh, or bound history.** The sole owner of a files space, or
  every owner of a group, succeeds the space. New devices start from the
  successor's genesis. The old space can be archived to a host or dropped.
- **Ephemeral conversations.** A conversation policy that succeeds the space
  every few days, carrying no state forward, and deletes the old keys,
  gives disappearing messages ([later.md](../later.md#ephemeral-conversations)).
- **Owners who disagree.** One owner of a relationship space, or of a group,
  succeeds it with the members they choose. The others keep the old space.
  A friendship in which one side was compromised ends this way, or by the
  compromised side's recovery; it is not decided by a rule.

Both owners of a relationship space succeed it together for a fresh start:
one proposes a successor, and the other accepts it by writing its own
`succeed` naming the same successor.

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
