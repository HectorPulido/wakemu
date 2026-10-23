import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_effect_area_targets import area_targets
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_simple_area import simple_area_constructor
from wakfu_server.combat_stat_handler import StatExecutionContext


def simple_definition():
    return dict(
        type="SIMPLE",
        native_class="bcW",
        native_type_id=6,
        native_container_type=3,
        raw_bcR=True,
        raw_bde=2,
        native_area_properties=[],
        native_fight_properties=[],
        properties=[],
        entry_masks=[],
        exit_masks=[],
        native_shape_class="anD",
        native_shape_description="point",
        native_hour_contract=False,
    )


def simple_row(identity, owner_id, definition, *, affiliation=None):
    row = dict(
        uid=identity,
        reference=314,
        level=1,
        cell=(identity % 5, 2, 0),
        owner_id=owner_id,
        direction=3,
        native_area_contract="fbb",
        native_type_id=6,
        native_simple_constructor=simple_area_constructor(definition),
        native_running_effect_manager=False,
        native_obstacle_id=-1,
        native_qq_bhi=False,
        native_qq_guard_source="Qq.constructor",
    )
    if affiliation is not None:
        row["native_fight_affiliation"] = affiliation
        row["native_fight_affiliation_source"] = "faV.j(PV).bcM"
    return row


class NativeAreaOwnerPVTests(unittest.TestCase):
    def test_active_and_retained_area_owners_are_validated_and_unknown_owner_rejects(
        self,
    ):
        definition = simple_definition()
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=1, team=0)
        owner = simple_row(901, 7, definition)
        target = simple_row(902, 901, definition, affiliation=0)
        fight = SimpleNamespace(
            actors={7: actor},
            native_effect_areas={901: owner, 902: target},
            native_retired_area_managers={},
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"314": definition},
        ):
            active = {target.id: target for target in area_targets(fight)}
            self.assertEqual(active[902].owner_id, 901)
            self.assertEqual(active[902].team, 0)

            del fight.native_effect_areas[901]
            fight.native_retired_area_managers[901] = owner
            retained = {target.id: target for target in area_targets(fight)}
            self.assertEqual(tuple(retained), (902,))
            self.assertEqual(retained[902].owner_id, 901)

            target["owner_id"] = 999
            with self.assertRaisesRegex(ValueError, "authoritative Qq owner"):
                area_targets(fight)
        self.assertEqual(fight.native_effect_areas, {902: target})
        self.assertEqual(fight.native_retired_area_managers, {901: owner})

    def test_area_creation_inherits_direction_from_registered_area_caster(self):
        from wakfu_server.combat_native_timing_context import native_time_payload

        definition = simple_definition()
        owner = simple_row(901, 7, definition)
        owner["cell"] = (2, 3, 0)
        owner["direction"] = 3
        fight = SimpleNamespace(
            id=77,
            actors={7: SimpleNamespace(id=7, position=(0, 0, 0), direction=1, team=0)},
            native_effect_areas={901: owner},
        )
        packets = []
        uid_calls = []
        area_calls = []
        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: uid_calls.append(71) or 71,
            allocate_area_uid=lambda: area_calls.append(902) or 902,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, native_time_payload(), None
            ),
            container=lambda invocation: (dict(container_type=3), 701),
            area_affiliation=lambda *_: 0,
        )
        handler.on_created = lambda row: None
        with patch(
            "wakfu_server.combat_delivery_owners.owner_catalog",
            return_value={"effects": {"315": dict(runner="eYQ", bbA=True, bbB=True)}},
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"314": definition},
        ):
            self.assertTrue(
                handler(
                    {"effect_class": 315},
                    {"parameters": [314, 4]},
                    EffectInvocation(500, 4, 901, None, (5, 5, 0)),
                )
            )
        created = fight.native_effect_areas[902]
        self.assertEqual(created["direction"], 3)
        self.assertEqual((uid_calls, area_calls), ([71], [902]))
        self.assertNotIn(901, fight.actors)
        self.assertEqual(len(packets), 1)
