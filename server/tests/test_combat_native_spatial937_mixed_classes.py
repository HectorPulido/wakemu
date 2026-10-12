"""Actual class casts after a source-qualified actor937 activates pointer QI."""
import json
import os
from pathlib import Path
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class Actor937MixedClassesTests(unittest.TestCase):
    def activate_pointer_mode(self, fight):
        from wakfu_server.combat_pointer_qi_handler import (
            NativeSpatialHandler,
            publish_spatial_registry,
        )
        from wakfu_server.combat_pointer_qi_lifecycle import _SOURCE
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_dispatch import (
            EffectInvocation,
            EffectDispatcher,
        )
        from wakfu_server.combat_qi_fight import current_registry

        effect = json.loads(_SOURCE.read_bytes())["112320"]
        plan = {"native_retained_container": {"present": False}}
        packets = []
        retention = NativeRetainedRuntime(
            fight, packets, plan=plan, state_catalog={}, action_id=90, timing=None
        )
        timing = NativeEffectTimingProvider({})
        handler = NativeSpatialHandler(
            fight,
            packets,
            action_id=90,
            retention=retention,
            context=lambda e, i: timing.stat(fight, plan, e, i),
            publish_registry=publish_spatial_registry,
            rng=lambda: 0.0,
        )
        actor = fight.actors[-7]
        invocation = EffectInvocation(
            112320,
            100,
            -7,
            -7,
            actor.position,
            native_retained_container={"present": False},
        )
        dispatcher = EffectDispatcher(
            {"112320": effect},
            {937: retention.wrap(handler)},
            resolve=lambda *args: (invocation,),
            condition_context=lambda i: {},
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda uid: fight.actors[uid].position,
            prepare_effect=handler.prepare,
        )
        self.assertTrue(dispatcher.execute(invocation))
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertIs(current_registry(fight).qi, fight.native_pointer_checkpoint._qi)
        self.assertTrue(any(opcode == 12613 for opcode, payload in packets))

    def test_actual_feca_glyph_creation_after_937(self):
        from test_feca_protection_pipeline import FecaProtectionPipelineTests
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        helper = FecaProtectionPipelineTests()
        helper.__class__.setUpClass()
        fight, characters, monster, decks = helper.fixture(
            active_spells=(6967,),
            caster_breed=1,
            level=200,
            caster_aptitudes=(),
            enemy_position=(-5, -7, -1),
        )
        self.activate_pointer_mode(fight)
        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6967, -8, -9, -1),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=91,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(
            {row["reference"] for row in tx.fight.native_effect_areas.values()},
            {1474, 1477},
        )
        tx.fight.native_pointer_checkpoint.validate(tx.fight)
        self.assertTrue(tx.packets)
        self.assertEqual(snapshot(fight), before)

    def test_actual_pandawa_barrel_summon_after_937(self):
        from test_combat_pandawa_runtime import PandawaRuntimeTests
        from wakfu_server.combat_qi_fight import current_registry

        helper = PandawaRuntimeTests()
        fixture = helper.fixture()
        self.activate_pointer_mode(fixture[2])
        result = helper.cast(fixture, 4718)
        barrels = [
            actor
            for actor in result.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        ]
        self.assertEqual(len(barrels), 1)
        self.assertEqual(barrels[0].native_summon_action_book["profile"], 3794)
        self.assertGreaterEqual(barrels[0].native_obstacle_id, 0)
        registry = current_registry(result.fight)
        self.assertIs(registry.qi.objects[barrels[0].id].actor, barrels[0])
        result.fight.native_pointer_checkpoint.validate(result.fight)

    def test_actual_pandawa_carry_and_throw_after_937(self):
        from test_combat_pandawa_runtime import PandawaRuntimeTests

        helper = PandawaRuntimeTests()
        fixture = helper.fixture()
        self.activate_pointer_mode(fixture[2])
        spawned = helper.cast(fixture, 4718, target=(-8, -8, -1))
        fixture = helper.adopt(fixture, spawned.fight)
        barrel = next(
            actor
            for actor in fixture[2].actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        carried = helper.cast(fixture, 6847, target=barrel.position, action_id=3)
        self.assertEqual(
            carried.fight.actors[barrel.id].position, carried.fight.actors[7].position
        )
        fixture = helper.adopt(fixture, carried.fight)
        thrown = helper.cast(fixture, 6848, action_id=4)
        self.assertNotEqual(
            thrown.fight.actors[barrel.id].position, thrown.fight.actors[7].position
        )
        thrown.fight.native_pointer_checkpoint.validate(thrown.fight)
