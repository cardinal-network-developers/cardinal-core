"""Random histories, checked against properties the rules must keep
whatever happens.

    python3 model/fuzz.py [identity-cases] [space-cases] [seed] [web-cases] [honest-cases]
    python3 model/fuzz.py --digest [cases] [seed]

Identity histories mix honest work with a thief who steals the phrase or a
device and writes with old parents, guardians who confirm late, twice, from
stolen devices, or under replaced policies, recoveries under any policy,
keys added twice at different powers, thresholds that are not a majority,
decisions with extra ops, and policies without guardians and their
controllers.
Honest identity histories have an owner whose devices may be partitioned
from each other, guardians whose software follows the chain rule
(world.may_confirm) with partial views of each other's confirmations, and
thieves who steal devices, admins, or the phrase and write anything.
Guardian webs are worlds of identities that guard each other (a pair with a
third guardian, a three-cycle, a mesh of four), where any of them may be
stolen from, contested, recovering or frozen while it confirms another's
decisions, and thieves confirm with stolen or freshly minted keys on old
branches of a guardian's log.
Space histories have an honest owner whose keys are never stolen, members
adding, removing, lowering, leaving and succeeding, thieves holding other
members' keys who write under any membership with old parents (ending
others' memberships, succeeding, adding), a stranger who was never a
member, devices removed in identity logs, keep ops, and a frozen member.

Properties checked:

  D  determinism: the result is the same however the entries are ordered,
     and under different Python hash seeds (run in subprocesses);
  M  monotone: for a causally closed subset S1 of S, if S1 is frozen so is
     S, and a decision in effect in S1 is in effect in S or S is frozen; in
     spaces, an entry whose signature counts in S1 counts in S;
  R  recovery: if S is not frozen, every key in effect was kept by the
     latest recovery or added after it, and every root descends from it;
  B  backdating: no valid entry by a removed key is outside the removal's
     causal past; no valid space entry descends from the end of its
     membership;
  A  authors: every valid space entry has an author whose key counted;
  H  honest guardians: guardians following the chain rule, with an honest
     owner, never cause a freeze, whatever thieves do;
  O  honest owner: an owner whose keys are not stolen keeps its membership
     and every entry it wrote, in the whole and in every closed subset;
  P  power: every removal in effect goes strictly down in power, except a
     root replacing itself and a recovery;
  K  a key removed by a recovery gains nothing: every valid entry it signed
     is in the recovery's causal past, and no decision it signed descending
     from the recovery is in effect;
  E  equal or lower: removing every space entry by one identity never makes
     valid an entry under a membership of equal or higher role than any it
     held, and a non-member's entries never matter at all;
  F  freezing keeps what others built on: every entry by an author who is
     not frozen that is valid when no one is treated as frozen is valid.

For guardian webs, D also covers the order in which identities are
evaluated, and every evaluation must terminate without the same evaluation
recurring.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datalog import check  # noqa: E402
from world import (Builder, Entry, World, PROGRAMS, ancestry, evaluate_identity,  # noqa: E402
                   evaluate_space, may_confirm)


class Failure(Exception):
    pass


def need(cond, prop, msg):
    if not cond:
        raise Failure(f"{prop}: {msg}")


def reorder(world, rng):
    """The same entries, inserted in a different random order."""
    w = World()
    left = list(world.entries.values())
    rng.shuffle(left)
    while left:
        for e in left:
            if all(p in w.entries for p in e.parents + world.refs(e)):
                w.put(e, world._kind[e.log])
                left.remove(e)
                break
    return w


def closed_subset(world, rng, must):
    pick = [x for x in world.entries if rng.random() < 0.5]
    return world.closure(pick + must)


def anc_of(world, log):
    return ancestry({x: e for x, e in world.entries.items() if e.log == log})


# ------------------------------------------------------------ identity

def identity_history(rng):
    b = Builder()
    gs = ("G1", "G2", "G3")
    for g in gs:
        b.identity(g, "r" + g, admin="a" + g, devices=("d" + g,))
    guarded = rng.random() < 0.7
    b.identity("I", "R0", admin="A0", devices=("D0",),
               guardians=gs if guarded else (), threshold=2 if guarded else 0)
    owner = {"root": "R0", "admin": "A0", "devices": ["D0"]}
    thief = set()
    thief_entries = set()
    n = [0]

    def nid(p):
        n[0] += 1
        return f"{p}{n[0]:03d}"

    def ilog():
        return [x for x, e in b.w.entries.items() if e.log == "I"]

    def honest_parents():
        view = [x for x in ilog() if x not in thief_entries]
        return b.heads("I", within=b.w.closure(view))

    def old_parents():
        return [rng.choice(ilog())]

    def decisions():
        return [x for x in ilog() if any(op[0] in ("recover", "policy") for op in b.w.entries[x].ops)
                and b.w.entries[x].parents]

    def policies():
        return [x for x in ilog() if any(op[0] == "policy" for op in b.w.entries[x].ops)]

    if guarded and rng.random() < 0.2:
        # the old phrase is stolen; guardians recover; later the guardians
        # agree to drop themselves, and the thief, holding the removed root,
        # acts on the policy without guardians
        thief.add("R0")
        rec = b.write("I", nid("r"), "N0", [("recover", "N0", ("A0",), "I")], ["I"])
        for g in gs[:2]:
            b.write(g, nid("c"), "a" + g, [("confirm", rec)])
        owner["root"] = "N0"
        op = ("policy", "I", (), 0) + (("N0",) if rng.random() < 0.7 else ())
        drop = b.write("I", nid("s"), "N0", [op])
        for g in gs[:2]:
            b.write(g, nid("c"), "a" + g, [("confirm", drop)])
        x = b.write("I", nid("t"), "R0", [("policy", drop, gs, 2)],
                    rng.choice([[drop], b.heads("I")]))
        thief_entries.add(x)

    for _ in range(rng.randint(6, 20)):
        a = rng.random()
        if a < 0.08:                                   # owner adds a device
            if rng.random() < 0.15:                    # or names a key a second time
                k = rng.choice(owner["devices"] + [owner["admin"]])
                b.write("I", nid("e"), owner["root"] if rng.random() < 0.5 else owner["admin"],
                        [("add", k, rng.choice([1, 2]))],
                        honest_parents() if rng.random() < 0.6 else old_parents())
                continue
            d = nid("D")
            owner["devices"].append(d)
            b.write("I", nid("e"), owner["admin"], [("add", d, 1)], honest_parents())
        elif a < 0.14:                                 # owner removes a device
            d = rng.choice(owner["devices"])
            b.write("I", nid("e"), owner["admin"], [("rem", d)], honest_parents())
        elif a < 0.20:                                 # owner replaces the root
            r = nid("R")
            b.write("I", nid("e"), owner["root"], [("add", r, 3), ("rem", owner["root"])],
                    honest_parents())
            owner["root"] = r
        elif a < 0.26:                                 # owner changes guardians
            pol = rng.choice(policies())
            new = tuple(rng.sample(gs, rng.randint(0, 3)))
            t = len(new) // 2 + 1 if new else 0
            if new and rng.random() < 0.15:            # a threshold that is no majority
                t = rng.choice([0, len(new) // 2, len(new) + 1])
            op = ("policy", pol, new, t)
            if not new and rng.random() < 0.8:         # names the root that controls it
                op += (owner["root"],)
            b.write("I", nid("s"), owner["root"] if rng.random() < 0.5 else owner["admin"],
                    [op], honest_parents())
        elif a < 0.29:                                 # something is stolen
            thief.add(rng.choice(["R0", "R0", owner["root"], owner["admin"],
                                  rng.choice(owner["devices"])]))
        elif a < 0.32:                                 # an admin removes an admin
            if "A1" not in owner["devices"] and rng.random() < 0.5:
                b.write("I", nid("e"), owner["admin"], [("add", "A1", 2)], honest_parents())
                owner["devices"].append("A1")
            else:
                k = rng.choice(sorted(thief | {owner["admin"]}))
                b.write("I", nid("t"), k, [("rem", rng.choice(["A0", "A1"]))],
                        old_parents() if rng.random() < 0.5 else b.heads("I"))
        elif a < 0.52 and thief:                       # the thief writes, backdated
            k = rng.choice(sorted(thief))
            x = nid("t")
            kind = rng.random()
            if kind < 0.35 or k.startswith(("R", "T")) and kind < 0.6:
                r = nid("T")
                thief.add(r)
                ops = [("add", r, 3), ("rem", k)]
            elif kind < 0.5:
                ops = [("rem", rng.choice([owner["admin"]] + owner["devices"]))]
            elif kind < 0.7:
                t = nid("K")
                thief.add(t)
                ops = [("add", t, rng.choice([1, 2]))]
            elif kind < 0.78:
                pol = rng.choice(policies())
                ops = [("policy", pol, ("X1", "X2", "X3"), 2)]
            elif kind < 0.85:                          # drop guardians, controlling it
                pol = rng.choice(policies())
                ops = [("policy", pol, (), 0, k)]
            elif kind < 0.92:                          # name a key again, at another power
                ops = [("add", rng.choice([owner["admin"]] + owner["devices"] + sorted(thief)),
                        rng.choice([1, 2]))]
            else:
                ops = [("sek",)]
            b.write("I", x, k, ops, old_parents() if rng.random() < 0.7 else b.heads("I"))
            thief_entries.add(x)
        elif a < 0.64:                                 # someone starts a recovery
            nroot = nid("N")
            keep = tuple(k for k in [owner["admin"]] + owner["devices"] if rng.random() < 0.5)
            pol = rng.choice(policies())
            par = honest_parents() if rng.random() < 0.7 else old_parents()
            ops = [("recover", nroot, keep, pol)]
            if rng.random() < 0.1:                     # a decision with company
                ops.append(rng.choice([("add", nid("K"), 1), ("recover", nid("N"), (), pol)]))
            b.write("I", nid("r"), nroot, ops, par)
            if rng.random() < 0.6:
                owner["root"] = nroot
        elif a < 0.92 and decisions():                 # a guardian confirms
            g = rng.choice(gs)
            ds = decisions()
            d = rng.choice(ds[-3:] if rng.random() < 0.7 else ds)
            signer = rng.choice(["a" + g, "d" + g])
            glog = [x for x, e in b.w.entries.items() if e.log == g]
            par = b.heads(g) if rng.random() < 0.7 else [rng.choice(glog)]
            b.write(g, nid("c"), signer, [("confirm", d)], par)
        elif a < 0.96:                                 # a guardian loses a device
            g = rng.choice(gs)
            b.write(g, nid("g"), "a" + g, [("rem", "d" + g)])
        else:
            b.write("I", nid("k"), owner["admin"], [("sek",)], honest_parents())
    return b


def identity_props(w, ident, r, stats):
    """R and B for one identity, given its result r over the whole world."""
    anc = anc_of(w, ident)

    def ae(x, y):
        return x == y or x in anc[y]

    # R
    recs = [d for (d,) in r["in_effect"] if any(op[0] == "recover" for op in w.entries[d].ops)]
    if recs and not r["frozen"]:
        last = [d for d in recs if all(ae(o, d) for o in recs)]
        need(len(last) == 1, "R", f"recoveries in effect do not form a chain: {recs}")
        d = last[0]
        rop = next(op for op in w.entries[d].ops if op[0] == "recover")
        for (k,) in r["effective"]:
            added_after = any(ae(d, e) for (kk, e) in r["key_added"] if kk == k)
            need(k in rop[2] or added_after, "R", f"{k} in effect but neither kept nor added after {d}")
        for (root,) in r["root_eff"]:
            ok = root == rop[1] or any(
                ae(d, y) and any(op[0] == "add" and op[1] == root for op in w.entries[y].ops)
                for y in anc)
            need(ok, "R", f"root {root} does not descend from recovery {d}")
        stats["recovered"] += 1

    # P: removals in effect go strictly down
    kpow = dict(r["kpow"])
    rec_entries = {x for x, e in w.entries.items()
                   if e.log == ident and any(op[0] == "recover" for op in e.ops)}
    for (k, y) in r["removal"]:
        if y in rec_entries:
            continue
        s = w.entries[y].signer
        need(kpow.get(s, 0) > kpow.get(k, 9), "P",
             f"{y} by {s} (power {kpow.get(s)}) removes {k} (power {kpow.get(k)})")
    for (x,) in r["valid"]:
        e = w.entries[x]
        for op in e.ops:
            if op[0] == "rem" and op[1] != e.signer and op[1] in kpow:
                need(kpow.get(e.signer, 0) > kpow[op[1]], "P",
                     f"valid {x} by {e.signer} removes {op[1]} of equal or higher power")

    # K: a key removed by a recovery gains nothing
    applied = {d for (d,) in r["applied"]}
    for (d, k) in r["rec_removes"]:
        if d not in applied:
            continue
        for (x,) in r["valid"]:
            if w.entries[x].signer == k:
                need(ae(x, d), "K", f"{x} by {k}, removed by {d}, is valid outside its past")
        if not r["frozen"]:
            # a change under a policy with guardians is only proposed by its
            # signer; the guardians decide it. Any other decision counts.
            guarded = {x for (x,) in r["in_effect"] if any(
                op[0] == "policy" and op[1] is not None and w.entries[op[1]].ops and any(
                    o[0] == "policy" and o[2] for o in w.entries[op[1]].ops)
                for op in w.entries[x].ops)}
            for (x,) in r["in_effect"]:
                if w.entries[x].signer == k and ae(d, x) and x != d and x not in guarded:
                    need(False, "K", f"decision {x} by {k}, removed by {d}, is in effect")

    # B
    removals = {}
    for (k, h) in r["removed_at"]:
        removals.setdefault(k, set()).add(h)
    for (x,) in r["valid"]:
        k = w.entries[x].signer
        if k in removals:
            # removed_at(K,H) holds for every H at or after a removal; the
            # entry must not be one of them
            need(x not in removals[k], "B", f"{x} by {k} is valid after {k}'s removal")


def check_identity(b, rng, stats):
    w = b.w
    full = frozenset(w.entries)
    r = evaluate_identity(w, "I", full)

    # D
    w2 = reorder(w, rng)
    r2 = evaluate_identity(w2, "I", frozenset(w2.entries))
    for k in ("valid", "in_effect", "effective", "root_eff", "current_key", "frozen", "contested"):
        need(r[k] == r2[k], "D", f"{k} differs with entry order")

    # M
    for _ in range(2):
        s1 = closed_subset(w, rng, ["I"])
        r1 = evaluate_identity(w, "I", s1)
        need(not r1["frozen"] or r["frozen"], "M", "frozen in a subset but not in the whole")
        for (d,) in r1["in_effect"]:
            need((d,) in r["in_effect"] or r["frozen"], "M", f"{d} in effect in a subset only")
        stats["subsets"] += 1

    identity_props(w, "I", r, stats)

    stats["frozen"] += r["frozen"]
    stats["contested"] += r["contested"]
    stats["entries"] += len(w.entries)


# ------------------------------------------------------------ honest guardians

def honest_identity_history(rng):
    """An honest owner, guardians whose software follows the chain rule, and
    thieves. The owner's devices may not see each other's latest entries, so
    the owner can propose decisions concurrently. Guardians see a random part
    of each other's confirmations, and all of their own."""
    b = Builder()
    n = rng.choice([3, 4, 5])
    gs = tuple(f"G{i}" for i in range(1, n + 1))
    for g in gs:
        b.identity(g, "r" + g, admin="a" + g, devices=("d" + g,))
    b.identity("I", "R0", admin="A0", devices=("D0",), guardians=gs, threshold=n // 2 + 1)
    owner = {"roots": ["R0"], "admin": "A0", "devices": ["D0"]}
    thief, bad, mine = set(), set(), []
    k = [0]

    def nid(p):
        k[0] += 1
        return f"{p}{k[0]:03d}"

    def ilog():
        return [x for x, e in b.w.entries.items() if e.log == "I"]

    def honest(partial=True):
        view = [x for x in ilog() if x not in bad]
        if partial and rng.random() < 0.4:             # a device that is behind
            view = [x for x in view if rng.random() < 0.6]
        return b.w.closure(view + ["I"])

    def parents(within):
        return b.heads("I", within=within)

    def current_root():
        r = b.ident("I", honest(partial=False) | frozenset(
            x for x, e in b.w.entries.items() if e.log != "I"))
        live = [x for (x,) in r["root_eff"] if x in owner["roots"]]
        return rng.choice(sorted(live)) if live else None

    def current_policy(view):
        r = b.ident("I", view | frozenset(x for x, e in b.w.entries.items() if e.log != "I"))
        ps = sorted(p for (p,) in r["current_policy"])
        return rng.choice(ps) if ps else "I"

    for _ in range(rng.randint(8, 24)):
        a = rng.random()
        if a < 0.08:                                   # owner adds a device
            d = nid("D")
            owner["devices"].append(d)
            b.write("I", nid("e"), owner["admin"], [("add", d, 1)], parents(honest()))
        elif a < 0.12:                                 # owner removes a device
            d = rng.choice(owner["devices"])
            b.write("I", nid("e"), owner["admin"], [("rem", d)], parents(honest()))
        elif a < 0.16:                                 # owner replaces the root
            r = current_root()
            if r:
                nr = nid("R")
                b.write("I", nid("e"), r, [("add", nr, 3), ("rem", r)],
                        parents(honest(partial=False)))
                owner["roots"].append(nr)
        elif a < 0.26:                                 # owner proposes new guardians
            view = honest()
            new = tuple(sorted(rng.sample(gs, rng.randint(1, n))))
            x = nid("s")
            b.write("I", x, rng.choice([owner["admin"]] + owner["devices"]),
                    [("policy", current_policy(view), new, len(new) // 2 + 1)], parents(view))
            mine.append(x)
        elif a < 0.38:                                 # owner asks for a recovery
            view = honest()
            pol = current_policy(view)
            if rng.random() < 0.5:
                # leave out changes of that policy that are not yet approved
                r = b.ident("I", view | frozenset(
                    x for x, e in b.w.entries.items() if e.log != "I"))
                approved = {d for (d,) in r["in_effect"]}
                pending = [x for x in view if x not in approved and any(
                    op[0] == "policy" and op[1] == pol for op in b.w.entries[x].ops)]
                anc = anc_of(b.w, "I")
                view = frozenset(x for x in view if not any(
                    p == x or p in anc[x] for p in pending))
            nroot = nid("N")
            keep = tuple(kk for kk in [owner["admin"]] + owner["devices"] if rng.random() < 0.5)
            x = nid("r")
            b.write("I", x, nroot, [("recover", nroot, keep, pol)], parents(view))
            mine.append(x)
            owner["roots"].append(nroot)
        elif a < 0.44:                                 # something is stolen
            thief.add(rng.choice(["R0", owner["admin"], rng.choice(owner["devices"])]
                                 + owner["roots"][-1:]))
        elif a < 0.58 and thief:                       # the thief writes anything
            kk = rng.choice(sorted(thief))
            c = rng.random()
            pol = rng.choice([x for x in ilog() if any(
                op[0] == "policy" for op in b.w.entries[x].ops)])
            if c < 0.25:
                t = nid("T")
                thief.add(t)
                ops = [("add", t, 3), ("rem", kk)]
            elif c < 0.45:
                t = nid("K")
                thief.add(t)
                ops = [("add", t, rng.choice([1, 2]))]
            elif c < 0.6:
                ops = [("rem", rng.choice([owner["admin"]] + owner["devices"]))]
            elif c < 0.75:
                ops = [("policy", pol, gs[:1], 1)]
            elif c < 0.9:
                t = nid("T")
                thief.add(t)
                b.write("I", nid("t"), t, [("recover", t, (), pol)],
                        rng.choice([[rng.choice(ilog())], b.heads("I")]))
                continue
            else:
                ops = [("sek",)]
            x = nid("t")
            b.write("I", x, kk, ops, [rng.choice(ilog())] if rng.random() < 0.7 else b.heads("I"))
            bad.add(x)
        elif mine:                                     # a guardian considers a decision
            g = rng.choice(gs)
            d = rng.choice(mine[-4:] if rng.random() < 0.7 else mine)
            view = b.w.closure([x for x in b.w.entries if rng.random() < 0.6]
                               + [x for x, e in b.w.entries.items() if e.log == g])
            if may_confirm(b.w, view, g, d):
                b.write(g, nid("c"), rng.choice(["a" + g, "d" + g]), [("confirm", d)],
                        b.heads(g))
    return b


def check_honest(b, rng, stats):
    w = b.w
    r = evaluate_identity(w, "I", frozenset(w.entries))
    need(not r["frozen"], "H", "guardians following the chain rule froze the identity")
    w2 = reorder(w, rng)
    r2 = evaluate_identity(w2, "I", frozenset(w2.entries))
    for k in ("valid", "in_effect", "effective", "root_eff", "current_key", "frozen", "contested"):
        need(r[k] == r2[k], "D", f"{k} differs with entry order")
    s1 = closed_subset(w, rng, ["I"])
    r1 = evaluate_identity(w, "I", s1)
    need(not r1["frozen"], "H", "frozen in a subset")
    for (d,) in r1["in_effect"]:
        need((d,) in r["in_effect"], "M", f"{d} in effect in a subset only")
    identity_props(w, "I", r, stats)
    stats["entries"] += len(w.entries)
    stats["decided"] += len(r["in_effect"])
    stats["contested"] += r["contested"]


# ------------------------------------------------------------ guardian webs

TOPOLOGIES = {
    # identity -> its guardians; every one is also an identity in the world
    "pair": {"A": ("B", "G"), "B": ("A", "G"), "G": ()},
    "cycle": {"A": ("B", "C"), "B": ("C", "A"), "C": ("A", "B")},
    "mesh": {"A": ("B", "C", "D"), "B": ("A", "C", "D"),
             "C": ("A", "B", "D"), "D": ("A", "B", "C")},
}


def guardian_web(rng):
    """Identities that guard each other. Each one may be stolen from,
    contested, recovering or frozen while it confirms another's decisions,
    and thieves holding a guardian's keys confirm with old parents, or mint a
    key on an old branch of the guardian's log and confirm with it."""
    b = Builder()
    topo = TOPOLOGIES[rng.choice(sorted(TOPOLOGIES))]
    names = sorted(topo)
    for x in names:
        gs = topo[x]
        b.identity(x, "R" + x, admin="A" + x, devices=("D" + x,),
                   guardians=gs, threshold=len(gs) // 2 + 1 if gs else 0)
    owner = {x: {"root": "R" + x, "admin": "A" + x, "devices": ["D" + x]} for x in names}
    thief = {x: set() for x in names}
    bad = set()                                         # entries a thief wrote
    n = [0]

    def nid(p):
        n[0] += 1
        return f"{p}{n[0]:03d}"

    def log(x):
        return [e for e, v in b.w.entries.items() if v.log == x]

    def honest(x):
        return b.heads(x, within=b.w.closure([e for e in log(x) if e not in bad]))

    def old(x):
        return [rng.choice(log(x))]

    def decisions(x):
        return [e for e in log(x) if b.w.entries[e].parents and any(
            op[0] in ("recover", "policy") for op in b.w.entries[e].ops)]

    def policies(x):
        return [e for e in log(x) if any(op[0] == "policy" for op in b.w.entries[e].ops)]

    def all_decisions():
        return [(x, d) for x in names for d in decisions(x)]

    def confirm_all(x, d):
        for g in topo[x]:
            b.write(g, nid("c"), owner[g]["admin"], [("confirm", d)], b.heads(g))

    # Often, start with one identity already in trouble, so that it confirms
    # others' decisions while frozen, contested or recovered.
    v = rng.choice(names)
    trouble = rng.choice(["none", "frozen", "contested", "recovered"])
    if trouble == "frozen" and topo[v]:                 # its guardians equivocate
        n1, n2 = nid("N"), nid("N")
        d1 = b.write(v, nid("r"), n1, [("recover", n1, (), v)], [v])
        d2 = b.write(v, nid("r"), n2, [("recover", n2, (), v)], [v])
        confirm_all(v, d1)
        confirm_all(v, d2)
        owner[v]["root"] = n1
    elif trouble in ("frozen", "contested"):            # a phrase thief races the owner
        r1, r2 = nid("R"), nid("T")
        b.write(v, nid("e"), "R" + v, [("add", r1, 3), ("rem", "R" + v)], [v])
        e = nid("t")
        b.write(v, e, "R" + v, [("add", r2, 3), ("rem", "R" + v)], [v])
        bad.add(e)
        thief[v].add(r2)
        owner[v]["root"] = r1
    elif trouble == "recovered" and topo[v]:
        n1 = nid("N")
        d1 = b.write(v, nid("r"), n1, [("recover", n1, ("A" + v,), v)], [v])
        confirm_all(v, d1)
        owner[v]["root"] = n1

    for _ in range(rng.randint(10, 30)):
        x = rng.choice(names)
        o = owner[x]
        a = rng.random()
        if a < 0.06:                                    # owner adds a device
            d = nid("D")
            o["devices"].append(d)
            b.write(x, nid("e"), o["admin"], [("add", d, 1)], honest(x))
        elif a < 0.10:                                  # owner removes a device
            b.write(x, nid("e"), o["admin"], [("rem", rng.choice(o["devices"]))], honest(x))
        elif a < 0.14:                                  # owner replaces the root
            r = nid("R")
            b.write(x, nid("e"), o["root"], [("add", r, 3), ("rem", o["root"])], honest(x))
            o["root"] = r
        elif a < 0.18:                                  # owner changes guardians
            others = [y for y in names if y != x]
            new = tuple(rng.sample(others, rng.randint(1, len(others))))
            b.write(x, nid("s"), rng.choice([o["root"], o["admin"]]),
                    [("policy", rng.choice(policies(x)), new, len(new) // 2 + 1)], honest(x))
        elif a < 0.26:                                  # something of x is stolen
            thief[x].add(rng.choice(["R" + x, "R" + x, o["root"], o["admin"],
                                     rng.choice(o["devices"])]))
        elif a < 0.30:                                  # a phrase thief races the owner
            r1, r2 = nid("R"), nid("T")
            b.write(x, nid("e"), o["root"], [("add", r1, 3), ("rem", o["root"])], honest(x))
            e = nid("t")
            b.write(x, e, o["root"], [("add", r2, 3), ("rem", o["root"])], old(x))
            bad.add(e)
            thief[x].add(r2)
            o["root"] = r1
        elif a < 0.40 and thief[x]:                     # the thief writes in x's log
            k = rng.choice(sorted(thief[x]))
            c = rng.random()
            roots = sorted(t for t in thief[x] if t.startswith(("R", "T", "N")))
            if c < 0.4 and roots:
                k = rng.choice(roots)
                r = nid("T")
                thief[x].add(r)
                ops = [("add", r, 3), ("rem", k)]       # root replacement: a contest
            elif c < 0.7:
                t = nid("K")
                thief[x].add(t)
                ops = [("add", t, rng.choice([1, 2]))]  # a key on an old branch
            elif c < 0.85:
                ops = [("rem", rng.choice([o["admin"]] + o["devices"]))]
            else:
                ops = [("sek",)]
            e = nid("t")
            b.write(x, e, k, ops, old(x) if rng.random() < 0.7 else b.heads(x))
            bad.add(e)
        elif a < 0.52:                                  # a recovery of x starts
            nroot = nid("N")
            keep = tuple(k for k in [o["admin"]] + o["devices"] if rng.random() < 0.5)
            par = honest(x) if rng.random() < 0.7 else old(x)
            b.write(x, nid("r"), nroot, [("recover", nroot, keep, rng.choice(policies(x)))], par)
            if rng.random() < 0.6:
                o["root"] = nroot
        elif a < 0.80 and all_decisions():              # x confirms someone's decision
            mine = [(y, d) for (y, d) in all_decisions() if y != x]
            if not mine:
                continue
            y, d = rng.choice(mine[-4:] if rng.random() < 0.7 else mine)
            if thief[x] and rng.random() < 0.4:         # with a stolen key, backdated
                k = rng.choice(sorted(thief[x]))
                b.write(x, nid("c"), k, [("confirm", d)], old(x))
            else:
                p = rng.random()                        # a device that saw only its
                par = (honest(x) if p < 0.4 else          # owner's work, saw
                       b.heads(x) if p < 0.85 else        # everything, or lagged
                       old(x))
                b.write(x, nid("c"), rng.choice([o["admin"]] + o["devices"]),
                        [("confirm", d)], par)
        elif a < 0.88 and thief[x]:                     # mint a key, then confirm with it
            k = rng.choice(sorted(thief[x]))
            t = nid("K")
            e1 = nid("t")
            b.write(x, e1, k, [("add", t, 2)], old(x))
            bad.add(e1)
            if all_decisions():
                ys = [(y, d) for (y, d) in all_decisions() if y != x]
                if ys:
                    y, d = rng.choice(ys)
                    e2 = nid("c")
                    b.write(x, e2, t, [("confirm", d)], [e1])
                    bad.add(e2)
        else:
            b.write(x, nid("k"), o["admin"], [("sek",)], honest(x))
    return b, names


RESULT_KEYS = ("valid", "in_effect", "effective", "root_eff", "current_key", "frozen",
               "contested")


def fresh(world, rng):
    """A reordered copy, so nothing is cached from earlier evaluations."""
    return reorder(world, rng)


def check_guardian_web(b, names, rng, stats):
    import world as W
    w = b.w
    full = frozenset(w.entries)
    res = {x: evaluate_identity(w, x, full) for x in names}

    # D, and independence from the order identities are evaluated: each copy
    # starts with an empty cache and evaluates the identities in a new order
    for _ in range(2):
        w2 = fresh(w, rng)
        order = list(names)
        rng.shuffle(order)
        for x in order:
            r2 = evaluate_identity(w2, x, frozenset(w2.entries))
            for k in RESULT_KEYS:
                need(res[x][k] == r2[k], "D", f"{x}: {k} differs with entry or evaluation order")

    # M
    for _ in range(2):
        s1 = closed_subset(w, rng, list(names))
        for x in names:
            r1 = evaluate_identity(w, x, s1)
            need(not r1["frozen"] or res[x]["frozen"], "M", f"{x} frozen in a subset only")
            for (d,) in r1["in_effect"]:
                need((d,) in res[x]["in_effect"] or res[x]["frozen"], "M",
                     f"{x}: {d} in effect in a subset only")
        stats["subsets"] += 1

    # how often guardians confirmed while in trouble themselves
    for c, e in w.entries.items():
        if any(op[0] == "confirm" for op in e.ops):
            g = evaluate_identity(w, e.log, w.closure([c]))
            stats["conf"] += 1
            stats["conf_frozen"] += g["frozen"]
            stats["conf_contested"] += g["contested"] and not g["frozen"]
            stats["conf_recovering"] += any(
                any(op[0] == "recover" for op in w.entries[d].ops) for (d,) in g["in_effect"])

    # R, B
    for x in names:
        identity_props(w, x, res[x], stats)
        stats["frozen"] += res[x]["frozen"]
        stats["contested"] += res[x]["contested"]
    stats["entries"] += len(w.entries)
    stats["depth"] = max(stats["depth"], W.depth["max"])


# ------------------------------------------------------------ spaces

PEOPLE = ("Ana", "Ben", "Cy", "Dee", "Eve")       # Eve is never added


def space_history(rng):
    """Ana is an honest owner whose keys are never stolen."""
    b = Builder()
    for p in PEOPLE:
        b.identity(p, "r" + p, admin="a" + p, devices=("p" + p, "q" + p))
    if rng.random() < 0.35:                         # Dee becomes frozen, later
        late_freeze = True
    else:
        late_freeze = False
    keys = {p: ["a" + p, "p" + p, "q" + p] for p in PEOPLE}
    stolen = []
    n = [0]
    info = {"ana": ["S"]}

    def nid(p):
        n[0] += 1
        return f"{p}{n[0]:03d}"

    def ilog(p):
        return [x for x, e in b.w.entries.items() if e.log == p]

    def slog():
        return [x for x, e in b.w.entries.items() if e.log == "S"]

    owner = b.space("S", "Ana", "aAna")
    mems = [(owner, "Ana", 3)]
    if late_freeze:                                 # Dee adds people before freezing
        r = rng.choice([2, 3])
        b.swrite("S", "dee", "Ana", "aAna", owner, [("add_member", "Dee", r)])
        mems.append(("dee#0", "Dee", r))
        info["ana"].append("dee")
        b.swrite("S", "deeadd", "Dee", "pDee", "dee#0", [("add_member", "Cy", 1)])
        mems.append(("deeadd#0", "Cy", 1))
        if rng.random() < 0.7:
            b.swrite("S", "cyw", "Cy", "pCy", "deeadd#0", [("app",)])

    steps = rng.randint(6, 22)
    for step in range(steps):
        if late_freeze and step == steps // 2:
            b.write("Dee", "dee1", "rDee", [("add", "rDee1", 3), ("rem", "rDee")])
            b.write("Dee", "dee2", "rDee", [("add", "rDee2", 3), ("rem", "rDee")],
                    parents=["Dee"])
        a = rng.random()
        others = [m for m in mems if m[1] != "Ana"]
        if a < 0.08:                                   # a device is removed
            p = rng.choice(PEOPLE[1:])
            k = rng.choice(keys[p][1:])
            par = b.heads(p) if rng.random() < 0.6 else [rng.choice(ilog(p))]
            b.write(p, nid("i"), "a" + p, [("rem", k)], par)
            continue
        if a < 0.14:                                   # a key of someone else is stolen
            p = rng.choice(PEOPLE[1:])
            stolen.append((p, rng.choice(keys[p])))
            continue
        x = nid("x")
        if a < 0.38:                                   # Ana, honestly
            c = rng.random()
            lower = [m for m in mems if m[1] != "Ana" and m[2] < 3]
            if c < 0.3:
                ops = [("add_member", rng.choice(PEOPLE[1:4]), rng.randint(0, 3))]
            elif c < 0.42 and lower:
                ops = [("remove_member", rng.choice(lower)[0])]
            elif c < 0.52 and [m for m in lower if m[2] > 0]:
                t = rng.choice([m for m in lower if m[2] > 0])
                ops = [("remove_member", t[0]), ("add_member", t[1], t[2] - 1)]
            elif c < 0.6:
                ops = [("reach",)]
            else:
                ops = [("app",)]
            for i, op in enumerate(ops):
                if op[0] == "add_member":
                    mems.append((f"{x}#{i}", op[1], op[2]))
            b.swrite("S", x, "Ana", rng.choice(keys["Ana"]), owner, ops, b.heads("S"),
                     head=b.heads("Ana")[-1])
            info["ana"].append(x)
            continue
        if a < 0.52 and stolen:                        # a thief, as the key's owner
            p, k = rng.choice(stolen)
            target = rng.choice(mems)
            i = rng.choice([target[0]] + [m[0] for m in mems if m[1] == p])
            c = rng.random()
            if c < 0.3:
                ops = [("remove_member", rng.choice(mems)[0])]
            elif c < 0.45:
                ops = [("succeed",)]
            elif c < 0.6:
                ops = [("add_member", rng.choice(PEOPLE), rng.randint(0, 3))]
                mems.append((f"{x}#0", ops[0][1], ops[0][2]))
            else:
                ops = [("app",)]
            par = [rng.choice(slog())] if rng.random() < 0.7 else b.heads("S")
            b.swrite("S", x, p, k, i, ops, par, head=rng.choice(ilog(p)))
            continue
        if a < 0.58:                                   # a stranger
            i = rng.choice([m[0] for m in mems] + ["S#9"])
            ops = rng.choice([[("remove_member", rng.choice(mems)[0])], [("succeed",)],
                              [("app",)], [("add_member", "Eve", 3)]])
            par = [rng.choice(slog())] if rng.random() < 0.5 else b.heads("S")
            b.swrite("S", x, "Eve", rng.choice(keys["Eve"]), i, ops, par,
                     head=b.heads("Eve")[-1])
            continue
        if not others:
            continue
        i, who, role = rng.choice(others)              # another member, any way
        signer = rng.choice(keys[who])
        head = rng.choice(ilog(who)) if rng.random() < 0.3 else b.heads(who)[-1]
        par = b.heads("S") if rng.random() < 0.7 else [rng.choice(slog())]
        c = rng.random()
        if c < 0.25:
            m, r = rng.choice(PEOPLE[:4]), rng.randint(0, 3)
            ops = [("add_member", m, r)]
            mems.append((f"{x}#0", m, r))
        elif c < 0.38:
            ops = [("remove_member", rng.choice(mems)[0])]
        elif c < 0.46:
            t = rng.choice(mems)
            if t[2] > 0:
                ops = [("remove_member", t[0]), ("add_member", t[1], t[2] - 1)]
                mems.append((f"{x}#1", t[1], t[2] - 1))
            else:
                ops = [("app",)]
        elif c < 0.52:
            ops = [("remove_member", i)]
        elif c < 0.56:
            ops = [("succeed",)]
        elif c < 0.64:
            mine = [e for e in slog() if b.w.entries[e].author == who]
            ops = [("keep", rng.choice(keys[who]), tuple(rng.sample(mine, min(2, len(mine)))))]
        elif c < 0.70:
            ops = [("reach",)]
        else:
            ops = [("app",)]
        b.swrite("S", x, who, signer, i, ops, par, head=head)
    b.info = info
    return b


def space_ids(w):
    return [x for x, e in w.entries.items() if e.log == "S"]


def membership_roles(w, valid):
    """Role of every membership created by a valid entry (or by genesis)."""
    out = {}
    for x in space_ids(w):
        e = w.entries[x]
        for i, op in enumerate(e.ops):
            if op[0] == "create":
                out[f"{x}#{i}"] = (e.author, 3)
            elif op[0] == "add_member" and (x,) in valid:
                out[f"{x}#{i}"] = (op[1], op[2])
    return out


def check_space(b, rng, stats):
    w = b.w
    r = evaluate_space(w, "S", space_ids(w))

    # D
    w2 = reorder(w, rng)
    r2 = evaluate_space(w2, "S", space_ids(w2))
    for k in ("valid", "member", "author_ok"):
        need(r[k] == r2[k], "D", f"space {k} differs with entry order")

    anc = anc_of(w, "S")
    # B: nothing valid descends from the end of its membership
    ends = {}
    for k in ("rm2", "rm1", "rm0", "leave"):
        for (i, y) in r[k] if k != "leave" else [(i, y) for (y, i) in r[k]]:
            ends.setdefault(i, set()).add(y)
    for (x,) in r["valid"]:
        i = w.entries[x].membership
        for y in ends.get(i, ()):
            need(y not in anc[x], "B", f"{x} is valid after the end of {i} at {y}")
        # A
        need((x,) in r["author_ok"], "A", f"{x} is valid without a counted author")

    # O: Ana keeps her membership and everything she wrote
    def honest_owner(res, ids):
        need(("S#0",) in res["member"], "O", "the honest owner lost her membership")
        for x in b.info["ana"]:
            if x in ids:
                need((x,) in res["valid"], "O", f"the honest owner's {x} is invalid")
    honest_owner(r, set(space_ids(w)))

    authors = sorted({w.entries[x].author for x in space_ids(w)})
    frozen = {a for a in authors if evaluate_identity(w, a, frozenset(w.entries))["frozen"]}

    # M: signatures of authors who are not frozen keep counting; the honest
    # owner in a subset
    sub = w.closure([x for x in space_ids(w) if rng.random() < 0.6] + ["S"])
    r1 = evaluate_space(w, "S", sub)
    for (x,) in r1["author_ok"]:
        if w.entries[x].author not in frozen:
            need((x,) in r["author_ok"], "M", f"{x} counts in a subset only")
    honest_owner(r1, sub)
    stats["subsets"] += 1

    # E: voiding one identity's entries never revives an equal or higher one
    roles = membership_roles(w, r["valid"])
    for m in authors:
        top = max([ro for (who, ro) in roles.values() if who == m], default=-1)
        rm = evaluate_space(w, "S", space_ids(w), void={m}, kept=r["kept_frozen"])
        for (x,) in rm["valid"]:
            if (x,) in r["valid"] or w.entries[x].author == m:
                continue
            role = roles.get(w.entries[x].membership, (None, -1))[1]
            if role < 0:
                # created by an entry that is valid only without m's entries
                role = membership_roles(w, rm["valid"]).get(w.entries[x].membership,
                                                            (None, -1))[1]
            need(role < top, "E",
                 f"{m} (role {top}) invalidates {x} under a role-{role} membership")
        stats["counterfactuals"] += 1

    # F: freezing keeps what others built on
    rf = evaluate_space(w, "S", space_ids(w), ignore_frozen=True)
    for (x,) in rf["valid"]:
        if w.entries[x].author not in frozen:
            need((x,) in r["valid"], "F", f"{x} is invalid only because someone is frozen")
    stats["space_frozen"] += bool(frozen)

    stats["space_valid"] += len(r["valid"])
    stats["space_entries"] += len(space_ids(w))


# ------------------------------------------------------------ digests

def digest(n, seed):
    """A digest of every result, for comparing runs under different hash
    seeds."""
    import hashlib
    h = hashlib.sha256()

    def put(res):
        for k in sorted(res):
            v = res[k]
            h.update(repr((k, sorted(v) if isinstance(v, (set, frozenset)) else v)).encode())

    for i in range(n):
        rng = random.Random(seed * 1_000_003 + i)
        b = identity_history(rng)
        put(evaluate_identity(b.w, "I", frozenset(b.w.entries)))
        rng = random.Random(seed * 2_000_003 + i)
        b = space_history(rng)
        put(evaluate_space(b.w, "S", space_ids(b.w)))
        rng = random.Random(seed * 3_000_017 + i)
        b, names = guardian_web(rng)
        for x in names:
            put(evaluate_identity(b.w, x, frozenset(b.w.entries)))
    return h.hexdigest()


def hash_seed_check(n, seed):
    import subprocess
    out = set()
    for hs in ("0", "1", "4242"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--digest", str(n),
                            str(seed)], env=env, capture_output=True, text=True, check=True)
        out.add(p.stdout.strip())
    return len(out) == 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--digest":
        print(digest(int(sys.argv[2]), int(sys.argv[3])))
        return 0
    n_id = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    n_sp = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    n_web = int(sys.argv[4]) if len(sys.argv) > 4 else 150
    n_hon = int(sys.argv[5]) if len(sys.argv) > 5 else 300
    for name in ("identity", "space"):
        errs = check(PROGRAMS[name])
        if errs:
            print(f"{name} rules are not stratified:", *errs, sep="\n  ")
            return 1
    stats = dict(entries=0, frozen=0, contested=0, recovered=0, subsets=0,
                 space_entries=0, space_valid=0, space_frozen=0, counterfactuals=0)
    web = dict(entries=0, frozen=0, contested=0, recovered=0, subsets=0, depth=0,
               conf=0, conf_frozen=0, conf_contested=0, conf_recovering=0)
    hon = dict(entries=0, recovered=0, decided=0, contested=0)
    failures = 0
    for i in range(n_id):
        rng = random.Random(seed * 1_000_003 + i)
        b = identity_history(rng)
        try:
            check_identity(b, rng, stats)
        except Failure as f:
            failures += 1
            print(f"identity case {i}: {f}")
    for i in range(n_hon):
        rng = random.Random(seed * 4_000_037 + i)
        b = honest_identity_history(rng)
        try:
            check_honest(b, rng, hon)
        except Failure as f:
            failures += 1
            print(f"honest case {i}: {f}")
    for i in range(n_sp):
        rng = random.Random(seed * 2_000_003 + i)
        b = space_history(rng)
        try:
            check_space(b, rng, stats)
        except Failure as f:
            failures += 1
            print(f"space case {i}: {f}")
    for i in range(n_web):
        rng = random.Random(seed * 3_000_017 + i)
        b, names = guardian_web(rng)
        try:
            check_guardian_web(b, names, rng, web)
        except (Failure, AssertionError, RecursionError) as f:
            failures += 1
            print(f"guardian web case {i}: {type(f).__name__}: {f}")
    same = hash_seed_check(20, seed)
    if not same:
        failures += 1
        print("D: results differ between Python hash seeds")
    print(f"identity: {n_id} histories, {stats['entries']} entries, {stats['subsets']} subsets; "
          f"{stats['frozen']} frozen, {stats['contested']} contested, "
          f"{stats['recovered']} recovered")
    print(f"honest guardians: {n_hon} histories, {hon['entries']} entries, "
          f"{hon['decided']} decisions in effect, {hon['recovered']} recovered, "
          f"{hon['contested']} contested, 0 frozen allowed")
    print(f"space: {n_sp} histories, {stats['space_entries']} entries, "
          f"{stats['space_valid']} valid, {stats['counterfactuals']} counterfactuals, "
          f"{stats['space_frozen']} with a frozen member")
    print(f"guardian webs: {n_web} worlds, {web['entries']} entries, {web['subsets']} subsets; "
          f"{web['frozen']} frozen, {web['contested']} contested, {web['recovered']} recovered "
          f"identities; deepest nesting {web['depth']}")
    print(f"  {web['conf']} confirmations, written while the guardian was frozen "
          f"{web['conf_frozen']}, contested {web['conf_contested']}, "
          f"recovered {web['conf_recovering']}")
    print(f"hash seeds: {'same results' if same else 'DIFFERENT results'} under 3 seeds")
    print(f"{failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
