# Profiles

Status: draft. Normative where marked; the rest is guidance for
applications.

A **profile** says what a space is for: which node kinds exist, which fields
they have, and who may change what. The core profiles are listed here. An
application can define its own profile, named by the hash of its schema
document, and it gets sync, history, encryption, membership, and backup
without writing any of them.

| Profile | Value | Members |
|---|---|---|
| account | 1 | one identity: yourself |
| files | 2 | usually yourself; any members to share a folder |
| relationship | 3 | exactly two identities, both owners |
| group | 4 | any number |
| public | 5 | writers you choose; readable by anyone |

Kinds below are profile-local uints. Fields are numbered per kind.

## Shared rules (normative)

- **Author-owned nodes.** A node created with field 15 = 1 may be changed or
  deleted only by its creator's identity. Messages, reach nodes, and read
  markers are author-owned. Ops by anyone else on such a node are ignored.
- **Reach.** Every profile except account may contain one reach node per
  member (see [Reach](#reach)).

## Account

Each identity has exactly one account space, created by the first device
right after the identity's genesis entry. It is
where a person's devices keep everything about the person that is not shared
with anyone else.

| Kind | Name | Fields |
|---|---|---|
| 1 | contact | 1: identity id; 2: petname; 3: relationship space id; 4: notes; 5: is a guardian; 6: accept introductions from (bool) |
| 2 | space | 1: space id; 2: local name |
| 3 | host | 1: grant (signed object bytes) |
| 4 | device | 1: device key; 2: name; 3: is always on; 4: is a host for this identity |
| 5 | secret | 1: purpose (text); 2: value (bytes). Holds the discovery secret and similar. |
| 6 | setting | 1: name (text); 2: value |
| 7 | placement | under a space node: 1: device key; 2: retention policy; 3: where the device shows the space, such as a folder path |
| 8 | storage label | under a host node: 1: label; 2: space id; 3: 0 entries, 1 chunks |
| 9 | token | under a host node: 1: token; 2: space id; 3: revoked (bool) |
| 10 | invitation | 1: invitation record; 2: cancelled (bool) |
| 11 | invitation use | under an invitation node: 1: identity id that used it |

Anything a person's devices may add to concurrently is a node of its own,
never an item in a list field, so concurrent additions merge instead of
conflicting.

Retention policies are 0 full, 1 on demand, 2 full with history
([blobs.md](blobs.md#retention)).

A device restored from the recovery phrase finds the account space at the
host printed on the person's recovery sheet, as described in
[hosts.md](hosts.md#restore). From the account space it finds everything
else.

## Files

A files space mirrors a folder tree.

| Kind | Name | Fields |
|---|---|---|
| 1 | folder | 1: ignore patterns (list of text, glob syntax) |
| 2 | file | 1: content: blob reference, or bytes for content under 1 KiB; 2: mode bits; 3: modified time (author's clock, display only) |
| 3 | link | 1: target (text) |

### Mapping to a disk (guidance)

- A device presents the space as a folder, using whatever the platform offers
  for files fetched on demand: FUSE, the macOS File Provider, the Windows
  Cloud Files API, or the Android Storage Access Framework. Where content is
  not local, the platform shows a placeholder until opened.
- Changes on disk are batched into one entry per burst of activity: after
  writes have been quiet for 200 ms, or after 2 seconds of continuous
  writing. Changes that belong together,
  such as a git commit, therefore arrive together.
- A file whose content field is in conflict appears as the version last in
  log order under its own name, and each other version as
  `name (conflict, <device name>).ext`. Deleting a conflict copy, or editing
  the main file, writes a `set` that descends from all versions and settles
  the conflict.
- Two nodes with the same name in one folder appear as `name` and
  `name (2)`.
- A delete conflict leaves the file in place and tells the person who deleted
  it and who was still editing it.
- Every earlier version of every file is in the history. Restoring one is a
  `set` of the old value.

Git repositories work unchanged. Git's objects are content-addressed and
never conflict. Concurrent changes to a branch's ref file become ordinary
conflict copies, which git users already know how to resolve.

## Relationship

A relationship space is a friendship, a business relationship, or any other
pair. It is created by [contact.md](contact.md).

| Kind | Name | Fields |
|---|---|---|
| 1 | conversation | 1: title |
| 2 | message | 1: text; 2: attachments: list of `{1: name, 2: blob reference, 3: media type}`; 3: in reply to (node id); 15: author-owned = 1 |
| 3 | reaction | 1: text, such as an emoji; 15: author-owned = 1. Created under a message. |
| 4 | read marker | 1: id of the last message read; 15: author-owned = 1. One per member. |
| 5 | folder, 6 file, 7 link | as in the files profile, for shared files |
| 8 | introduction | 1: introducer identity; 2: introduced identity; 3: suggested name; 4: note; 5: invitation ([contact.md](contact.md#introductions)) |
| 9 | reach | see [Reach](#reach) |

The genesis creates one conversation node. Messages are created under it, and
appear in log order, which every device computes the same way and which
always shows a reply after the message it answers.

Editing a message is a `set` on its text. Deleting it is a `delete`. Both
remain in the history, which is honest about what was said: the members
already saw it.

### Calls (guidance)

A call needs no new mechanism. One device sends a `ring` on the space's
ephemeral service to the other members' online devices. Media then flows over
link datagram channels labeled `first16(BLAKE3(space id || call id))`, in
the real-time priority class. With more than about six participants, one
participant's device forwards media for the rest. Codecs are an application
choice.

## Group

A group space is a relationship space with any number of members and the full
set of [roles](spaces.md#roles). Families, teams, clubs, and congregations
are groups. Members who are not direct contacts of each other can still
reach each other through the group's reach nodes, but only about that
group's space.

## Public

A public space publishes. Its policy has `public = 1`, so its epoch keys are
in the clear ([spaces.md](spaces.md#public-spaces)), and its writers are the
members.

| Kind | Name | Fields |
|---|---|---|
| 1 | profile | 1: suggested name; 2: picture (blob reference); 3: about (text) |
| 2 | post | 1: text; 2: attachments; 3: in reply to: `{1: space id, 2: node id}` |
| 3 | front door | 1: invitation ([contact.md](contact.md#front-door)) |
| 4 | link | 1: public address of another public space ([contact.md](contact.md#following)); 2: label |
| 5 | folder, 6 file | as in the files profile, for publishing software, documents, and media |

Replies to someone else's post are posts in the replier's own public space,
pointing at the original. No one writes into anyone else's space without
being made a member.

## Reach

A reach node (normative) is author-owned and lists how to reach its author
about this space:

| Field | Value |
|---|---|
| 1 | list of `{1: endpoints, 2: host link key, 3: delivery token}`, one per host |

Tokens in a reach node are valid only for this space ([hosts.md](hosts.md#delivery-tokens)).
