# Cardinal Core

A specification for personal communication and computing in which people own
their identity, their data, and their relationships. Nothing reaches a
person without their consent, and nobody's permission is needed to take
part.

Status: **first complete draft.** It is coherent end to end and has not been
implemented. The cryptographic constructions need review by a cryptographer
before anything is frozen.

## Reading order

1. [principles.md](principles.md): the problem, the goals, the tests. Ten
   minutes. Everything else answers to this.
2. [architecture.md](architecture.md): the five concepts, how they fit, and
   walkthroughs. Fifteen minutes.
3. [experience.md](experience.md): what a person should experience.
4. [decisions.md](decisions.md): why each major choice was made, and what it
   costs.
5. [spec/](spec/): the normative documents, in dependency order:

| Document | What it defines |
|---|---|
| [encoding.md](spec/encoding.md) | the one binary encoding; signed objects |
| [crypto.md](spec/crypto.md) | the cryptographic suite; sealing |
| [identity.md](spec/identity.md) | identity logs, device powers, recovery |
| [spaces.md](spec/spaces.md) | spaces, membership, epochs |
| [state.md](spec/state.md) | the shared tree and its merge rules |
| [blobs.md](spec/blobs.md) | chunking, encryption, and references for content |
| [sync.md](spec/sync.md) | set reconciliation; fetching; bundles |
| [link.md](spec/link.md) | sessions, handshake, streams, priority, roaming |
| [hosts.md](spec/hosts.md) | mailbox, rendezvous, relay, storage, discovery |
| [contact.md](spec/contact.md) | invitations, pairing, introductions |
| [profiles.md](spec/profiles.md) | account, files, relationship, group, public |

6. [later.md](later.md): designed for, not yet specified.

## The five concepts

| | |
|---|---|
| **Identity** | who you are: a log of which devices speak for you and who can recover you |
| **Space** | where shared things live: encrypted, merged, replicated |
| **Blob** | content: encrypted chunks; a reference is also the key |
| **Link** | how devices talk: roaming, prioritized, silent to strangers |
| **Host** | an always-on device that helps: mailbox, introductions, relay, storage |

## First milestone

One person, several devices, a folder that is the same everywhere, with
history and conflict copies. That needs encoding, crypto, identity (without
guardians), spaces, state, blobs, sync, link, pairing, local discovery, and
one host. It must replace a real rsync job before anything else is built.

## Relationship to earlier work

This replaces the drafts in `../tools`. It keeps their principles and several
of their mechanisms, and departs from them in the places listed in
[decisions.md](decisions.md).
