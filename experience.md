# Experience

The protocol exists so that people can do ordinary things without thinking
about it. This document lists what a person should experience. Each item is
a requirement on the protocol as much as on applications: if the protocol
makes one of these impossible, the protocol is wrong.

## Words a person never sees

Key, certificate, scope, epoch, entry, blob, chunk, hash, session, host
(say "always-on device" or name the machine), token, sync conflict (say
"two versions"), identity (say the person's name).

## Setup

- **First device: under two minutes, no account.** Install, type your name,
  write down 24 words (or print a recovery sheet). Optionally pick
  guardians from your contacts later. There is no sign-up, email, phone
  number, or password.
- **Every other device: one code.** "Add this device" shows a short code
  like `4-amber-harbor-quiet` on the new device; type it on your laptop or
  home computer, the devices that manage the others. Everything appears.
- **The recovery sheet** is printed or written once. It holds the 24 words
  and the address of one always-on device. Software reminds you, gently and
  rarely, until you have one, and until you have chosen guardians.

## Daily use

- **One folder, everywhere.** Files appear on every device. Phones and small
  laptops show everything and fetch on open. Nothing asks which device has
  what.
- **Share by putting things where people are.** Drag a file into a
  conversation, or invite someone to a folder. There is no "upload," no
  link expiry, no service choice.
- **Messages, files, and calls live in the same place.** A conversation with
  a person holds everything you share with them.
- **Offline is normal.** Everything works on a plane. Nothing is "pending"
  in a way that blocks the person. Changes go out when they can.
- **Background work stays in the background.** Sync and backup never make a
  call stutter or a page load slowly. The link's priority classes exist for
  this.
- **Continue where you left off.** Open the laptop and the document you were
  editing on the desktop is current. For applications whose state lives in
  spaces, this is automatic.

## Things that go wrong

- **Two versions.** When two people, or two devices, changed the same thing
  apart, the person sees both, labeled by who and where, and picks or
  merges. Nothing is lost and nothing is chosen silently.
- **Lost phone.** On the laptop or home computer: "This phone is lost."
  Everything it wrote that your other devices had already seen is kept. The
  software shows anything else it wrote, and you keep what you recognize.
  The phone is cut off from everything, and contacts' devices learn it the
  next time they connect.
- **Sold or replaced a device.** "I'm done with this laptop." Everything it
  did is kept, and nothing it does later counts.
- **Lost everything.** On a new device: enter the 24 words and the
  always-on device's address. Or ask three of your guardians to approve:
  each reads a short code off your new device. After the waiting period,
  everything returns.
- **Someone has my words.** The software notices the conflicting change,
  says so plainly, and walks the person through asking guardians to settle
  it. Without guardians, it says that the identity is frozen and helps the
  person start over.
- **Beyond recovery.** With no words, no device, and no guardians able to
  act, nothing can prove the old identity is yours. You make a new one and
  ask each contact, by whatever human means you share, to replace the old
  one with it. Their software then stops trusting the old identity and
  offers to copy your shared spaces' contents into new spaces with you.
  This is slow and manual by design: anything faster would also work for a
  thief.
- **A contact asks to be replaced.** This is exactly what a scammer would
  ask, so the software slows the person down. Before replacing anyone it
  says, in substance: "Only do this if you have confirmed it is really
  them, in person or by voice. Scammers pretend to be friends who lost
  their account." It shows when the old identity was frozen, and why, and
  never offers to replace a contact whose old identity is still in good
  standing.
- **Starting fresh.** A space whose history has grown too long, or a
  friendship that has gone wrong, is succeeded by a new space. What should
  carry over does; the old one can be archived or dropped.
- **Running out of copies.** "Your photos are only on this laptop" is a
  warning the software can give, because the person's devices check where
  the copies are ([blobs.md](spec/blobs.md#counting-copies)). Fixing it is
  one button: add a friend's always-on device, or your own.

## Trust is visible

- Contacts are shown by the names **you** gave them.
- A suggested name from someone not in your contacts is visibly marked as
  unverified.
- An introduction always says who introduced.
- An identity whose keys are in dispute is shown as disputed until it is
  resolved.
- An application asking for access to a space says which space and what it
  will be able to do, in a sentence.

## Measures

These are the targets to test against:

| Measure | Target |
|---|---|
| install to first synced file on a second device | under 5 minutes |
| an edit on one device visible on another on the same LAN | under 1 second |
| ... over the internet, both online | under 2 seconds |
| time for a call to connect, both online | under 2 seconds |
| background sync's effect on a concurrent call | none audible |
| a person told something irreversible happened without being asked first | never |
