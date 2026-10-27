# Identity

Status: draft. Normative.

An **identity** is a signed, append-only log of entries. The log says which
keys speak for the identity, what each may do, which key encrypts data for
the identity, and who may recover it. An identity is named by the id of its
first entry, so every key in it can change while the name stays.

An identity may be a person, a family, a company, a server, or a software
agent. The protocol does not distinguish them.

The rules that decide which entries are valid are written as a small logic
program in [model/rules.md](../model/rules.md), which is normative and is
checked by machine. This document explains them.

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
- The **signer** of an entry is the key of its one signature. A `recover`
  entry is signed by the new root key it names; every other entry by a key of
  the identity ([Recovery](#recovery)).
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
| device | 1 | nothing | nothing |
| admin | 2 | device and admin keys | device keys |
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
| 1 | `add_key` | 1: signing key (32); 2: power; 3: link key (device and admin only); 4: label (text, display only); 5: proof; 6: recovery public key (roots only) | see powers |
| 2 | `remove_key` | 1: signing key | see powers |
| 3 | `set_encryption_key` | 1: hybrid public key; 2: list of wraps; 3: recovery wraps; 4: key chain | admin or root |
| 4 | `wrap` | 1: list of wraps | admin or root |
| 5 | `set_recovery` | 1: list of guardian identity ids; 2: threshold; 3: delay in seconds; 4: list of sealed shares; 5: guardian public key; 6: recovery wraps of the current encryption key; 7: id of the policy this changes (absent in genesis) | see [Guardian decisions](#guardian-decisions) |
| 6 | `recover` | 1: new root key; 2: list of signing keys to keep; 3: link key of the device that will receive shares; 4: id of the policy it acts under; 5: recovery public key of the new root | the new root key |
| 7 | `endorse` | 1: identity id; 2: id of a decision in that identity's log | any key of the guardian, in the **guardian's own log** |
| 8 | `confirm` | 1: identity id; 2: id of a decision in that identity's log; 3: sealed share (recoveries only) | any key of the guardian, in the **guardian's own log** |
| 9 | `object` | 1: id of a decision | admin or root |
| 10 | `set_suite` | defined by the suite being adopted | root, [replacing itself](#roots) |

`endorse` and `confirm` are written by guardians about *another* identity,
in their own logs, so that their own revocation rules govern them and every
device of the guardian sees what the guardian has confirmed.

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

The genesis entry MUST contain `add_key` for one root key, with its
recovery public key, MUST be signed by it, and MUST contain `set_recovery`,
which may name no guardians. It SHOULD also contain `add_key` for the first
device as admin, and `set_encryption_key`. An entry that contains
`set_recovery` after genesis, or `recover`, contains nothing else.

### Roots

An identity has one root key. The set of roots changes in only three ways:

- the genesis entry adds the first root;
- a root **replaces itself**: an entry signed by root `R` whose ops are
  exactly an `add_key` of a new root, with its proof and the new phrase's
  recovery public key, and a `remove_key` of `R`, and nothing else. A new
  phrase, and a new suite, are replacements;
- a [recovery](#recovery) in effect.

No entry may add a root in any other way, and no root may remove another.

## Evaluating a log

**Validity and state are pure functions of the set of entries.** Every
device that holds the same causally closed set (every parent of every entry,
and every decision a confirmation names, is in the set) computes the same
result, whatever order the entries arrived in and whatever its clock says.
Local time affects only when software acts, such as when a guardian chooses
to confirm, never what a set of entries means.

The normative rules are the `identity` program in
[model/rules.md](../model/rules.md). It is **stratified**: it works in
layers that follow authority, each layer only adds facts, and a rule may
depend on the *absence* of a fact only if that fact comes from an earlier
layer. A stratified program has exactly one result, and
[model/check.py](../model/check.py) verifies that these rules are
stratified. The layers are:

1. **Guardian decisions**, which depend only on guardians' confirmations and
   on the shape of entries ([below](#guardian-decisions)).
2. **What recoveries remove.**
3. **Roots**, then whether the identity is **contested**.
4. **Admins**, whose entries only roots and recoveries can invalidate.
5. **Devices**, whose entries only admins, roots and recoveries can
   invalidate.
6. **Results**: keys in effect, the current encryption key, and whether the
   identity is **frozen**.

Within each layer, three ideas do the work:

- **Authorization.** An entry is authorized if its signer was in effect, with
  the power its ops require, in the entry's own causal past.
- **Revocation.** An entry signed by a removed key is valid only if it is an
  ancestor of every removal of that key. The causal past of a removal is
  what the identity keeps of the removed key's work. Everything else that
  key signed, whenever it was written, is discarded.
- **Strict authority.** A key's entries can be invalidated only by a
  removal from a strictly higher layer, so nothing loops.

So:

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

An identity is **contested** while more than one root key is in effect.
Only two concurrent replacements of the same root cause that: the owner and
a thief who both hold the phrase each replaced it.

While an identity is contested:

- every entry signed by a root in effect waits, except further root
  replacements. Neither side can add or remove keys;
- the current encryption key is the latest one that is an ancestor of every
  root in effect, so neither side can move the identity to a key it chose;
- devices MUST display the identity as contested, and contacts SHOULD NOT
  accept new space memberships from it or rotate spaces to its keys.

A contest ends only by a recovery, which the guardians decide.

**Answering a theft.** Software holding the root key, normally only while the
person is entering their phrase, that finds the root replaced by an entry it
did not write MUST tell the person. If the person says the replacement was
not theirs, the software replaces the root itself, with parents that do not
descend from the hostile entry. The identity is then contested, and the
guardians decide. Without guardians, it is frozen.

### Frozen identities

Some conflicts have no one above them to settle them. An identity is
**frozen** when its entries show one of these:

- **Guardians who decided both ways.** Two decisions in effect under the
  same policy, neither an ancestor of the other, or one made after a change
  of that policy in its own past. With a majority threshold, that means some
  guardian confirmed both, or the policy had no guardians and two holders of
  the phrase acted.
- **A contest with no guardians to settle it.** The identity is contested
  and its current policy names no guardians.
- **Guardians named by one side of a contest.** A policy without guardians
  was changed by an entry that is not an ancestor of both sides of a root
  contest.

Freezing is permanent. Adding entries never unfreezes an identity, which the
fuzzer in [model/fuzz.py](../model/fuzz.py) checks. A frozen identity's
entries are no longer accepted in any space, and its keys no longer open
sessions. Software shows contacts that the identity "can no longer be
trusted", and offers the person and their contacts the slow, manual way
forward: a new identity, recognized by each contact in person
([later.md](../later.md#starting-over)).

A pending recovery is neither contested nor frozen. Software shows it as a
warning, to the person and to their contacts.

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
Its public half belongs to the root key: it is `add_key` field 6 of the
entry that added the root, or `recover` field 5. A new phrase therefore
brings a new recovery key with it, in effect at once, because it is the
root's own secret and needs no one's approval. The private half exists only
where the phrase is entered.

Entering the phrase on any device recreates the root key and the recovery
key pair. The root key can remove lost devices, add new ones, or replace
itself with a new phrase.

### Guardians

`set_recovery` sets the **recovery policy**: guardian identities, a
threshold, a delay, and the guardian key. When guardians are named, the
threshold MUST be more than half of them; a `set_recovery` that breaks this
is invalid. The recommended default is 3 of 5 with a delay of seven days.
More guardians make the identity more robust, because a majority must stay
reachable for as long as the policy lasts. Software SHOULD offer to name
guardians during first setup, and SHOULD keep asking until the person has.
Guardians named later protect against theft only from then on: whoever
held a phrase that was in use while the identity had no guardians can
freeze it.

A software agent's guardians are naturally the people it acts for. An agent
cannot meet anyone in person, so the trust its contacts place in it beyond
its keys comes from the humans who vouch for it, and its recovery is theirs
to decide.

### Guardian decisions

Two kinds of entry are **guardian decisions**: a `recover` entry, and any
`set_recovery` after the one in genesis. Each is alone in its entry, names
the policy it acts under, and must descend from that policy's entry.
Guardians decide both. Your court approves changes to your court.

- **Confirmations.** A guardian confirms a decision with a `confirm` op in
  the guardian's own log. A confirmation counts if it is valid, and the
  guardian is not frozen, when the guardian's log is evaluated over the
  confirmation's own causal past. It is judged as of when it was made;
  nothing later in the guardian's log changes it. That past is always
  smaller than the set being evaluated, so this never loops, even when two
  people guard each other, or guard each other while both recover.
  Each guardian counts once, however many of its keys confirm.

  Judging as of the past has a consequence worth stating. A guardian frozen
  later keeps the confirmations it made before, which is what makes a
  recovery final. But a thief holding a guardian's phrase or device can
  still confirm on a branch of the guardian's log that does not show the
  freeze. That is one vote, the same as any stolen guardian device
  ([D31](../decisions.md)). An identity whose guardian is frozen SHOULD
  replace that guardian, which the remaining guardians approve.
- **Signer.** A `recover` is signed by the new root key it names, which
  proves possession. A `set_recovery` is signed by a key of the identity.
- **Approved.** Under a policy that names guardians, a decision is approved
  when distinct guardians of that policy, meeting its threshold, have
  counting confirmations of it. Under a policy that names no guardians, a
  `recover` is never approved, and a `set_recovery` is approved if it is
  signed by a root that is in its causal past and was not replaced there.
- **In effect.** A decision is in effect if it is approved and the policy it
  acts under is in effect. The genesis policy is in effect, and so is every
  `set_recovery` decision in effect.

Decisions only accumulate: nothing that arrives later takes one out of
effect. Confirmations arrive in any order, so a rule that ignored a decision
because of a change approved afterwards would undo something already in
effect. Instead, a decision under a policy that had already been changed in
its own causal past is evidence that guardians misbehaved, and it
[freezes](#frozen-identities) the identity, as do two decisions under one
policy that do not know each other. Former guardians therefore cannot act on
a policy they agreed to replace; acting together, they can only freeze it.

Honest guardians never cause a freeze. Guardian software MUST NOT confirm a
decision under a policy if the decision's causal past contains a change of
that policy that is approved or that the guardian has confirmed, or if the
decision is concurrent with another decision under that policy that the
guardian has confirmed. It MUST sync the guardian's own log before
confirming, so that a guardian's phone and laptop cannot confirm opposite
decisions unawares.

### How guardians act

Everything that follows is what software does, on its own clock. None of it
affects what a set of entries means.

1. **Recover.** The person's new device generates a new root key and a new
   phrase. A guardian's device, which holds the identity's log, proposes
   parents: the latest entries that the person recognizes, leaving out any
   a thief wrote. The new device signs the `recover` entry, naming the new
   root, the keys to keep, its link key, and the policy, and the guardian's
   device appends it to the identity's log.
2. **Endorse.** Each guardian, after confirming with the person by whatever
   human means they trust, writes `endorse` in their own log. Before
   endorsing, guardian software MUST show a short fingerprint of `recover`
   fields 1 and 3, which the person reads from their new device. An
   endorsement binds nothing. It tells everyone a recovery is wanted.
3. **Wait.** When a threshold of guardians has endorsed, the recovery is
   **pending**. Each guardian's software alerts the person's devices and
   waits the policy's delay, on its own clock, from when it saw the
   threshold. If it has seen an `object` naming the recovery, it waits twice
   the delay. It doubles once, however many objections there are.
4. **Confirm.** After the wait, and after checking the fingerprint again
   with the person, the guardian writes `confirm` in their own log, carrying
   their [share](#data-recovery). A guardian who has changed their mind
   simply does not confirm.

A change of policy is decided the same way, without step 1: guardian
software that sees a `set_recovery` alerts the person's devices, waits the
delay (doubled after an objection), checks with the person, and confirms.
The first guardians, named under a policy with none, are not asked: the
root names them. Guardian software SHOULD still ask each new guardian to
accept the role.

Any admin or root key of the identity may append an `object`. It cancels
nothing and binds no one. It tells guardians that a device the person holds
disagrees, and doubles their wait.

### What a recovery does

When a recovery is in effect:

- its new root key is the identity's root, with the recovery public key in
  its field 5;
- the device and admin keys in its field 2 keep their powers. A removal of
  one of them in the recovery's causal past no longer counts; removals
  written later apply as usual;
- every other key added in its causal past is removed, and so is the root
  of every earlier recovery;
- **every entry concurrent with it is invalid**, whoever signed it,
  including entries by kept keys. A recovery keeps keys, not work done
  without knowledge of it. Entries in its causal past stand as they were;
  entries that descend from it are judged as usual;
- the new root MUST then append `set_encryption_key` with a fresh key whose
  key chain carries the earlier keys, and SHOULD append a `set_recovery`
  with a new guardian key and shares. That `set_recovery` is a decision like
  any other, and the guardians who just acted confirm it.

A recovery is never undone. Whether it is in effect depends only on
confirmations, and a confirmation is judged as of when it was written. A
guardian device stolen years later can confirm a conflicting decision only
by writing it concurrently with what it already confirmed, which freezes the
identity rather than reviving anything.

### Data recovery

Getting control back is not enough; a person also needs their data. Every
space is encrypted to the identity encryption key, and that key normally
lives only on devices.

The phrase gives the recovery private key. That opens the latest recovery
wrap made to it, which gives the current encryption key, and its key chain
gives every earlier one.

For people who lose the phrase too, each policy that names guardians has its
own **guardian key**: 32 random bytes `g`, and the
[hybrid key pair generated from it](crypto.md#hybrid-public-keys), whose
public half is `set_recovery` field 5. Field 6 carries the current
encryption private key sealed to field 5, as a recovery wrap, so new
guardians can open it at once. Field 4 carries **sealed shares** of `g`.
Shares use Shamir secret sharing over GF(2^8) with the reduction polynomial
x^8 + x^4 + x^3 + x + 1, as in SLIP-0039. Each of the 32 bytes of `g` is the
constant term of its own random polynomial of degree threshold − 1.
Guardian `i`, counting from 1 in the order of field 1, receives the share
`{1: i, 2: the 32 polynomial values at x = i}`. Field 4 lists one share per
guardian, in the same order, each [sealed](crypto.md#sealing) to that
guardian identity's encryption key with context
`"recovery share" || identity id`. A guardian whose own encryption key
changes later still opens its share, through its own key chain.

A guardian's `confirm` of a recovery carries, in field 3, their share sealed
to the link key named in the `recover` entry, with the same context. Shares
are released only by confirming, so no share leaves a guardian before the
wait is over. The new device collects the shares from the guardians' logs,
rebuilds `g` with Lagrange interpolation at zero, and opens the newest
recovery wrap made to that policy's guardian key.

Every `set_encryption_key` carries recovery wraps to the recovery public key
of each root in effect, and to the guardian key of the current policy.
Guardians are replaced together with their key. When a new policy takes
effect, its `g` is new, and the identity rotates its encryption key, so
former guardians cannot read anything written after. A threshold of current
guardians acting together could read the person's data. That is the same
trust that lets them restore the identity, and the person grants it
knowingly. A person who would rather lose their data than extend that trust
leaves fields 4 to 6 empty.

**After the phrase is exposed**, the root replaces itself with a new
phrase's root, whose recovery public key takes effect at once, then appends
`set_encryption_key` with a fresh key whose recovery wraps use it. Whoever
held the old phrase can still read what was encrypted before. That is the
physics rule. They cannot read anything after.

### What recovery cannot do

These are the limits, stated plainly:

- **A colluding majority of current guardians can do anything** to the
  identity. They are the person's court.
- **A guardian's keys are that guardian's vote.** A thief who steals a
  guardian's phrase or device can confirm in that guardian's name, with
  parents from before the guardian noticed. A majority of guardians is still
  needed.
- **Without guardians, two holders of the phrase freeze the identity.**
  Nothing can tell them apart, and no one stands above them.
- **Guardians who decide both ways freeze it.** So do former guardians
  acting together on a policy they replaced.

A frozen identity is not recovered. Its owner starts a new identity, and
each contact recognizes the new one in person
([later.md](../later.md#starting-over)). That is slow on purpose: anything
faster would work for a thief too.

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
need each guardian's log, where confirmations live; the identity's hosts
SHOULD store those logs.

## Display names

Identities have no global names. Each person keeps **petnames**, their own
labels for the identities they know, in their account space
([profiles.md](profiles.md)). An identity may suggest a name for itself in
its profile space; software MUST show the user's own petname when one
exists, and mark any suggested name as unverified.
