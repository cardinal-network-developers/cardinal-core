# Principles

Everything else in this repository is measured against this document. If a
specification conflicts with it, the specification is wrong.

## The problem

Communication networks bind three things together that should be separate:
**who you are**, **where you are**, and **whether you may speak**. An email
address is a name rented from a domain, which is rented from a registrar,
served from an address rented from a provider. Permission to be heard comes
down the same chain. When identity is rented, the landlords decide who exists.

The second flaw is economic. Sending is cheap and attention is expensive. A
network that delivers by default makes the receiver pay. The receiver then
needs a filter, a filter needs information, and the party with the most
information wins. Spam is the strongest force toward centralization on the
internet. It cannot be fixed with a better filter. It can only be fixed by a
network in which unrequested traffic does not arrive.

## What a person should be able to do

These are the goals. Every mechanism exists to serve one of them.

1. **Own their data.** Data lives on machines the person controls, or
   encrypted on machines they chose to trust. It survives the loss of any one
   machine.
2. **Decide who sees it.** Access is granted by the person, to people, and
   can be withdrawn going forward.
3. **Never lose access because of popularity or money.** No account can be
   closed by a third party. Hosting can be mutual aid between friends.
4. **Share without choosing how.** Send the file, write the message, place
   the call. The person never picks a protocol, a service, or an app to do it.
5. **Stop caring which device has what.** Every device shows everything; a
   device may fetch on demand.
6. **Be recognized without passwords or permission.** Contacts verify you
   cryptographically. No one issues you a name.
7. **Recover with help from friends.** From lost devices, lost backups, and
   stolen keys.
8. **Continue work across devices.** Leave the laptop, sit at the desktop,
   carry on.
9. **Pool compute** across one's own devices and those entrusted by friends.
10. **Not require expertise.** A person's grandmother gets the same benefits
    without learning any of the words in this repository.

## Non-goals

The design is what the goals require, no more and no less.

- **Anonymity.** People in this network are known to those they talk to.
  Pseudonyms are possible (an identity is only a key), but nothing is added
  to make them easy.
- **Evading law or taxes.** Nothing is added to make it easy.
- **Built-in moral filtering.** Communities and individuals decide what they
  accept. The protocol enforces consent, not content policy.

The network is about freedom inside a well-ordered society. Order is built
by the people who choose each other, not by whoever owns the wires.

## Constraints

1. **Physics, not promises.** The system promises nothing that logic and
   physics do not guarantee. You cannot unshare what was shared; a
   disconnected machine cannot learn news; a key held by two people belongs
   to both of them.
2. **Partitions are normal.** Groups of devices, of people, or of planets may
   be disconnected for minutes or years. Everything works inside a partition
   and reconciles when contact resumes. Nothing requires global consensus,
   a global clock, or a global name.
3. **Most devices cannot listen.** Phones sit behind carrier NAT and sleep.
   The design must work when the only reachable machine is someone's
   always-on box.
4. **People lose keys.** Recovery is part of the foundation.
5. **Value for one person, on day one.** Network effects are brutal. The
   first user must benefit with zero counterparties.
6. **Commodity hardware and operating systems.**

## Design rules

- **Consent before delivery.** Nothing arrives from anyone you have not
  connected with. The only unrequested thing anyone can send is one small
  unit, and only with a token you issued.
- **The sender bears the cost.** Bulk data is pulled by the recipient, never
  pushed.
- **No special nodes.** Every role (relay, mailbox, storage, introducer) can
  be filled by any device the owner chooses, and is trusted with nothing but
  availability.
- **No special codes.** No registry of names, numbers, or accounts is needed
  to participate. Protocol constants are the only shared vocabulary.
- **Design for trust.** Trust is real and unavoidable. Make it explicit,
  verifiable, and revocable, rather than pretending to remove it.
- **Silence to strangers.** A personal device does not respond to traffic
  from parties with no relationship to it.
- **One primitive per concept.** If two mechanisms do the same job, delete
  one.
- **Plain words.** Use the least surprising existing term. Files are files.
- **Simple means implementable forever.** A competent programmer with this
  repository and the cited primitives must be able to build an
  interoperating node, without asking anyone.
- **Climb down the stack when the stack is wrong.** Reuse an outside design
  when it fits. When it does 90% or 200% of what is needed, write the part
  that fits. Reuse cryptographic primitives freely. Never invent new
  cryptographic primitives.

## The tests

Apply these to every design:

- **The nomad test.** Could a person wandering a galaxy of disconnected
  settlements keep control of their identity, data, and relationships?
- **The grandmother test.** Can someone who does not know what a key is set
  it up, use it daily, and recover from a lost phone?
- **The landlord test.** Is there any party whose cooperation is required,
  whose refusal would lock a person out?
- **The spam test.** What is the worst a stranger can make you receive?
  The answer must be: nothing.
- **The half-hour test.** Can a contributor re-enter the project cold, read
  one document, and make a correct change?

## AI participants

Software agents will act on behalf of people and organizations. In this
design an agent is a device or identity like any other, holding only the
powers it was delegated, accountable to whoever delegated them, and bound by
the same consent rules. That protects people from machine-generated noise,
and it gives agents a legitimate, accountable way to act. Both are needed.
