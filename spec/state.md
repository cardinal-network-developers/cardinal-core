# State

Status: draft. Normative.

A space's entries are a history. Its **state** is what that history adds up
to: a tree of nodes. Every profile ([profiles.md](profiles.md)) uses this one
tree. A files space puts folders and files in it, a conversation puts
messages in it, and an account space puts contacts and settings in it.

Every member computes the same state from the same set of entries, with no
coordination, and no merge ever discards data silently. Entries are discarded
only for reasons of authority ([spaces.md](spaces.md#authors)), and software
shows when that happens.

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
exist.

An entry is checked as a whole. If any of its ops violates the profile,
breaks the author-owned rule ([profiles.md](profiles.md#shared-rules-normative)),
or names a node whose `create` is not in the entry's causal past or in the
entry itself, the whole entry is ignored for state, though it still syncs.
These checks depend only on the entry and its causal past, so every device
makes the same decision. A move skipped to prevent a cycle is not a
rejection; it is part of the merge, below.

## Merge rules

Let the **valid entries** be those that pass the space's author and
membership checks ([spaces.md](spaces.md)). Process their ops in log order.

### Fields are multi-value registers

For each node and field key, the field's **values** are those written by
`set` ops (or by `create`) that no other `set` of the same field has
superseded. A `set` supersedes another if its entry is a descendant of the
other's entry, or if both are in the same entry and it comes later in the
op list.

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

A `delete` of node `N` takes effect unless an op in a concurrent entry
**touches** `N`. An op touches `N` if any node it names (as target, parent,
or new parent) is `N`, or is beneath `N` in the state computed from the
delete's causal past. Ops in entries that descend from the delete do not
count: they were written knowing about it. If the delete is touched:

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

### Barriers

A checkpoint that may be pruned changes the rules, for everyone, so that
pruning cannot change the result.

A **barrier** is a valid prunable checkpoint written by an owner. If two
prunable checkpoints are concurrent, only the one earlier in log order is a
barrier. An owner MUST NOT write a prunable checkpoint that does not descend
from every barrier it knows. Software SHOULD let one always-on device of one
owner write them, rarely, such as monthly.

With a barrier `B` whose frontier is `F`, every holder, pruned or not,
computes state the same way:

1. The state at `F` is the canonical state in `B`. Decisions about entries
   in `F`'s causal past are final: an entry the checkpoint included stays,
   even if a removal that would invalidate it arrives later.
2. Every other valid entry is applied on top of that state, in log order
   among themselves.
3. For every merge rule, each entry in `F`'s causal past counts as an
   ancestor of each entry that is not. A late entry concurrent with `F`
   therefore never reorders, outvotes, or blocks anything before the
   barrier.

A member whose own computation of the state at `F` differs from `B`'s state
root SHOULD tell its person; the barrier still holds. A checkpoint by a key
later found to be compromised is invalid unless witnessed, like any entry
([spaces.md](spaces.md#authors)), and then it was never a barrier.

### Pruning

Pruning drops the content of entries in the latest barrier's frontier's
causal past. Entries containing control operations
([spaces.md](spaces.md#control-operations)) are never pruned. A holder that
prunes keeps the ids of the pruned entries, so that it can tell whether an
arriving entry's parents exist and whether an entry is before the barrier.

The space's sync set excludes pruned entries for every holder, so holders
that pruned and holders that did not still agree on the set
([sync.md](sync.md#sets)). Full history remains available, from holders that
keep it, under the history label.

A device MAY start from a checkpoint written by its own identity or by a
space owner, and MUST NOT start from anyone else's. The checkpoint's state
blob is the record `{0: 13, 1: canonical state, 2: ids of every entry in the
frontier's causal past}`. The device verifies the state root against field
1, checks that the frontier's ids are in field 2, and continues from there.

## Cost

A device holding a space keeps its state materialized and applies new
entries incrementally. Recomputing from scratch is needed only when an entry
arrives that is earlier in log order than entries already applied, and then
only for the nodes it touches.
