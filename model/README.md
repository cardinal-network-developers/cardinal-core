# Model

The authority rules of Cardinal Core, as a program a machine can check.

| File | What it is |
|---|---|
| [rules.md](rules.md) | **Normative.** The identity and space validity rules, in a small stratified logic notation, with prose |
| [datalog.py](datalog.py) | Parser, stratification checker, and evaluator for that notation |
| [world.py](world.py) | Abstract entries (no bytes, no signatures), the input facts the rules read, and evaluation of identities and spaces |
| [check.py](check.py) | Checks that the rules are stratified: one result for any set of entries |
| [scenarios.py](scenarios.py) | One scenario per review finding that still applies, with the outcome the rules must give |
| [fuzz.py](fuzz.py) | Random adversarial histories, checked against determinism, monotone freezing, recovery, backdating, and author properties |

Python 3, standard library only. From the repository root:

```
python3 model/check.py
python3 model/scenarios.py
python3 model/fuzz.py [identity-cases] [space-cases] [seed]
```

The defaults run 1,000 of each, in a few minutes.

## Why a program

Four reviews of the prose found sets of entries with no consistent reading,
or with two. Rules that say "not" can loop through each other, and nobody
can see that by reading. A **stratified** program cannot: it works in
layers, each layer only adds facts, and "not" may refer only to an earlier
layer. Such a program has exactly one result. `check.py` verifies the
layering, so the question "is there one answer?" is settled by a machine.

What the machine cannot settle is whether the rules say the right thing.
That is what the scenarios and the fuzzer are for. The fuzzer has already
found one flaw the reviews missed ([decisions.md](../decisions.md) D33).

## What the model leaves out

Bytes, signatures, encryption, epochs, and the state tree. A signature is
modeled by an entry's `signer` field, which the fuzzer gives only to actors
holding that key. The model covers exactly the question that kept going
wrong: who has authority, given a set of entries.
