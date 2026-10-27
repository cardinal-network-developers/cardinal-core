# Hosts

Status: draft. Normative.

Most devices cannot accept incoming connections, and most are asleep most of
the time. A **host** is any device that can listen, and that agreed to help
an identity: by holding small envelopes for it, introducing peers to it,
relaying its traffic, or storing its encrypted data.

A host may be your own desktop, a single-board computer at home, a rented
server, or a friend's machine. Anyone can be a host for anyone who asks.
A host holds only ciphertext, is trusted only to stay available, and can be
replaced without changing anything else. That is the difference between a
host and a provider.

## Grants

A host serves an identity under a **grant**, a signed object whose body is:

| Key | Field | Type |
|---|---|---|
| 0 | kind = 9 | uint |
| 1 | host identity | bytes(32) |
| 2 | served identity | bytes(32) |
| 3 | services | list of uint: 3 mailbox, 4 rendezvous, 5 relay, 6 storage |
| 4 | classes | list of quota classes (below) |
| 5 | storage bytes | uint |
| 6 | retention | uint: days an unfetched envelope or unrenewed storage is kept |
| 7 | endpoints | list of endpoints |
| 8 | host link key | hybrid public key of the serving device |

A **quota class** is `{1: class number, 2: envelopes outstanding per token,
3: deposits per day per token, 4: relay bytes per day per token}`. Class 0
applies to tokens registered without a class.

An **endpoint** is `{1: carrier (1 UDP, 2 TCP), 2: address, 3: port}`, where
the address is 4 or 16 bytes, or a host name as text. Host names are a
convenience for hosts on changing addresses; a host name that stops resolving
costs reachability, never identity.

The grant is signed by a device key of the host identity. The served identity
records it in its account space ([profiles.md](profiles.md#account)). A host
may end a grant at any time: no one can be forced to keep serving. Software
SHOULD keep at least two hosts for anything important.

A person's own always-on device can grant itself to its own identity. That is
the common case, and needs no other party.

## Telling others where to reach you

Each member of a space SHOULD publish a **reach node** in that space
([profiles.md](profiles.md#reach)). It lists the member's hosts (endpoints
and host link key) and a **delivery token** for each host, issued for that
space. The reach node is part of the space, so it is encrypted to the other
members, merges like any other state, and is withdrawn by the same means.

When a person changes hosts, their devices SHOULD also deposit the new reach
node in each contact's mailbox, so contacts offline at the time of the change
can still find them.

## Delivery tokens

A delivery token is 16 random bytes, created by the owner, registered with a
host, and given to the members of exactly one space through that space's
reach node. A token is the only thing that lets anyone but the owner use a
host's services for that owner.

Token registration merges, so devices with stale views cannot undo each
other's revocations. A host keeps, for each served identity, a set of active
tokens with their classes, and a set of revoked tokens. A revoked token can
never become active again.

Tokens rotate whenever the space's epoch rotates: the old token was known to
members who may have been removed.

## Service messages

Every service message is a record whose key 0 is its **op** within that
service. Each request is answered on the same stream by exactly one reply,
in order. An error reply is `{0: 0, 1: code}`, with codes 1 not permitted,
2 full, 3 unknown, and 4 malformed.

## Mailbox

A mailbox holds **envelopes**: sealed messages of at most 1024 bytes, waiting
for the owner to collect them. Envelopes carry notice of change: a small
space entry, a heads message, an updated reach node, or a join request. Bulk
data never enters a mailbox.

### Envelopes

An envelope is `{1: epoch id (16), 2: nonce (24), 3: ciphertext}`, at most
1024 bytes encoded. The ciphertext is XChaCha20-Poly1305 under
`derive("mailbox", epoch key)`, where the epoch is the one named in field 1,
of the space the token belongs to. The owner knows the space from the token,
and the epoch from field 1. Join requests omit field 1
([contact.md](contact.md#when-the-inviter-is-offline)).

The plaintext is an **envelope payload**:

| Key | Field |
|---|---|
| 0 | kind = 7 |
| 1 | space id |
| 2 | a sealed entry, or a heads message ([sync.md](sync.md#when-to-sync)) |

### Operations

| Op | Request | Reply | Who |
|---|---|---|---|
| 1 | deposit: `{0: 1, 1: token, 2: envelope}` | `{0: 1}` | token holder |
| 2 | fetch: `{0: 2, 1: after sequence}` | `{0: 2, 1: list of {1: sequence, 2: token, 3: envelope}, 2: more (bool)}` | owner device |
| 3 | ack: `{0: 3, 1: sequence}` | `{0: 3}` | owner device |
| 4 | register: `{0: 4, 1: list of {1: token, 2: class}}` | `{0: 4}` | owner device |
| 5 | revoke: `{0: 5, 1: list of tokens}` | `{0: 5}` | owner device |
| 6 | usage: `{0: 6}` | `{0: 6, 1: list of {1: token, 2: envelopes held, 3: deposits today}}` | owner device |

A deposit that exceeds the token's class is refused with error 2. A full
mailbox refuses; it never absorbs. The depositor tries another host, or tries
later.

Sequences are per served identity and increase by one per envelope. The host
deletes an envelope once every owner device that has fetched within the
retention period has acknowledged it, or when the retention period ends.

### What a mailbox learns

How many envelopes arrive under each token, their sizes, when, and when the
epoch changes. Not who sent them, which space they concern, or what they
contain. Tokens rotate with epochs, so this record does not accumulate.

### The worst case

A person's worst-case unsolicited inbound traffic is: tokens issued × class
quota × 1 KiB. It is bounded, attributable to a specific token, and revocable
token by token. There is no stranger in that formula.

## Rendezvous

Two devices behind NAT can usually connect directly, if each is told the
other's address at the same moment. A host does that.

| Op | Request | Reply | Who |
|---|---|---|---|
| 1 | present: `{0: 1, 1: local addresses}` | `{0: 1}` | owner device, while awake |
| 2 | connect: `{0: 2, 1: token}` or `{0: 2, 2: device signing key}` | `{0: 2, 1: list of {1: static X25519 key, 2: observed address}}` | token holder, or owner device |
| 3 | incoming: `{0: 3, 1: static X25519 key, 2: observed address, 3: token or absent}` | (none) | sent by the host to owner devices |

- On `connect`, the host sends `incoming` to each present owner device, with
  the requester's static key and the address **the host observed**. Owner
  devices accept an incoming connect if the token is active, or the requester
  is the owner's own device. They may also apply their own rate limits.
- The host replies with the static key and observed address of each owner
  device that is present. Local addresses reported in `present` are passed
  only between devices of the same identity.
- Both sides then send initiations to the addresses they were given. The
  first session to complete wins. If none completes within three seconds,
  the requester relays.

Because the host forwards only addresses it observed, a requester cannot aim
an owner's device at a third party.

## Relay

| Op | Request | Reply | Who |
|---|---|---|---|
| 1 | relay: `{0: 1, 1: token}` or `{0: 1, 2: device signing key}` | `{0: 1, 1: channel (u32)}` | token holder, or owner device |
| 2 | relayed: `{0: 2, 1: channel, 2: static X25519 key of the peer}` | (none) | sent by the host to the owner device |

Once a channel is assigned, each side sends **relayed packets** (link type 5)
to the host's address: `5, 0, 0, 0, channel (u32), inner packet`. The host
checks that the channel belongs to that source address, and forwards the
inner packet, unchanged and under the same header, to the other side. The
two devices run an ordinary end-to-end session through it, which the host
cannot read. A relay is just another path for the session
([link.md](link.md#paths-and-roaming)), abandoned as soon as a direct path
validates. Relay bytes count against the token's class.

## Storage

A host granted storage keeps sets of objects for the owner: sealed entries of
the owner's spaces, chunks, and identity logs, each set under a random label
the owner chose. The host verifies each object against its id and nothing
else, because it can read nothing else.

| Op | Request | Reply | Who |
|---|---|---|---|
| 1 | reconcile: a [sync](sync.md) message | a sync message | owner device; token holder for allowed labels; anyone for public labels |
| 2 | fetch: as in [sync.md](sync.md#fetching-objects) | objects | same |
| 3 | put: `{0: 3, 1: label, 2: list of objects}` | `{0: 3}` | owner device |
| 4 | drop: `{0: 4, 1: label, 2: list of ids}` | `{0: 4}` | owner device |
| 5 | list: `{0: 5}` | `{0: 5, 1: list of {1: label, 2: count, 3: bytes}}` | owner device |
| 6 | allow: `{0: 6, 1: token, 2: label}` | `{0: 6}` | owner device |
| 7 | public: `{0: 7, 1: label, 2: bool}` | `{0: 7}` | owner device |
| 8 | prove: `{0: 8, 1: list of identity log entries}` | `{0: 8}` | restore (below) |

`allow` lets members of the token's space fetch from the host while the
owner's devices are asleep. This is how a photo shared with a friend can be
fetched when the sharer's laptop is closed.

### Public service

A label marked public may be reconciled and fetched by anyone who can reach
the host. A host with any public label accepts handshakes from unknown static
keys, without a secret, but only for storage ops 1 and 2 on public labels.
Such a host still requires mac1, so only those given its static key (for
example in a [public address](contact.md#following)) can reach it.

### Restore

A person who lost every device enters the recovery phrase on a new device,
and the address and static key of one host, both printed on their recovery
sheet. Software updates the sheet's host whenever hosts change.

1. The new device recreates the root key, and creates a root-signed identity
   entry that adds itself as an admin.
2. It connects to the host without a secret and without an ML-KEM
   ciphertext, since it does not yet know the host's ML-KEM key. A host
   accepts this handshake only for op 8. The first request MUST be `prove`,
   carrying identity log entries that make the initiator an effective device
   of an identity the host serves. Otherwise the host closes the session.
3. After `prove`, the session is an owner session, and the device runs the
   mandatory post-quantum rekey before anything else.
4. The device fetches its identity log (by the identity log label), recovers
   the encryption key from the latest recovery wrap
   ([identity.md](identity.md#data-recovery)), lists the labels, and opens
   each set until it finds the account space. The account space records
   everything else: other hosts, labels, spaces, and contacts.

## Staying reachable

- A device that can receive connections needs no host for itself.
- A device that cannot keeps a session with at least one host while it is
  awake, presents itself for rendezvous, and polls its mailbox when it wakes.
- Phones MAY use the platform's push service to be woken. The push service
  learns only that a device should wake. This is an application choice, not
  a protocol dependency.

## Local discovery

On a local network, a person's devices find each other without any host.

Each device advertises with DNS-SD over multicast DNS (RFC 6762, RFC 6763),
service type `_cardinal._udp`, with a TXT record `t=` followed by hex of
`nonce (8) || first8(BLAKE3.keyed_hash(d, nonce))`. Here
`d = derive("discovery", discovery secret)`, and the discovery secret is a
random 32-byte value kept in the owner's account space. The nonce changes
every time the advertisement is refreshed.

A device of the same identity recognizes the tag and connects. Anyone else
learns only that some device of this kind is present. The advertisement
names no identity, and successive advertisements cannot be linked.

Contacts on the same network do not need discovery: rendezvous passes local
addresses between a person's own devices, and contacts connect through their
observed addresses, which on a shared network are local.
