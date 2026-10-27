"""A small stratified Datalog: parser, stratification checker, evaluator.

The notation is described in rules.md. Programs are read from the
```datalog blocks of that file. Standard library only.
"""

import re
from collections import defaultdict

# ---------------------------------------------------------------- parsing

TOKEN = re.compile(r"""
    (?P<ws>\s+|%[^\n]*)
  | (?P<op>:-|!=|<=|>=|[(),.{}:<>=/@])
  | (?P<num>-?\d+)
  | (?P<str>"[^"]*")
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
""", re.VERBOSE)


class Var(str):
    """A variable. Plain str values are constants."""


class Atom:
    def __init__(self, pred, args):
        self.pred, self.args = pred, tuple(args)

    def __repr__(self):
        return f"{self.pred}({', '.join(map(str, self.args))})" if self.args else self.pred


class Lit:
    """kind: 'pos', 'neg', 'cmp', 'count'."""

    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)


class Rule:
    def __init__(self, head, body, stratum, line):
        self.head, self.body, self.stratum, self.line = head, body, stratum, line


class Program:
    def __init__(self, name):
        self.name = name
        self.inputs = {}          # pred -> arity
        self.strata = []          # names, in order
        self.rules = []


def tokenize(text):
    pos, line, out = 0, 1, []
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise SyntaxError(f"line {line}: cannot read {text[pos:pos+20]!r}")
        kind = m.lastgroup
        val = m.group(kind)
        if kind != "ws":
            out.append((kind, val, line))
        line += val.count("\n")
        pos = m.end()
    return out


def parse(text):
    """Parse every @program in text. Returns {name: Program}."""
    toks = tokenize(text)
    i = 0
    programs, prog, stratum = {}, None, None

    def peek(k=0):
        return toks[i + k] if i + k < len(toks) else (None, None, None)

    def take(expect=None):
        nonlocal i
        tok = toks[i]
        if expect is not None and tok[1] != expect:
            raise SyntaxError(f"line {tok[2]}: expected {expect!r}, got {tok[1]!r}")
        i += 1
        return tok

    def term():
        kind, val, line = take()
        if kind == "num":
            return int(val)
        if kind == "str":
            return val[1:-1]
        if kind == "name":
            return Var(val) if (val[0].isupper() or val[0] == "_") else val
        raise SyntaxError(f"line {line}: expected a term, got {val!r}")

    def atom():
        kind, name, line = take()
        if kind != "name":
            raise SyntaxError(f"line {line}: expected a predicate, got {name!r}")
        args = []
        if peek()[1] == "(":
            take("(")
            args.append(term())
            while peek()[1] == ",":
                take(",")
                args.append(term())
            take(")")
        return Atom(name, args)

    def literal():
        kind, val, line = peek()
        if val == "not":
            take()
            return Lit("neg", atom=atom())
        if val == "count" and peek(1)[1] == "{":
            take()
            take("{")
            vars_ = [term()]
            while peek()[1] == ",":
                take(",")
                vars_.append(term())
            take(":")
            atoms = [atom()]
            while peek()[1] == ",":
                take(",")
                atoms.append(atom())
            take("}")
            op = take()[1]
            return Lit("count", vars=vars_, atoms=atoms, op=op, rhs=term())
        if kind == "name" and peek(1)[1] not in ("!=", "<", "<=", ">", ">=", "="):
            return Lit("pos", atom=atom())
        lhs = term()
        op = take()[1]
        return Lit("cmp", lhs=lhs, op=op, rhs=term())

    while i < len(toks):
        kind, val, line = peek()
        if val == "@":
            take("@")
            directive = take()[1]
            if directive == "program":
                name = take()[1]
                prog = programs.setdefault(name, Program(name))
                stratum = None
            elif directive == "stratum":
                stratum = take()[1]
                if stratum in prog.strata:
                    raise SyntaxError(f"line {line}: stratum {stratum} declared twice")
                prog.strata.append(stratum)
            elif directive == "input":
                while peek()[0] == "name" and peek(1)[1] == "/":
                    pred = take()[1]
                    take("/")
                    prog.inputs[pred] = int(take()[1])
            else:
                raise SyntaxError(f"line {line}: unknown directive @{directive}")
            continue
        if prog is None or stratum is None:
            raise SyntaxError(f"line {line}: rule outside a @program/@stratum")
        head = atom()
        body = []
        if peek()[1] == ":-":
            take(":-")
            body.append(literal())
            while peek()[1] == ",":
                take(",")
                body.append(literal())
        take(".")
        prog.rules.append(Rule(head, body, stratum, line))
    return programs


def read_rules(path):
    """Concatenate the ```datalog blocks of a Markdown file and parse them."""
    text = open(path, encoding="utf-8").read()
    blocks = re.findall(r"```datalog\n(.*?)```", text, re.S)
    # keep line numbers meaningful: blank out everything outside blocks
    return parse("\n".join(blocks))


# ---------------------------------------------------- stratification check

def check(prog):
    """Return a list of problems. An empty list means the program is
    stratified, safe, and consistent."""
    errors = []
    level = {s: n for n, s in enumerate(prog.strata)}
    defined = {}
    arity = dict(prog.inputs)

    def note_arity(a, line):
        n = len(a.args)
        if arity.setdefault(a.pred, n) != n:
            errors.append(f"line {line}: {a.pred} used with arity {n} and {arity[a.pred]}")

    for r in prog.rules:
        p = r.head.pred
        if p in prog.inputs:
            errors.append(f"line {r.line}: {p} is an input and cannot be derived")
        if defined.setdefault(p, r.stratum) != r.stratum:
            errors.append(f"line {r.line}: {p} is defined in strata {defined[p]} and {r.stratum}")
        note_arity(r.head, r.line)

    def stratum_of(pred, line):
        if pred in prog.inputs:
            return -1
        if pred not in defined:
            errors.append(f"line {line}: {pred} is neither an input nor derived")
            return -1
        return level[defined[pred]]

    for r in prog.rules:
        here = level[r.stratum]
        bound = set()
        for lit in r.body:
            if lit.kind == "pos":
                note_arity(lit.atom, r.line)
                if stratum_of(lit.atom.pred, r.line) > here:
                    errors.append(f"line {r.line}: {r.head.pred} uses {lit.atom.pred} from a later stratum")
                bound |= {a for a in lit.atom.args if isinstance(a, Var)}
        for lit in r.body:
            if lit.kind == "neg":
                note_arity(lit.atom, r.line)
                if stratum_of(lit.atom.pred, r.line) >= here:
                    errors.append(f"line {r.line}: {r.head.pred} negates {lit.atom.pred}, "
                                  f"which is not from an earlier stratum")
                free = {a for a in lit.atom.args if isinstance(a, Var)} - bound
                if free:
                    errors.append(f"line {r.line}: unbound {sorted(free)} under 'not'")
            elif lit.kind == "cmp":
                for t in (lit.lhs, lit.rhs):
                    if isinstance(t, Var) and t not in bound:
                        errors.append(f"line {r.line}: unbound {t} in comparison")
            elif lit.kind == "count":
                inner = set()
                for a in lit.atoms:
                    note_arity(a, r.line)
                    if stratum_of(a.pred, r.line) >= here:
                        errors.append(f"line {r.line}: {r.head.pred} counts {a.pred}, "
                                      f"which is not from an earlier stratum")
                    inner |= {x for x in a.args if isinstance(x, Var)}
                for v in lit.vars:
                    if v not in inner:
                        errors.append(f"line {r.line}: counted {v} does not occur in the count")
                if isinstance(lit.rhs, Var) and lit.rhs not in bound:
                    errors.append(f"line {r.line}: unbound {lit.rhs} in count")
        free = {a for a in r.head.args if isinstance(a, Var)} - bound
        if free:
            errors.append(f"line {r.line}: head variables {sorted(free)} are not bound")
    return errors


# --------------------------------------------------------------- evaluation

CMP = {
    "=": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
}


class DB:
    def __init__(self, facts):
        self.rel = defaultdict(set)
        for pred, tuples in facts.items():
            self.rel[pred] |= {tuple(t) for t in tuples}
        self._index = {}

    def invalidate(self):
        self._index.clear()

    def lookup(self, pred, args, env):
        """Yield extended environments matching atom pred(args)."""
        key_pos, key_val = [], []
        for n, a in enumerate(args):
            if isinstance(a, Var):
                if a in env:
                    key_pos.append(n)
                    key_val.append(env[a])
            else:
                key_pos.append(n)
                key_val.append(a)
        key_pos = tuple(key_pos)
        idx = self._index.get((pred, key_pos))
        if idx is None:
            idx = defaultdict(list)
            for t in self.rel[pred]:
                idx[tuple(t[p] for p in key_pos)].append(t)
            self._index[(pred, key_pos)] = idx
        for t in idx.get(tuple(key_val), ()):
            e = env
            ok = True
            for a, v in zip(args, t):
                if isinstance(a, Var):
                    if a in e:
                        if e[a] != v:
                            ok = False
                            break
                    else:
                        if e is env:
                            e = dict(env)
                        e[a] = v
            if ok:
                yield e

    def holds(self, atom, env):
        return any(True for _ in self.lookup(atom.pred, atom.args, env))


def _value(t, env):
    return env[t] if isinstance(t, Var) else t


def _solve(db, lits, env):
    """Join a body. Filters run as soon as their variables are bound."""
    if not lits:
        yield env
        return
    # run any ready filter first
    for n, lit in enumerate(lits):
        if lit.kind == "pos":
            continue
        vars_ = _filter_vars(lit)
        if all(v in env for v in vars_):
            if _filter(db, lit, env):
                yield from _solve(db, lits[:n] + lits[n + 1:], env)
            return
    # otherwise the positive atom with the most bound arguments
    best, score = None, -1
    for n, lit in enumerate(lits):
        if lit.kind == "pos":
            s = sum(1 for a in lit.atom.args if not isinstance(a, Var) or a in env)
            if s > score:
                best, score = n, s
    if best is None:
        raise RuntimeError("unsafe rule body")
    lit = lits[best]
    rest = lits[:best] + lits[best + 1:]
    for e in db.lookup(lit.atom.pred, lit.atom.args, env):
        yield from _solve(db, rest, e)


def _filter_vars(lit):
    if lit.kind == "neg":
        return [a for a in lit.atom.args if isinstance(a, Var)]
    if lit.kind == "cmp":
        return [t for t in (lit.lhs, lit.rhs) if isinstance(t, Var)]
    return []


def _filter(db, lit, env):
    if lit.kind == "neg":
        return not db.holds(lit.atom, env)
    if lit.kind == "cmp":
        return CMP[lit.op](_value(lit.lhs, env), _value(lit.rhs, env))
    if lit.kind == "count":
        seen = set()
        for e in _solve(db, [Lit("pos", atom=a) for a in lit.atoms], env):
            seen.add(tuple(e[v] for v in lit.vars))
        return CMP[lit.op](len(seen), _value(lit.rhs, env))
    raise ValueError(lit.kind)


def _order_count_last(body):
    # a count's outer variables must be bound before it runs; place it after
    # every positive literal, so _solve only sees it once they are.
    pos = [l for l in body if l.kind == "pos"]
    other = [l for l in body if l.kind != "pos" and l.kind != "count"]
    counts = [l for l in body if l.kind == "count"]
    return pos + other, counts


def evaluate(prog, facts):
    """Evaluate a checked program over input facts {pred: iterable of
    tuples}. Returns {pred: set of tuples} for every predicate."""
    db = DB(facts)
    for stratum in prog.strata:
        rules = [r for r in prog.rules if r.stratum == stratum]
        changed = True
        while changed:
            changed = False
            db.invalidate()
            new = defaultdict(set)
            for r in rules:
                body, counts = _order_count_last(r.body)
                for env in _solve(db, body, {}):
                    if all(_filter(db, c, env) for c in counts):
                        new[r.head.pred].add(tuple(_value(a, env) for a in r.head.args))
            for pred, ts in new.items():
                fresh = ts - db.rel[pred]
                if fresh:
                    db.rel[pred] |= fresh
                    changed = True
    return db.rel
