# Evolution

Status: draft. Normative.

Once this project is open, nobody owns it. People on different planets, or
just in different communities, will extend it, and nobody should have to
ask anyone's permission to do so. This document says how the protocol
changes without a registry, an authority, or silent disagreement.

## The problem with numbers

Application kinds and profiles are already named by hash
([encoding.md](encoding.md#kinds)), so two applications can never collide.
The core is different. Identity ops, space control ops, and core kinds are
small integers, and their meaning decides **validity**: which keys count,
who is a member. If Mars gives identity op 12 one meaning and Earth gives it
another, every device still preserves the bytes, but the two planets decide
validity differently. An identity valid on one is invalid on the other, and
nobody notices until it matters. That is the worst kind of split.

## The base is frozen

The **base protocol** is this specification, frozen as one document: every
small-integer kind, op, and field defined here. Its **base hash** is
`BLAKE3` of that document, computed once when it is frozen and published
with it. Nobody ever extends the small integers. A device that implements
the base knows every small integer it will ever meet.

Until the base is frozen, the base hash of drafts is 32 zero bytes, and
drafts make no promise of compatibility.

## Extensions are named by hash

Anything new is an **extension**: a document that defines new kinds, ops, or
fields, named by its hash, `BLAKE3` of the document. Wherever the base puts a
small integer, an extension puts its 32-byte name:

- an extension **kind** is key `0` of an object, with the extension's name as
  its value, as application kinds already are;
- an extension **op** is an op record whose key `0` is the extension's name,
  with the extension's fields under keys 1 and up. An extension that defines
  several ops numbers them in field 1.

Two documents never share a name, so two extensions never collide. No
registry is needed, now or ever. Thirty-two bytes, not sixteen: an attacker
who could find two documents sharing a shorter name could swap a popular
extension for their own.

A new base, such as one that changes the signature suite, is just a new
document with a new base hash. Two communities that fork the base itself
end up with different base hashes, and every device can see which one a
contact speaks.

## Critical and ignorable

Every extension declares, in its document, one of two things:

- **Ignorable.** It adds meaning without changing validity: display hints,
  new profile metadata, a new application feature. A device that does not
  know it preserves its ops and fields and otherwise ignores them.
- **Critical.** It can change validity: a new kind of key, a new authority
  op, a new rule for membership. A device that does not know it cannot judge
  anything that depends on it.

### What a device does with a critical extension it does not know

In an identity log or a space, a valid entry that uses a critical extension
the verifier does not know is **opaque**. The verifier:

1. evaluates the log as usual, treating the opaque entry's unknown ops as
   having no effect, to find which entries are valid ([model](../model/rules.md));
2. evaluates it again without each valid opaque entry and everything that
   descends from it, and uses that result;
3. tells its person plainly, for example: "Ben's identity uses a feature
   this software doesn't understand. Changes after that point can't be
   checked until you update."

An entry that is invalid for reasons that do not depend on its content,
such as being signed by a key that was removed, is simply invalid, whatever
ops it carries. So a thief cannot stall an identity with nonsense ops from a
device whose removal excludes them.

Two rules keep this from becoming a weapon:

- **Declared first.** An entry using a critical extension is invalid unless
  a `set_protocol` that names the extension is in its causal past, or in the
  same entry.
- **Admins and up.** In an identity log, only admin and root keys may use
  critical extensions or `set_protocol`. In a space, only owners may write
  `set_protocol`, and an extension says which roles may use its ops.

A stolen phone therefore cannot stall its identity. A stolen admin can, and
is removed as any stolen admin is.

### Agreement

The authority rules give one result for any set of entries
([model/README.md](../model/README.md)). With extensions, that holds **for
verifiers that know the same extensions.** A device that knows an extension
and one that does not may legitimately disagree about what follows an
opaque entry: one judges it, the other stops. They never disagree silently,
because the one that stops says so, and they agree again as soon as both
know the same extensions. What a device does not know only ever makes it
accept less, never more.

The model checks this: for any one set of known extensions, the result does
not depend on the order entries arrive; a verifier that knows every
extension used gets exactly the plain result; and a verifier stops only at
valid entries using a critical extension it lacks.

## Declaring what you speak

An identity says which protocol it speaks with a **protocol record**:

| Key | Field |
|---|---|
| 1 | base hash |
| 2 | list of extension names this identity uses |

The genesis entry carries one in field 5 ([identity.md](identity.md#entries)).
`set_protocol` (identity op 10) replaces it. A space's `start` op carries one
in field 5, and space control op 9, `set_protocol`, replaces it
([spaces.md](spaces.md#control-operations)).

A device compares a contact's protocol record with its own before it
relies on that contact's log, and can say in advance: "Your software can't
fully check Ben's identity until you update."

A change of base that changes the signature suite also needs a new root
key. It is made inside a [root replacement](identity.md#roots), which may
carry one `set_protocol` op alongside its `add_key` and `remove_key`.

## Who decides which extensions to adopt

Nobody, for everybody. Each person decides for their own devices.

A **protocol publisher** is any identity with a public space that publishes
protocol documents: extensions, new bases, and their test vectors, each a
file whose name is its hash. Publishing is endorsement: a publisher puts in
its space the documents it vouches for, and may write notes saying why, or
withdraw a note later.

A person's account space lists the publishers they follow. A device adopts
an extension when it has an implementation of it and a followed publisher
endorses its hash. Software comes with a default list of publishers, which
the person can change. The authors of this specification would be one
publisher among many, with no special standing in the protocol.

Implementations are distributed the same way as other software
([later.md](../later.md#software-distribution)): a publisher's space holds
the code, and devices take updates from publishers they follow.

## What this costs

- Ops from extensions carry a 32-byte name instead of a one-byte number.
- A device that does not keep up may stop trusting parts of its contacts'
  logs. That is the honest outcome: it cannot judge them.
- Forks are possible and visible. A community can always go its own way,
  and everyone can tell which way a contact went.
