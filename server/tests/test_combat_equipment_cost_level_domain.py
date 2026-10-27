"""Original Apacible eYt payment execution and its bounded child-domain proof."""
from copy import copy, deepcopy
from dataclasses import replace
import os
from pathlib import Path
import unittest

from wakfu_server.combat_cost_level_group import runtime_group_level
from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_equipment_cost_level_domain import (
    child_domain_witnesses,
    parse,
)
from wakfu_server.combat_equipment_dynamic_levels import UnknownDynamicLevel
from wakfu_server.combat_movement_payment_events import (
    consume_step_payment,
    replay_movement_payment,
)


class EquipmentCostLevelDomainTests(unittest.TestCase):
    def test_original_apacible_paid_movement_preview_retry_and_cost_domain(self):
        # This fixture installs the original attachment through the configured
        # factory, owner snapshot, native PA/QI and equipment pinning path.
        from tools.sublimation_semantic_fixture import build_fixture

        manifest = Path(
            os.environ.get(
                "WAKFU_SUBLIMATION_SEMANTIC_MANIFEST",
                ".runtime/sublimation-phase1-dataset/manifest-semantic.json",
            )
        )
        fixture = build_fixture(28390, manifest)
        from wakfu_server.combat_equipment_external_contracts import (
            preflight,
            rebind_owned_equipment_producers,
        )

        container = fixture.plan["native_retained_container"]
        self.assertTrue(preflight(copy(fixture.factory), container, 1032, 5))
        raw_factory = fixture.factory._factory
        self.assertFalse(preflight(copy(raw_factory), container, 1032, 5))
        changed = copy(raw_factory)
        changed.contexts = replace(raw_factory.contexts)
        with self.assertRaisesRegex(ValueError, "changed execution authority"):
            rebind_owned_equipment_producers(raw_factory, changed)
        original = fixture.fight
        actor_id = fixture.character["id"]
        definition = fixture.compiled.source_effects["309490"]
        source_level = fixture.plan["native_retained_container"]["level"]
        witnesses = child_domain_witnesses(
            definition,
            fixture.compiled.source_effects,
            fixture.compiled.source_states,
            registry=fixture.registry,
            level=source_level,
        )
        # These interior levels would disappear in an endpoint-only proof.
        self.assertTrue({(309491, value) for value in range(128)} <= set(witnesses))
        self.assertTrue(
            all(reference == 309491 and level >= 0 for reference, level in witnesses)
        )

        for costs in ({"ap": 3, "mp": 2, "wp": 1}, {"ap": 0, "mp": -1, "wp": 0}):
            source = dict(cost_source=dict(runner_class="eWf", action_costs=costs))
            invocation = EffectInvocation(
                309490,
                20,
                actor_id,
                actor_id,
                original.actors[actor_id].position,
                native_trigger_context=source,
            )
            expected = 20 if costs["mp"] == -1 else costs["mp"]
            self.assertEqual(
                runtime_group_level(definition, {}, invocation, {}), expected
            )
        for source in (None, {"cost_source": {"runner_class": "other"}}):
            invocation = EffectInvocation(
                309490,
                20,
                actor_id,
                actor_id,
                original.actors[actor_id].position,
                native_trigger_context=source,
            )
            self.assertEqual(runtime_group_level(definition, {}, invocation, {}), 20)
        wide = deepcopy(definition)
        wide["parameters"][14] = 3.0
        sparse = parse(wide, effect_profile(wide, source_level), source_level)
        self.assertEqual(
            set(sparse["child_levels"]),
            {source_level}
            | {((3 * payment + 32768) % 65536) - 32768 for payment in range(-128, 128)},
        )
        scaled = deepcopy(definition)
        scaled["parameters"][14:16] = [0.0, 1.0]
        sparse = parse(scaled, effect_profile(scaled, source_level), source_level)
        self.assertEqual(
            set(sparse["child_levels"]),
            {source_level}
            | {
                ((source_level * payment + 32768) % 65536) - 32768
                for payment in range(-128, 128)
                if source_level * payment != -1
            },
        )
        wide["parameters"][12] = 3.0
        with self.assertRaises(UnknownDynamicLevel):
            parse(wide, effect_profile(wide, source_level), source_level)
        nonfinite = deepcopy(definition)
        nonfinite["parameters"][14] = float("inf")
        with self.assertRaises((ValueError, UnknownDynamicLevel)):
            parse(nonfinite, effect_profile(definition, source_level), source_level)

        player = original.actors[actor_id]
        origin = player.position
        occupied = {actor.position for actor in original.actors.values()}
        destinations = sorted(
            cell
            for cell in original.walkable
            if cell not in occupied
            and cell[2] == origin[2]
            and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) == 1
        )
        self.assertTrue(
            destinations, "Semantic fixture needs an actual free movement cell"
        )
        destination = destinations[0]

        def bonus_level(fight):
            return sum(
                entry.level
                for entry in fight.actors[actor_id].state_ledger.entries
                if entry.reference == 6715
            )

        self.assertEqual(bonus_level(original), 0)
        before = (player.mp, player.position, deepcopy(original.events))

        def preview(reject):
            working = deepcopy(original)
            packets = []

            def step(current, actor, origin, destination):
                policy = consume_step_payment(
                    current, actor_id=actor.id, origin=origin, path=[destination]
                )
                self.assertIsNotNone(policy)
                # Production consumption proves the paid source, then clones
                # a separate unpublished destination for effect execution.
                effect_preview = deepcopy(current)
                dispatcher, effect_packets = fixture.dispatcher_for(effect_preview)
                replay_movement_payment(dispatcher, policy)
                if reject:
                    raise ValueError("unpublished paid movement")
                with self.assertRaises(ValueError):
                    replay_movement_payment(dispatcher, policy)
                from wakfu_server.combat_area_boundary import adopt_fight

                adopt_fight(current, effect_preview)
                packets.extend(effect_packets)

            working.move(fixture.owner_id, actor_id, [destination], step_callback=step)
            return working, packets

        with self.assertRaisesRegex(ValueError, "unpublished"):
            preview(True)
        self.assertEqual((player.mp, player.position, original.events), before)
        self.assertEqual(bonus_level(original), 0)
        accepted, packets = preview(False)
        self.assertEqual(accepted.actors[actor_id].mp, before[0] - 1)
        self.assertEqual(bonus_level(accepted), 1)
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets))
        self.assertEqual(bonus_level(original), 0)
        foreign = deepcopy(original)
        with self.assertRaises(ValueError):
            foreign.move(fixture.owner_id + 1, actor_id, [destination])
        self.assertEqual(bonus_level(foreign), 0)
