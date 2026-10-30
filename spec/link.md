# Link

Status: draft. Normative. The handshake requires cryptographic review before
it is frozen.

The link carries everything between two devices: an authenticated, encrypted
**session** that survives network changes, carries reliable streams and
unreliable datagrams, schedules traffic by priority, and never answers a
stranger.

## Why not QUIC or TLS

QUIC does about 200% of what is needed and is missing the essential 10%.
It assumes certificate-authority identities, negotiates versions and
algorithms in the clear, answers anyone who connects, and its specification
runs to hundreds of pages. What is needed instead:

- identities that are keys from an identity log, with no authority;
- silence to anyone who does not already know the device's key;
- sessions that roam between networks without renegotiation;
- post-quantum key agreement;
- three priority classes, so a backup never ruins a call;
- simple enough to implement from this document.

The design is the WireGuard model (fixed handshake, indexes instead of
connection state tied to addresses, MAC-gated silence, cookies under load)
with a small stream layer on top and ML-KEM added to the key schedule.

## Keys

Each device has a **link key** (a hybrid public key: X25519 and ML-KEM-768),
published in its identity log ([identity.md](identity.md#keys-and-powers)).
A device accepts sessions only from:

- devices of its own identity;
- devices of identities it has a relationship with;
- devices of identities it shares a space with, once both have accepted
  it, for that space only ([spaces.md](spaces.md#holding-a-space));
- its hosts;
- initiators holding an invitation it issued ([contact.md](contact.md)).

A host additionally accepts initiators holding a delivery token it serves,
and the narrow public and restore cases in [hosts.md](hosts.md).

## Packets

Every datagram is at most **1232 bytes**, which fits every IPv6 path, so
there is no fragmentation and no path MTU discovery is required. Packets are
sized so that a relayed packet, with its 8-byte relay header, also fits.
Integers are little-endian.

| Type | Packet | Size |
|---|---|---|
| 1 | initiation | 1216 |
| 2 | response | 1180 |
| 3 | cookie reply | 64 |
| 4 | data | 32–1200 |
| 5 | relayed | 8 + an inner packet ([hosts.md](hosts.md#relay)) |

### Initiation (type 1)

| Field | Bytes |
|---|---|
| type = 1, then a 3-byte secret hint | 4 |
| sender index | 4 |
| counter (u64), authenticated, not encrypted | 8 |
| ephemeral X25519 public key | 32 |
| ML-KEM ciphertext to the responder's link key | 1088 |
| encrypted initiator static X25519 key | 48 |
| mac1 | 16 |
| mac2 | 16 |

### Response (type 2)

| Field | Bytes |
|---|---|
| type = 2, then 3 zero bytes | 4 |
| sender index | 4 |
| receiver index | 4 |
| ephemeral X25519 public key | 32 |
| ML-KEM ciphertext to the initiator's link key | 1088 |
| encrypted empty payload | 16 |
| mac1 | 16 |
| mac2 | 16 |

### Data (type 4)

| Field | Bytes |
|---|---|
| type = 4, key phase (0 or 1), then 2 zero bytes | 4 |
| receiver index | 4 |
| counter (u64) | 8 |
| ChaCha20-Poly1305 ciphertext of frames, nonce = 4 zero bytes ∥ counter, associated data = the 16 header bytes before it | rest |

**Indexes** are random 32-bit values chosen by each side for each session.
They are the session's only identifier on the wire, so a passive observer
cannot link sessions, and a session does not depend on addresses.

## Handshake

The handshake follows the Noise IK pattern, with a KEM step added. It is
written out in full here so that it can be implemented without the Noise
framework.

Notation: `H(x) = BLAKE3(x)`. `MixHash(x)`: `h = H(h || x)`.
`MixKey(x)`: let `o` be 64 bytes of `BLAKE3.derive_key("cardinal 1
handshake", ck || x)` output; `ck = o[0..32]`, `k = o[32..64]`.
`Encrypt(p)`: `c = ChaCha20-Poly1305(k, nonce 0, aad = h, p)`, then
`MixHash(c)`. Each `k` encrypts at most once.

Let `R` be the responder's link key and `I` the initiator's.

**Initiator**

1. `ck = h = H("cardinal 1 handshake")`; `MixHash(R.x25519)`;
   `MixHash(counter)`.
2. Generate ephemeral `(e, E)`. `MixHash(E)`.
3. If the responder's ML-KEM key is known: `(ct, ss) = Encaps(R.kem)`,
   `MixHash(ct)`, `MixKey(ss)`. It is unknown only when connecting with an
   invitation, which carries just an X25519 key; then the ciphertext field
   is 1088 zero bytes and nothing is mixed. A responder that receives a
   zero ciphertext MUST require a secret at step 5, except in the public and
   restore cases ([hosts.md](hosts.md#public-service)), which carry no
   secret and rely on the rekey that follows.
4. `MixKey(X25519(e, R.x25519))`. The **secret hint** in the header is then
   `first3(H(p)) XOR first3(BLAKE3.keyed_hash(ck, "hint"))` if a secret `p`
   is used at step 5, and 3 random bytes otherwise. The mask is fresh for
   every initiation, so the hint links nothing; a responder that has
   computed `ck` this far unmasks it and finds the matching secret by
   lookup.
5. If this handshake uses a secret `p`, `MixKey(p)`. The secret is an
   invitation secret ([contact.md](contact.md)), or, toward a host,
   `derive("token", delivery token)`.
6. `Encrypt(I.x25519)`. This is the encrypted static. Its tag proves the
   counter, the KEM step, and the secret.
7. `MixKey(X25519(I.private, R.x25519))`.

**Responder** repeats these steps to decrypt. It first tries without a
secret; if the static decrypts to a key it accepts, it continues. Otherwise it
tries the invitation secrets and tokens whose hint matches, and drops the
packet silently if none works. It drops the initiation unless the counter is
greater than the **confirmed counter** for that static key, then replies:

1. Generate ephemeral `(f, F)`. `MixHash(F)`.
2. `MixKey(X25519(f, E))`.
3. `MixKey(X25519(f, I.x25519))`.
4. If the initiator's ML-KEM key is known (always, except during an
   invitation): `(ct2, ss2) = Encaps(I.kem)`; `MixHash(ct2)`; `MixKey(ss2)`.
   Otherwise the ciphertext field is 1088 zero bytes and is not mixed.
5. `Encrypt(empty)`.

The counter is authenticated only by keys an attacker who knows both
public keys could also compute, since the static-static step comes after the
last encryption in the initiation. So a responder does not trust it yet. It
keeps any existing session with that static key, and records the
initiation's counter as confirmed only when the first data packet of the new
session authenticates, which proves the initiator holds its private key. A
forged initiation with a huge counter therefore costs the responder one
reply and changes nothing. Initiators use `max(last counter + 1,
milliseconds since 1970)` and SHOULD persist it.

**Transport keys.** Both sides take 64 bytes of
`BLAKE3.derive_key("cardinal 1 handshake", ck || "split")`. The first 32
bytes key initiator-to-responder traffic and the last 32 bytes key the
reverse.

### Post-quantum forward secrecy

The handshake's ML-KEM steps protect against a future quantum computer
unless a device's link private key is later stolen. To close that gap, the
initiator MUST send a `rekey` frame carrying a fresh ephemeral ML-KEM public
key immediately after its `device proof`, and the responder answers with
`rekey reply`. Both then derive new transport keys from
`BLAKE3.derive_key("cardinal 1 rekey", ck || ss)` (64 bytes, split as above),
switch the key phase bit, and set `ck` to the first 32 bytes of
`BLAKE3.derive_key("cardinal 1 rekey", ck || ss || "ck")`.

The session's initiator starts the same exchange every two minutes of
activity, or every 2^40 packets, whichever comes first. Only the initiator
sends `rekey`, so the two sides never start one at once. Packet counters
continue across key phases; they never
reset within a session. Receivers accept the previous key phase for five
seconds after a switch.

Receivers MUST reject replayed data packets, with a sliding window of at
least 2048 counters, as in WireGuard. The window is updated only after a
packet authenticates.

### Silence and cookies

`mac1` is `first16(BLAKE3.keyed_hash(m1, packet bytes before mac1))`, with
`m1 = H("cardinal 1 mac1" || R.x25519)`. Only a party that knows the
responder's static key can compute it. **A device
MUST NOT send anything in response to a packet with an invalid mac1, or to a
handshake from an unknown static key with no matching invitation.** To an
outsider, the address looks unused. Hosts also accept token holders, plus
two narrow cases (public service and restore) defined in
[hosts.md](hosts.md). All of these still require mac1.

Under load, a responder MAY reply to a valid-mac1 initiation with a cookie
reply instead of a response, exactly as WireGuard does. The cookie is
`first16(keyed_hash(rotating secret, source address))`. It is sent encrypted
with XChaCha20-Poly1305 under `H("cardinal 1 cookie" || R.x25519)`, with the
initiation's mac1 as associated data. The initiator
then retransmits with
`mac2 = first16(keyed_hash(cookie, packet bytes before mac2))`. Otherwise
mac2 is zero.

### Identity binding

A static key could appear in more than one identity log. Sessions are
therefore bound to a device's signing key, which carries a proof of
possession in its log ([identity.md](identity.md#operations)).

Before anything else, each side sends a `device proof` frame:
`{1: identity id, 2: device signing key, 3: Ed25519 signature over
"cardinal device proof" || h}`, where `h` is the handshake hash after the
response. The receiver MUST check the signature, that the key is effective in
that identity's log, and that the log lists this session's static key as its
link key. Until both proofs are verified, only `device proof`, `rekey`,
`rekey reply`, `ack`, and `padding` frames may be sent. Proofs are omitted only in invitation sessions
whose invitee has no identity yet, and in the restore case.

Both sides re-check the peer's log whenever it changes, and close the
session if the peer's key is no longer effective.

Simultaneous handshakes between the same two devices both complete. The
session initiated by the device with the smaller static key survives; the
other is closed.

## Frames

The plaintext of a data packet is a sequence of encoded records, each a
frame whose key 0 is its type:

| Type | Frame | Fields |
|---|---|---|
| 1 | padding | 1: bytes |
| 2 | ping | (none) |
| 3 | ack | 1: largest counter; 2: delay in µs; 3: list of (gap, length) ranges |
| 4 | stream | 1: stream id; 2: offset; 3: data; 4: fin; 5: service (offset 0 only); 6: priority (offset 0 only) |
| 5 | reset | 1: stream id; 2: reason |
| 6 | window | 1: stream id, or 0 for the session; 2: maximum offset |
| 7 | datagram | 1: channel (bytes 16); 2: data |
| 8 | path challenge | 1: bytes 8 |
| 9 | path response | 1: bytes 8 |
| 10 | observed address | 1: IP address (4 or 16 bytes); 2: port |
| 11 | rekey | 1: ML-KEM public key |
| 12 | rekey reply | 1: ML-KEM ciphertext |
| 13 | close | 1: reason (text) |
| 14 | device proof | see [Identity binding](#identity-binding) |

Ack ranges are records `{1: gap, 2: length}`, counting down from the
largest counter, as in QUIC.

Frames other than ack, padding, and close are acknowledged. Lost frames are
resent in new packets; packets are never retransmitted as-is.

### Streams

A stream is a reliable, ordered byte sequence. The initiator of the session
uses odd stream ids and the responder even ones. The first frame of a stream
names its **service**:

| Service | Purpose | Defined in |
|---|---|---|
| 1 | sync | [sync.md](sync.md) |
| 2 | blob | [sync.md](sync.md#blob-transfer) |
| 3 | mailbox | [hosts.md](hosts.md#mailbox) |
| 4 | rendezvous | [hosts.md](hosts.md#rendezvous) |
| 5 | relay | [hosts.md](hosts.md#relay) |
| 6 | storage | [hosts.md](hosts.md#storage) |
| 7 | ephemeral | [spaces.md](spaces.md#ephemeral-messages) |
| 8 | contact | [contact.md](contact.md) |
| bytes(32) | an application's own protocol | the application |

Messages on a stream are encoded values, each preceded by its length as a
varint. Flow control works per stream and per session, through window
frames. The initial window is 256 KiB per stream and 1 MiB per session.

### Datagrams

Datagram frames are unreliable and unordered. They carry real-time media and
game state. A **channel** is a 16-byte label that an application derives,
for example `first16(H(space id || call id))`, so a call belongs to a space
and only that space's members' devices may join it.

## Priority

Every stream and channel has a priority class:

| Class | Value | Used for | Behavior |
|---|---|---|---|
| real-time | 0 | calls, games | sent first; never queued behind other classes |
| interactive | 1 | a person waiting: opening a file, sending a message; [notices](sync.md#notices) | next |
| background | 2 | sync, backup, prefetch | uses only spare capacity |

Congestion control is REQUIRED. Implementations MUST pace packets and MUST
respond to both loss and rising delay. They SHOULD use a delay-based
controller for the session as a whole, and a LEDBAT-style limit (target
queuing delay of 25 ms) for background traffic, so a large sync yields
within one round trip to a call on the same network. The exact algorithm is
local; the behavior is the requirement.

## Paths and roaming

A session is bound to keys and indexes, not to an address. When an
authenticated packet arrives from a new address, the receiver sends a path
challenge there, and moves the session once the response arrives. A laptop
moving from home Wi-Fi to a phone hotspot keeps every session.

A session may have several validated paths at once: LAN, internet, and relay
through a host. Traffic goes on the path with the lowest smoothed round-trip
time, and real-time traffic MAY be duplicated across two paths.

The `observed address` frame tells a peer the address its packets came from.
It is the only function of a STUN server, and every peer performs it.

## Keepalive and idle

A session is closed after three minutes without traffic, except sessions a
device keeps open for reachability ([hosts.md](hosts.md#staying-reachable)),
which send a ping often enough to hold the NAT mapping open: every 25 seconds
by default, longer once a longer timeout has been observed.

## Carriers

Packets travel over any carrier that delivers datagrams of 1232 bytes:

- **UDP**: the default. Personal devices listen only on UDP.
- **TCP**: each packet is prefixed by its length as a 16-bit integer. Hosts
  MAY listen on TCP, including port 443, for devices on networks that block
  UDP. A TCP listener is visible to scanners, so only hosts use one; their
  existence is already disclosed by their role.
- **Relay**: packets wrapped and forwarded by a host
  ([hosts.md](hosts.md#relay)).
- **Local radio** (Bluetooth, Wi-Fi Direct), with fragmentation inside the
  carrier when its frames are smaller.

Above this layer, nothing can tell which carrier was used.
