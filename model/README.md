# Model

The authority rules of Cardinal Core, as a program a machine can check.

| File | What it is |
|---|---|
| [rules.md](rules.md) | **Normative.** The identity and space validity rules, in a small stratified logic notation, with prose |
| [datalog.py](datalog.py) | Parser, stratification checker, and evaluator for that notation |
| [world.py](world.py) | Abstract entries (no bytes, no signatures), the input facts the rules read, evaluation of identities and spaces, and the guardian software rule (`may_confirm`) |
| [check.py](check.py) | Checks that the rules are stratified: one result for any set of entries |
| [scenarios.py](scenarios.py) | One scenario per review finding that still applies, with the outcome the rules must give |
| [fuzz.py](fuzz.py) | Random histories with honest actors, thieves and strangers, including identities that guard each other, checked against determinism and against what the rules are for |

Python 3, standard library only. From the repository root:

```
python3 model/check.py
python3 model/scenarios.py
python3 model/fuzz.py [identity-cases] [space-cases] [seed] [guardian-web-cases] [honest-cases]
```

The defaults run 300 adversarial identity histories, 300 honest identity
histories, 300 space histories and 150 guardian webs, in about seven
minutes, and then compare results under three Python hash seeds in
separate processes.

## What the fuzzer checks

| Property | Statement |
|---|---|
| D | The same result however entries are ordered, and under different Python hash seeds |
| M | Freezing and decisions in effect only accumulate; in spaces, a signature by an author who is not frozen keeps counting |
| R | If not frozen, every key in effect was kept by the latest recovery or added after it, and every root descends from it |
| B | Nothing valid by a removed key is outside the removal's past; nothing valid descends from the end of its membership |
| A | Every valid space entry has an author whose key counted |
| H | Guardians following the chain rule, with partial views of each other and an honest owner whose devices are partitioned, never freeze an identity, whatever thieves do |
| O | An owner whose keys are not stolen keeps its membership and every entry it wrote, in the whole and in every closed subset |
| P | Every removal in effect goes strictly down in power, except a root replacing itself and a recovery |
| K | A key removed by a recovery gains nothing: everything valid it signed is in the recovery's past, and no decision it signed after is in effect, except a change it only proposed that guardians approved |
| E | Voiding every space entry of one identity never makes valid an entry under a membership of equal or higher role than any it held; a non-member's entries never matter |
| F | Every entry by an author who is not frozen that is valid when no one is treated as frozen is valid |

Each fix for the cold review of this program (V1–V11) was checked by
putting the flaw back and confirming that the fuzzer or a scenario finds
it. One boundary, a change counted dead one confirmation too early, is
caught only by a scenario.

**Blind spots.** The fuzzer does not model epochs, encryption or the state
tree; honest owners never drop all their guardians in the H histories,
because without guardians a phrase thief may freeze the identity by
design; E judges one identity at a time, so collusion between two lower
members is not covered; and the hash-seed check compares a sample of
twenty histories of each kind.

## Why a program

Four reviews of the prose found sets of entries with no consistent reading,
or with two. Rules that say "not" can loop through each other, and nobody
can see that by reading. A **stratified** program cannot: it works in
layers, each layer only adds facts, and "not" may refer only to an earlier
layer. Such a program has exactly one result. `check.py` verifies the
layering, so the question "is there one answer?" is settled by a machine.

What the machine cannot settle is whether the rules say the right thing.
That is what the scenarios and the fuzzer's intent properties are for
([decisions.md](../decisions.md) D35). The fuzzer has found flaws the
reviews missed (D33, and the guarded-change signer noted under K).

## What the model leaves out

Bytes, signatures, encryption, epochs, and the state tree. A signature is
modeled by an entry's `signer` field, which the fuzzer gives only to actors
holding that key. The model covers exactly the question that kept going
wrong: who has authority, given a set of entries.
