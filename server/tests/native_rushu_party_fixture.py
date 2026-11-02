"""Declared ordinary230 Rushu cohort; inventory is a pre-fight fixture premise.

This preserves the qualified Feca/four-Iop/Eniripsa build exactly. The existing
native_paid_party_fixture owns inventory, build validation and constructor/Ready;
no fight actors, HP, states or resources are edited by this helper.
"""


def declared_builds():
    from native_paid_party_fixture import NativeGear, NativePartyBuild

    refs = (
        (20722, 3),
        (20723, 5),
        (20724, 13),
        (20725, 0),
        (20726, 12),
        (20727, 4),
        (20728, 7),
        (20729, 15),
        (20730, 8),
    )
    tank = NativePartyBuild(
        breed=1,
        level=230,
        active_spells=(
            6968,
            6969,
            6971,
            6972,
            6977,
            6978,
            6979,
            6980,
            6982,
            6983,
            6984,
            6986,
        ),
        passive_spells=(6991, 6995, 6997, 7004, 7005, 5144),
        aptitudes=((1, 48), (16, 10), (35, 1), (2, 1), (3, 1), (4, 1), (5, 1)),
        gear=tuple(NativeGear(ref, slot, damage_mask=26) for ref, slot in refs),
    )
    healer = NativePartyBuild(
        breed=7,
        level=230,
        active_spells=(625, 627, 638, 779, 780, 781, 782, 1533, 1534, 1535, 1538, 7985),
        passive_spells=(1415, 1536, 5146, 7991, 7987, 4957),
        aptitudes=(
            (1, 48),
            (16, 10),
            (30, 40),
            (23, 18),
            (14, 58),
            (2, 1),
            (3, 1),
            (38, 1),
            (4, 1),
            (5, 1),
        ),
        gear=tuple(
            NativeGear(29635, slot)
            if slot == 15
            else NativeGear(ref, slot, damage_mask=14)
            for ref, slot in refs
        ),
    )
    from dataclasses import replace

    tank = replace(tank, passive_spells=(6991, 6995, 6997, 7004, 7005, 5145))
    damage = replace(
        tank,
        breed=8,
        active_spells=(
            4775,
            4776,
            4777,
            4778,
            4779,
            4780,
            4781,
            4783,
            4786,
            4789,
            4790,
            4794,
        ),
        passive_spells=(4795, 4796, 8415, 8416, 8420, 5144),
        aptitudes=(
            (1, 48),
            (16, 10),
            (26, 40),
            (23, 18),
            (19, 58),
            (9, 20),
            (11, 38),
            (2, 1),
            (3, 1),
            (35, 1),
            (8, 1),
            (4, 1),
        ),
        gear=tuple(
            NativeGear(ref, slot, damage_mask=mask)
            for ref, slot, mask in (
                (29454, 0, 26),
                (29472, 3, 0),
                (29527, 4, 0),
                (29466, 5, 10),
                (29455, 7, 10),
                (23984, 8, 26),
                (29531, 10, 10),
                (29545, 12, 26),
                (29462, 13, 0),
                (29625, 15, 26),
                (23994, 17, 26),
            )
        ),
    )
    return tank, damage, damage, damage, damage, healer
