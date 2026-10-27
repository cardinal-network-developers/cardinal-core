"""Random adversarial histories, checked against properties the rules must
keep whatever happens.

    python3 model/fuzz.py [identity-cases] [space-cases] [seed] [web-cases]

Identity histories mix honest work with a thief who steals the phrase or a
device and writes with old parents, guardians who confirm late, twice, from
stolen devices, or under replaced policies, and recoveries under any policy.
Guardian webs are worlds of identities that guard each other (a pair with a
third guardian, a three-cycle, a mesh of four), where any of them may be
stolen from, contested, recovering or frozen while it confirms another's
decisions, and thieves confirm with stolen or freshly minted keys on old
branches of a guardian's log.
Space histories mix members adding, removing, lowering, leaving and
succeeding, devices removed in identity logs, keep ops, and backdated writes
under ended memberships.

Properties checked:

  D  determinism: the result is the same however the entries are ordered;
  M  monotone decisions: for a causally closed subset S1 of S, if S1 is
     frozen so is S, and a decision in effect in S1 is in effect in S or S
     is frozen;
  R  recovery: if S is not frozen, every key in effect was kept by the
     latest recovery or added after it, and every root descends from it;
  B  backdating: no valid entry by a removed key is outside the removal's
     causal past; no valid space entry descends from the end of its
     membership;
  A  authors: every valid space entry has an author whose key counted.

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
                   evaluate_space)


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

    for _ in range(rng.randint(6, 20)):
        a = rng.random()
        if a < 0.08:                                   # owner adds a device
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
            b.write("I", nid("s"), owner["root"] if rng.random() < 0.5 else owner["admin"],
                    [("policy", pol, new, len(new) // 2 + 1 if new else 0)], honest_parents())
        elif a < 0.32:                                 # something is stolen
            thief.add(rng.choice(["R0", "R0", owner["root"], owner["admin"],
                                  rng.choice(owner["devices"])]))
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
            elif kind < 0.85:
                pol = rng.choice(policies())
                ops = [("policy", pol, ("X1", "X2", "X3"), 2)]
            else:
                ops = [("sek",)]
            b.write("I", x, k, ops, old_parents() if rng.random() < 0.7 else b.heads("I"))
            thief_entries.add(x)
        elif a < 0.64:                                 # someone starts a recovery
            nroot = nid("N")
            keep = tuple(k for k in [owner["admin"]] + owner["devices"] if rng.random() < 0.5)
            pol = rng.choice(policies())
            par = honest_parents() if rng.random() < 0.7 else old_parents()
            b.write("I", nid("r"), nroot, [("recover", nroot, keep, pol)], par)
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

def space_history(rng):
    b = Builder()
    people = ("Ana", "Ben", "Cy", "Dee")
    for p in people:
        b.identity(p, "r" + p, admin="a" + p, devices=("p" + p, "q" + p))
    if rng.random() < 0.2:                          # someone becomes frozen
        b.write("Dee", "dee1", "rDee", [("add", "rDee1", 3), ("rem", "rDee")])
        b.write("Dee", "dee2", "rDee", [("add", "rDee2", 3), ("rem", "rDee")], parents=["Dee"])
    keys = {p: ["a" + p, "p" + p, "q" + p] for p in people}
    n = [0]

    def nid(p):
        n[0] += 1
        return f"{p}{n[0]:03d}"

    def ilog(p):
        return [x for x, e in b.w.entries.items() if e.log == p]

    owner = b.space("S", "Ana", "aAna")
    mems = [(owner, "Ana", 3)]

    for _ in range(rng.randint(4, 18)):
        a = rng.random()
        if a < 0.12:                                   # a device is removed
            p = rng.choice(people)
            k = rng.choice(keys[p][1:])
            par = b.heads(p) if rng.random() < 0.6 else [rng.choice(ilog(p))]
            b.write(p, nid("i"), "a" + p, [("rem", k)], par)
            continue
        i, who, role = rng.choice(mems)
        signer = rng.choice(keys[who])
        head = rng.choice(ilog(who)) if rng.random() < 0.3 else b.heads(who)[-1]
        slog = [x for x, e in b.w.entries.items() if e.log == "S"]
        par = b.heads("S") if rng.random() < 0.7 else [rng.choice(slog)]
        x = nid("x")
        c = rng.random()
        if c < 0.25:
            m, r = rng.choice(people), rng.randint(0, 3)
            ops = [("add_member", m, r)]
            mems.append((f"{x}:{m}", m, r))
        elif c < 0.38:
            ops = [("remove_member", rng.choice(mems)[0])]
        elif c < 0.46:
            t = rng.choice(mems)
            if t[2] > 0:
                ops = [("remove_member", t[0]), ("add_member", t[1], t[2] - 1)]
                mems.append((f"{x}:{t[1]}", t[1], t[2] - 1))
            else:
                ops = [("app",)]
        elif c < 0.52:
            ops = [("remove_member", i)]
        elif c < 0.56:
            ops = [("succeed",)]
        elif c < 0.64:
            mine = [e for e in slog if b.w.entries[e].author == who]
            ops = [("keep", rng.choice(keys[who]), tuple(rng.sample(mine, min(2, len(mine)))))]
        elif c < 0.70:
            ops = [("reach",)]
        else:
            ops = [("app",)]
        b.swrite("S", x, who, signer, i, ops, par, head=head)
    return b


def check_space(b, rng, stats):
    w = b.w
    r = evaluate_space(w, "S", [x for x, e in w.entries.items() if e.log == "S"])

    # D
    w2 = reorder(w, rng)
    r2 = evaluate_space(w2, "S", [x for x, e in w2.entries.items() if e.log == "S"])
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
    stats["space_valid"] += len(r["valid"])
    stats["space_entries"] += sum(1 for e in w.entries.values() if e.log == "S")


def main():
    n_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    n_sp = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    n_web = int(sys.argv[4]) if len(sys.argv) > 4 else 500
    for name in ("identity", "space"):
        errs = check(PROGRAMS[name])
        if errs:
            print(f"{name} rules are not stratified:", *errs, sep="\n  ")
            return 1
    stats = dict(entries=0, frozen=0, contested=0, recovered=0, subsets=0,
                 space_entries=0, space_valid=0)
    web = dict(entries=0, frozen=0, contested=0, recovered=0, subsets=0, depth=0,
               conf=0, conf_frozen=0, conf_contested=0, conf_recovering=0)
    failures = 0
    for i in range(n_id):
        rng = random.Random(seed * 1_000_003 + i)
        b = identity_history(rng)
        try:
            check_identity(b, rng, stats)
        except Failure as f:
            failures += 1
            print(f"identity case {i}: {f}")
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
    print(f"identity: {n_id} histories, {stats['entries']} entries, {stats['subsets']} subsets; "
          f"{stats['frozen']} frozen, {stats['contested']} contested, "
          f"{stats['recovered']} recovered")
    print(f"space: {n_sp} histories, {stats['space_entries']} entries, "
          f"{stats['space_valid']} valid")
    print(f"guardian webs: {n_web} worlds, {web['entries']} entries, {web['subsets']} subsets; "
          f"{web['frozen']} frozen, {web['contested']} contested, {web['recovered']} recovered "
          f"identities; deepest nesting {web['depth']}")
    print(f"  {web['conf']} confirmations, written while the guardian was frozen "
          f"{web['conf_frozen']}, contested {web['conf_contested']}, "
          f"recovered {web['conf_recovering']}")
    print(f"{failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
