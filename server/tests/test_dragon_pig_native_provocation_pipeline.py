"""Real native Dragon Pig scene and paid-player provocation production."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))


class DragonPigNativeProvocationPipelineTests(unittest.TestCase):
    def test_paid_native_action_earns_provocation_on_original_arena(self):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from test_ultimate_encounter_scene_recipes import (
            UltimateNativePaidProducerTests,
        )
        from tools.combat_audit_turns import advance_actual_turn

        geometry = json.loads(
            (ROOT / ".runtime/ultimate-scenes-20261021/map-545.json").read_text()
        )
        scene = resolve_supreme_scene(2430, geometry)
        tank, facts = native_tank_fixture(validator, feca=True)
        fixture, preparation = encounter_fixture_factory(
            validator,
            scene,
            caster_cell=scene["source"],
            player_level=200,
            player_breed=1,
            player_deck=[6972],
            character_constructor=tank.__globals__["_healthy_owned_character"],
            production_bootstrap=True,
        )
        with original_bootstrap_publication():
            fight, character, monsters, deck = fixture(
                2430, 125, scene["anchor"], native_lifecycle=False
            )
        rng = Random(0)
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            deck,
            action_id=2,
            rng=rng,
            fight_start=True,
            player_characters={7: character},
            deck_blobs={7: deck},
        )
        serializer = UltimateNativePaidProducerTests._serializer(character, monsters)
        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=serializer,
            turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                character,
                monsters,
                phase,
                deck,
                rng=rng,
                native_events=True,
                area_callbacks=True,
                **kw
            ),
            turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                character, monsters, phase, deck, rng=rng, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, rng=rng
            )[0],
        )
        runtime.turn_started()
        if runtime.awaiting_ack is not None:
            runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        for _ in range(4):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        actor = runtime.fight.actors[7]
        self.assertEqual(runtime.fight.current.id, actor.id)
        self.assertIn(1812, {entry.reference for entry in actor.state_ledger.entries})
        level = lambda current: sum(
            entry.level
            for entry in current.state_ledger.entries
            if entry.reference == 1813
        )
        before = dict(ap=actor.ap, provocation=level(actor), hp=actor.hp)
        baseline = snapshot(runtime.fight)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6972, *actor.position),
            character,
            monsters,
            runtime.fight,
            character["account_id"],
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
            line_of_sight=lambda origin, target, current: authoritative_visible(
                545,
                origin,
                target,
                current,
                blocking_footprints={
                    other.id: footprint(other.position, other.physical_radius)
                    for other in current.actors.values()
                    if other.hp > 0
                },
            ),
        )
        self.assertEqual(snapshot(runtime.fight), baseline)
        self.assertEqual(transaction.plan["costs"]["ap"], 2)
        commit_spell_transaction(runtime, transaction, stats_serializer=serializer)
        after = runtime.fight.actors[7]
        receipt = dict(
            scope="Real arena and one paid action; consuming attacks, phase transitions and victory remain separate",
            scene=preparation,
            healthy_owned_player=facts,
            before=before,
            after=dict(ap=after.ap, provocation=level(after), hp=after.hp),
            native_initialization=deepcopy(
                runtime.fight.native_npc_initialization_receipts
            ),
            paid_reference=6972,
            source_map=545,
        )
        (
            ROOT
            / ".runtime/parallel-readiness-20261021/dragon-pig-paid-provocation-receipt.json"
        ).write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertEqual(after.ap, before["ap"] - 2)
        self.assertGreater(level(after), before["provocation"])
