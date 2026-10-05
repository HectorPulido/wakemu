"""A legitimate second Cinetosis listener must not undo a lethal first hit."""
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_active_spells as native
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class NativeLethalReactionTests(unittest.TestCase):
    def test_two_native_cinetosis_listeners_preserve_lethal_hit_and_victory(self):
        origin = (-8, -7, -1)
        terrain = native.bounded_arena(
            native.map_geometry(1134), origin, [(-7, -7, -1)], radius=12
        )
        cell = dict(
            native.target_candidates(
                native.catalog()["spells"]["5041"], 200, terrain, origin
            )
        )["enemy"]
        character, monster, original = native.fixture(
            11, 200, cell, terrain, origin, monster_reference=5525, monster_level=1
        )
        self.assertEqual(original.actors[-7].hp, 12)
        deck, rng = encode_deck([5041, 5030]), random.Random(0)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            original,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        while fight.current.id != 7:
            fight.end_server_turn(fight.current.id, fight.turn_id)

        def los(source, target, preview):
            return authoritative_visible(
                1134,
                source,
                target,
                preview,
                blocking_footprints={
                    identity: {actor.position[:2]}
                    for identity, actor in preview.actors.items()
                    if actor.hp > 0
                },
            )

        installed = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5041, *cell),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=los,
            critical=False,
            rng=rng,
        ).fight
        before = snapshot(installed)
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5030, *installed.actors[-7].position),
            character,
            {-7: monster},
            installed,
            3,
            deck,
            action_id=3,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(installed), before)
        self.assertEqual(result.fight.actors[-7].hp, 0)
        self.assertEqual(result.fight.phase, "finished")
        self.assertEqual([event["kind"] for event in result.events].count("death"), 1)
        self.assertEqual(
            result.events[-1],
            {
                "sequence": result.events[-1]["sequence"],
                "kind": "finished",
                "winner": 0,
            },
        )
        self.assertIn(12613, [opcode for opcode, _ in result.packets])


if __name__ == "__main__":
    unittest.main()
