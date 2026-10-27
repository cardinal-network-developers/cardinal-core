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
| root | 3 | device and admin keys | device and admin keys; itself, by [replacement](#roots) |

Above root stands **recovery**: a threshold of guardians, which may replace
every key ([Recovery](#recovery)).

The order is strict on purpose. **No key can remove a key of equal power.**
Two equal keys, one honest and one stolen, are indistinguishable to any
protocol. If each could remove the other, the outcome would depend either on
a race or on a rule an attacker can game by writing entries with old
parents. With a strict order, every removal has a higher arbiter, and the
chain ends with people: the guardians.

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
| 2 | `remove_key` | 1: signing key | see powers |
| 3 | `set_encryption_key` | 1: hybrid public key; 2: list of wraps; 3: recovery wraps; 4: key chain | admin or root |
| 4 | `wrap` | 1: list of wraps | admin or root |
| 5 | `set_recovery` | 1: list of guardian identity ids; 2: threshold; 3: delay in seconds; 4: list of sealed shares; 5: recovery public key; 6: guardian public key; 7: recovery wraps of the current encryption key | root |
| 6 | `recover` | 1: new root key; 2: list of signing keys to keep; 3: link key of the device that will receive shares; 4: guardian identity id; 5: id of the guardian's log head at signing | a key of that guardian |
| 7 | `endorse` | 1: id of a `recover` entry; 2: guardian identity id; 3: id of the guardian's log head at signing | a key of that guardian |
| 8 | `confirm` | 1: id of a `recover` or `set_recovery` entry; 2: guardian identity id; 3: id of the guardian's log head at signing; 4: sealed share (recoveries only) | a key of that guardian |
| 9 | `object` | 1: id of a `recover` or `set_recovery` entry | admin or root |
| 10 | `set_suite` | defined by the suite being adopted | root, [replacing itself](#roots) |

"A key of that guardian" means a device or admin key that is effective in the
guardian's identity log at the cited head. Later changes to the guardian's
log do not affect an entry already written.

**Proof of possession.** `add_key` field 5 is an Ed25519 signature by the
added signing key over `"cardinal add key" || binding || signing key ||
encoding of link key`, where `binding` is the identity id, or, in the
genesis entry, the root key. It proves the device consented to join this
identity, and it stops anyone from listing someone else's device in their
own log. Verifiers MUST reject an `add_key` without a valid proof, except for
the genesis root key, whose proof is the genesis signature.

The label in `add_key` is visible to everyone the log is synced with. It
SHOULD be absent; device names belong in the account space
([profiles.md](profiles.md#account)).

A **wrap** is the record `{1: target signing key, 2: fingerprint of the
encryption key, 3: sealed record}`. The sealed record is
[`seal`](crypto.md#sealing) of the encryption private key material to the
target's link key, with context `"identity key" || identity id`.

The genesis entry MUST contain `add_key` for one root key, MUST be signed by
it, and MUST contain `set_recovery`, with at least the recovery public key.
It SHOULD also contain `add_key` for the first device as admin, and
`set_encryption_key`.

### Roots

An identity has one root key. The set of roots changes in only three ways:

- the genesis entry adds the first root;
- a root **replaces itself**: an entry signed by root `R` whose ops are
  exactly an `add_key` of a new root, with its proof, and a `remove_key` of
  `R`, and nothing else. A new phrase, and a new suite, are replacements;
- a [recovery](#recovery) in effect.

No entry may add a root in any other way, and no root may remove another.

## Evaluating a log

**Validity and state are pure functions of the set of entries.** Every
device that holds the same causally closed set (every parent of every entry
is in the set) computes the same result, whatever order the entries arrived
in and whatever its clock says. Local time affects only when software acts,
such as when a guardian chooses to sign, never what a set of entries means.

1. **Authorization.** An entry is *authorized* if its signer, in the state
   built from its valid ancestors, has the power its ops require.
2. **Removals.** A **removal** of key `K` is a `remove_key` of `K` in a valid
   entry, or a recovery in effect that does not keep `K`, in which case the
   removal is the `recover` entry.
3. **Revocation.** An entry signed by `K` is **valid** if it is authorized
   and it is an ancestor of every removal of `K`. Two exceptions: an entry in
   which `K` removes itself is not invalidated by other removals of `K` by
   `K` itself, so two concurrent replacements of a root both stand; and
   [guardian decisions](#guardian-decisions) are judged by their own rules.
4. **State.** Apply the ops of valid entries in log order. A key is
   **effective** if a valid entry added it and no removal of it is in the
   set, or a recovery in effect keeps it. A removed key is never added again.

The causal past of a removal is what the identity keeps of the removed key's
work. Everything else that key signed, whenever it was written, is
discarded. So:

- **Backdating gains nothing.** A removed key that writes new entries with
  old parents produces entries that are not ancestors of its removal.
- **The remover chooses what to keep.** A removal is written by a higher
  authority, so it may have any parents. When a person removes a device they
  sold or replaced, software uses all current heads, and keeps everything
  the device did. When a device was lost or stolen, software shows the person
  the device's entries in the identity log that other keys have not already
  built on, and picks parents that leave out any the person does not
  recognize.
- **Keys added by a removed key** stay unless the person removes them too.
  Software MUST show them to the person when it writes the removal.

These rules never loop. A key's entries depend only on removals by strictly
higher authority, or by itself, and at the top on recoveries, which depend
only on guardians' entries.

### The identity encryption key

Spaces encrypt to identities, not devices. Each identity therefore has one
**encryption key**, a hybrid key pair whose private part is shared by all of
its device and admin keys through wraps.

- `set_encryption_key` MUST include a wrap for every device and admin key
  effective in the entry's causal past, except keys removed by the same
  entry.
- An admin device that sees an effective key without a wrap of the current
  encryption key SHOULD append a `wrap` op for it.
- After any key is removed, and after any change of guardians takes effect,
  an admin MUST append `set_encryption_key` with a fresh key before the
  identity encrypts anything new.
- If concurrent `set_encryption_key` ops leave more than one current key, the
  one whose entry is last in log order is current. Devices keep every
  private key they have received, so earlier ones still decrypt.
- **Key chain.** Field 4 lists one sealed record per encryption key that is
  current in the entry's causal past: that key's private material,
  [sealed](crypto.md#sealing) to the new public key with context
  `"key chain" || identity id`. Whoever holds the newest private key can
  therefore open every earlier one. A new device needs only a wrap of the
  current key to read every space, however long a space has been idle.
- **Recovery wraps.** Field 3 is a list of sealed records of the new private
  key, with context `"recovery wrap" || identity id`: one to the
  [recovery public key](#recovery-phrase) and one to the
  [guardian public key](#data-recovery) of the policy in effect in the
  entry's causal past. Any admin can write them. Only the phrase, or a
  threshold of guardians, can open them.
- **Checking.** Nobody but the holders of the keys can check a seal, so a
  device that receives a wrap, a key chain, or a recovery wrap it can open
  MUST check that it holds the key it claims to. If one is wrong, an admin
  device appends `set_encryption_key` with a fresh key and a correct chain
  built from the keys it holds, and software tells the person.

### Contested identities

An identity is **contested** while:

- more than one root key is effective, as after two concurrent replacements;
  or
- two [guardian decisions](#guardian-decisions) conflict.

Devices MUST display a contested identity as such. Contacts SHOULD NOT accept
new space memberships from it while it is contested. A recovery in effect
ends the first kind of contest; the next section says how the second ends.

A pending recovery is not a contest. Software shows it as a warning, to the
person and to their contacts.

**Answering a theft.** Software holding the root key, normally only while the
person is entering their phrase, that finds the root replaced by an entry it
did not write MUST tell the person. If the person says the replacement was
not theirs, the software replaces the root itself, with parents that do not
descend from the hostile entry. Both replacements stand, the identity is
contested, and the guardians decide. Until they do, both roots can act, so a
phrase thief can disrupt the identity. Only the guardians can stop them,
which is why guardians matter.

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

`set_recovery` sets the **recovery policy**: guardian identities, a
threshold, a delay, and the public keys. When guardians are named, the
threshold MUST be more than half of them; a `set_recovery` that breaks this
is invalid. The recommended default is 3 of 5 with a delay of seven days.
More guardians make the identity more robust, because the threshold must be
reachable for as long as the policy lasts. Software SHOULD offer to set
guardians during first setup, while the root key is still present.

### Guardian decisions

Two kinds of entry are **guardian decisions**: a `recover` entry, and any
`set_recovery` after the one in genesis. Either is alone in its entry. Guardians decide both. Your court
approves changes to your court.

- **Knowing.** Decision `D` **knows** decision `E` if `D`'s entry descends
  from confirmations of `E` that meet `E`'s threshold.
- **Policy.** A decision's policy is the one set by the latest change in
  effect that it knows, or else the genesis policy.
- **Signer.** A `set_recovery` decision must be signed by a key that is a
  root in the state built from its causal past, judged by rule 1 alone. A
  `recover` decision must be signed by a key of a guardian of its policy.
  Removals do not invalidate either: guardians judge them instead.
- **Confirmed.** A decision is confirmed when distinct guardians of its
  policy, meeting its threshold, have each appended a `confirm` naming it.
  A decision whose policy names no guardians is confirmed at once.
- **In effect.** A confirmed decision is in effect unless it **conflicts**
  with another confirmed decision, that is, neither knows the other. Then
  neither is in effect, and the identity is contested. A later decision that
  knows both ends the conflict; it is confirmed only when a threshold of
  each policy involved has confirmed it: its own, and the one each
  conflicting decision would have set.

Honest guardians never cause a conflict: guardian software MUST NOT confirm
a decision that does not know a decision it has already confirmed, except
one that ends a conflict. A threshold is always a majority, and two
majorities always share a guardian, so a conflict means some guardian
confirmed both sides, or the identity had no guardians and a thief with the phrase
raced its owner. Only a threshold of each side's guardians can end it. A
person who sets guardians at first setup never faces the second case.

### How guardians act

Everything that follows is what guardian software does, on its own clock.
None of it affects what a set of entries means.

1. **Recover.** A guardian's device appends a `recover` entry to the
   *recovering* identity's log, naming the new root key, the keys to keep,
   the link key of the person's new device, and its own identity and log
   head.
2. **Endorse.** Each guardian, after confirming with the person by whatever
   human means they trust, appends `endorse`. Before endorsing, guardian
   software MUST show a short fingerprint of `recover` fields 1 and 3, which
   the person reads from their new device. A guardian who wrote the
   `recover` entry also endorses it. An endorsement binds nothing. It tells
   everyone a recovery is wanted.
3. **Wait.** When a threshold of guardians has endorsed, the recovery is
   **pending**. Each guardian's software alerts the person's devices and
   waits the policy's delay, on its own clock, from when it saw the
   threshold. If it has seen an `object` naming the recovery, it waits twice
   the delay. It doubles once, however many objections there are.
4. **Confirm.** After the wait, and after checking the fingerprint again
   with the person, the guardian appends `confirm`, carrying their
   [share](#data-recovery). A guardian who has changed their mind simply
   does not confirm.

A change of policy is decided the same way, without steps 1 and 2: guardian
software that sees a `set_recovery` alerts the person's devices, waits the
delay (doubled after an objection), checks with the person, and confirms.

Any admin or root key of the identity may append an `object`. It cancels
nothing and binds no one. It tells guardians that a device the person holds
disagrees, and doubles their wait. A thief holding the person's phrase can
object, but cannot stop guardians who know the real person. Guardians who
collude against a person face a doubled wait, during which the person,
alerted on every device they still hold, can reach the honest ones.

### What a recovery does

When a recovery is in effect:

- its new root key is the identity's root, and the device and admin keys in
  its field 2 keep the powers they last had, even if they were removed in its causal past;
- every other key is removed. By rule 3, everything those keys signed that
  is not an ancestor of the `recover` entry is invalid, including anything a
  thief wrote with old parents, before or after;
- the new root proves possession by signing its first entry. It MUST then
  append `set_recovery` with the new phrase's recovery public key and a new
  guardian key and shares, and `set_encryption_key` with a fresh key whose
  key chain carries the earlier keys. That `set_recovery` is a decision like
  any other, and the guardians who just acted confirm it.

A recovery is never undone. Whether it is in effect depends only on
confirmations, and a confirmation cannot be withdrawn. A guardian device
stolen years later can start a new recovery, which needs a new threshold,
but cannot touch an old one.

### Data recovery

Getting control back is not enough; a person also needs their data. Every
space is encrypted to the identity encryption key, and that key normally
lives only on devices.

The phrase gives the recovery private key. That opens the latest recovery
wrap, which gives the current encryption key, and its key chain gives every
earlier one.

For people who lose the phrase too, each policy that names guardians has its
own **guardian key**: 32 random bytes `g`, and the
[hybrid key pair generated from it](crypto.md#hybrid-public-keys), whose
public half is `set_recovery` field 6. Field 7 carries the current
encryption private key sealed to field 5 and field 6, as recovery wraps, so
new guardians can open it at once. Field 4 carries **sealed shares** of `g`.
Shares use Shamir secret sharing over GF(2^8) with the reduction polynomial
x^8 + x^4 + x^3 + x + 1, as in SLIP-0039. Each of the 32 bytes of `g` is the
constant term of its own random polynomial of degree threshold − 1.
Guardian `i`, counting from 1 in the order of field 1, receives the share
`{1: i, 2: the 32 polynomial values at x = i}`. Field 4 lists one share per
guardian, in the same order, each [sealed](crypto.md#sealing) to that
guardian identity's encryption key with context
`"recovery share" || identity id`. A guardian whose own encryption key
changes later still opens its share, through its own key chain.

A guardian's `confirm` of a recovery carries, in field 4, their share sealed
to the link key named in the `recover` entry, with the same context. Shares
are released only by confirming, so no share leaves a guardian before the
wait is over. The new device collects the shares from the log, rebuilds `g`
with Lagrange interpolation at zero, and opens the newest guardian wrap made
to that policy's guardian key.

Guardians are replaced together with their key. When a new policy takes
effect, its `g` is new, and the identity rotates its encryption key, so
former guardians cannot read anything written after. A threshold of current
guardians acting together could read the person's data. That is the same
trust that lets them restore the identity, and the person grants it
knowingly. A person who would rather lose their data than extend that trust
leaves field 6 and field 4 empty.

**After the phrase is exposed**, the root replaces itself with a new
phrase's root, then appends `set_recovery` with the new recovery public key,
and `set_encryption_key` with a fresh key whose recovery wraps use it.
Whoever held the old phrase can still read what was encrypted before. That
is the physics rule. They cannot read anything after.

### What recovery cannot do

If an attacker and the owner both hold the recovery phrase, no cryptography
can tell them apart. The protocol makes the conflict visible (the identity is
contested) and lets the owner's guardians, who are people who know the
owner, choose. If guardians themselves split into two majorities, nothing
can choose for them. That is the most physics allows.

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
identities, the threshold, and how many keys the identity has. Verifiers
need each guardian's log up to the heads its entries cite; the identity's
hosts SHOULD store those logs.

## Display names

Identities have no global names. Each person keeps **petnames**, their own
labels for the identities they know, in their account space
([profiles.md](profiles.md)). An identity may suggest a name for itself in
its profile space; software MUST show the user's own petname when one
exists, and mark any suggested name as unverified.
