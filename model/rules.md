# Authority rules

Status: draft. **Normative.** These rules define which identity entries and
which space entries are valid, which keys and memberships are in effect, and
when an identity is frozen. [identity.md](../spec/identity.md) and
[spaces.md](../spec/spaces.md) explain them in prose; where the prose and
these rules disagree, these rules win.

They are written as a small logic program, so that two properties can be
checked by machine instead of argued:

- **A unique answer.** The program is *stratified*: it is divided into
  layers, each layer only adds facts, and a rule may say "not" only about
  facts from an earlier layer. A stratified program has exactly one result
  for any set of entries, whatever order they arrived in. The checker in
  [check.py](check.py) verifies this for the rules below.
- **No hidden clock.** The inputs are facts about entries and nothing else.
  No input depends on when or in what order a device received anything.

## Notation

A rule `head :- a, b, not c.` means: `head` holds whenever `a` and `b` hold
and `c` does not. Names starting with a capital letter are variables.
`count{G : p(G), q(G)} >= T` counts the distinct `G` for which the listed
facts hold. `X != Y` and `P < 3` compare values. `%` starts a comment.

`@input` lists the facts computed directly from entries (defined in the
tables below). `@stratum` starts a layer. A predicate is defined in exactly
one layer. Positive uses may refer to the same or earlier layers; `not` and
`count` only to earlier ones.

The reference implementation is [datalog.py](datalog.py) (about 300 lines)
and the inputs are computed by [world.py](world.py).

## Identity logs

### Inputs

All facts are about the entries of one identity log, except `confirm_ok`,
which comes from guardians' logs.

| Fact | Meaning |
|---|---|
| `entry(E)`, `genesis(E)` | E is an entry of the log; E is its genesis |
| `anc(A,B)`, `ae(A,B)` | A is an ancestor of B; A is B or an ancestor of B |
| `conc(A,B)` | A and B are concurrent |
| `later(A,B)` | B comes after A in log order |
| `signer(E,K)` | E is signed by key K |
| `add(E,K,P)` | E contains `add_key` of K with power P (1 device, 2 admin, 3 root) |
| `rem(E,K)` | E contains `remove_key` of K |
| `selfrep(E,R,N)`, `is_selfrep(E)` | E is a root replacement: signed by R, its ops are exactly `add_key` of root N and `remove_key` of R |
| `badops(E,P)` | E contains an op that a key of power P may not perform ([table](../spec/identity.md#operations)) |
| `policy(E)` | E carries `set_recovery` |
| `change(D,P)` | D is a `set_recovery` after genesis, naming P as the policy it changes |
| `guardian(P,G)`, `threshold(P,T)`, `unguarded(P)` | the guardians and threshold of policy P; P names no guardians |
| `recover(D,N,P)`, `keeps(D,K)` | D is a `recover` naming new root N under policy P; it keeps key K |
| `confirm_ok(G,D)` | guardian G has a valid confirmation of decision D (below) |
| `sek(E)` | E contains `set_encryption_key` |

**Confirmations.** A confirmation is an entry in the *guardian's own*
identity log. `confirm_ok(G,D)` holds if some entry `C` of G's log names
`D`, and `C` is valid and G is not frozen when G's log is evaluated over
`C`'s causal past. That past is strictly smaller than the set being
evaluated, so this recursion always ends, even when two people guard each
other. A confirmation is judged as of when it was made, and nothing later
in the guardian's log changes it: not a removal of the confirming key, and
not the guardian being frozen. Votes are counted per guardian, not per key.

### Rules

```datalog
@program identity

@input entry/1 genesis/1 anc/2 ae/2 conc/2 later/2 signer/2
@input add/3 rem/2 selfrep/3 is_selfrep/1 badops/2
@input policy/1 change/2 guardian/2 threshold/2 unguarded/1
@input recover/3 keeps/2 confirm_ok/2 sek/1

% ---- Layer 1: shapes. Facts read straight off the entries.
@stratum shape
power(K,P) :- add(E,K,P).
power(N,3) :- recover(D,N,P).
keyof(K) :- power(K,P).
under(D,P) :- change(D,P).
under(D,P) :- recover(D,N,P).
kept_key(D,K) :- keeps(D,K), power(K,P), P < 3.
replaced0(R,X) :- selfrep(Y,R,N), anc(Y,X).
root_add_entry(R,G) :- genesis(G), add(G,R,3).
root_add_entry(N,Y) :- selfrep(Y,R,N).
root_add_entry(N,D) :- recover(D,N,P).

% ---- Layer 2: votes. Who signed what, and how many guardians agreed.
@stratum votes
votes(D) :- under(D,P), threshold(P,T), not unguarded(P),
            count{G : guardian(P,G), confirm_ok(G,D)} >= T.
% roots as they stand before anything is revoked, for judging who may
% change a policy that has no guardians
root0(R,X) :- genesis(G), add(G,R,3), anc(G,X).
root0(N,X) :- selfrep(Y,R,N), root0(R,Y), anc(Y,X).
root0(N,X) :- recover(D,N,P), votes(D), anc(D,X).
prerep(Y) :- selfrep(Y,R,N), root0(R,Y), not replaced0(R,Y).
signer_ok(D) :- recover(D,N,P), signer(D,N).
signer_ok(D) :- change(D,P), not unguarded(P), signer(D,K), keyof(K).
signer_ok(D) :- change(D,P), unguarded(P), signer(D,R), root0(R,D), not replaced0(R,D).
approved(D) :- votes(D).
approved(D) :- change(D,P), unguarded(P).

% ---- Layer 3: guardian decisions in effect.
@stratum decisions
live(P) :- genesis(P), policy(P).
live(D) :- change(D,P), in_effect(D).
in_effect(D) :- under(D,P), live(P), anc(P,D), signer_ok(D), approved(D).
replaced_policy(P) :- change(S,P), in_effect(S).

% ---- Layer 4: what recoveries remove.
@stratum recovery
rec_removes(D,K) :- in_effect(D), recover(D,N,P), add(E,K,Q), ae(E,D), K != N,
                    not kept_key(D,K).
rec_removes(D,K) :- in_effect(D), recover(D,N,P), recover(D0,K,P0), in_effect(D0),
                    anc(D0,D), K != N.
kept_over(Y,K) :- rem(Y,K), kept_key(D,K), in_effect(D), ae(Y,D).
% a recovery keeps keys, not work done without knowledge of it
rec_conc(X) :- in_effect(D), recover(D,N,P), conc(X,D).
gone3(R,X) :- replaced0(R,X).
gone3(K,X) :- rec_removes(D,K), anc(D,X).
revoked3(X) :- signer(X,K), rec_removes(D,K), not ae(X,D).
revoked3(X) :- rec_conc(X).
revoked3(X) :- signer(X,R), selfrep(Y,R,N), Y != X, not ae(X,Y), not is_selfrep(X).

% ---- Layer 5: roots.
@stratum roots
root_in(R,X) :- genesis(G), add(G,R,3), anc(G,X).
root_in(N,X) :- selfrep(Y,R,N), valid3(Y), anc(Y,X).
root_in(N,X) :- recover(D,N,P), in_effect(D), anc(D,X).
valid3(G) :- genesis(G).
valid3(X) :- signer(X,R), power(R,3), root_in(R,X), not gone3(R,X), not revoked3(X),
             not badops(X,3).
root_added(R) :- genesis(G), add(G,R,3).
root_added(N) :- selfrep(Y,R,N), valid3(Y).
root_added(N) :- recover(D,N,P), in_effect(D).
root_removed(R) :- selfrep(Y,R,N), valid3(Y).
root_removed(K) :- rec_removes(D,K), power(K,3).

% ---- Layer 6: contests. More than one root is in effect.
@stratum contest
root_eff(R) :- root_added(R), not root_removed(R).
contested :- root_eff(R1), root_eff(R2), R1 != R2.
% while contested, the contestants' ops other than root replacements wait
suspended(X) :- contested, signer(X,R), root_eff(R), not is_selfrep(X).
after_fork(E) :- sek(E), contested, root_eff(R), root_add_entry(R,Y), not ae(E,Y).

% ---- Layer 7: root ops in effect, and admin removals.
@stratum rootops
rop(X) :- valid3(X), not suspended(X).
adm_rm(K,Y) :- rem(Y,K), power(K,2), rop(Y), not kept_over(Y,K).
adm_rm(K,D) :- rec_removes(D,K), power(K,2).
gone2(K,X) :- adm_rm(K,Y), anc(Y,X).
revoked2(X) :- signer(X,K), adm_rm(K,Y), not ae(X,Y).
revoked2(X) :- rec_conc(X).

% ---- Layer 8: admins.
@stratum admins
adm_in(K,X) :- add(E,K,2), rop(E), anc(E,X).
adm_in(K,X) :- add(E,K,2), valid2(E), anc(E,X).
adm_in(K,X) :- kept_key(D,K), in_effect(D), power(K,2), anc(D,X).
valid2(X) :- signer(X,K), power(K,2), adm_in(K,X), not gone2(K,X), not revoked2(X),
             not badops(X,2).

% ---- Layer 9: device removals.
@stratum device_removals
dev_rm(K,Y) :- rem(Y,K), power(K,1), rop(Y), not kept_over(Y,K).
dev_rm(K,Y) :- rem(Y,K), power(K,1), valid2(Y), not kept_over(Y,K).
dev_rm(K,D) :- rec_removes(D,K), power(K,1).
gone1(K,X) :- dev_rm(K,Y), anc(Y,X).
revoked1(X) :- signer(X,K), dev_rm(K,Y), not ae(X,Y).
revoked1(X) :- rec_conc(X).

% ---- Layer 10: devices.
@stratum devices
dev_in(K,X) :- add(E,K,1), rop(E), anc(E,X).
dev_in(K,X) :- add(E,K,1), valid2(E), anc(E,X).
dev_in(K,X) :- kept_key(D,K), in_effect(D), power(K,1), anc(D,X).
valid1(X) :- signer(X,K), power(K,1), dev_in(K,X), not gone1(K,X), not revoked1(X),
             not badops(X,1).

% ---- Layer 11: keys, policies, freezing.
@stratum keys
valid(X) :- rop(X).
valid(X) :- valid2(X).
valid(X) :- valid1(X).
key_added(K,E) :- add(E,K,P), P < 3, rop(E).
key_added(K,E) :- add(E,K,P), P < 3, valid2(E).
key_added(K,D) :- kept_key(D,K), in_effect(D).
removal(K,Y) :- adm_rm(K,Y).
removal(K,Y) :- dev_rm(K,Y).
removed(K) :- removal(K,Y).
removed_at(K,H) :- removal(K,Y), ae(Y,H).
current_policy(P) :- live(P), not replaced_policy(P).
fork(Y1,Y2) :- prerep(Y1), prerep(Y2), selfrep(Y1,R,N1), selfrep(Y2,R,N2), conc(Y1,Y2).
% F1: two decisions under one policy, neither knowing the other, or one made
% after the policy was already changed
frozen :- in_effect(D1), in_effect(D2), under(D1,P), under(D2,P), conc(D1,D2).
frozen :- in_effect(S), change(S,P), in_effect(D), under(D,P), anc(S,D).
% F2: a contest with no guardians to settle it
frozen :- contested, current_policy(P), unguarded(P).
% F3: guardians named, without guardians, by a side of a root fork
frozen :- fork(Y1,Y2), in_effect(S), change(S,P), unguarded(P), not ae(S,Y1), not ae(S,Y2).
sek_ok(E) :- sek(E), valid(E), not after_fork(E).
newer_key(E) :- sek_ok(E), sek_ok(E2), later(E,E2).

% ---- Layer 12: results.
@stratum outcome
effective(K) :- key_added(K,E), not removed(K).
effective_at(K,H) :- key_added(K,E), ae(E,H), not removed_at(K,H).
current_key(E) :- sek_ok(E), not newer_key(E).
```

### Reading the rules

- **Layers follow authority.** Guardians' decisions (layers 2–3) depend only
  on guardians' confirmations and on the shape of entries. Roots (5) depend on
  decisions. Admins (8) depend on roots. Devices (10) depend on admins. A
  key's entries are invalidated only by a removal from a strictly higher
  layer, so nothing can loop.
- **Revocation** (`revoked1`–`revoked3`): an entry by a removed key is valid
  only if it is an ancestor of the removal. Entries descending from the
  removal fail authorization (`gone`). Backdating gains nothing.
- **Recoveries** remove every key added in their causal past that they do
  not keep, and every earlier recovery's root. Every entry concurrent with a
  recovery in effect is invalid, whoever signed it: a recovery keeps keys,
  not work done without knowledge of it. A kept key's earlier removal,
  in the recovery's past, no longer counts (`kept_over`). Later removals
  apply normally.
- **Contests** (`contested`): two roots in effect at once, which only
  concurrent root replacements can cause. The contestants' other ops wait
  (`suspended`), and so does the encryption key (`after_fork`). Guardians
  end a contest by recovery.
- **Decisions only accumulate.** Whether a decision is in effect never
  depends on the absence of anything, so a decision in effect stays in
  effect as entries arrive. Confirmations can arrive in any order, so a rule
  that ignored a decision because of a change approved later would undo it.
  A decision made under a policy that had already been changed is therefore
  evidence of misbehaving guardians, and freezes the identity.
- **Freezing** (`frozen`) is evidence that no rule can settle. It is
  monotone: adding entries never unfreezes an identity (the fuzzer checks
  this).

## Spaces

### Inputs

Facts about the entries of one space, plus the evaluated identity logs of
its authors.

| Fact | Meaning |
|---|---|
| `s_entry(X)`, `s_genesis(X)`, `s_anc`, `s_ae`, `s_conc` | as for identity logs |
| `author(X,A)`, `skey(X,K)`, `cites(X,H)` | X's author identity, signing key, and cited head of the author's log |
| `mem(X,I)` | X names membership I as its author's ([spaces.md](../spec/spaces.md#memberships)) |
| `incarnation(I,M,R)`, `inc_from(I,E)` | membership I is identity M with role R (0 reader … 3 owner), created by entry E |
| `adds(X,I)` | X creates membership I (genesis creates its author's, as owner) |
| `s_rem(X,I)` | X ends membership I |
| `replaces(Y,I,J)` | Y ends I and creates J for the same identity with a lower role |
| `s_succeed(X)` | X contains `succeed` |
| `s_keep(X,K,E)` | X contains `keep` for key K, listing entry E |
| `s_badops(X,R)` | X contains an op that role R may not perform |
| `id_effective_at(A,K,H)`, `id_removed(A,K)`, `id_removed_at(A,K,H)`, `id_frozen(A)` | `effective_at`, `removed`, `removed_at`, `frozen` from A's identity log |

### Rules

```datalog
@program space

@input s_entry/1 s_genesis/1 s_anc/2 s_ae/2 s_conc/2
@input author/2 skey/2 cites/2 mem/2
@input incarnation/3 inc_from/2 adds/2 s_rem/2 replaces/3 s_succeed/1 s_keep/3 s_badops/2
@input id_effective_at/3 id_removed/2 id_removed_at/3 id_frozen/1

% ---- Layer 1: authors. Depends only on identity logs, never on membership.
@stratum authors
attrib(X) :- author(X,A), skey(X,K), cites(X,H), id_effective_at(A,K,H), not id_frozen(A).
author_ok(X) :- attrib(X), author(X,A), skey(X,K), not id_removed(A,K).
author_ok(X) :- attrib(X), witnessed(X).
witnessed(X) :- author(X,A), skey(X,K), s_anc(X,W), author(W,A), skey(W,K2), K2 != K,
                author_ok(W), cites(W,H), not id_removed_at(A,K,H).
witnessed(X) :- author(X,A), skey(X,K), s_keep(W,K,E), s_ae(X,E), author(W,A), author_ok(W).
leave(Y,I) :- s_rem(Y,I), mem(Y,I), author_ok(Y).
leave(Y,I) :- s_succeed(Y), mem(Y,I), author_ok(Y).
left_before(I,X) :- leave(Y,I), s_anc(Y,X).
left_conc(I,X) :- leave(Y,I), s_conc(Y,X).
lowered(Y,I,X) :- replaces(Y,I,J), incarnation(J,M,R), s_entry(X), not s_badops(X,R).

% ---- Layer 2: owners. Nobody can remove an owner; owners can only leave.
@stratum owners
inc_ok3(I) :- s_genesis(G), adds(G,I), incarnation(I,A,3).
inc_ok3(I) :- adds(X,I), incarnation(I,M,3), v3(X).
v3(X) :- mem(X,I), incarnation(I,A,3), author(X,A), inc_ok3(I), inc_from(I,E), s_ae(E,X),
         author_ok(X), not left_before(I,X), not left_conc(I,X), not s_badops(X,3).

@stratum owner_facts
owner_live(X) :- inc_ok3(I), inc_from(I,E), s_ae(E,X), s_entry(X), not left_before(I,X).
closing(Y) :- s_succeed(Y), v3(Y).

% ---- Layer 3: admins, removed only by owners or by leaving.
@stratum admin_removals
closed(X) :- closing(Y), s_anc(Y,X), not owner_live(X).
rm2(I,Y) :- s_rem(Y,I), incarnation(I,M,2), v3(Y).
rm2(I,Y) :- leave(Y,I), incarnation(I,M,2).
gone2(I,X) :- rm2(I,Y), s_anc(Y,X).
clash2(I,X) :- rm2(I,Y), s_conc(Y,X), not lowered(Y,I,X).

@stratum admins
inc_ok2(I) :- adds(X,I), incarnation(I,M,2), v3(X).
inc_ok2(I) :- adds(X,I), incarnation(I,M,2), v2(X).
v2(X) :- mem(X,I), incarnation(I,A,2), author(X,A), inc_ok2(I), inc_from(I,E), s_anc(E,X),
         author_ok(X), not gone2(I,X), not clash2(I,X), not closed(X), not s_badops(X,2).

% ---- Layer 4: writers, removed by owners, admins, or by leaving.
@stratum writer_removals
rm1(I,Y) :- s_rem(Y,I), incarnation(I,M,1), v3(Y).
rm1(I,Y) :- s_rem(Y,I), incarnation(I,M,1), v2(Y).
rm1(I,Y) :- leave(Y,I), incarnation(I,M,1).
gone1(I,X) :- rm1(I,Y), s_anc(Y,X).
clash1(I,X) :- rm1(I,Y), s_conc(Y,X), not lowered(Y,I,X).

@stratum writers
inc_ok1(I) :- adds(X,I), incarnation(I,M,1), v3(X).
inc_ok1(I) :- adds(X,I), incarnation(I,M,1), v2(X).
v1(X) :- mem(X,I), incarnation(I,A,1), author(X,A), inc_ok1(I), inc_from(I,E), s_anc(E,X),
         author_ok(X), not gone1(I,X), not clash1(I,X), not closed(X), not s_badops(X,1).

% ---- Layer 5: readers.
@stratum reader_removals
rm0(I,Y) :- s_rem(Y,I), incarnation(I,M,0), v3(Y).
rm0(I,Y) :- s_rem(Y,I), incarnation(I,M,0), v2(Y).
rm0(I,Y) :- leave(Y,I), incarnation(I,M,0).
gone0(I,X) :- rm0(I,Y), s_anc(Y,X).
clash0(I,X) :- rm0(I,Y), s_conc(Y,X), not lowered(Y,I,X).
ended(I) :- leave(Y,I).
ended(I) :- rm2(I,Y).
ended(I) :- rm1(I,Y).
ended(I) :- rm0(I,Y).

@stratum readers
inc_ok0(I) :- adds(X,I), incarnation(I,M,0), v3(X).
inc_ok0(I) :- adds(X,I), incarnation(I,M,0), v2(X).
v0(X) :- mem(X,I), incarnation(I,A,0), author(X,A), inc_ok0(I), inc_from(I,E), s_anc(E,X),
         author_ok(X), not gone0(I,X), not clash0(I,X), not closed(X), not s_badops(X,0).

% ---- Layer 6: results.
@stratum outcome
valid(X) :- v3(X).
valid(X) :- v2(X).
valid(X) :- v1(X).
valid(X) :- v0(X).
member(I) :- inc_ok3(I), not ended(I).
member(I) :- inc_ok2(I), not ended(I).
member(I) :- inc_ok1(I), not ended(I).
member(I) :- inc_ok0(I), not ended(I).
```

### Reading the rules

- **Authors first.** Whether a signature counts (`author_ok`) depends only on
  the author's identity log: the key was in effect at the cited head, and
  either it is still in effect or the entry is witnessed by another of the
  author's keys, or listed in a `keep`. Membership never enters into it, so
  witnessing cannot loop through membership.
- **Memberships, not identities, hold roles.** Each `add_member` creates a
  membership with a fixed role, and each entry names the membership it
  writes under. Changing a role ends one membership and creates another in
  the same entry (`replaces`). Adding someone who is already a member creates
  a second membership and changes nothing about the first.
- **Layers follow roles.** An entry under a membership is invalidated only by
  an end of that membership written by a strictly higher role, or by the
  member leaving. Entries concurrent with the end are invalid, unless the end
  was a lowering of role and the entry was allowed under the new role
  (`lowered`). Entries descending from the end fail authorization.
- **Closing.** After an owner's `succeed`, entries whose past has no owner
  left are invalid.
