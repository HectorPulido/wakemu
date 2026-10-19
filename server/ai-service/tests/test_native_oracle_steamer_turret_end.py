"""Native Oracle end boundary delivers Steamer turret attacks and regeneration."""
import copy
import os
import random
import struct
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[3]
for _path in (str(_ROOT / "server"), str(_ROOT / "server" / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_server.combat_runtime_messages import RuntimeMessages
import test_native_oracle as oracle_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativeOracleSteamerTurretEndTests(unittest.TestCase):
    def test_end_boundary_delivers_turret_attack_and_wp_regeneration(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from tools.class_spell_eligible_targets import candidate_cells
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            16,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=3,
            variation_seed=17,
        )
        deck = encode_deck([6902])
        rng = random.Random(0)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )

        # Place the real turret adjacent to the enemy and beyond the owner, as
        # required by the native 1037 targeting branch.
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=2,
            critical=False,
            rng=rng,
        )
        enemy = fight.actors[-7]
        owner = fight.actors[7]
        distance = sum(abs(owner.position[i] - enemy.position[i]) for i in (0, 1))
        cells, total = candidate_cells(fight, 7, limit=256)

        def preferred(cell):
            adjacent = sum(abs(cell[i] - enemy.position[i]) for i in (0, 1)) == 1
            beyond = sum(abs(cell[i] - owner.position[i]) for i in (0, 1)) > distance
            return not (adjacent and beyond)

        import tools.class_spell_eligible_targets as selector

        cells = sorted(cells, key=preferred)
        from unittest.mock import patch

        with patch.object(selector, "candidate_cells", return_value=(cells, total)):
            targets = eligible_cast_targets(
                fight,
                character,
                deck,
                granted_spells(fight, 7)[7700]["uid"],
                adapter=adapter,
                line_of_sight=lambda *args: True,
                actor_id=7,
                limit=256,
                maximum_eligible=16,
            )
        desired = [
            row["target"] for row in targets["eligible"] if not preferred(row["target"])
        ]
        self.assertTrue(desired, targets)
        uid = granted_spells(fight, 7)[7700]["uid"]
        turret_cast = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *desired[0]),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        fight = turret_cast.fight
        turret = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_action_book", {}).get("profile") == 2011
        )
        self.assertIn(114, turret.native_fight_properties)
        self.assertNotIn(turret.id, fight.order)
        enemy_hp_before = fight.actors[-7].hp
        owner = fight.actors[7]
        # The actual elemental spell arms the turret; 1037 alone must not
        # trigger an unarmed turret.
        fire_uid = granted_spells(fight, 7).get(6902, {"uid": (7 << 32) | 6902})["uid"]
        fire = prepare_server_spell(
            struct.pack(">qqiih", 7, fire_uid, *fight.actors[-7].position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        fight = fire.fight
        owner = fight.actors[7]
        self.assertLess(owner.effect_stats[4], owner.effect_maxima[4])
        self.assertTrue(fire.packets)

        runtime = RuntimeMessages(fight)
        oracle = oracle_fixture.NativeOracleTests.oracle_for(
            runtime, character, monster, deck
        )
        runtime.turn_end_provider = oracle.end_boundary
        source = snapshot(fight)
        live_events = copy.deepcopy(fight.events)
        candidate, packets = oracle.live_end_boundary(fight, actor_id=7, action_id=4)

        self.assertEqual(snapshot(fight), source)
        self.assertEqual(fight.events, live_events)
        self.assertLess(
            candidate.actors[-7].hp,
            enemy_hp_before,
            {
                "before": enemy_hp_before,
                "after": candidate.actors[-7].hp,
                "deliveries": candidate.native_turn_event_deliveries,
                "turret_states": [
                    (entry.reference, entry.level)
                    for entry in candidate.actors[turret.id].state_ledger.entries
                ],
                "events": candidate.events[-20:],
            },
        )
        self.assertGreater(candidate.actors[7].effect_stats[4], owner.effect_stats[4])
        self.assertTrue(packets)
        self.assertTrue(
            any(key.endswith(":end") for key in candidate.native_turn_event_deliveries)
        )
        self.assertTrue(
            any(
                key.endswith(":regeneration")
                for key in candidate.native_turn_event_deliveries
            )
        )


if __name__ == "__main__":
    unittest.main()
