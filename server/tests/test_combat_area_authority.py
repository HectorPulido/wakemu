import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_area_authority import area_guards
from wakfu_server.combat_effect_area import (
    NativeEffectAreaHandler,
    remove_owned_hour_area,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_state_managers import state_manager
from wakfu_server.fight_checkpoint_store import snapshot


class NativeAreaGuardAuthorityTests(unittest.TestCase):
    def area_row(self, *, removed=False, source="Qq.constructor"):
        return dict(
            uid=91,
            reference=1477,
            cell=(2, 3, 0),
            owner_id=7,
            native_area_contract="faY",
            native_running_effect_manager=True,
            native_qq_bhi=removed,
            native_qq_guard_source=source,
            child_effect_uids={},
            state_ledger=StateLedger(91),
        )

    def fight(self, row):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        return SimpleNamespace(
            id=77,
            actors={7: actor},
            native_effect_areas={row["uid"]: row},
        )

    def test_false_guard_provenance_accepts_constructor_and_reset_writers(self):
        for source in ("Qq.constructor", "Qq.aWs", "Qq.aWr"):
            with self.subTest(source=source):
                fight = self.fight(self.area_row(source=source))
                self.assertEqual(
                    area_guards(fight, 91),
                    dict(baG=False, baK=False, baF=True),
                )

    def test_only_qqb_provenance_can_establish_true_removed_guards(self):
        fight = self.fight(self.area_row(removed=True, source="Qq.b"))
        self.assertEqual(area_guards(fight, 91), dict(baG=True, baK=True, baF=False))
        for removed, source in (
            (True, "Qq.constructor"),
            (True, "Qq.aWs"),
            (False, "Qq.b"),
        ):
            with self.subTest(removed=removed, source=source):
                with self.assertRaisesRegex(ValueError, "guard provenance"):
                    area_guards(
                        self.fight(self.area_row(removed=removed, source=source)), 91
                    )

    def test_legacy_unknown_and_unregistered_rows_fail_closed(self):
        legacy = self.area_row()
        legacy.pop("native_qq_bhi")
        legacy.pop("native_qq_guard_source")
        with self.assertRaisesRegex(ValueError, "guard provenance"):
            area_guards(self.fight(legacy), 91)
        with self.assertRaisesRegex(ValueError, "registered native area"):
            area_guards(SimpleNamespace(native_effect_areas={}), 91)

    def test_fresh_area_constructor_records_false_qeq_guard(self):
        definition = dict(
            reference=1477,
            type="HOUR",
            raw_bde=-1,
            effect_ids=[],
            entry_masks=[],
            exit_masks=[],
            native_shape_class="anD",
            native_hour_contract=True,
            properties=[],
            native_fight_properties=[],
            native_area_properties=[],
            native_type_id=0,
        )
        fight = self.fight(self.area_row())
        fight.native_effect_areas = {}
        next_uid = iter((901, 902))
        handler = NativeEffectAreaHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: next(next_uid),
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1477": definition},
        ), patch(
            "wakfu_server.combat_effect_area_geometry.registered_area_cells",
            return_value=frozenset({(2, 3)}),
        ):
            self.assertTrue(
                handler(
                    {"effect_class": 315},
                    {"parameters": [1477]},
                    EffectInvocation(100, 1, 7, None, (2, 3, 0)),
                )
            )
        row = fight.native_effect_areas[901]
        self.assertEqual(
            (row["native_qq_bhi"], row["native_qq_guard_source"]),
            (False, "Qq.constructor"),
        )
        self.assertIsNone(state_manager(fight, 901))
        self.assertEqual(area_guards(fight, 901), dict(baG=False, baK=False, baF=True))

    def test_qs_unregister_preserves_false_guard_through_checkpoint_snapshot(self):
        row = self.area_row()
        row["state_ledger"]._entries = (
            RunningState(1001, 6339, 1, 7, 91, -1, "target", False, (), 0, True, None),
        )
        fight = self.fight(row)
        fight.native_retained_records = {1001: {"manager_id": 91}}
        self.assertEqual(area_guards(fight, 91)["baG"], False)
        removed = remove_owned_hour_area(fight, 91)
        self.assertEqual(len(removed), 1)
        self.assertNotIn(91, fight.native_effect_areas)
        self.assertEqual(area_guards(fight, 91)["baG"], False)
        state = json.loads(json.dumps(snapshot(fight)))
        restored = SimpleNamespace(
            actors={},
            native_effect_areas=state["native_effect_areas"],
            native_retired_area_managers={
                int(uid): row
                for uid, row in state["native_retired_area_managers"].items()
            },
        )
        self.assertEqual(
            area_guards(restored, 91), dict(baG=False, baK=False, baF=True)
        )


if __name__ == "__main__":
    unittest.main()
