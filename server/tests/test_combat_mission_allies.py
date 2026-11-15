"""Typed mission ally admission binds an exact character and room roster."""

from copy import deepcopy
import unittest

from wakfu_server.combat_mission_allies import admit, validate, MissionAlliesAdmission


def character():
    return {"id": 7, "account_id": 2, "map_id": 312, "instance_id": 99}


def room_members():
    return [
        {"id": -101 - index, "ref": 2616, "x": 5 + index, "y": 2, "z": 0}
        for index in range(3)
    ]


class CombatMissionAlliesTests(unittest.TestCase):
    def test_admission_freezes_owner_private_instance_and_exact_room(self):
        owner, members = character(), room_members()
        admission = admit(owner, members, room=1)
        self.assertIs(type(admission), MissionAlliesAdmission)
        declaration = validate(admission, owner, members)
        self.assertEqual(
            declaration["helpers"], (("tristepin", 4691, 6, "player", "self"),)
        )
        self.assertEqual(
            admission.record()["members"],
            [[-101, 2616, 5, 2, 0], [-102, 2616, 6, 2, 0], [-103, 2616, 7, 2, 0]],
        )

    def test_admission_rejects_owner_account_map_instance_and_room_mismatches(self):
        admission = admit(character(), room_members(), room=1)
        for key, value in (
            ("id", 8),
            ("account_id", 3),
            ("map_id", 527),
            ("instance_id", 100),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(admission, {**character(), key: value}, room_members())
        with self.assertRaises(ValueError):
            admit(character(), room_members(), room=2)
        with self.assertRaises(ValueError):
            admit({**character(), "instance_id": 0}, room_members(), room=1)

    def test_admission_rejects_changed_enemy_ids_species_or_positions(self):
        owner, original = character(), room_members()
        admission = admit(owner, original, room=1)
        mutations = (
            lambda rows: rows[0].update(id=-999),
            lambda rows: rows[0].update(ref=2617),
            lambda rows: rows[0].update(x=44),
            lambda rows: rows[0].update(y=-7),
            lambda rows: rows[0].update(z=1),
            lambda rows: rows[1].update(id=rows[0]["id"]),
        )
        for mutate in mutations:
            members = deepcopy(original)
            mutate(members)
            with self.subTest(members=members), self.assertRaises(ValueError):
                validate(admission, owner, members)


if __name__ == "__main__":
    unittest.main()
