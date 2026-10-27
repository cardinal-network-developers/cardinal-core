# Identity

Status: draft. Normative.

An **identity** is a signed, append-only log of entries. The log says which
keys speak for the identity, what each may do, which key encrypts data for
the identity, and who may recover it. An identity is named by the id of its
first entry, so every key in it can change while the name stays.

An identity may be a person, a family, a company, a server, or a software
agent. The protocol does not distinguish them.

## Entries

An identity entry is the body of a [signed object](encoding.md#signed-objects)
with exactly one signature.

| Key | Field | Type | Notes |
|---|---|---|---|
| 0 | kind = 2 | uint | |
| 1 | identity | bytes(32) | absent in the genesis entry |
| 2 | parents | list of bytes(32) | ids of entries this one follows; absent in genesis, otherwise non-empty |
| 3 | ops | list of op records | applied in list order |
| 4 | time | uint | author's clock, milliseconds since 1970; display only, never used for ordering or security |
| 5 | suite | uint | genesis only; `1` for [suite 1](crypto.md#suite-1) |

- The **identity id** is the id of the genesis entry.
- The **signer** of an entry is the key of its one signature. Guardians are
  the only signers who are not keys of the identity; see [Recovery](#recovery).
- The **parents** of a new entry SHOULD be all current heads the author
  knows.
- Entries MUST NOT exceed 64 KiB. An entry whose parents are missing is held
  until they arrive.

The entries form a directed acyclic graph. Entry `A` is an **ancestor** of
`B` if `A` is reachable from `B` through parents. Two entries are
**concurrent** if neither is an ancestor of the other. Concurrency is normal:
two devices that are offline at the same time both append.

The **log order** of a set of entries is a topological order in which, among
entries whose parents have all been placed, the entry with the smallest id
(compared as bytes) comes next. Log order breaks ties; it never decides
authority.

## Keys and powers

| Power | Value | May add | May remove |
|---|---|---|---|
| device | 1 | nothing | itself |
| admin | 2 | device and admin keys | device keys; itself |
| root | 3 | any key | any key |

Above root stands **recovery**: a threshold of guardians, which may remove
any key ([Recovery](#recovery)).

The order is strict on purpose. **No key can remove a key of equal power,
except a root removing a root.** Two equal keys, one honest and one stolen,
are indistinguishable to any protocol. If each could remove the other, the
outcome would depend either on a race or on a rule an attacker can game by
writing entries with old parents. With a strict order, every removal has a
higher arbiter, so conflicts always resolve.

Consequences for people:

- **Phones and most devices are device power.** Losing one is fixed from any
  admin device.
- **One or two devices kept at home are admins**: the first device, and
  usually the always-on one. Adding new devices requires an admin.
- **Losing an admin device is fixed with the recovery phrase or the
  guardians.** It is rare, and it is the case where the protocol cannot know
  which device is honest.

**Root keys** are meant to be offline. The first root key is derived from the
recovery phrase. In normal use, no device keeps a root private key after
setup.

Every device and admin key has a **link key**, a
[hybrid public key](crypto.md#hybrid-public-keys) used for sessions and for
sealing secrets to that device.

There is no partial device. A device that should see only some data, such as
a shared television or a software agent, is its own identity, added as a
member to the spaces it should see ([spaces.md](spaces.md)).

## Operations

Each op is a record whose key `0` is the op number.

| Op | Name | Fields | Signer |
|---|---|---|---|
| 1 | `add_key` | 1: signing key (32); 2: power; 3: link key (device and admin only); 4: label (text, display only); 5: proof | see powers |
| 2 | `remove_key` | 1: signing key; 2: mode: 0 retired, 1 compromised | see powers |
| 3 | `set_encryption_key` | 1: hybrid public key; 2: list of wraps; 3: recovery wrap; 4: key chain | admin or root |
| 4 | `wrap` | 1: list of wraps | admin or root |
| 5 | `set_recovery` | 1: list of guardian identity ids; 2: threshold; 3: delay in seconds; 4: list of sealed shares; 5: recovery public key | root |
| 6 | `recover` | 1: new root key; 2: list of keys to keep; 3: link key of the device that will receive shares; 4: guardian identity id; 5: id of the guardian's log head at signing | a device or admin key of that guardian |
| 7 | `endorse` | 1: id of a `recover` entry; 2: guardian identity id; 3: id of the guardian's log head at signing | a device or admin key of that guardian |
| 8 | `withdraw` | 1: id of an `endorse` entry | the key that signed that `endorse` |
| 9 | `object` | 1: id of a `recover` entry | admin or root |
| 10 | `set_suite` | defined by the suite being adopted | root |
| 11 | `share` | 1: id of a `recover` entry; 2: guardian identity id; 3: id of the guardian's log head at signing; 4: sealed share | a device or admin key of that guardian |

**Proof of possession.** `add_key` field 5 is an Ed25519 signature by the
added signing key over `"cardinal add key" || binding || signing key ||
encoding of link key`, where `binding` is the identity id, or, in the
genesis entry, the root key. It proves the device consented to join this
identity, and it stops anyone from listing someone else's device in their
own log. Verifiers MUST reject an `add_key` without a valid proof, except for
root keys, whose proof is the signature of the entry itself or of a later
entry they sign.

The label in `add_key` is visible to everyone the log is synced with. It
SHOULD be absent; device names belong in the account space
([profiles.md](profiles.md#account)).

A **wrap** is the record `{1: target signing key, 2: fingerprint of the
encryption key, 3: sealed record}`. The sealed record is
[`seal`](crypto.md#sealing) of the encryption private key material to the
target's link key, with context `"identity key" || identity id`.

The genesis entry MUST contain `add_key` for a root key and MUST be signed by
it. It SHOULD also contain, in this order, `add_key` for the first device as
admin, `set_recovery` with at least the recovery public key, and
`set_encryption_key`.

## Evaluating a log

Given a causally closed set of entries (every parent of every entry is in the
set), every device computes the same state by these rules.

1. **Authorization.** An entry is *authorized* if its signer, in the state
   built from its valid ancestors, has the power its ops require.
2. **Revocation.** A **removal** of key `K` is a `remove_key` of `K` with mode
   *compromised* in a valid entry, or a valid `recover` that removes `K`
   (once in effect, see below). An entry signed by `K` is **valid** if it is
   authorized, and every removal of `K` signed by a strictly higher authority
   is a descendant of it.
3. **Retirement.** A `remove_key` with mode *retired*, or any key removing
   itself, ends the key's power for entries that descend from it, but does
   not invalidate the key's earlier or concurrent entries in this log.
   Use it for a device that was sold, broken, or replaced, not one that was
   stolen. Spaces judge entries by removed keys more strictly
   ([spaces.md](spaces.md#authors)).
4. **Roots.** Root keys are removed only by root keys or recovery. An entry
   that adds or removes root keys is judged by authorization alone. Any other
   entry signed by a root key is invalid if it is concurrent with a valid
   entry by another root that removes that key. If two concurrent valid
   entries both change the set of root keys, the identity is **contested**
   ([below](#contested-identities)).
5. **State.** Apply the ops of valid entries in log order. A key is
   **effective** if a valid entry added it, and no removal or retirement of
   it is an ancestor of, or concurrent with, the latest valid entry that
   added it.

Validity of an entry depends only on removals by higher authority, and
changes to the set of roots are judged by authorization alone, so these rules
never loop, and every device that holds the same entries agrees.

What this guarantees:

- **A stolen device's actions after it is stolen are discarded everywhere**,
  once the removal arrives, whatever order things were seen in.
- **Backdating gains nothing.** A removed key that writes new entries with old
  parents produces entries that are concurrent with its removal, and so are
  invalid. It cannot remove keys of its own power or higher, by
  construction.
- **At the top, backdating is visible.** A removed root can still write a
  change to the root set with old parents. That makes the identity contested,
  and only guardians resolve a contest.

### The identity encryption key

Spaces encrypt to identities, not devices. Each identity therefore has one
**encryption key**, a hybrid key pair whose private part is shared by all of
its device and admin keys through wraps.

- `set_encryption_key` MUST include a wrap for every device and admin key
  effective in the entry's causal past, except keys removed by the same
  entry.
- An admin device that sees an effective key without a wrap of the current
  encryption key SHOULD append a `wrap` op for it.
- After any key is removed, an admin MUST append `set_encryption_key` with a
  fresh key before the identity encrypts anything new.
- If concurrent `set_encryption_key` ops leave more than one current key, the
  one whose entry is last in log order is current. Devices keep every
  private key they have received, so earlier ones still decrypt.
- **Key chain.** Field 4 lists one sealed record per encryption key that is
  current in the entry's causal past: that key's private material,
  [sealed](crypto.md#sealing) to the new public key with context
  `"key chain" || identity id`. Whoever holds the newest private key can
  therefore open every earlier one. A new device needs only a wrap of the
  current key to read every space, however long a space has been idle.
- **Recovery wrap.** Field 3 is the new private key sealed to the
  [recovery public key](#recovery-phrase) in effect, with context
  `"recovery wrap" || identity id`. Any admin can write it. Only the phrase,
  or a threshold of guardians, can open it.

### Contested identities

An identity is **contested** while:

- two concurrent valid entries both change the set of root keys, and no
  recovery has taken effect since; or
- a recovery has been objected to and has not yet taken effect or been
  withdrawn.

Having several root keys is not by itself a contest. Devices MUST display a
contested identity as such. Contacts SHOULD NOT accept new space memberships
from it while it is contested.

Only a recovery ends a contest over roots. A root cannot end it, because the
other root can always answer with an entry of its own, and no rule can tell
which of two holders of a root key is the owner.

**Answering a theft.** Software holding a root key, normally only while the
person is entering their phrase, that finds that root removed by an entry it
did not write MUST tell the person. If the person says the removal was not
theirs, the software appends a removal of the other root, whose parents are
the latest heads that do not descend from the hostile entry. The two entries
are then concurrent, the identity is contested, and the guardians decide.

## Recovery

### Recovery phrase

The first root key comes from 256 bits of entropy, shown as 24 words from
the BIP-39 English wordlist, with BIP-39's checksum. The root key seed is
`derive("root key", entropy)`; the Ed25519 key pair is generated from that
seed. BIP-39's PBKDF2 step is not used: it adds nothing to 256 bits of
entropy.

The phrase also gives the **recovery seed**, `derive("recovery key",
entropy)`, and from it the **recovery key pair**, a
[hybrid key pair generated from that seed](crypto.md#hybrid-public-keys).
Its public half is published in `set_recovery` field 5. Its private half
exists only where the phrase is entered.

Entering the phrase on any device recreates the root key and the recovery
key pair. The root key can remove lost devices, add new ones, or replace
itself with a new phrase.

### Guardians

`set_recovery` names guardian identities, a threshold, a delay, and the
recovery public key. The recommended defaults are 3 of 5 and seven days.
Software SHOULD offer to set guardians during first setup, while the root
key is still present.

**Changing guardians waits.** A `set_recovery` that changes the guardians,
the threshold, or the delay **takes effect** at a verifier only once that
verifier has held it for the delay of the policy it replaces. Software of
the replaced guardians alerts them when it sees the change. An identity's
first `set_recovery` takes effect at once. Without the wait, a thief holding
the phrase could replace the guardians before they act; with it, the
guardians have the same delay to act as any recovery gives the owner.

Recovery is collected as separate entries, so that it syncs like everything
else:

1. A guardian's device appends a `recover` entry to the *recovering*
   identity's log, naming the new root key, the keys to keep, the link key
   of the person's new device, and its own identity and log head.
2. Each guardian, after confirming with the person by whatever human means
   they trust, appends an `endorse` entry naming that `recover` entry. The
   guardian who wrote the `recover` entry also endorses it.
3. A `recover` entry's **policy** is the latest `set_recovery` in its causal
   past that had taken effect when the verifier first held the `recover`
   entry. The `recover` entry is ignored if its signer is not an effective
   key of a guardian of that policy, or if some other `set_recovery`, not in
   its causal past, had already taken effect at that time. Former guardians
   therefore cannot recover with old parents.
4. An endorsement **counts** if its signer is an effective key in the
   guardian's log as the verifier holds it, and it has no valid `withdraw`.
   A device removed in any mode after endorsing no longer counts; the
   guardian endorses again from another device. The cited head tells the
   verifier how much of the guardian's log it needs. Verifiers MUST obtain
   the guardians' logs before evaluating a recovery. The recovering
   identity's hosts SHOULD store them.
5. A recovery is **endorsed** when distinct guardians of its policy with
   counting endorsements meet the policy's threshold.

Verifiers MUST persist the times they rely on: when they first held each
`set_recovery` and `recover` entry, and when each recovery became endorsed.

### Taking effect

An endorsed recovery is **pending** until the delay has passed, measured by
each verifier's own clock from when it first held the endorsements that
satisfied the threshold.

Any admin or root key of the identity may append an `object` entry. An
objection does not cancel the recovery. It marks the identity contested,
alerts every guardian, and **doubles the delay**. The delay doubles once,
however many objections there are. Only guardians can stop a recovery, by
withdrawing endorsements until it falls below threshold.

This is the right division of trust. A thief holding the person's phrase can
object, but cannot stop guardians who know the real person. Guardians who
collude against a person face a doubled waiting period, during which the
person, alerted on every device they still hold, can reach the honest
guardians.

When a recovery takes effect, it adds the new root key and removes every key
of the identity not listed in its field 2, in compromised mode. Entries those
keys signed concurrently with the `recover` entry become invalid, as with any
removal.

A recovery becomes **final** when its new root signs a valid entry. The new
root MUST do so as soon as the recovery takes effect, starting with the
`set_recovery` required [below](#data-recovery). After that, withdrawals and
removals of endorsing keys that are not ancestors of the earliest such entry
in log order are ignored. A guardian device stolen years later cannot undo a
recovery.

Whether a recovery is endorsed, withdrawn, or final is a fact about the set
of entries, so every verifier reaches the same outcome. Local clocks decide
only when the outcome applies, and they differ by no more than the time it
takes entries to travel. A verifier that receives a withdrawal after applying
a recovery that is not yet final recomputes the state.

### Data recovery

Getting control back is not enough; a person also needs their data. Every
space is encrypted to the identity encryption key, and that key normally
lives only on devices.

The phrase gives the recovery private key. That opens the latest recovery
wrap, which gives the current encryption key, and its key chain gives every
earlier one.

For people who lose the phrase too, `set_recovery` field 4 carries **sealed
shares** of the recovery seed, with the same threshold as the guardians.
Shares use Shamir secret sharing over GF(2^8) with the reduction polynomial
x^8 + x^4 + x^3 + x + 1, as in SLIP-0039. Each of the seed's 32 bytes is
the constant term of its own random polynomial of degree threshold − 1.
Guardian `i`, counting from 1 in the order of field 1, receives the share
`{1: i, 2: the 32 polynomial values at x = i}`. Field 4 lists one share per
guardian, in the same order, each [sealed](crypto.md#sealing) to that
guardian identity's encryption key with context
`"recovery share" || identity id`. A guardian whose own encryption key
changes later still opens its share, through its own key chain.

When a recovery takes effect, each endorsing guardian's software, having
seen the delay pass on its own clock, opens its share and appends a `share`
entry to the recovering identity's log. The entry carries the share sealed
to the link key named in the `recover` entry, with the same context. The new
device collects the shares from the log, rebuilds the recovery seed with
Lagrange interpolation at zero, and decrypts everything as above.

A threshold of guardians acting together could therefore read the person's
data. That is the same trust that lets them restore the identity, and the
person grants it knowingly. A person who would rather lose their data than
extend that trust sets no shares.

**After any change of root key**, whether by recovery or because the phrase
was exposed, the new root MUST append, in order: `set_recovery` with the new
phrase's recovery public key and fresh shares of its recovery seed, and
`set_encryption_key` with a fresh key, whose recovery wrap uses the new
recovery public key and whose key chain carries the earlier keys. Whoever
held the old phrase can still read what was encrypted before. That is the
physics rule. They cannot read anything after.

### What recovery cannot do

If an attacker and the owner both hold the recovery phrase, no cryptography
can tell them apart. The protocol makes the conflict visible (the identity is
contested) and lets the owner's guardians, who are people who know the
owner, choose. That is the most physics allows.

## Distribution

An identity's log is synced, as a set of signed objects, with:

- its own devices;
- every identity it has a relationship with;
- every identity it shares a space with ([spaces.md](spaces.md#holding-a-space));
- its hosts;
- its guardians, and the identities it guards.

It is synced with [sync.md](sync.md), using the set label
`BLAKE3("identity log" || identity id)`. When two devices open a session,
each reconciles the other's identity log first. This is how revocations
spread. No directory or server is involved.

Devices MUST verify every entry's signature and evaluate the log before
trusting any key in it.

A log is not secret from anyone it is synced with. They see the guardian
identities, the threshold, and how many keys the identity has.

## Display names

Identities have no global names. Each person keeps **petnames**, their own
labels for the identities they know, in their account space
([profiles.md](profiles.md)). An identity may suggest a name for itself in
its profile space; software MUST show the user's own petname when one
exists, and mark any suggested name as unverified.
