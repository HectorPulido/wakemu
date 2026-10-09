import unittest
from types import SimpleNamespace

from wakfu_server.combat_wall_area import (
    update_wall_hp,
    verified_wall_constructor,
    wall_constructor,
    wall_damage_snapshot,
)


def definition(parameters):
    return {
        "type": "WALL",
        "native_class": "bcZ",
        "native_type_id": 7,
        "native_container_type": 3,
        "raw_bdh": parameters,
    }


class NativeWallConstructorTests(unittest.TestCase):
    def test_installed_wall_definition_uses_constructor_qf_without_property12(self):
        from wakfu_server.combat_effect_area import native_effect_areas

        native = native_effect_areas()["1605"]
        facts = wall_constructor(native, 30)
        self.assertEqual(native["native_class"], "bcZ")
        self.assertEqual(native["native_type_id"], 7)
        self.assertEqual(native["raw_bdh"], [0.0, 0.0, 1.0, 0.0])
        self.assertNotIn(12, native["native_area_properties"])
        self.assertEqual(facts["hp"], 0)
        self.assertTrue(facts["mandatory_qf"])
        self.assertTrue(facts["movement_blocking"])
        self.assertFalse(facts["los_blocking"])

    def test_constructor_facts_keep_hp_movement_los_and_qf_sources_distinct(self):
        facts = wall_constructor(definition([10.5, 2.25, 1, 0]), 3)
        self.assertEqual(facts["hp"], 17)
        self.assertEqual(facts["hp_source"], "fbd.aQc.bhe[0]+cmZ()*bhe[1]")
        self.assertTrue(facts["obstacle"])
        self.assertTrue(facts["movement_blocking"])
        self.assertFalse(facts["los_blocking"])
        self.assertTrue(facts["mandatory_qf"])
        self.assertTrue(facts["running_effect_manager"])
        self.assertEqual(facts["qf_callback_channel"], 1)
        self.assertEqual(facts["bcK_value"], 6)

    def test_los_only_wall_is_obstacle_without_blocking_movement(self):
        facts = wall_constructor(definition([0, 0, 0, 1]), 1)
        self.assertTrue(facts["obstacle"])
        self.assertFalse(facts["movement_blocking"])
        self.assertTrue(facts["los_blocking"])

    def test_non_one_flags_are_false_like_native_float_comparison(self):
        facts = wall_constructor(definition([0, 0, 2, -1]), 1)
        self.assertFalse(facts["obstacle"])
        self.assertFalse(facts["movement_blocking"])
        self.assertFalse(facts["los_blocking"])

    def test_java_float32_formula_truncates_and_saturates(self):
        self.assertEqual(wall_constructor(definition([5.9, -2.0, 0, 0]), 2)["hp"], 1)
        self.assertEqual(
            wall_constructor(definition([1e30, 0, 0, 0]), 2)["hp"], 2147483647
        )
        self.assertEqual(
            wall_constructor(definition([-1e30, 0, 0, 0]), 2)["hp"], -2147483648
        )

    def test_incomplete_or_mismatched_native_authority_rejects(self):
        for candidate, level in (
            ({**definition([1, 2, 1]), "raw_bdh": [1, 2, 1]}, 1),
            ({**definition([1, 2, 1, 0]), "native_class": "faW"}, 1),
            ({**definition([1, 2, 1, 0]), "native_type_id": 15}, 1),
            (definition([1, 2, True, 0]), 1),
            (definition([1, 2, 0, 0]), 32768),
        ):
            with self.subTest(candidate=candidate, level=level):
                with self.assertRaises(ValueError):
                    wall_constructor(candidate, level)

    def test_registered_wall_requires_exact_constructor_and_qi_checkpoint(self):
        source = definition([1, 0, 1, 0])
        expected = wall_constructor(source, 2)
        row = {
            "native_area_contract": "fbd",
            "native_type_id": 7,
            "native_running_effect_manager": True,
            "level": 2,
            "native_wall_constructor": expected,
            "native_wall_hp_current": expected["hp_initial"],
            "native_wall_hp_source": "fbd.PA.sgC.aYS",
            "native_obstacle_id": 4,
            "native_obstacle_source": "QI.f(QK)",
        }
        self.assertEqual(verified_wall_constructor(row, source), expected)
        update_wall_hp(row, expected, 1)
        self.assertEqual(verified_wall_constructor(row, source), expected)
        changed = dict(row, native_wall_constructor=dict(expected, los_blocking=True))
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            verified_wall_constructor(changed, source)
        missing_slot = dict(
            row, native_obstacle_id=-1, native_obstacle_source="fbm.constructor"
        )
        with self.assertRaisesRegex(ValueError, "QI obstacle"):
            verified_wall_constructor(missing_slot, source)
        invalid_hp = dict(row, native_wall_hp_current=2)
        with self.assertRaisesRegex(ValueError, "current HP"):
            verified_wall_constructor(invalid_hp, source)

    def test_damage_snapshot_uses_only_fbd_characteristics_and_mutable_pa_hp(self):
        from wakfu_server.combat_effect_area import native_effect_areas

        source = native_effect_areas()["1063"]
        constructor = wall_constructor(source, 30)
        row = {
            "native_area_contract": "fbd",
            "native_type_id": 7,
            "native_running_effect_manager": True,
            "level": 30,
            "native_wall_constructor": constructor,
            "native_wall_hp_current": constructor["hp_initial"],
            "native_wall_hp_source": "fbd.PA.sgC.aYS",
            "native_obstacle_id": 0,
            "native_obstacle_source": "QI.f(QK)",
        }

        snapshot = wall_damage_snapshot(row, source)
        self.assertGreater(snapshot["maximum_hp"], 0)
        self.assertEqual(snapshot["stats"][1], snapshot["current_hp"])
        self.assertEqual(set(snapshot["stats"]), {1, 17, 27, 28, 29, 30, 31, 49, 95})
        self.assertEqual(snapshot["absent_actor_absorption_stats"], (92, 97, 100))
        update_wall_hp(row, constructor, snapshot["current_hp"] - 17)
        damaged = wall_damage_snapshot(row, source)
        self.assertEqual(damaged["current_hp"], snapshot["current_hp"] - 17)
        self.assertEqual(damaged["maximum_hp"], snapshot["maximum_hp"])
        self.assertEqual(damaged["stats"][17], 0)

    def test_actual_wall_area_creation_registers_qi_and_constructor_qf(self):
        from wakfu_server.combat_effect_area import (
            NativeEffectAreaHandler,
            native_effect_areas,
            remove_owned_hour_area,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_state_managers import registered_area_pv, state_manager
        from wakfu_server.combat_stat_handler import StatExecutionContext

        fight = SimpleNamespace(
            id=77,
            actors={7: SimpleNamespace(id=7, position=(0, 0, 0), direction=0, team=0)},
            native_effect_areas={},
            native_qi_snapshot=dict(x=0, y=0, width=4, height=4, cell_masks=[0] * 16),
            native_qi_slots=[None] * 127,
            native_qi_touched_cells=[],
            native_qi_byte_topology={},
        )
        allocated, packets = [], []

        def allocate():
            uid = 901 + len(allocated)
            allocated.append(uid)
            return uid

        def register(preview, row, constructor):
            if row is None:
                return None
            registry = NativeQIRegistry(
                preview.native_qi_snapshot,
                preview.native_qi_slots,
                touched_cells=preview.native_qi_touched_cells,
                byte_topology=preview.native_qi_byte_topology,
            )
            slot = registry.register(
                dict(
                    identity=("effect_area", row["uid"]),
                    position=row["cell"][:2],
                    radius=0,
                    indexed=False,
                    movement_blocking=constructor["movement_blocking"],
                )
            )
            preview.native_qi_slots = registry.serialized_slots()
            preview.native_qi_touched_cells = registry.serialized_cells()
            preview.native_qi_byte_topology = registry.serialized_byte_topology()
            return slot

        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
            area_affiliation=lambda *args: 0,
            area_obstacle_register=register,
        )
        handler.on_created = lambda row: None
        effect = {"effect_class": 339}
        self.assertTrue(
            handler(
                effect,
                {"parameters": [1605]},
                EffectInvocation(100, 30, 7, None, (2, 3, 0)),
            )
        )
        row = fight.native_effect_areas[901]
        source = native_effect_areas()["1605"]
        constructor = verified_wall_constructor(row, source)
        self.assertEqual(allocated, [901, 902])
        self.assertEqual(row["native_area_contract"], "fbd")
        self.assertEqual(row["native_obstacle_id"], 0)
        self.assertTrue(row["native_running_effect_manager"])
        self.assertEqual(row["native_wall_hp_current"], 0)
        self.assertTrue(constructor["mandatory_qf"])
        self.assertTrue(state_manager(fight, 901))
        self.assertTrue(registered_area_pv(fight, 901).native_running_effect_manager)
        registry = NativeQIRegistry(
            fight.native_qi_snapshot,
            fight.native_qi_slots,
            touched_cells=fight.native_qi_touched_cells,
            byte_topology=fight.native_qi_byte_topology,
        )
        self.assertEqual(registry.snapshot().U(2, 3), frozenset((0,)))
        self.assertTrue(registry.slots[0]["movement_blocking"])
        remove_owned_hour_area(fight, 901)
        self.assertIsNone(fight.native_qi_slots[0])
        self.assertEqual(row["native_obstacle_id"], -1)
        self.assertEqual(len(packets), 1)

    def test_damage_updates_wall_pa_without_actor_alias_or_hp0_qi_removal(self):
        from wakfu_server.combat_effect_area import NativeEffectAreaHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_qi_fight import (
            current_registry,
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
            register_effect_area_obstacle,
        )
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_damage_handler import (
            NativeDamageHandler,
        )
        from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
        from random import Random

        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, owner_id=1, controlled=True)
        actor.physical_radius = 0
        actor.effect_stats = {
            1: 100,
            20: 0,
            21: 0,
            22: 0,
            23: 0,
            24: 0,
            52: 0,
            92: 0,
            97: 0,
            100: 0,
        }
        actor.effect_minima = {1: 0}
        actor.effect_maxima = {1: 100, 92: 0}
        actor.effect_frozen = frozenset()
        npc = Actor(-7, 1, (3, 3, 0), 30, 0, 0, 1, 1)
        npc.physical_radius = 0
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        fight = Fight(77, [actor, npc], cells, {0: {actor.position}, 1: {npc.position}})
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        prepared = prepare_fresh_actor_slots(
            fight, physical_radii={actor.id: 0, npc.id: 0}
        )
        install_fresh_actor_slots(fight, prepared)
        fight.ready(1)

        area_packets, next_uid = [], [901]

        def allocate_area_uid():
            value = next_uid[0]
            next_uid[0] += 1
            return value

        creator = NativeEffectAreaHandler(
            fight,
            area_packets,
            action_id=1,
            allocate_uid=allocate_area_uid,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
            area_affiliation=lambda *args: 0,
            area_obstacle_register=register_effect_area_obstacle,
        )
        creator.on_created = lambda row: None
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [1063, 30, 0, 2]},
                EffectInvocation(339483, 30, actor.id, None, (2, 2, 0)),
            )
        )
        wall_id = 901
        row = fight.native_effect_areas[wall_id]
        initial_hp = row["native_wall_hp_current"]
        self.assertEqual(initial_hp, 1_000_000_000)
        slot = row["native_obstacle_id"]

        plan = {"spell_id": 6266}
        from unittest.mock import patch
        from wakfu_server.combat_ordinary_events import (
            OrdinaryDamageEvents,
            OrdinaryHealingEvents,
        )
        from wakfu_server.combat_ordinary_authority import (
            native_damage_target,
            native_facing,
        )

        event_adapter = object.__new__(OrdinaryDamageEvents)
        event_adapter.preview, event_adapter.plan = fight, plan
        event_effect = {
            "effect_class": 1,
            "native_effect_flags": [],
            "target_masks": [None, None, None, None, None, None, []],
        }
        event_invocation = EffectInvocation(100, 30, actor.id, wall_id, (2, 2, 0))
        with patch.object(OrdinaryHealingEvents, "phase", autospec=True) as phase:
            event_adapter.phase(
                event_effect,
                event_invocation,
                uid=950,
                value=25,
                channel=3,
                blocked=False,
                localization="FRONT",
            )
        event_target = native_damage_target(fight, wall_id)
        self.assertIsNot(event_target, actor)
        self.assertEqual(native_facing(actor, event_target), "BACK")
        self.assertIn(29, phase.call_args.kwargs["_event_ids"])

        authority = ordinary_cast_authority(
            actors=lambda preview, source: None,
            timing=SimpleNamespace(state=lambda *args: None),
            rng=Random(7),
            critical=False,
        )
        damage = NativeDamageHandler(
            fight,
            [],
            action_id=2,
            allocate_uid=lambda: 950,
            context=lambda effect, invocation: authority.damage(
                fight, plan, effect, invocation
            ),
            rng=lambda: 0.5,
            block_after_calculation=lambda effect, invocation: authority.damage_block(
                fight, plan, effect, invocation
            ),
        )
        effect = {
            "effect_class": 1,
            "parameters": [25, 0],
            "native_effect_flags": [],
            "native_localization_enabled": True,
        }
        invocation = EffectInvocation(100, 30, actor.id, wall_id, (2, 2, 0))
        self.assertTrue(damage(effect, {}, invocation))
        self.assertEqual(row["native_wall_hp_current"], initial_hp - 25)
        self.assertNotIn(wall_id, fight.actors)
        self.assertEqual(row["native_obstacle_id"], slot)

        effect["parameters"] = [1_100_000_000, 0]
        self.assertTrue(damage(effect, {}, invocation))
        self.assertEqual(row["native_wall_hp_current"], 0)
        self.assertEqual(row["native_obstacle_id"], slot)
        self.assertEqual(
            current_registry(fight).slots[slot]["identity"], ["effect_area", wall_id]
        )
        self.assertFalse(
            any(
                event.get("kind") == "death" and event.get("actor_id") == wall_id
                for event in fight.events
            )
        )


if __name__ == "__main__":
    unittest.main()
