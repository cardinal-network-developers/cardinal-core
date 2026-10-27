"""Abstract entries, input facts, and evaluation of identity logs and spaces.

Entries are plain records: no bytes, no signatures. A signature is modeled
by the `signer` field, which only the holder of a key may set; the fuzzer
gives each actor only the keys it holds.

Identity log ops:
    ("add", K, power)            add_key; power 1 device, 2 admin, 3 root
    ("rem", K)                   remove_key
    ("policy", P, guardians, t[, controller])
                                 set_recovery; P is the policy it changes
                                 (None in genesis); controller is the root
                                 that may change a policy naming no guardians
    ("recover", N, keeps, P)     recover: new root N, keys kept, under policy P
    ("confirm", D)               a guardian's confirmation of decision D
    ("sek",)                     set_encryption_key
    ("object", D)                advisory

Space ops:
    ("create",)                  genesis; the author becomes an owner
    ("add_member", M, role)      role 0 reader .. 3 owner
    ("remove_member", I)         I is a membership id: "<entry id>#<op index>"
    ("succeed",)
    ("keep", K, entry ids)
    ("app",)                     application data; writers and up
    ("reach",)                   reach node; anyone
"""

import os
from dataclasses import dataclass

from datalog import evaluate, read_rules

RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.md")
PROGRAMS = read_rules(RULES)


@dataclass(frozen=True)
class Entry:
    id: str
    log: str                       # identity id or space id
    parents: tuple
    signer: str
    ops: tuple
    # spaces only
    author: str = None
    head: str = None               # cited head of the author's identity log
    membership: str = None


def membership_id(entry_id, index):
    """A membership is named by the entry and the position of the op that
    created it, as in spaces.md."""
    return f"{entry_id}#{index}"


class World:
    """A global set of entries across logs."""

    _serial = 0

    def __init__(self):
        self.entries = {}
        self._kind = {}            # log id -> "identity" | "space"
        World._serial += 1
        self.serial = World._serial  # cache key; id() can be reused

    def put(self, e, kind):
        assert e.id not in self.entries, e.id
        for p in e.parents:
            assert p in self.entries and self.entries[p].log == e.log, (e.id, p)
        for r in self.refs(e):
            # a reference is a hash: it can only name an entry that exists
            assert r in self.entries, (e.id, r)
        self.entries[e.id] = e
        self._kind.setdefault(e.log, kind)

    def refs(self, e):
        """Cross-log references: a confirmation names its decision."""
        return tuple(op[1] for op in e.ops if op[0] == "confirm")

    def closure(self, ids):
        out, todo = set(), list(ids)
        while todo:
            x = todo.pop()
            if x in out or x not in self.entries:
                continue
            out.add(x)
            e = self.entries[x]
            todo.extend(e.parents)
            todo.extend(self.refs(e))
        return frozenset(out)


# ------------------------------------------------------------ graph helpers

def ancestry(entries):
    """anc[x] = set of strict ancestors of x, within one log."""
    anc = {}

    def go(x):
        if x not in anc:
            s = set()
            for p in entries[x].parents:
                s.add(p)
                s |= go(p)
            anc[x] = s
        return anc[x]

    for x in entries:
        go(x)
    return anc


def log_order(entries):
    """Topological order; among ready entries, the smallest id first."""
    import heapq
    children = {x: [] for x in entries}
    waiting = {}
    for x, e in entries.items():
        waiting[x] = len(e.parents)
        for p in e.parents:
            children[p].append(x)
    ready = [x for x, n in waiting.items() if n == 0]
    heapq.heapify(ready)
    out = []
    while ready:
        x = heapq.heappop(ready)
        out.append(x)
        for c in children[x]:
            waiting[c] -= 1
            if waiting[c] == 0:
                heapq.heappush(ready, c)
    return out


def graph_facts(entries, prefix=""):
    anc = ancestry(entries)
    ids = sorted(entries)
    f = {prefix + k: set() for k in ("entry", "anc", "ae", "conc", "genesis")}
    for x in ids:
        f[prefix + "entry"].add((x,))
        f[prefix + "ae"].add((x, x))
        if not entries[x].parents:
            f[prefix + "genesis"].add((x,))
        for a in anc[x]:
            f[prefix + "anc"].add((a, x))
            f[prefix + "ae"].add((a, x))
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            if x not in anc[y] and y not in anc[x]:
                f[prefix + "conc"].add((x, y))
                f[prefix + "conc"].add((y, x))
    return f, anc


# ------------------------------------------------------------ identity logs

ALLOWED = {
    # power -> op names a key of that power may sign (decisions excepted)
    3: {"add", "rem", "sek", "object", "confirm", "policy"},
    2: {"add", "rem", "sek", "object", "confirm"},
    1: {"confirm"},
}


def identity_facts(world, ident, ids):
    entries = {x: world.entries[x] for x in sorted(ids) if world.entries[x].log == ident}
    f, anc = graph_facts(entries)
    order = log_order(entries)
    pos = {x: n for n, x in enumerate(order)}
    f["later"] = {(a, b) for a in entries for b in entries if pos[a] < pos[b]}
    for k in ("signer", "add", "readd", "rem", "selfrep", "is_selfrep", "badops", "policy",
              "change", "guardian", "threshold", "unguarded", "majority", "bad_policy",
              "ctrl", "recover", "keeps", "bad_decision", "sek"):
        f[k] = set()
    # keys each entry names: added, or a recovery's new root
    names_of = {x: {op[1] for op in e.ops if op[0] in ("add", "recover")}
                for x, e in entries.items()}
    for x in sorted(entries):
        e = entries[x]
        f["signer"].add((x, e.signer))
        names = [op[0] for op in e.ops]
        named_before = set().union(*(names_of[a] for a in anc[x])) if anc[x] else set()
        readd = any(op[0] == "add" and op[1] in named_before for op in e.ops)
        if readd:
            f["readd"].add((x,))           # a key, once named, is never added again
        for op in e.ops:
            if op[0] == "add":
                f["add"].add((x, op[1], op[2]))
            elif op[0] == "rem":
                f["rem"].add((x, op[1]))
            elif op[0] == "policy":
                gs, t = tuple(op[2]), op[3]
                f["policy"].add((x,))
                if op[1] is not None:
                    f["change"].add((x, op[1]))
                for g in gs:
                    f["guardian"].add((x, g))
                f["threshold"].add((x, t))
                if not gs:
                    f["unguarded"].add((x,))
                    if op[1] is None:      # genesis: its root controls
                        for o in e.ops:
                            if o[0] == "add" and o[2] == 3:
                                f["ctrl"].add((x, o[1]))
                    elif len(op) > 4 and op[4] is not None:
                        f["ctrl"].add((x, op[4]))
                elif len(gs) // 2 < t <= len(gs):
                    f["majority"].add((x,))
                else:
                    f["bad_policy"].add((x,))
            elif op[0] == "recover":
                f["recover"].add((x, op[1], op[3]))
                for k in op[2]:
                    f["keeps"].add((x, k))
            elif op[0] == "sek":
                f["sek"].add((x,))
        decision = "recover" in names or "policy" in names
        if decision and e.parents and len(e.ops) != 1:
            f["bad_decision"].add((x,))    # a decision is alone in its entry
        if any(op[0] == "recover" and op[1] in named_before for op in e.ops):
            f["bad_decision"].add((x,))    # a new root is a new key
        # root replacement: exactly add root N and remove the signer
        if (sorted(names) == ["add", "rem"] and not readd
                and any(op[0] == "add" and op[2] == 3 for op in e.ops)
                and any(op[0] == "rem" and op[1] == e.signer for op in e.ops)):
            n = next(op[1] for op in e.ops if op[0] == "add")
            f["selfrep"].add((x, e.signer, n))
            f["is_selfrep"].add((x,))
            continue
        # decisions are judged only as decisions, never as ordinary entries;
        # whether a removal targets a lower power is decided by the rules
        for p in (1, 2, 3):
            bad = decision or readd or any(n not in ALLOWED[p] for n in names)
            for op in e.ops:
                if op[0] == "add" and (op[2] >= 3 or op[2] > p):
                    bad = True            # roots are added only by replacement
            if bad:
                f["badops"].add((x, p))
    return f


def confirm_facts(world, ident, ids):
    """confirm_ok(G, D): a confirmation of D, judged in G's log as of its own
    causal past."""
    out = set()
    decisions = {x for x in ids if world.entries[x].log == ident}
    for c in ids:
        e = world.entries[c]
        if e.log == ident:
            continue
        for op in e.ops:
            if op[0] == "confirm" and op[1] in decisions:
                past = world.closure([c])
                r = evaluate_identity(world, e.log, past)
                if (c,) in r["valid"] and not r["frozen"]:
                    out.add((e.log, op[1]))
    return out


_cache = {}
_active = []                       # evaluations in progress, outermost first
depth = {"max": 0}


def evaluate_identity(world, ident, ids):
    """Evaluate identity `ident` over the causally closed set `ids`.

    Judging a confirmation evaluates the guardian's log over the
    confirmation's own causal past, which may hold confirmations of the
    guardian's decisions by other identities, and so on. Each nested
    evaluation of the same log is over a strictly smaller set, because hash
    links cannot form a cycle, so the recursion ends: sets are finite, and a
    loop would need the same evaluation to recur. The assertion checks that.
    """
    ids = frozenset(x for x in ids if x in world.entries)
    own = frozenset(x for x in ids if world.entries[x].log == ident)
    key = (world.serial, ident, ids)
    if key in _cache:
        return _cache[key]
    assert key not in _active, f"identity evaluation of {ident} recurs"
    _active.append(key)
    depth["max"] = max(depth["max"], len(_active))
    try:
        f = identity_facts(world, ident, own)
        f["confirm_ok"] = confirm_facts(world, ident, ids)
    finally:
        _active.pop()
    rel = evaluate(PROGRAMS["identity"], f)
    r = {k: rel.get(k, set()) for k in (
        "valid", "in_effect", "applied", "tainted", "effective", "effective_at", "removed",
        "removed_at", "removal", "root_eff", "current_policy", "current_key", "rec_removes",
        "key_added", "votes", "suspended", "kpow")}
    r["frozen"] = bool(rel.get("frozen"))
    r["contested"] = bool(rel.get("contested"))
    _cache[key] = r
    return r


# ------------------------------------------------------------------ spaces

ROLE_OPS = {
    3: {"create", "add_member", "remove_member", "succeed", "keep", "app", "reach"},
    2: {"add_member", "remove_member", "keep", "app", "reach"},
    1: {"remove_member", "keep", "app", "reach"},
    0: {"remove_member", "keep", "reach"},
}


def space_facts(world, space, ids):
    entries = {x: world.entries[x] for x in sorted(ids) if world.entries[x].log == space}
    f, anc = graph_facts(entries, prefix="s_")
    for k in ("author", "skey", "cites", "mem", "incarnation", "inc_from", "adds", "s_rem",
              "replaces", "s_succeed", "s_keep", "s_badops"):
        f[k] = set()
    role = {}
    for x, e in entries.items():
        for n, op in enumerate(e.ops):
            if op[0] == "create":
                role[membership_id(x, n)] = (e.author, 3, x)
            if op[0] == "add_member":
                role[membership_id(x, n)] = (op[1], op[2], x)
    for i, (m, r, x) in role.items():
        f["incarnation"].add((i, m, r))
        f["inc_from"].add((i, x))
        f["adds"].add((x, i))
    for x, e in entries.items():
        f["author"].add((x, e.author))
        f["skey"].add((x, e.signer))
        f["cites"].add((x, e.head))
        if e.membership:
            f["mem"].add((x, e.membership))
        ended, made = [], []
        for n, op in enumerate(e.ops):
            if op[0] == "remove_member":
                f["s_rem"].add((x, op[1]))
                ended.append(op[1])
            elif op[0] == "add_member":
                made.append(membership_id(x, n))
            elif op[0] == "succeed":
                f["s_succeed"].add((x,))
            elif op[0] == "keep":
                for t in op[2]:
                    f["s_keep"].add((x, op[1], t))
        for i in ended:
            for j in made:
                if i in role and role[i][0] == role[j][0] and role[j][1] < role[i][1]:
                    f["replaces"].add((x, i, j))
        for r in (0, 1, 2, 3):
            bad = False
            for op in e.ops:
                if op[0] not in ROLE_OPS[r]:
                    bad = True
                elif op[0] == "create" and entries[x].parents:
                    bad = True
                elif op[0] == "add_member" and not (op[2] < r or (op[2] == r and r >= 2)):
                    bad = True
                elif op[0] == "remove_member":
                    tgt = role.get(op[1])
                    own = op[1] == e.membership
                    if not own and (tgt is None or tgt[1] >= r):
                        bad = True
            if bad:
                f["s_badops"].add((x, r))
    return f, entries


def evaluate_space(world, space, ids, ignore_frozen=False, void=(), kept=None):
    """Evaluate a space over the closure of `ids`.

    A frozen author's entries count only as far as valid entries by authors
    who are not frozen built on them, as judged with no author frozen; so a
    space with a frozen author is evaluated twice. With ignore_frozen, every
    author is treated as not frozen. Entries by authors in `void` count for
    nothing; `kept` fixes the frozen entries kept. The fuzzer uses these
    three to compare."""
    ids = world.closure(ids)
    f, entries = space_facts(world, space, ids)
    if void:
        f["author"] = {(x, ("void", a) if a in void else a) for (x, a) in f["author"]}
    authors = sorted({e.author for e in entries.values()})
    for k in ("id_effective_at", "id_removed", "id_removed_at", "id_frozen", "kept_frozen"):
        f[k] = set()
    for a in authors:
        # the verifier's identity logs: everything it holds about the author,
        # including guardians' confirmations
        r = evaluate_identity(world, a, frozenset(world.entries))
        for (k, h) in r["effective_at"]:
            f["id_effective_at"].add((a, k, h))
        for (k,) in r["removed"]:
            f["id_removed"].add((a, k))
        for (k, h) in r["removed_at"]:
            f["id_removed_at"].add((a, k, h))
        if r["frozen"] and not ignore_frozen:
            f["id_frozen"].add((a,))
    frozen = {a for (a,) in f["id_frozen"]}
    if frozen and kept is None:
        nf = evaluate_space(world, space, ids, ignore_frozen=True, void=void)
        anc = ancestry(entries)
        kept = {y for (y,) in nf["author_ok"] if entries[y].author in frozen
                and any(y in anc[x] for (x,) in nf["valid"]
                        if entries[x].author not in frozen)}
    f["kept_frozen"] = {(y,) for y in (kept or ()) if y in entries}
    rel = evaluate(PROGRAMS["space"], f)
    out = {k: rel.get(k, set()) for k in (
        "valid", "member", "author_ok", "rm2", "rm1", "rm0", "leave", "closed", "ended")}
    out["kept_frozen"] = {y for (y,) in f["kept_frozen"]}
    return out


# ----------------------------------------------------------------- builder

class Builder:
    """Write entries by name, for scenarios and the fuzzer."""

    def __init__(self):
        self.w = World()
        self.last = {}             # log -> last entry written

    def heads(self, log, within=None):
        ids = [x for x, e in self.w.entries.items() if e.log == log
               and (within is None or x in within)]
        parents = {p for x in ids for p in self.w.entries[x].parents}
        return tuple(sorted(x for x in ids if x not in parents))

    def identity(self, name, root, admin=None, devices=(), guardians=(), threshold=0):
        ops = [("add", root, 3)]
        if admin:
            ops.append(("add", admin, 2))
        ops += [("add", d, 1) for d in devices]
        ops += [("policy", None, tuple(guardians), threshold), ("sek",)]
        e = Entry(name, name, (), root, tuple(ops))
        self.w.put(e, "identity")
        self.last[name] = name
        return name

    def write(self, log, name, signer, ops, parents=None):
        if parents is None:
            parents = self.heads(log)
        e = Entry(name, log, tuple(parents), signer, tuple(ops))
        self.w.put(e, "identity")
        self.last[log] = name
        return name

    def space(self, name, author, signer, head=None):
        e = Entry(name, name, (), signer, (("create",),), author=author,
                  head=head or self.last[author], membership=membership_id(name, 0))
        self.w.put(e, "space")
        self.last[name] = name
        return membership_id(name, 0)

    def swrite(self, space, name, author, signer, membership, ops, parents=None, head=None):
        if parents is None:
            parents = self.heads(space)
        e = Entry(name, space, tuple(parents), signer, tuple(ops), author=author,
                  head=head or self.last[author], membership=membership)
        self.w.put(e, "space")
        self.last[space] = name
        return name

    def ident(self, log, ids=None):
        return evaluate_identity(self.w, log, frozenset(ids or self.w.entries))

    def sp(self, space):
        return evaluate_space(self.w, space, [x for x, e in self.w.entries.items()
                                              if e.log == space])


# --------------------------------------------------------- software rules
#
# What honest guardian software does. None of this decides validity; the
# fuzzer uses it to check that guardians who follow it never cause a freeze.

def decision_policy(e):
    """The policy a decision entry acts under, or None if it is not one."""
    if not e.parents:
        return None
    for op in e.ops:
        if op[0] == "recover":
            return op[3]
        if op[0] == "policy":
            return op[1]
    return None


def is_change(e):
    return bool(e.parents) and any(op[0] == "policy" for op in e.ops)


def may_confirm(world, view, guardian, d):
    """Whether guardian software may confirm decision `d`.

    `view` is the set of entries the guardian's device holds; it always
    includes the guardian's own log, which the software syncs first.

    A guardian confirms decisions under one policy in a chain: every
    decision under that policy it has already confirmed must be in the new
    one's causal past, and each of those that is a change of the policy must
    be dead. A change is dead when more than n - t of the policy's guardians
    have confirmed decisions under the policy that are concurrent with it:
    guardians following this rule never confirm it afterwards, so it can no
    longer reach its threshold.
    """
    w = world.entries
    de = w[d]
    p = decision_policy(de)
    if p is None or p not in w:
        return False
    pol = next(op for op in w[p].ops if op[0] == "policy")
    gs, t = tuple(pol[2]), pol[3]
    if guardian not in gs:
        return False
    log = de.log
    anc = ancestry({x: e for x, e in w.items() if e.log == log})

    def confirmed_by(g, ids):
        return {op[1] for x in ids for op in w[x].ops
                if w[x].log == g and op[0] == "confirm" and op[1] in w
                and w[op[1]].log == log and decision_policy(w[op[1]]) == p}

    own = {x for x, e in w.items() if e.log == guardian}
    mine = confirmed_by(guardian, own)
    seen = {g: confirmed_by(g, view) for g in gs if g != guardian}
    seen[guardian] = mine

    def conc(a, b):
        return a != b and a not in anc[b] and b not in anc[a]

    def dead(x):
        n = sum(1 for g in gs if any(conc(y, x) for y in seen[g]))
        return n > len(gs) - t

    for x in mine:
        if x == d or x not in anc[d]:
            return False
        if is_change(w[x]) and not dead(x):
            return False
    return True
