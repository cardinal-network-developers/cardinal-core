# Applications

Status: draft. Sections marked normative touch the protocol; the rest is
guidance for the local interface between the Cardinal service on a device
and the applications it runs.

An application should be able to do something with your friends without
learning anything else about you: not your other spaces, not your other
applications, not who your guardians are, not your devices or addresses.
Scopes tried to express that inside the protocol ([D12](../decisions.md)).
It belongs instead at the boundary between the person's device and the
application, where the person can see it, and the protocol stays simple:
it only ever sees "this identity wrote to this space."

There are two cases. Most applications run on the person's device and
never hold a key. Applications that must act on their own, such as a game
server or an AI agent, get their own identity.

## Local applications

### The service holds everything

On each device, one **Cardinal service** holds the device's keys, the
identity logs, every space the person holds, and every link session. It
evaluates validity, merges state, and syncs. Applications talk only to the
service, through a local interface the platform protects (a socket, a
binder, an XPC service).

An application never holds or sees:

- keys of any kind;
- identity logs, so not device counts, guardians, or recovery state;
- network addresses, hosts, or tokens;
- any space it was not granted, including the account space;
- which other applications exist.

### The person grants spaces

An application asks the service for a space. The **service**, not the
application, draws the picker: "Board game wants to play with: Ana, Ben."
The person's choice in that picker is the grant. This is the **powerbox**
pattern from capability systems: there is no permission to request and no
dialog to click through, because choosing is granting.

From the person's choice the service either grants an existing space or
creates a new one, with the application's profile (the hash of its schema,
[profiles.md](profiles.md)) and the chosen people as members. Those people
receive an offer through their relationships with the person, as with any
space ([spaces.md](spaces.md#holding-a-space)), and their own service shows
it: "Daniel invites you to play Board game."

A grant is local to the device: the service records it in the account
space, so the person's other devices honor it, and the person can see and
revoke every grant in one place. Revoking a grant does not change the space;
it only stops that application from reading or writing it.

### What the application sees

For each granted space, the service gives the application:

- the space's state, as nodes of the application's profile, and changes as
  they arrive;
- members as **handles** the service chooses, opaque and different for each
  application, with the person's petname for each where the person has one.
  An application cannot correlate a handle with anything outside the space,
  or across applications;
- ephemeral messages and real-time channels for that space, labeled by the
  space, as for [calls](profiles.md#calls-guidance). The service carries
  them over its own sessions; the application sees no addresses.

### What the application writes

The application asks the service to append ops to a granted space. The
service checks them against the profile and the grant, and signs the entry
with the device's key, **as the person**. Friends' devices see "Daniel
moved", verified by their own services, not by their copy of the
application. A buggy or hostile copy of an application elsewhere cannot
forge a move: it never holds a key.

### Friends need nothing new

The chosen friends are co-members of the space, so their devices may reach
each other about it ([spaces.md](spaces.md#holding-a-space)) through
ordinary reach nodes and sessions. No new relationship, permission, or
service is involved. The application on each device sees only that space.

### The limit

None of this holds against an application the platform lets read the whole
disk or the service's memory. Isolation is as good as the operating system's
sandbox: Android, iOS, macOS, and Flatpak provide one; a plain desktop
process with the person's privileges does not. The protocol's part is that
it never requires giving an application more than one space. Services
SHOULD refuse to grant anything to an application that is not sandboxed,
or say plainly that it can read everything.

## Agents (normative where marked)

An application that must act while the person is away, run on someone
else's machine, or hold its own keys, such as a game server, a household
assistant, or an AI agent, is an **agent**. An agent is its own identity
([identity.md](identity.md#keys-and-powers)). It holds only the memberships
it is given, so it can read nothing else, and compromising it costs only
those spaces.

**Agent of (normative).** `add_member` field 3 names the identity the added
member acts for: its **principal**. It has no effect on validity. Software
shows the member as the principal's agent, "Daniel's game bot", only when
the `add_member` entry's author is the principal, so the binding is the
principal's own signed statement. When anyone else wrote it, software shows
the claim as unverified.

**Guardians.** An agent's guardians are naturally its principals. An agent
cannot meet anyone in person, so the trust others place in it beyond its
keys comes from the humans who vouch for it, and its recovery is theirs to
decide ([identity.md](identity.md#guardians)).

**What an agent learns.** An agent that verifies entries itself needs the
identity logs of the members of its spaces, so it learns their identity ids
and whatever their logs reveal ([identity.md](identity.md#distribution)).
That is consented: the members accepted a space with the agent in it. An
agent that only needs to act can instead be a local application of its
principal's service, and learn nothing beyond the space.

## Summary

| | Local application | Agent |
|---|---|---|
| Holds keys | no | its own identity's |
| Sees | granted spaces, through handles | its memberships, and those members' identity logs |
| Writes as | the person, signed by the person's device | itself, shown as its principal's agent |
| Granted by | the person, in the service's picker | `add_member`, by a member who may add |
| Protected by | the platform sandbox | its own keys; losing them costs only its spaces |
