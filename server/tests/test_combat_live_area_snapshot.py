"""Native myK snapshots for live non-retained area constructors."""
from collections import OrderedDict
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_live_area_snapshot import sections


class LiveAreaSnapshotTests(unittest.TestCase):
    def gate(self, uid, *, affiliation=1, owner=7, **extra):
        row = dict(
            uid=uid,
            reference=823,
            level=1,
            direction=3,
            cell=(uid, -4, 0),
            owner_id=owner,
            native_area_contract="faX",
            native_type_id=19,
            native_obstacle_id=-1,
            native_fight_affiliation=affiliation,
            native_fight_affiliation_source="faV.j(PV).bcM",
        )
        row.update(extra)
        return row

    def test_projects_only_live_public_fax_rows_in_native_collection_order(self):
        rows = OrderedDict(
            (
                (101, self.gate(101)),
                (102, self.gate(102)),
                (103, self.gate(103, native_private_area={"scope": "private"})),
                (104, self.gate(104, native_environment_source="terrain")),
                (105, self.gate(105)),
            )
        )
        fight = SimpleNamespace(
            native_effect_areas=rows,
            native_owned_area_effects={
                9001: dict(
                    uid=9001,
                    area_uid=102,
                    effect_class=315,
                    executed=True,
                    native_private_area=None,
                )
            },
            native_retained_records={9001: dict(effect_class=315)},
            actors={7: SimpleNamespace(id=7, team=1)},
        )
        with (
            patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={
                    "823": dict(
                        type="GATE",
                        native_class="bcS",
                        native_type_id=19,
                        effect_ids=[],
                        entry_masks=[],
                        exit_masks=[],
                    )
                },
            ),
            patch(
                "wakfu_server.combat_effective_control.effective_affiliation",
                return_value=1,
            ),
            patch(
                "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
                return_value=set(),
            ),
        ):
            result = sections(fight)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            struct.unpack_from(">qqiihqhib", result[0]),
            (823, 101, 101, -4, 0, 7, 1, 3, -1),
        )
        self.assertEqual(result[0][struct.calcsize(">qqiihqhib") :], b"")
        self.assertEqual(struct.unpack_from(">qqiihqhib", result[1])[:2], (823, 105))

    def test_faw_appearance_tracks_native_hp_presence_without_inventing_stats(self):
        row = self.gate(
            201,
            reference=120,
            native_area_contract="faW",
            native_type_id=15,
            native_obstacle_id=-1,
            native_obstacle_source="fbm.constructor",
            native_faw_constructor={"kind": 1},
        )
        fight = SimpleNamespace(
            native_effect_areas={201: row},
            native_owned_area_effects={},
            native_retained_records={},
            actors={7: SimpleNamespace(id=7, team=1)},
        )
        with (
            patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={"120": {"type": "MONSTER"}},
            ),
            patch(
                "wakfu_server.combat_effective_control.effective_affiliation",
                return_value=1,
            ),
            patch(
                "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
                return_value=set(),
            ),
            patch(
                "wakfu_server.combat_fake_fighter.verified_fake_fighter",
                return_value={"characteristic_ids": frozenset()},
            ),
        ):
            without_hp = sections(fight)
        self.assertEqual(without_hp[0][struct.calcsize(">qqiihqhib") :], b"")

        with (
            patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={"120": {"type": "MONSTER"}},
            ),
            patch(
                "wakfu_server.combat_effective_control.effective_affiliation",
                return_value=1,
            ),
            patch(
                "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
                return_value=set(),
            ),
            patch(
                "wakfu_server.combat_fake_fighter.verified_fake_fighter",
                return_value={"characteristic_ids": frozenset({1})},
            ),
            patch(
                "wakfu_server.combat_fake_fighter_resources.fake_fighter_hp_state",
                return_value={"maximum": 140, "current": 93},
            ),
        ):
            with_hp = sections(fight)
        self.assertEqual(
            with_hp[0][struct.calcsize(">qqiihqhib") :], struct.pack(">ii", 140, 93)
        )

    def test_owner_affiliation_must_match_captured_native_snapshot(self):
        fight = SimpleNamespace(
            native_effect_areas={101: self.gate(101, affiliation=0)},
            native_owned_area_effects={},
            native_retained_records={},
            actors={7: SimpleNamespace(id=7, team=1)},
        )
        with (
            patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={
                    "823": dict(
                        type="GATE",
                        native_class="bcS",
                        native_type_id=19,
                        effect_ids=[],
                        entry_masks=[],
                        exit_masks=[],
                    )
                },
            ),
            patch(
                "wakfu_server.combat_effective_control.effective_affiliation",
                return_value=1,
            ),
            patch(
                "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
                return_value=set(),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "cannot be reconstructed"):
                sections(fight)


if __name__ == "__main__":
    unittest.main()
