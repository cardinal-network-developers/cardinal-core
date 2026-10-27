# Cryptography

Status: draft. Normative. **Requires review by a cryptographer before any
part is frozen.** The handshake in [link.md](link.md) and the sealing
construction below are compositions of standard primitives, not new
primitives, but compositions are where mistakes happen.

## One suite, no negotiation

Each identity declares one suite in its genesis entry. Devices never
negotiate algorithms on the wire: negotiation is attack surface, a
fingerprint, and complexity. An identity moves to a new suite with a
`set_suite` operation in its log ([identity.md](identity.md)), and its
contacts follow when they read the log.

## Suite 1

| Purpose | Primitive | Reference |
|---|---|---|
| Hash, KDF, MAC | BLAKE3 | BLAKE3 specification |
| Signature | Ed25519 (pure) | RFC 8032 |
| Key agreement | X25519 | RFC 7748 |
| Post-quantum KEM | ML-KEM-768 | FIPS 203 |
| AEAD, random nonces | XChaCha20-Poly1305 | draft-irtf-cfrg-xchacha |
| AEAD, counter or unique-key nonces | ChaCha20-Poly1305 | RFC 8439 |
| Password-authenticated key exchange | CPace over Ristretto255 | draft-irtf-cfrg-cpace |
| Mnemonic | BIP-39 English wordlist, 24 words | BIP-39 |

### Why post-quantum now

A personal archive is meant to last decades. Traffic recorded today can be
decrypted by whoever eventually builds a large quantum computer. Every key
agreement in suite 1 therefore combines X25519 with ML-KEM-768, so an
attacker must break both. Signatures stay classical (Ed25519) because a
forged signature after the fact gains nothing against an archive, and
post-quantum signatures are large. A later suite will change signatures; the
identity log already supports that change.

## Derivations

All derived keys use BLAKE3 in key-derivation mode:

```
derive(purpose, material) = BLAKE3.derive_key(context = "cardinal 1 " || purpose,
                                              key_material = material)
```

The output is 32 bytes unless stated. Every `purpose` string used anywhere in
the specification is listed here:

| Purpose | Used for | Defined in |
|---|---|---|
| `seal` | hybrid sealing key | this document |
| `root key` | identity root key seed from the recovery phrase | [identity.md](identity.md) |
| `recovery data` | recovery data key from the recovery phrase | [identity.md](identity.md#data-recovery) |
| `entry key` | space entry encryption key, from an epoch key | [spaces.md](spaces.md) |
| `epoch id` | epoch identifier, from an epoch key | [spaces.md](spaces.md) |
| `convergence` | per-epoch convergence secret for chunks | [blobs.md](blobs.md) |
| `mailbox` | envelope key, from an epoch key | [hosts.md](hosts.md) |
| `discovery` | LAN discovery MAC key | [hosts.md](hosts.md) |
| `invite` | invitation keys | [contact.md](contact.md) |
| `token` | link secret from a delivery token | [link.md](link.md#handshake) |
| `pair`, `pair words` | pairing channel key and confirmation words | [contact.md](contact.md#pairing) |
| `handshake` | link handshake key schedule | [link.md](link.md) |
| `rekey` | link post-quantum rekey | [link.md](link.md) |

A keyed hash is `BLAKE3.keyed_hash(key, input)`.

## Hybrid public keys

A **hybrid public key** is a record `{1: x25519 public (32), 2: ML-KEM-768
encapsulation key (1184)}`. Its **fingerprint** is `BLAKE3` of its encoding.

## Sealing

`seal(recipient, plaintext, context)` encrypts to a hybrid public key:

1. Generate an ephemeral X25519 key pair `(e, E)`.
2. `(ct, ss_kem) = ML-KEM.Encaps(recipient.kem)`.
3. `ss_dh = X25519(e, recipient.x25519)`.
4. `k = derive("seal", ss_kem || ss_dh || E || ct || fingerprint(recipient)
   || BLAKE3(context))`.
5. `c = ChaCha20-Poly1305(k, nonce = 0, aad = context, plaintext)`.
6. Output the record `{1: E, 2: ct, 3: c}`.

The key `k` is unique per sealing because `e` is fresh, so the zero nonce is
safe. Overhead is 32 + 1088 + 16 bytes, plus encoding headers.

`open` reverses these steps. A recipient that does not know which of several
sealed records is for it tries each one; the AEAD tag tells it which.

## Random numbers

All secrets come from the operating system's cryptographic random source.
Devices without one cannot participate.

## What is deliberately absent

- **No cipher lists, no versions on the wire.** The suite is part of the
  identity.
- **No Double Ratchet.** Forward secrecy on the wire comes from the link
  handshake; protection of stored data comes from epoch rotation. See
  [decisions.md](../decisions.md) for the reasoning.
- **No custom variants of primitives.** Ed25519 is pure Ed25519 over the
  message bytes, so any standard library works.
