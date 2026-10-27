"""Check that the rules in rules.md are stratified, safe, and consistent.

    python3 model/check.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datalog import check, read_rules  # noqa: E402

RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.md")


def main():
    programs = read_rules(RULES)
    bad = 0
    for name in ("identity", "space"):
        prog = programs.get(name)
        if prog is None:
            print(f"{name}: missing")
            bad += 1
            continue
        errors = check(prog)
        for e in errors:
            print(f"{name}: {e}")
        bad += len(errors)
        print(f"{name}: {len(prog.rules)} rules in {len(prog.strata)} layers, "
              f"{len(prog.inputs)} inputs: {'stratified' if not errors else 'NOT stratified'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
