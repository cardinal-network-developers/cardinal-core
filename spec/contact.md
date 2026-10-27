# Contact

Status: draft. Normative.

Nothing reaches a person except from identities they have connected with. This
document defines the only ways a connection starts:

1. **Invitation**: a code or link sent by any channel.
2. **Pairing**: a short code exchanged in person on the same local network.
   The same mechanism adds a new device to your own identity.
3. **Introduction**: a mutual contact vouches, and both sides accept.

Each ends the same way: a session between two devices, an exchange of
identity logs, and a **relationship space** with both identities as owners
([profiles.md](profiles.md#relationship)).

Consent is two-sided. The inviter consents by issuing the invitation; the
invitee consents by using it. Nothing else creates a relationship.

Messages on the `contact` service are records whose key 0 is an op:

| Op | Message |
|---|---|
| 1 | hello: `{0: 1, 1: identity id, 2: suggested name}` |
| 2 | genesis: `{0: 2, 1: sealed genesis entry of the relationship space}` |
| 3 | done: `{0: 3}` |

Identity logs are exchanged on the `sync` service, as usual.

## Invitations

An invitation is the record:

| Key | Field | Type |
|---|---|---|
| 0 | kind = 6 | uint |
| 1 | inviter identity | bytes(32) |
| 2 | responder static key | bytes(32): X25519 key of the endpoint in field 3 |
| 3 | endpoint | an [endpoint](hosts.md#grants): an inviter device, or a host |
| 4 | secret | bytes(16) |
| 5 | token | bytes(16): registered at the host, if field 3 is a host |
| 6 | uses | uint: default 1 |
| 7 | suggested name | text: the name the inviter suggests for themselves |
| 8 | for | bytes(32): if present, only this identity may use the invitation |

Its text form is `cardinal:` followed by the unpadded lowercase base32
encoding of the record, about 200 characters. A QR code holds the same
string. Operating systems route the `cardinal:` scheme to the installed
software. No web domain is involved, because a domain would be a special
node.

The invitation is small because it carries no ML-KEM key. The handshake
mixes in the invitation secret instead ([link.md](link.md#handshake), step
5), and the session's mandatory post-quantum rekey follows immediately. An
invitation sent over a channel the attacker records is therefore exactly as
secure as that channel. Send invitations the way you would send a house key.

The inviter's software keeps each invitation until its uses run out, or until
the inviter cancels it. Expiry is local policy: no clock is trusted but the
inviter's own.

### Accepting

1. The invitee's device reaches the inviter:
   - if the endpoint is an inviter device, it connects directly;
   - if the endpoint is a host, it opens a session with the host using the
     token ([link.md](link.md#handshake), step 5), and uses `rendezvous`
     `connect` with the token. The host returns the static key and observed
     address of each online inviter device. If no direct session completes,
     the invitee relays.
2. It runs the handshake with an inviter device, using the invitation secret.
   The inviter device accepts the unknown static key because the secret
   matches an outstanding invitation.
3. The invitee sends `device proof` ([link.md](link.md#identity-binding)) if
   it has an identity, and `hello`. If the invitation has a `for` field, the
   inviter checks that the proven identity matches it. Both sides reconcile
   each other's identity logs.
4. The inviter's device creates the relationship space, with a genesis entry
   adding both identities as owners, wrapped for both encryption keys, and
   sends it as `genesis`.
5. Each device asks its person for a petname, offering the other's suggested
   name, and records the contact in the account space. Then `done`.

### When the inviter is offline

The invitee deposits a **join request** at the invitation's host, using the
invitation's token. It is an envelope without an epoch field, encrypted under
`derive("invite", secret)`, whose payload is:

| Key | Field |
|---|---|
| 0 | kind = 8 |
| 1 | invitee identity id |
| 2 | invitee host: endpoint, host static key, and a token for that host |

The inviter's device collects it later and reaches the invitee through the
invitee's host, with that token, exactly as in step 1. It then runs the
handshake as initiator, with the same invitation secret, and the invitee's
device accepts it because the secret matches the invitation it used. Steps 3
to 5 proceed.

## Pairing

Pairing is for two devices in the same place: two people meeting, or one
person adding a device.

1. One device shows a code like `4-amber-harbor-quiet`: a channel number from
   0 to 999 and three words from the BIP-39 English list.
2. That device advertises `_cardinal-pair._udp` by multicast DNS, with TXT
   `c=<channel>`, and listens on the advertised UDP port. The device where the
   code is typed finds it.
3. The two devices run CPace (Ristretto255, SHA-512), with password = the
   three words joined by single spaces, and session identifier =
   `BLAKE3("cardinal 1 pair" || channel as varint || the shower's address ||
   the typer's address)`. Each CPace message is one UDP datagram:
   `{0: 1, 1: CPace share}`. The result is a shared key `K`.
4. Key confirmation: each side sends `{0: 2, 1: tag}`, with
   `tag = BLAKE3.keyed_hash(K, "cardinal 1 pair confirm" || own share)`.
   A wrong tag ends the attempt. After three failed attempts on a code, the
   showing device invents a new code. An attacker therefore gets three
   guesses against 33 bits.
5. Each side sends `{0: 3, 1: nonce (24), 2: ciphertext}`, encrypted with
   XChaCha20-Poly1305 under `derive("pair", K)`. The plaintext is
   `{1: identity id (if any), 2: device signing key, 3: full link key,
   4: endpoint, 5: suggested name, 6: proof}`. The proof is the
   [proof of possession](identity.md#operations) for adding this device to
   the other side's identity, made only by a device that has no identity yet.
6. The devices open a link session, using `derive("invite", K)` as the secret.
7. Both screens show the other side's suggested name, and four words from the
   BIP-39 list, chosen by the first 44 bits of `derive("pair words", K)`. The
   people confirm that the words match.

Then:

- **Adding your own device.** The new device has no identity. An admin
  device of the person appends to the identity log an `add_key` for the new
  device, with the proof it received, at **device** power unless the person
  says this device will stay at home and manage others, and a `wrap` of the
  identity encryption key. It sends the log. The new device can now open the
  account space and every other space, and begins to sync. No space needs to
  change, because spaces belong to identities.
- **Meeting a person.** Steps 3 to 5 of [Accepting](#accepting).

## Introductions

Ana and Ben both know Carol. Carol introduces them:

1. In her relationship space with Ben, Carol creates an **introduction** node
   ([profiles.md](profiles.md#relationship)) with fields `1: Carol's
   identity, 2: Ana's identity, 3: Ana's suggested name, 4: a note`.
2. Ben's software shows: "Carol would like you to meet Ana." If Ben accepts,
   his device issues a single-use invitation whose `for` field is Ana's
   identity, and sets it as the node's field 5.
3. Carol's device creates the same introduction, with Ben's invitation and
   the roles swapped, in her relationship space with Ana.
4. Ana's software shows: "Carol introduced you to Ben." If Ana accepts, her
   device uses the invitation.

Because the invitation is bound to Ana's identity, neither Carol nor anyone
else who sees it can use it. Both people consented, and both know who
vouched. If an introducer repeatedly introduces people who turn out to be
unwelcome, that is visible, and people can stop accepting that introducer's
introductions. Reputation lives where it belongs: with people who know each
other.

## Front door

Some people want strangers to be able to reach them: a shop, a doctor, a
public figure. A **front door** is a multi-use invitation, without a `for`
field, published in the person's public space
([profiles.md](profiles.md#public)). Its token has a small quota class, for
example ten deposits per day. When the door is full, it is full. If it
attracts abuse, the owner replaces it. The bound is the owner's choice.

## Following

Reading someone's public space needs no relationship: the reader pulls, and
nothing is pushed to anyone. A public space is found by its **public
address**: `{0: 10, 1: space id, 2: list of {1: endpoint, 2: host static
key, 3: label}}`, naming hosts that serve it publicly
([hosts.md](hosts.md#public-service)). Its text form is `cardinal:` and the
base32 encoding, like an invitation. Public spaces link to each other by
public address.

Following does not let the followed person, or anyone else, send anything to
the follower.
