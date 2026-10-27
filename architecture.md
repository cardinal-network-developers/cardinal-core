# Architecture

Read [principles.md](principles.md) first. This document explains how the
pieces fit; the normative details live in [spec/](spec/).

## Five concepts

The whole system is built from five things. Everything a user does is one of
them or a combination.

| Concept | One sentence | Spec |
|---|---|---|
| **Identity** | A person (or organization, or agent) is a signed, append-only log of which devices speak for them and who can recover them. | [identity.md](spec/identity.md) |
| **Space** | All shared data lives in spaces: encrypted, replicated logs of changes, with members, roles, and a deterministic merge. | [spaces.md](spec/spaces.md), [state.md](spec/state.md) |
| **Blob** | File content is split into encrypted, content-addressed chunks; a reference to a blob is also the key to read it. | [blobs.md](spec/blobs.md) |
| **Link** | Devices talk over authenticated, encrypted sessions that roam between networks and stay silent to strangers. | [link.md](spec/link.md) |
| **Host** | Any always-on device can hold mail, relay traffic, introduce peers, and store encrypted data for an identity that asked it to. | [hosts.md](spec/hosts.md) |

Two supporting specifications hold everything together:
[encoding.md](spec/encoding.md) (one binary format for everything) and
[crypto.md](spec/crypto.md) (one cryptographic suite, no negotiation). Two
more define how relationships start and what the first applications look
like: [contact.md](spec/contact.md) and [profiles.md](spec/profiles.md).
[sync.md](spec/sync.md) defines how any two holders of a set of objects make
their sets equal.

## The key idea: one way to share

There is no separate protocol for files, messages, contacts, settings, or
backup. There is a space, and changes to it.

- **Your files** are a space whose only member is you. Your devices replicate it.
- **Your settings and contact list** are a space whose only member is you.
- **A friendship** is a space with two members. Messages are entries in it.
  Sharing a file with that friend is adding it to that space.
- **A family** or a club is a space with several members.
- **A public blog** is a space anyone may read.
- **Backup** is a host holding encrypted copies of a space's entries and chunks.

Because everything is a space, everything gets the same properties for free:
offline editing, merge after partition, history, encryption, membership
changes, and backup. A user never chooses how to share. They put something
where the people are.

## Layers

```
 Applications   files · conversations · calls · public pages · (compute, commerce)
                     all expressed as space profiles             profiles.md
 ─────────────────────────────────────────────────────────────────────────────
 Data           spaces · state merge · blobs · sync               spaces, state,
                                                                  blobs, sync
 Trust          identity logs · relationships · invitations       identity, contact
 Reach          hosts: mailbox, relay, rendezvous, storage        hosts
 Link           sessions over UDP / TCP / LAN / relay / files     link
 Foundation     encoding · cryptographic suite                    encoding, crypto
```

Each layer uses only those below it. Applications never touch sockets,
addresses, or keys; they read and write spaces.

## How the pieces connect

**Identity → devices.** An identity log names device keys and their powers.
Any device can verify any other device's authority by reading the log. Logs
are shared with contacts, so key changes and revocations spread along the
contact graph without any directory.

**Identity → spaces.** Spaces have identities as members, not devices. When
you add a phone to your identity, it can read every space you belong to, and
no other member needs to do anything. Each identity has one encryption key,
shared among its devices, to which space keys are wrapped.

**Spaces → blobs.** A space entry holds references to blobs, never the bulk
bytes themselves. Entries stay small; content is fetched on demand.

**Spaces and blobs → sync.** Every holder of a space, whether a member's
device or a host that cannot read it, reconciles the same thing: a set of
encrypted objects identified by hash. One reconciliation protocol serves
device sync, friend sync, and backup.

**Link → hosts.** Devices that cannot listen keep sessions with hosts. Hosts
hold small envelopes for them, introduce them to peers for direct
connections, and relay when direct connection fails.

**Consent.** A device opens sessions only with its own identity's devices,
with identities it has a relationship with, and with hosts it uses. Hosts
accept envelopes only with tokens the owner issued. No other path exists for
traffic to reach a person.

## Walkthrough: one person, three devices

1. **First device.** Ana installs the software on her laptop. It creates her
   identity and shows her a 24-word recovery phrase, which it asks her to
   write down. It also offers to let her choose guardians later. It creates
   her personal account space and a files space, and maps the files space to
   a folder.
2. **Second device.** On her desktop she chooses "add this device." The
   desktop shows a short code like `7-amber-harbor-quiet`. She types it on
   the laptop. The two devices find each other on the LAN, verify the code
   with a password-authenticated key exchange, and the laptop appends "add
   desktop" to her identity log. The desktop receives her identity
   encryption key and starts syncing. Her files appear.
3. **Phone.** The same, with the phone. The phone is set to fetch file
   content on demand; it lists everything but stores only what she opens.
4. **Away from home.** Ana's desktop is reachable from the internet, so the
   laptop made it her host. Her phone, behind carrier NAT, keeps a session
   with the desktop when it is awake. Edits on the phone travel to the
   desktop and on to the laptop. When the laptop and phone are both away,
   the desktop introduces them for a direct connection or relays for them.
5. **Conflict.** On a plane, she edits `budget.ods` on the laptop. At home,
   her husband edits the same file on the desktop. When the laptop lands,
   both versions are kept: the file shows as conflicted, with both versions
   available. Nothing is silently lost.
6. **Lost phone.** The laptop and the desktop are admins; the phone is not.
   She opens settings on the laptop and marks the phone lost.
   The removal is appended to her identity log. Her identity encryption key
   rotates, every space rotates its keys at the next write, and her contacts
   stop accepting the phone as soon as they see her log.

## Walkthrough: Ana meets Ben

1. **Invitation.** Ana chooses "invite someone" and sends Ben the resulting
   link by any channel, or they meet and use a short code in person.
2. **Acceptance.** Ben opens it. His device connects to Ana's host using a
   one-time token in the link, the two devices authenticate, and they
   exchange identity logs. Ana's device creates a relationship space with
   both of them as members.
3. **Petnames.** Ana's contact list shows "Ben," which she typed. Ben's shows
   whatever name he chose for her. Neither name is global.
4. **Messages.** Ben writes. His device appends an entry to their space. If
   Ana's laptop is online, the entry goes directly. If not, Ben's device puts
   it, sealed, in Ana's mailbox at her host, using the token she gave him.
   Any of Ana's devices can open it, because the space key belongs to her
   identity, not one device.
5. **A photo album.** Ana drags a folder into the conversation. Its entries
   reference blobs; Ben's devices fetch the chunks from Ana's host when he
   opens them.
6. **A call.** Ben presses call. The devices open a real-time channel inside
   their session, labeled with their relationship space. No new
   relationship, permission, or service is involved.

## Walkthrough: partition

A research station loses its uplink for six months. Inside the station,
everyone's devices keep syncing with each other through the station's own
hosts. People still message, share, add devices, and even remove compromised
devices. When the link returns, every space and identity log reconciles
deterministically: what a set of entries means never depends on when or in
what order they arrived. Revocations made inside the station take effect outside
as soon as the logs propagate, and changes a revoked device made that none
of its owner's other devices had seen are discarded on both sides. Nobody
had to ask permission from anyone outside the station.

## Walkthrough: identity theft

A thief steals Ana's recovery phrase and replaces her root key with one of
his own. Ana's software notices, and with her phrase replaces the root
itself, from before the theft. Her log now has two roots, and every contact
who syncs it sees the fork: the identity is **contested**. While it is,
neither root can add or remove keys, so the thief cannot lock Ana's laptop
out. The thief asks her guardians to approve new guardians, but guardians
approve changes to themselves, and they check with Ana first. Ana calls her
guardians. Ana's new phone writes a recovery that gives it the root and
keeps her laptop, and three of the five friends she named endorse it in
their own logs. Each guardian's software compares a short fingerprint with
Ana's new phone, then waits a week. The thief objects, which doubles the
wait, but cannot stop it. When the wait is over, the guardians confirm,
each confirmation carrying a piece of the key that opens Ana's data. Once
three have confirmed, the recovery is in effect for everyone who holds
those entries, whenever they arrive. Everything the thief did is discarded,
and Ana writes down a new phrase. Physics cannot tell two holders of the
same secret apart, but her friends can.

Had Ana named no guardians, nobody could have told her from the thief. Her
identity would have been **frozen**: shown to every contact as no longer
trustworthy, and replaced by a new one that each contact recognizes in
person. The protocol adds to relationships people already have; when the
evidence runs out, it hands the decision back to them.

## What is deliberately not here yet

Compute pooling, live process handoff, commerce, and very large groups are
designed for but not specified. See [later.md](later.md).
