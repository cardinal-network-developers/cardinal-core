# State

Status: draft. Normative.

A space's entries are a history. Its **state** is what that history adds up
to: a tree of nodes. Every profile ([profiles.md](profiles.md)) uses this one
tree. A files space puts folders and files in it, a conversation puts
messages in it, and an account space puts contacts and settings in it.

Every member computes the same state from the same set of entries, with no
coordination, and no merge ever discards data silently.

## Nodes

A node has:

- an **id**, 16 bytes;
- a **kind**, a uint or bytes(32), set at creation and never changed;
- a **position**: a parent node id and a name (text);
- **fields**: a map from uint keys to values;
- a **deleted** flag.

The **root node** has id sixteen zero bytes, always exists, and has no
position. A node's id is the first 16 bytes of
`BLAKE3(entry id || varint(i))`, where `entry id` is the id of the
[space entry](spaces.md#entries-and-sealed-entries) (not the sealed entry)
that created it, and `i` is the zero-based position of the `create` op in
that entry's op list.

Names need not be unique within a parent. Two nodes created concurrently
with the same name in the same folder both exist; views disambiguate them
([profiles.md](profiles.md#files)).

## Operations

Profile op numbers start at 32. These are shared by every profile:

| Op | Name | Fields |
|---|---|---|
| 32 | `create` | 1: kind; 2: parent id; 3: name; 4: fields (record) |
| 33 | `set` | 1: node id; 2: field key; 3: value (absent to clear) |
| 34 | `move` | 1: node id; 2: new parent id; 3: new name |
| 35 | `delete` | 1: node id |
| 36 | `restore` | 1: node id |
| 37 | `checkpoint` | see [Checkpoints](#checkpoints) |

A profile may restrict which kinds may be created where, and which fields
exist. Ops that violate the profile are ignored, but the entry still syncs.

## Merge rules

Let the **valid entries** be those that pass the space's author and
membership checks ([spaces.md](spaces.md)). Process their ops in log order.

### Fields are multi-value registers

For each node and field key, the field's **values** are those written by
`set` ops (or by `create`) that no other `set` of the same field has
superseded. A `set` supersedes another if its entry is a descendant of the
other's entry.

- One value means the field is settled.
- Several values mean a **conflict**. Every value is kept. The field stays in
  conflict until some later `set` that descends from all of them settles it.
- Applications decide how to present a conflict. Files show both versions
  ([profiles.md](profiles.md#files)). Nothing is chosen silently.

### Moves form a tree

Positions follow the move algorithm of Kleppmann et al., "A highly-available
move operation for replicated trees" (2021):

- Apply `create` and `move` ops in log order.
- A move that would make a node its own ancestor is skipped.
- Concurrent moves of the same node: the one later in log order wins. The
  losing position is not a conflict; the node was moved twice, and one move
  was applied last.

Because the procedure is defined on the full log order, an implementation
that receives an entry out of order undoes and redoes later moves, or
recomputes. The result is the same on every device.

### Deletion yields to concurrent work

A `delete` of node `N` takes effect only if every other op that touches `N`
or any node beneath it is an ancestor of the delete. Otherwise:

- the node stays, and is flagged **delete conflict**;
- descendants that were not touched concurrently are deleted;
- the application shows the user that someone deleted what someone else was
  still changing.

Deleted nodes keep their fields. `restore` clears the flag. History is the
undo.

### Nothing else

Every application builds on these three rules. An application that needs
ordered sequences, such as messages in a conversation, creates nodes under a
parent and orders them by log order. Log order is the same on every device,
and respects causality: a reply always comes after what it replies to.

## Checkpoints

A long history is a cost for a new device. A **checkpoint** lets a device
start from a recent state instead of the beginning.

`checkpoint` op fields:

| Key | Field |
|---|---|
| 1 | frontier: the ids of the entries whose state this describes (the entry's own parents) |
| 2 | state root: hash of the canonical state at that frontier |
| 3 | state blob: [blob reference](blobs.md#references) to the canonical state |
| 4 | prunable: 1 if the author proposes that entries before the frontier may be dropped |

The **canonical state** is the encoding of a list of node records, sorted by
node id. Each node record is `{1: id, 2: kind, 3: parent, 4: name, 5: fields
as a list of {1: key, 2: list of {1: entry id, 2: value}}, 6: deleted,
7: position writer, 8: delete conflict}`. Values are sorted by the id of the
entry that wrote them, and field 7 is the id of the entry whose `create` or
`move` set the current position. The **state root** is `BLAKE3` of that
encoding. Membership and epochs are not part of it; they are always computed
from control entries, which are never pruned.

### Pruning never changes the result

Pruning drops the *content* of old entries, never their place in history.

- A holder that prunes keeps, for every pruned entry, its **skeleton**: its
  entry id, its parents, and its author. Skeletons cost under 100 bytes per
  entry, and are enough to compute ancestry and log order exactly.
- Entries containing control operations ([spaces.md](spaces.md#control-operations))
  are never pruned.
- Every merge rule is defined on ancestry and log order, and on the writers
  recorded in the canonical state. So a pruned holder and a full holder
  compute the same state from the same entries.

Only entries that are ancestors of the frontier of a prunable checkpoint
written by an owner may be pruned. The space's sync set excludes them for
every holder, so holders that pruned and holders that did not still agree on
the set ([sync.md](sync.md#sets)). Full history remains available, from
holders that keep it, under the history label.

A device MAY start from a checkpoint written by its own identity or by a
space owner, and MUST NOT start from anyone else's. The checkpoint's state
blob is the record `{1: canonical state, 2: skeletons of every entry before
the frontier, as {1: entry id, 2: parents, 3: author}}`. The device verifies
the state root against field 1, verifies that the skeletons link up to the
frontier, and continues from there.

## Cost

A device holding a space keeps its state materialized and applies new
entries incrementally. Recomputing from scratch is needed only when an entry
arrives that is earlier in log order than entries already applied, and then
only for the nodes it touches.
