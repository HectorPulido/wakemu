"""Native class/monster area scenarios execute the current spatial boundary.

Original native prerequisites/assertions and real callback/packet observations
remain intact; historical differentials run in the pinned external archive.
"""
import os
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativeSpatialPilotAreaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_feca_protection_pipeline import FecaProtectionPipelineTests

        FecaProtectionPipelineTests.setUpClass()

    @staticmethod
    def _fight_observation(fight):
        from wakfu_server.combat_reproduction_state import encode_state

        if getattr(fight, "native_rail_movement_authority", None) is not None:
            from test_combat_spatial_pilot_new_attack import native_world_observation

            # The engine deliberately rebuilds this service. Its complete
            # reviewed ordinary/summon inputs, catalog bytes and stateless NPC
            # provider identity are captured explicitly by the shared helper;
            # unknown types, callbacks or additional services still reject.
            return native_world_observation(fight)

        encoded = encode_state(fight)
        if encoded["services"]:
            raise AssertionError(
                "Native area observation contains omitted services: "
                + repr(encoded["services"])
            )
        return encoded

    def _run_native_scenario(self, case_type, method_name):
        from wakfu_server import combat_server_spell
        from wakfu_server import combat_runtime_messages
        from wakfu_server import combat_terrain
        from wakfu_server import combat_phase
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
        from wakfu_server.combat_reproduction_state import encode_state

        actual_server_runtime = combat_server_spell.server_runtime
        actual_movement = NativeAreaEventRuntime.movement
        actual_turn_start = NativeAreaEventRuntime.turn_start
        actual_removed = NativeAreaEventRuntime.removed
        actual_runtime_init = combat_runtime_messages.RuntimeMessages.__init__
        actual_authority_observer = combat_server_spell.observe_authority
        actual_local_arena = combat_terrain.local_arena
        bindings, movements, lifecycle, random_sources = [], [], [], []
        random_initial_states, clock_observations, runtimes = [], [], []
        authority_observations = []
        arena_observations = []

        def deterministic_local_arena(*args, **kwargs):
            import hashlib
            import json

            # The existing compact-arena API supports a seed. An omitted seed
            # creates Random(None), which produces different initial terrain
            # before the native scenario executes. Pin that actual fixture input,
            # never rewrite the resulting geometry or mask population.
            if kwargs.get("variation_seed") is None:
                kwargs["variation_seed"] = 17
            arena = actual_local_arena(*args, **kwargs)
            terrain = {
                "cells": sorted(arena["validated_cells"]),
                "edges": sorted(arena["valid_edges"]),
                "cell_masks": arena["cell_masks"],
            }
            arena_observations.append(
                {
                    "arguments": encode_state({"args": args, "kwargs": kwargs}),
                    "variation_seed": kwargs["variation_seed"],
                    "bounds": {
                        key: arena[key] for key in ("x", "y", "width", "height")
                    },
                    "native_qi_surface_provenance": encode_state(
                        arena["native_qi_surface_provenance"]
                    ),
                    "terrain_sha256": hashlib.sha256(
                        json.dumps(
                            terrain,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest(),
                }
            )
            return arena

        def record_actual_authority(label, value):
            authority_observations.append((label, encode_state(value)))
            return actual_authority_observer(label, value)

        def fixed_monotonic():
            clock_observations.append(("monotonic", 1000.0))
            return 1000.0

        def fixed_wall_time(label):
            clock_observations.append((label, 1700000000.0))
            return 1700000000.0

        def deterministic_runtime_init(runtime, *args, **kwargs):
            if "clock" in kwargs:
                raise AssertionError("Scenario declares an unreviewed external clock")
            actual_runtime_init(runtime, *args, clock=fixed_monotonic, **kwargs)
            runtimes.append(runtime)

        class ObservedFactory:
            def __init__(self, factory):
                self.factory = factory

            def __getattr__(self, name):
                return getattr(self.factory, name)

            def __call__(self, fight, plan):
                initial = NativeSpatialPilotAreaIntegrationTests._fight_observation(
                    fight
                )
                dispatcher, packets = self.factory(fight, plan)
                bindings.append((fight, packets, initial))
                return dispatcher, packets

        def bind_selected(*args, **kwargs):
            rng = kwargs.get("rng")
            if rng is None:
                raise AssertionError("Native scenario requires an explicit owned RNG")
            if rng is not None and not any(rng is source for source in random_sources):
                random_sources.append(rng)
                random_initial_states.append(rng.getstate())
            factory, adapter = actual_server_runtime(*args, **kwargs)
            return ObservedFactory(factory), adapter

        def record_actual_movement(runtime, target_id, *, from_cell, to_cell):
            result = actual_movement(
                runtime, target_id, from_cell=from_cell, to_cell=to_cell
            )
            movements.append(
                {
                    "target_id": target_id,
                    "from_cell": tuple(from_cell),
                    "to_cell": tuple(to_cell),
                    "result": result,
                    "state": self._fight_observation(runtime.fight),
                }
            )
            return result

        def record_actual_turn_start(runtime, target_id):
            result = actual_turn_start(runtime, target_id)
            lifecycle.append(
                {
                    "boundary": "turn_start",
                    "target_id": target_id,
                    "result": result,
                    "state": self._fight_observation(runtime.fight),
                }
            )
            return result

        def record_actual_removed(runtime, row, *, target_id=None):
            result = actual_removed(runtime, row, target_id=target_id)
            lifecycle.append(
                {
                    "boundary": "removed",
                    "area_uid": row["uid"],
                    "target_id": target_id,
                    "result": result,
                    "state": self._fight_observation(runtime.fight),
                }
            )
            return result

        # Each call constructs its own fresh native scenario from scratch.
        # Existing source assertions are executed, rather than copied into a
        # weaker recording runtime with mocked activation or removal.
        scenario = case_type(method_name)
        with (
            patch.object(combat_server_spell, "server_runtime", bind_selected),
            patch.object(NativeAreaEventRuntime, "movement", record_actual_movement),
            patch.object(
                NativeAreaEventRuntime, "turn_start", record_actual_turn_start
            ),
            patch.object(NativeAreaEventRuntime, "removed", record_actual_removed),
            patch.object(
                combat_runtime_messages.RuntimeMessages,
                "__init__",
                deterministic_runtime_init,
            ),
            patch.object(combat_runtime_messages, "wall_time", fixed_wall_time),
            patch.object(combat_phase, "wall_time", fixed_wall_time),
            patch.object(
                combat_server_spell, "observe_authority", record_actual_authority
            ),
            patch.object(combat_terrain, "local_arena", deterministic_local_arena),
        ):
            scenario.setUp()
            try:
                getattr(scenario, method_name)()
            finally:
                scenario.tearDown()
                scenario.doCleanups()
        self.assertTrue(
            movements or lifecycle, "Native scenario did not execute an area boundary"
        )
        self.assertTrue(bindings, "Native scenario did not bind a runtime")
        return {
            "movement_boundaries": movements,
            "lifecycle_boundaries": lifecycle,
            "runtime_results": [
                {
                    "initial_state": initial,
                    "state": self._fight_observation(fight),
                    "packets": tuple(packets),
                }
                for fight, packets, initial in bindings
            ],
            "rng_states": [source.getstate() for source in random_sources],
            "rng_initial_states": random_initial_states,
            "clock_observations": clock_observations,
            "runtime_authority_observations": authority_observations,
            "arena_initialization_observations": arena_observations,
            "runtime_queue_state": [
                encode_state(
                    {
                        name: value
                        for name, value in vars(runtime).items()
                        if name
                        not in {
                            "fight",
                            "clock",
                            "stats_serializer",
                            "runtime_stats_serializer",
                            "turn_end_provider",
                            "turn_start_provider",
                            "expiration_runtime_factory",
                        }
                    }
                )
                for runtime in runtimes
            ],
        }

    def _assert_native_contract(self, case_type, method_name):
        observed = self._run_native_scenario(case_type, method_name)
        if not hasattr(self, "native_observations"):
            self.native_observations = []
        self.native_observations.append({"current": observed})
        return observed

    def test_sram_repulsion_trap_recursive_monster_push_and_actual_retirement(self):
        from test_forced_displacement_areas import (
            RealRepulsionTrapForcedDisplacementTests,
        )

        observed = self._assert_native_contract(
            RealRepulsionTrapForcedDisplacementTests,
            "test_push_through_real_trap_uses_final_recursive_position_and_retires",
        )
        packets = [
            packet
            for binding in observed["runtime_results"]
            for packet in binding["packets"]
        ]
        self.assertTrue(any(opcode == 13560 for opcode, _ in packets))
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets))
        self.assertTrue(
            any(
                movement["target_id"] == -7
                for movement in observed["movement_boundaries"]
            )
        )

    def test_feca_real_empty_glyph_creation_and_paid_walking_preserve_native_masks(
        self,
    ):
        from test_feca_protection_pipeline import FecaProtectionPipelineTests

        self._assert_native_contract(
            FecaProtectionPipelineTests,
            "test_empty_glyph_movement_is_not_a_damage_trigger",
        )

    def test_feca_actual_glyph_monster_turn_damage_and_paired_area_retirement(self):
        from test_feca_protection_pipeline import FecaProtectionPipelineTests
        import random
        import struct

        class ActivatingGlyphScenario(unittest.TestCase):
            fixture = FecaProtectionPipelineTests.fixture
            active_retained_metadata = (
                FecaProtectionPipelineTests.active_retained_metadata
            )

            def exercise(self):
                from wakfu_server.combat_server_spell import (
                    prepare_server_spell,
                    prepare_server_turn_start,
                    prepare_server_turn_end,
                    server_runtime,
                )
                from wakfu_server.combat_runtime_messages import RuntimeMessages
                from tools.combat_audit_turns import advance_actual_turn
                from wakfu_server.combat_effect_area_geometry import (
                    registered_area_cells,
                )
                from wakfu_server.combat_effect_area import native_effect_areas

                fight, characters, monster, decks = self.fixture(
                    active_spells=(6967,),
                    caster_breed=1,
                    level=200,
                    caster_aptitudes=(),
                    enemy_position=(-5, -7, -1),
                )
                rng = random.Random(7)
                common = dict(
                    player_characters=characters,
                    deck_blobs=decks,
                    rng=rng,
                )
                center = (-6, -7, -1)
                self.assertFalse(
                    any(actor.position == center for actor in fight.actors.values())
                )
                enemy_hp = fight.actors[-7].hp
                tx = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | 6967, *center),
                    characters[7],
                    {-7: monster},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    **common,
                )
                areas = {
                    uid: row
                    for uid, row in tx.fight.native_effect_areas.items()
                    if row["reference"] in (1474, 1477)
                }
                self.assertEqual(
                    {row["reference"] for row in areas.values()}, {1474, 1477}
                )
                damage_area = next(
                    row for row in areas.values() if row["reference"] == 1474
                )
                self.assertIn(
                    tx.fight.actors[-7].position[:2],
                    registered_area_cells(
                        native_effect_areas()["1474"], center, damage_area["direction"]
                    ),
                )
                self.assertEqual(tx.fight.actors[-7].hp, enemy_hp)
                self.assertEqual(
                    tx.fight.actors[7].ap, fight.actors[7].ap - tx.plan["costs"]["ap"]
                )
                parent_uids = {row["effect_uid"] for row in areas.values()}
                runtime = RuntimeMessages(
                    tx.fight,
                    turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                        characters[7],
                        {-7: monster},
                        preview,
                        decks[7],
                        **common,
                        **boundary,
                    ),
                    turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                        characters[7],
                        {-7: monster},
                        preview,
                        decks[7],
                        area_callbacks=True,
                        **common,
                        **boundary,
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[7],
                        {-7: monster},
                        decks[7],
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0],
                )
                for _ in range(16):
                    if not set(areas).intersection(runtime.fight.native_effect_areas):
                        break
                    advance_actual_turn(runtime)
                self.assertLess(runtime.fight.actors[-7].hp, enemy_hp)
                self.assertFalse(
                    set(areas).intersection(runtime.fight.native_effect_areas)
                )
                self.assertFalse(
                    parent_uids.intersection(runtime.fight.native_owned_area_effects)
                )
                self.assertFalse(
                    parent_uids.intersection(runtime.fight.native_retained_records)
                )

        observed = self._assert_native_contract(ActivatingGlyphScenario, "exercise")
        self.assertTrue(
            any(
                boundary["boundary"] == "turn_start" and boundary["target_id"] == -7
                for boundary in observed["lifecycle_boundaries"]
            )
        )
        self.assertGreaterEqual(
            sum(
                boundary["boundary"] == "removed"
                for boundary in observed["lifecycle_boundaries"]
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
