# Encoding

Status: draft. Normative.

Every structure in the protocol, whether a packet frame, a log entry, a file
tree node, or an invitation, uses this one encoding. There is no second
format.

## Why a new encoding

The protocol needs three properties together: **one encoding per value**, so
hashes and signatures are reproducible; **forward compatibility**, so an old
device keeps fields it does not understand while partitioned from newer
ones; and **a definition short enough to implement from memory**. JSON fails
the first, Protobuf the first, and CBOR meets them only through a profile
larger than this whole document. A smaller format whose only possible
encodings are canonical is simpler than any profile of a larger one.

Human auditability is provided by a canonical **text rendering**, which is
defined below. It is a property of tools, not of the wire.

## Varint

An unsigned integer is written as unsigned LEB128: 7 bits per byte, least
significant group first, high bit set on every byte except the last.

- The encoding MUST be minimal: the final byte MUST NOT be `0x00` unless the
  whole varint is the single byte `0x00`.
- A varint MUST NOT exceed 9 bytes, so values are below 2^63.

## Values

Every value starts with a varint header `h`. Let `t = h & 7` (type) and
`n = h >> 3`.

| `t` | Type | `n` means | Followed by |
|---|---|---|---|
| 0 | unsigned integer | the value | nothing |
| 1 | negative integer | the value is `-1 - n` | nothing |
| 2 | bytes | length | `n` raw bytes |
| 3 | text | length in bytes | `n` bytes of valid UTF-8 |
| 4 | list | number of items | `n` values |
| 5 | record | number of fields | `n` fields |
| 6, 7 | reserved | | decoders MUST reject |

Integers therefore range from `-2^60` to `2^60 - 1`.

A **record field** is a varint key followed by a value. Keys MUST be strictly
increasing within a record. A field that is absent is omitted; there is no
null.

Booleans are unsigned integers `0` and `1`. Text is not normalized; it is
compared byte for byte.

### Canonical form

Because varints are minimal, lengths are exact, and record keys are sorted
and unique, every value has exactly one encoding. Decoders MUST reject any
input that violates these rules, including trailing bytes after the
top-level value when the context says the input is one value.

### Limits

Nesting depth MUST NOT exceed 32. Each context that carries values states
its maximum size.

## Kinds

The first field of every stored or transferable object is key `0`, the
**kind**. Messages on a link service also use key `0`, for the message's op
within that service; the service, named when the stream opens, says which
table applies. Core
kinds are small unsigned integers listed in the registry below. Application
kinds are 32-byte bytes values: the BLAKE3 hash of a schema document written
by the application author. No registry is needed for application kinds.

## Unknown fields

A decoder MUST accept records with keys it does not know and MUST preserve
them when it stores the record. Objects are always stored and forwarded as
their original bytes, never re-encoded from a parsed form. A device that
predates a field still syncs it intact.

## Signed objects

A **signed object** is a record:

| Key | Field | Type |
|---|---|---|
| 0 | kind = 1 | uint |
| 1 | body | bytes: the canonical encoding of the inner record |
| 2 | signatures | list of signature records |

Signature record:

| Key | Field | Type |
|---|---|---|
| 1 | key | bytes(32): Ed25519 public key |
| 2 | signature | bytes(64) |

- The object **id** is `BLAKE3(body)`.
- Each signature is Ed25519 over the 46-byte message
  `"cardinal sig 1" || id`.
- Signatures are not part of the id, so adding a co-signature does not
  change what was signed.
- Signatures MUST be sorted by key and keys MUST be unique.

## Text rendering

The canonical text form is used for audit tools, examples, and test vectors.

```
value   = uint | neg | bytes | text | list | record
uint    = digits                         ; 42
neg     = "-" digits                     ; -5
bytes   = "h'" hexdigits "'"             ; h'00ff', lowercase
text    = JSON string                    ; "hi\n"
list    = "[" [value *(", " value)] "]"
record  = "{" [field *(", " field)] "}"
field   = digits ": " value              ; {0: 3, 1: "x"}
```

A tool that knows the schema MAY show field names instead of keys
(`{kind: 3, name: "x"}`). That is a display form and is never hashed.

## Registry of core kinds

| Kind | Name | Defined in |
|---|---|---|
| 1 | signed object | this document |
| 2 | identity entry | [identity.md](identity.md) |
| 3 | sealed entry | [spaces.md](spaces.md) |
| 4 | space entry | [spaces.md](spaces.md) |
| 5 | blob index | [blobs.md](blobs.md) |
| 6 | invitation | [contact.md](contact.md) |
| 7 | envelope payload | [hosts.md](hosts.md#envelopes) |
| 8 | join request | [contact.md](contact.md#when-the-inviter-is-offline) |
| 9 | host grant | [hosts.md](hosts.md#grants) |
| 10 | public address | [contact.md](contact.md#following) |
| 11 | envelope | [hosts.md](hosts.md#envelopes) |
| 12 | bundle | [sync.md](sync.md#sneakernet-and-delay-tolerant-carriage) |
| 13 | checkpoint state | [state.md](state.md#pruning) |
| 14–63 | reserved for this specification | |

Operation records inside entries carry their own small `op` numbers, defined
in the document that defines the entry.

## Example

The record `{0: 6, 1: h'0a0b', 3: "Ana"}`:

Record header: `h = (3 << 3) | 5 = 29 = 0x1d`. Then field `0`: key `00`, value uint
6 = header `(6<<3)|0 = 48 = 0x30`. Field `1`: key `01`, bytes length 2 =
header `(2<<3)|2 = 18 = 0x12`, then `0a 0b`. Field `3`: key `03`, text
length 3 = `(3<<3)|3 = 27 = 0x1b`, then `41 6e 61`.

```
1d 00 30 01 12 0a 0b 03 1b 41 6e 61
```
