# Blobs

Status: draft. Normative.

A **blob** is a sequence of bytes, usually a file's content. A blob is
stored as encrypted chunks, each identified by the hash of its ciphertext.
A **reference** to a blob names it and holds the key to read it, so a
reference is both an address and a permission.

## Goals

- **Transfer only what changed.** Editing the middle of a large file moves a
  few chunks, not the whole file, the way rsync does, without rsync's two
  round trips.
- **Deduplicate within a space.** The same content stored twice in a space
  is stored once.
- **Let blind hosts verify.** A host can check any chunk against its id
  without holding any key.
- **Read from anywhere in a file.** Seeking a video or opening one page of a
  document fetches only the chunks needed.

## Chunking

Chunk boundaries depend on content, so an insertion moves only nearby
boundaries.

Gear table: for `i` in `0..255`, `gear[i]` is the first 8 bytes,
little-endian, of `BLAKE3("cardinal 1 gear" || byte(i))`.

Parameters: `min = 16 KiB`, `avg = 64 KiB`, `max = 256 KiB`.
`mask_hard` has the top 18 bits of a 64-bit word set; `mask_easy` has the
top 14 bits set.

To find the end of the chunk starting at position `s`:

```
h = 0
for p from s while p < len:
    h = (h << 1) + gear[byte[p]]          # mod 2^64
    n = p - s + 1
    if n < min: continue
    if n == max: return p + 1
    mask = (n < avg) ? mask_hard : mask_easy
    if h & mask == 0: return p + 1
return len
```

This is FastCDC's normalized chunking, fixed to one set of parameters so all
implementations produce the same chunks.

Content smaller than 1 KiB SHOULD be stored inline in the space entry instead
of as a blob.

## Encryption

Each space epoch has a **convergence secret**,
`derive("convergence", epoch key)`.

For a chunk with plaintext `m`:

```
k  = BLAKE3.keyed_hash(convergence secret, m)        # 32 bytes
c  = ChaCha20-Poly1305(k, nonce = 0, aad = "", m)
id = BLAKE3(c)
```

The key depends on the content, so identical chunks in the same epoch encrypt
identically and deduplicate. The zero nonce is safe because a key is reused
only for identical plaintext, which yields identical ciphertext. Only members
holding the epoch can compute these keys, so outsiders cannot test whether a
space contains a known file.

After an epoch rotates, a writer re-encoding an edited file SHOULD reuse the
existing reference of any chunk whose plaintext is unchanged, rather than
re-encrypting it under the new epoch. Old references remain readable by every
current member, so only changed chunks are new.

Public spaces use a convergence secret of 32 zero bytes. Anyone holding a
file can then confirm that a public space contains it, which is harmless for
public data.

## Index

A blob with more than one chunk has an **index**, the record:

| Key | Field | Type |
|---|---|---|
| 0 | kind = 5 | uint |
| 1 | level | uint: 0 if entries name chunks, otherwise the level of the indexes they name |
| 2 | entries | list of `{1: id, 2: key, 3: plaintext length}` |

An index is encrypted and identified the same way as a chunk. An index whose
encoding would exceed 256 KiB is split into consecutive indexes, which are
named by an index one level up. One index holds about 3,600 entries, so one
level covers about 230 MiB and two levels about 800 GiB.

## References

A **blob reference** is the record:

| Key | Field | Type |
|---|---|---|
| 1 | id | bytes(32): id of the chunk, if the blob is one chunk; otherwise of the top index |
| 2 | key | bytes(32) |
| 3 | size | uint: total plaintext length |
| 4 | levels | uint: 0 for a single chunk; otherwise top index level + 1 |

References live inside space entries, so they are encrypted with the space.
A reference can also be handed to someone outside the space, which lets them
read that blob and nothing else. "Send this file to Ben" can be exactly that.

## Fetching

Chunks and indexes are fetched by id from any holder, through the
[link](link.md) `blob` service ([sync.md](sync.md#blob-transfer)). A fetcher
MUST verify that `BLAKE3(ciphertext) == id` before using or storing a chunk.
Verification needs no key, so a chunk may come from anywhere.

## Retention

A device decides locally which chunks to keep. Typical policies, set per
space in the account space ([profiles.md](profiles.md#account)):

- **full**: keep every chunk referenced by current state;
- **on demand**: keep what was opened recently, up to a size budget;
- **history**: also keep chunks referenced only by older versions.

The account space records which devices and hosts hold full copies of each
space, so the software can tell a person how many copies of their files
exist, and warn when the answer is one.
