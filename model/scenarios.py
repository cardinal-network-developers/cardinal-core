"""Targeted scenarios: each review finding that still applies, with the
outcome the rules must give.

    python3 model/scenarios.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import Builder  # noqa: E402

SCENARIOS = []


def scenario(fn):
    SCENARIOS.append(fn)
    return fn


def guarded(b, name="I", threshold=2):
    """Identity with root R0, admin A0, device D0, and guardians G1-G3."""
    for g in ("G1", "G2", "G3"):
        b.identity(g, "r" + g, admin="a" + g, devices=("d" + g,))
    b.identity(name, "R0", admin="A0", devices=("D0",),
               guardians=("G1", "G2", "G3"), threshold=threshold)


def unguarded(b, name="I"):
    b.identity(name, "R0", admin="A0", devices=("D0",))


def confirm(b, g, name, decision, signer=None, parents=None):
    return b.write(g, name, signer or "a" + g, [("confirm", decision)], parents)


def keys(r):
    return {k for (k,) in r["effective"]}


def roots(r):
    return {k for (k,) in r["root_eff"]}


def effect(r):
    return {d for (d,) in r["in_effect"]}


# ------------------------------------------------------------ identity

@scenario
def recovery_takes_effect():
    b = Builder()
    guarded(b)
    b.write("I", "rec", "N", [("recover", "N", ("D0",), "I")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    r = b.ident("I")
    assert "rec" in effect(r) and roots(r) == {"N"}, r
    assert keys(r) == {"D0"}, keys(r)
    assert not r["frozen"]


@scenario
def T13_one_guardian_alone_does_nothing():
    b = Builder()
    guarded(b)
    b.write("I", "rec", "N", [("recover", "N", (), "I")])
    confirm(b, "G1", "c1", "rec")
    r = b.ident("I")
    assert not effect(r) and roots(r) == {"R0"} and not r["contested"] and not r["frozen"]


@scenario
def T6_objection_changes_nothing():
    b = Builder()
    guarded(b)
    b.write("I", "rec", "N", [("recover", "N", (), "I")])
    b.write("I", "obj", "A0", [("object", "rec")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    assert "rec" in effect(b.ident("I"))


@scenario
def U1_conflicting_recovery_freezes_never_revives():
    b = Builder()
    guarded(b)
    b.write("I", "rec1", "N1", [("recover", "N1", (), "I")])
    confirm(b, "G1", "c1", "rec1")
    confirm(b, "G2", "c2", "rec1")
    before = b.ident("I")
    assert "rec1" in effect(before) and not before["frozen"]
    # years later: G2's stolen device and G3 confirm a recovery that does not
    # know the first
    b.write("I", "rec2", "N2", [("recover", "N2", ("A0",), "I")], parents=["I"])
    confirm(b, "G2", "c2b", "rec2", signer="dG2")
    confirm(b, "G3", "c3", "rec2")
    after = b.ident("I")
    assert after["frozen"], "equivocating guardians must freeze, not revive"
    assert "rec1" in effect(after)


@scenario
def U1B_guardian_change_hostage_freezes():
    b = Builder()
    guarded(b)
    b.write("I", "s1", "A0", [("policy", "I", ("G1", "G2", "G3"), 2)])
    confirm(b, "G1", "c1", "s1")
    confirm(b, "G2", "c2", "s1")
    b.write("I", "s2", "A0", [("policy", "I", ("X1", "X2", "X3"), 2)], parents=["I"])
    confirm(b, "G2", "c2b", "s2", signer="dG2")
    confirm(b, "G3", "c3", "s2")
    assert b.ident("I")["frozen"]


@scenario
def T2_former_guardians_after_change_can_only_freeze():
    b = Builder()
    guarded(b)
    for h in ("H1", "H2", "H3"):
        b.identity(h, "r" + h, admin="a" + h)
    b.write("I", "s", "A0", [("policy", "I", ("H1", "H2", "H3"), 2)])
    confirm(b, "G1", "c1", "s")
    confirm(b, "G2", "c2", "s")
    b.write("I", "rec", "N", [("recover", "N", (), "I")])          # after s
    confirm(b, "G1", "c1b", "rec")
    confirm(b, "G2", "c2b", "rec")
    r = b.ident("I")
    assert "s" in effect(r) and r["frozen"]


@scenario
def T2_former_guardians_backdating_can_only_freeze():
    b = Builder()
    guarded(b)
    for h in ("H1", "H2", "H3"):
        b.identity(h, "r" + h, admin="a" + h)
    b.write("I", "s", "A0", [("policy", "I", ("H1", "H2", "H3"), 2)])
    confirm(b, "G1", "c1", "s")
    confirm(b, "G2", "c2", "s")
    b.write("I", "rec", "N", [("recover", "N", (), "I")], parents=["I"])
    confirm(b, "G1", "c1b", "rec")
    confirm(b, "G2", "c2b", "rec")
    assert b.ident("I")["frozen"]


@scenario
def U2_confirmation_after_device_removal_does_not_count():
    b = Builder()
    guarded(b)
    b.write("G1", "g1rm", "aG1", [("rem", "dG1")])
    b.write("I", "rec", "N", [("recover", "N", (), "I")])
    confirm(b, "G1", "c1", "rec", signer="dG1")                   # after removal
    confirm(b, "G2", "c2", "rec")
    assert "rec" not in effect(b.ident("I"))


@scenario
def U2_concession_backdated_stolen_guardian_device_counts():
    # A stolen guardian device that confirms with old parents casts that
    # guardian's vote. A majority of guardians is still needed.
    b = Builder()
    guarded(b)
    b.write("G1", "g1rm", "aG1", [("rem", "dG1")])
    b.write("I", "rec", "N", [("recover", "N", (), "I")])
    confirm(b, "G1", "c1", "rec", signer="dG1", parents=["G1"])
    confirm(b, "G2", "c2", "rec")
    assert "rec" in effect(b.ident("I"))


@scenario
def U3_backdated_root_cannot_strip_admins():
    b = Builder()
    guarded(b)
    b.write("I", "own", "R0", [("add", "R1", 3), ("rem", "R0")])
    b.write("I", "thief", "R0", [("add", "R2", 3), ("rem", "R0")], parents=["I"])
    b.write("I", "strip", "R2", [("rem", "A0")], parents=["thief"])
    r = b.ident("I")
    assert r["contested"] and not r["frozen"]
    assert "A0" in keys(r), "a contestant's ops must wait"
    assert r["current_key"] == {("I",)}
    # guardians settle it, choosing parents that leave out the thief
    b.write("I", "rec", "N", [("recover", "N", ("A0", "D0"), "I")], parents=["own"])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    r = b.ident("I")
    assert not r["contested"] and roots(r) == {"N"} and "A0" in keys(r)
    assert ("strip",) not in r["valid"]


@scenario
def U3_without_guardians_a_contest_freezes():
    b = Builder()
    unguarded(b)
    b.write("I", "own", "R0", [("add", "R1", 3), ("rem", "R0")])
    b.write("I", "thief", "R0", [("add", "R2", 3), ("rem", "R0")], parents=["I"])
    assert b.ident("I")["frozen"]


@scenario
def concession_old_phrase_from_before_guardians_can_freeze():
    b = Builder()
    unguarded(b)
    for g in ("G1", "G2", "G3"):
        b.identity(g, "r" + g, admin="a" + g)
    b.write("I", "s", "R0", [("policy", "I", ("G1", "G2", "G3"), 2)])
    b.write("I", "own", "R0", [("add", "R1", 3), ("rem", "R0")])
    # a thief holding the old phrase forks the root: guardians can settle that
    b.write("I", "thief", "R0", [("add", "R2", 3), ("rem", "R0")], parents=["I"])
    r = b.ident("I")
    assert r["contested"] and not r["frozen"]
    # but naming rival guardians under the old, guardian-less policy freezes
    b.write("I", "s2", "R2", [("policy", "I", ("X1", "X2", "X3"), 2)], parents=["thief"])
    assert b.ident("I")["frozen"]


@scenario
def F3_guardians_named_after_an_unguarded_fork_freeze():
    b = Builder()
    unguarded(b)
    for g in ("G1", "G2", "G3"):
        b.identity(g, "r" + g, admin="a" + g)
    b.write("I", "own", "R0", [("add", "R1", 3), ("rem", "R0")])
    b.write("I", "thief", "R0", [("add", "R2", 3), ("rem", "R0")], parents=["I"])
    assert b.ident("I")["frozen"]
    b.write("I", "s", "R1", [("policy", "I", ("G1", "G2", "G3"), 2)], parents=["own", "thief"])
    assert b.ident("I")["frozen"], "freezing must be monotone"


@scenario
def kept_key_work_concurrent_with_recovery_is_revoked():
    # found by the fuzzer: a thief holding a kept admin key added a key with
    # old parents, and it survived the recovery
    b = Builder()
    guarded(b)
    b.write("I", "rec", "N", [("recover", "N", ("A0",), "I")])
    b.write("I", "t", "A0", [("add", "K9", 2)], parents=["I"])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    b.write("I", "after", "A0", [("add", "D9", 1)], parents=["rec"])
    r = b.ident("I")
    assert "K9" not in keys(r) and {"A0", "D9"} <= keys(r), keys(r)


@scenario
def late_approval_of_a_change_freezes_rather_than_undoes():
    # found by the fuzzer: a change approved by confirmations that arrived
    # late used to switch off a recovery already in effect
    b = Builder()
    guarded(b)
    b.write("I", "s", "A0", [("policy", "I", (), 0)])
    b.write("I", "rec", "N", [("recover", "N", (), "I")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    early = b.ident("I")
    assert "rec" in effect(early) and not early["frozen"]
    confirm(b, "G2", "c2s", "s")
    confirm(b, "G3", "c3s", "s")
    late = b.ident("I")
    assert "rec" in effect(late) and late["frozen"]


@scenario
def U5a_kept_key_can_be_removed_later():
    b = Builder()
    guarded(b)
    b.write("I", "rec", "N", [("recover", "N", ("D0",), "I")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    b.write("I", "n1", "N", [("add", "A1", 2)])
    b.write("I", "n2", "A1", [("rem", "D0")])
    r = b.ident("I")
    assert keys(r) == {"A1"}, keys(r)


@scenario
def U5b_keep_overrides_an_earlier_removal():
    b = Builder()
    guarded(b)
    b.write("I", "x", "A0", [("rem", "D0")])
    b.write("I", "rec", "N", [("recover", "N", ("D0",), "I")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    b.write("I", "after", "D0", [("confirm", "nothing")])
    r = b.ident("I")
    assert "D0" in keys(r) and ("after",) in r["valid"]


@scenario
def U5c_keys_added_after_a_recovery_stay():
    b = Builder()
    guarded(b)
    b.write("I", "rec", "N", [("recover", "N", (), "I")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    b.write("I", "n1", "N", [("add", "D9", 1)])
    assert keys(b.ident("I")) == {"D9"}


@scenario
def U6_policy_change_and_recovery_have_one_reading():
    b = Builder()
    b.identity("G", "rG", admin="aG")
    b.identity("H", "rH", admin="aH")
    b.identity("I", "R0", admin="A0", guardians=("G",), threshold=1)
    b.write("I", "X", "R0", [("add", "R1", 3), ("rem", "R0")])
    b.write("I", "S", "R1", [("policy", "I", ("H",), 1)])
    confirm(b, "G", "cS", "S")
    b.write("I", "Rec", "N", [("recover", "N", (), "S")])
    confirm(b, "H", "cR", "Rec")
    r = b.ident("I")
    assert {"S", "Rec"} <= effect(r) and roots(r) == {"N"} and not r["frozen"]


@scenario
def U14_one_guardians_two_devices_confirming_both_sides_freezes():
    b = Builder()
    guarded(b)
    b.write("I", "rec1", "N1", [("recover", "N1", (), "I")])
    b.write("I", "rec2", "N2", [("recover", "N2", (), "I")], parents=["I"])
    confirm(b, "G1", "c1", "rec1", signer="aG1")
    confirm(b, "G1", "c1b", "rec2", signer="dG1", parents=["G1"])
    confirm(b, "G2", "c2", "rec1")
    confirm(b, "G3", "c3", "rec2")
    assert b.ident("I")["frozen"]


@scenario
def T4_retired_admin_cannot_backdate():
    b = Builder()
    unguarded(b)
    b.write("I", "rm", "R0", [("rem", "A0")])
    b.write("I", "late", "A0", [("add", "D9", 1)], parents=["I"])
    r = b.ident("I")
    assert "D9" not in keys(r) and ("late",) not in r["valid"]


@scenario
def T5_root_change_with_other_ops_is_invalid():
    b = Builder()
    unguarded(b)
    b.write("I", "x", "R0", [("add", "R9", 3), ("rem", "R0"), ("add", "Z", 2)])
    r = b.ident("I")
    assert roots(r) == {"R0"} and "Z" not in keys(r)


@scenario
def T9_key_whose_add_was_revoked_was_never_added():
    b = Builder()
    unguarded(b)
    b.write("I", "bad", "A0", [("add", "K3", 1)])
    b.write("I", "rm", "R0", [("rem", "A0")], parents=["I"])
    r = b.ident("I")
    assert "K3" not in keys(r) and ("bad",) not in r["valid"]


@scenario
def T21_keys_added_before_removal_stay():
    b = Builder()
    unguarded(b)
    b.write("I", "ok", "A0", [("add", "K3", 1)])
    b.write("I", "rm", "R0", [("rem", "A0")])
    assert "K3" in keys(b.ident("I"))


# ------------------------------------------------------------ spaces

def people(b, *names):
    for n in names:
        b.identity(n, "r" + n, admin="a" + n, devices=("p" + n,))


@scenario
def U7_witnessing_does_not_loop_through_membership():
    b = Builder()
    people(b, "Ana", "Bob")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "X", "Ana", "pAna", ana, [("add_member", "Bob", 1)])
    bob = "X:Bob"
    b.swrite("S", "W", "Ana", "aAna", ana, [("remove_member", bob)])
    b.write("Ana", "lost", "aAna", [("rem", "pAna")], parents=["Ana"])
    r = b.sp("S")
    assert {("X",), ("W",)} <= r["valid"] and (bob,) not in r["member"]


@scenario
def U8a_lowering_a_role_keeps_allowed_concurrent_work():
    b = Builder()
    people(b, "Ana", "Ben")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "e1", "Ana", "aAna", ana, [("add_member", "Ben", 2)])
    ben = "e1:Ben"
    b.swrite("S", "msg", "Ben", "pBen", ben, [("app",)], parents=["e1"])
    b.swrite("S", "add", "Ben", "pBen", ben, [("add_member", "Cy", 1)], parents=["e1"])
    b.swrite("S", "lower", "Ana", "aAna", ana,
             [("remove_member", ben), ("add_member", "Ben", 1)], parents=["e1"])
    b.swrite("S", "msg2", "Ben", "pBen", "lower:Ben", [("app",)], parents=["lower", "msg", "add"])
    r = b.sp("S")
    assert ("msg",) in r["valid"] and ("add",) not in r["valid"] and ("msg2",) in r["valid"]


@scenario
def U8a_removed_member_can_be_added_again():
    b = Builder()
    people(b, "Ana", "Cy")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "e1", "Ana", "aAna", ana, [("add_member", "Cy", 1)])
    b.swrite("S", "e2", "Ana", "aAna", ana, [("remove_member", "e1:Cy")])
    b.swrite("S", "old", "Cy", "pCy", "e1:Cy", [("app",)])
    b.swrite("S", "e3", "Ana", "aAna", ana, [("add_member", "Cy", 1)])
    b.swrite("S", "new", "Cy", "pCy", "e3:Cy", [("app",)])
    r = b.sp("S")
    assert ("old",) not in r["valid"] and ("new",) in r["valid"]


@scenario
def U8b_leaving_cannot_be_backdated_around():
    b = Builder()
    people(b, "Ana", "Cy")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "e1", "Ana", "aAna", ana, [("add_member", "Cy", 1)])
    b.swrite("S", "bye", "Cy", "pCy", "e1:Cy", [("remove_member", "e1:Cy")])
    b.swrite("S", "late", "Cy", "pCy", "e1:Cy", [("app",)], parents=["e1"])
    r = b.sp("S")
    assert ("bye",) in r["valid"] and ("late",) not in r["valid"]


@scenario
def succession_closes_the_old_space():
    b = Builder()
    people(b, "Ana", "Ben")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "e1", "Ana", "aAna", ana, [("add_member", "Ben", 2)])
    b.swrite("S", "concurrent", "Ben", "pBen", "e1:Ben", [("app",)], parents=["e1"])
    b.swrite("S", "succ", "Ana", "aAna", ana, [("succeed",)], parents=["e1"])
    b.swrite("S", "after", "Ben", "pBen", "e1:Ben", [("app",)], parents=["succ", "concurrent"])
    b.swrite("S", "anaback", "Ana", "aAna", ana, [("app",)], parents=["e1"])
    r = b.sp("S")
    assert ("concurrent",) in r["valid"] and ("after",) not in r["valid"]
    assert ("anaback",) not in r["valid"]


@scenario
def U9_adding_an_existing_member_changes_nothing():
    b = Builder()
    people(b, "Ana", "Ben")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "e1", "Ana", "aAna", ana, [("add_member", "Ben", 2)])
    b.swrite("S", "e2", "Ben", "pBen", "e1:Ben", [("add_member", "Ana", 0)])
    b.swrite("S", "e3", "Ana", "aAna", ana, [("app",)])
    r = b.sp("S")
    assert ("e3",) in r["valid"] and (ana,) in r["member"]


@scenario
def T3_owners_cannot_remove_owners():
    b = Builder()
    people(b, "Ana", "Ben")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "e1", "Ana", "aAna", ana, [("add_member", "Ben", 3)])
    b.swrite("S", "coup", "Ben", "pBen", "e1:Ben", [("remove_member", ana)], parents=["S"] and ["e1"])
    b.swrite("S", "e2", "Ana", "aAna", ana, [("app",)], parents=["e1"])
    r = b.sp("S")
    assert ("coup",) not in r["valid"] and ("e2",) in r["valid"] and (ana,) in r["member"]


@scenario
def removed_device_entries_need_a_witness():
    b = Builder()
    people(b, "Ana")
    ana = b.space("S", "Ana", "aAna")
    b.swrite("S", "p1", "Ana", "pAna", ana, [("app",)])           # seen by the laptop
    b.swrite("S", "w", "Ana", "aAna", ana, [("app",)])
    b.swrite("S", "p2", "Ana", "pAna", ana, [("app",)], parents=["p1"])   # never seen
    b.write("Ana", "rm", "aAna", [("rem", "pAna")])
    r = b.sp("S")
    assert ("p1",) in r["valid"] and ("p2",) not in r["valid"]
    b.swrite("S", "k", "Ana", "aAna", ana, [("keep", "pAna", ("p2",))], head="rm")
    assert ("p2",) in b.sp("S")["valid"]


@scenario
def U13_keep_after_recovery_from_nothing():
    b = Builder()
    guarded(b, "Ana")
    ana = b.space("S", "Ana", "A0")
    b.swrite("S", "old", "Ana", "D0", ana, [("app",)])
    b.write("Ana", "rec", "N", [("recover", "N", (), "Ana")])
    confirm(b, "G1", "c1", "rec")
    confirm(b, "G2", "c2", "rec")
    b.write("Ana", "n1", "N", [("add", "A9", 2)])
    r = b.sp("S")
    assert ("old",) not in r["valid"] and ("S",) not in r["valid"]
    b.swrite("S", "k", "Ana", "A9", ana,
             [("keep", "D0", ("old",)), ("keep", "A0", ("S",))], head="n1")
    r = b.sp("S")
    assert {("S",), ("old",), ("k",)} <= r["valid"], r["valid"]


@scenario
def frozen_author_writes_nothing():
    b = Builder()
    people(b, "Ana")
    b.identity("Tom", "R0", admin="aTom")
    b.write("Tom", "own", "R0", [("add", "R1", 3), ("rem", "R0")])
    tom = b.space("S", "Tom", "aTom", head="Tom")
    b.write("Tom", "thief", "R0", [("add", "R2", 3), ("rem", "R0")], parents=["Tom"])
    assert ("S",) not in b.sp("S")["valid"]


def main():
    failed = 0
    for fn in SCENARIOS:
        try:
            fn()
            print(f"ok    {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"{len(SCENARIOS) - failed}/{len(SCENARIOS)} scenarios pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
