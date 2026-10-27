# State

Status: draft. Normative.

A space's entries are a history. Its **state** is what that history adds up
to: a tree of nodes. Every profile ([profiles.md](profiles.md)) uses this one
tree. A files space puts folders and files in it, a conversation puts
messages in it, and an account space puts contacts and settings in it.

**State is a pure function of the set of entries** and the members'
identity logs. Every member computes the same state from the same set, with
no coordination, whatever order entries arrived in, and no merge ever
discards data silently. Entries are discarded
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
or names a node whose `create` is not in a valid entry in the entry's causal
past or in the entry itself, the whole entry is ignored for state, though it
still syncs. These checks depend only on the entry and its causal past, so
every device makes the same decision. A reply to a message that is later
found invalid is therefore ignored too; software shows both as discarded. A move skipped to prevent a cycle is not a
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

A long history is a cost for a new device. A **checkpoint** records the state
at a point, so that a device can start there instead of at the beginning.

`checkpoint` op fields:

| Key | Field |
|---|---|
| 1 | frontier: the ids of the entries whose state this describes (the entry's own parents) |
| 2 | state root: `BLAKE3` of the canonical state at that frontier |
| 3 | state blob: [blob reference](blobs.md#references) to the canonical state |

A checkpoint changes nothing about the state. It is a claim about what the
state was, which anyone holding the history can check.

### Canonical state

The **canonical state** is the record `{0: 13, 1: list of node records}`,
sorted by node id. Each node record is `{1: id, 2: kind, 3: parent, 4: name,
5: fields as a list of {1: key, 2: list of {1: entry id, 2: value}}, 6:
deleted, 7: position writer, 8: delete conflict, 9: creator identity}`.
Values are sorted by the id of the entry that wrote them, and field 7 is the
id of the entry whose `create` or `move` set the current position. Membership
and epochs are not part of it; they are computed from control entries.

The canonical state is also how a [successor space](spaces.md#succession)
starts.

### Light holders

The state is defined over the full history, and nothing in this
specification lets a holder drop entries and still claim to compute it.
A device short on storage MAY instead run as a **light holder**:

- It starts from a checkpoint written by a key of **its own identity**. It
  trusts its own devices; it trusts no one else's checkpoint.
- It keeps the sealed ids of the entries before the checkpoint, so that it
  reconciles the space's set like any holder, and omits their content when
  asked for them ([sync.md](sync.md#fetching-objects)).
- It applies directly only entries whose causal past includes every entry of
  the checkpoint's frontier. For any other entry, and whenever a member's
  identity log gains a removal or a recovery, it fetches the full history
  from a full holder and recomputes, or asks a full holder of its own
  identity for a new checkpoint.

Being light is a local choice that never changes a result. It depends on
someone keeping the full history: every space MUST have at least one **full
holder** per member identity that wants the space to survive, either one of
its devices or a storage host. The account space records which devices are
light ([profiles.md](profiles.md#account)), and software warns when a space
has no full holder.

To bound history itself, rather than one device's copy of it, a space is
[succeeded](spaces.md#succession).

## Cost

A device holding a space keeps its state materialized and applies new
entries incrementally. Recomputing from scratch is needed only when an entry
arrives that is earlier in log order than entries already applied, and then
only for the nodes it touches.
