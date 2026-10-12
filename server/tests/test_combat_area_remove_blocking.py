"""Native1021/eXV removes only movement-blocking Qq instances."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_area_remove import movement_blocking_area, select_removal_area


class BlockingAreaRemovalTests(unittest.TestCase):
    def test_actual_bcp_contracts_and_unknown_authority(self):
        for contract, key in (
            ("faW", "native_faw_constructor"),
            ("fbd", "native_wall_constructor"),
        ):
            for value in (False, True):
                self.assertIs(
                    movement_blocking_area(
                        {
                            "native_area_contract": contract,
                            key: {"movement_blocking": value},
                        }
                    ),
                    value,
                )
            with self.assertRaisesRegex(ValueError, "constructor authority"):
                movement_blocking_area({"native_area_contract": contract})
        for contract in ("faZ", "faY", "faN", "faX", "faU", "fbc", "faP"):
            self.assertFalse(movement_blocking_area({"native_area_contract": contract}))
        with self.assertRaisesRegex(ValueError, "Unknown native"):
            movement_blocking_area({})

    def test_first_eligible_qs_area_and_explicit_no_fallback(self):
        rows = (
            dict(uid=901, reference=1759, native_area_contract="faY"),
            dict(
                uid=902,
                reference=1759,
                native_area_contract="faW",
                native_faw_constructor={"movement_blocking": True},
            ),
            dict(
                uid=903,
                reference=1759,
                native_area_contract="fbd",
                native_wall_constructor={"movement_blocking": True},
            ),
        )
        with patch("wakfu_server.combat_area_remove._rows", return_value=rows), patch(
            "wakfu_server.combat_area_remove.contains_area_cell",
            return_value=True,
        ), patch(
            "wakfu_server.combat_global_pv_collections.global_area_order",
            return_value=(901, 903, 902),
        ):
            self.assertEqual(
                select_removal_area(
                    None,
                    -1,
                    None,
                    (0, 0, 0),
                    eligible=movement_blocking_area,
                )["uid"],
                903,
            )
            self.assertIsNone(
                select_removal_area(
                    None,
                    -1,
                    901,
                    (0, 0, 0),
                    eligible=movement_blocking_area,
                )
            )
            self.assertIsNone(
                select_removal_area(
                    None,
                    1725,
                    902,
                    (0, 0, 0),
                    eligible=movement_blocking_area,
                )
            )

    def test_actual_reference_1759_uses_existing_removal_lifecycle(self):
        from test_combat_area_remove import AreaRemovalTests
        from wakfu_server.combat_area_remove import NativeAreaRemovalHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from types import SimpleNamespace

        fight = AreaRemovalTests().fixture()
        row = fight.native_effect_areas[901]
        row.update(
            reference=1759,
            native_area_contract="faW",
            native_faw_constructor={"movement_blocking": True},
        )
        packets = []
        handler = NativeAreaRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            context=lambda *args: StatExecutionContext(True, True, None, False, b""),
            container=lambda *args: ({"container_type": None}, None),
            rng=lambda: 0.5,
        )
        handler.events = SimpleNamespace(removed=lambda row: None)
        # Selection rows are isolated here; source-derived faW constructor
        # validation is independently covered by fake-fighter tests.
        with patch("wakfu_server.combat_area_remove._rows", return_value=(row,)), patch(
            "wakfu_server.combat_area_remove.native_effect_areas",
            return_value={"1759": {"raw_bdi": True}},
        ), patch(
            "wakfu_server.combat_area_remove.remove_owned_hour_area",
            side_effect=lambda fight, uid, **kwargs: fight.native_effect_areas.pop(uid),
        ) as remove:
            self.assertTrue(
                handler(
                    {"effect_class": 1021},
                    {"parameters": [1759]},
                    EffectInvocation(341885, 1, 7, 901, (0, 0, 0)),
                )
            )
            self.assertEqual(remove.call_args.args[1], 901)
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(packets[0][1][12], 1)
