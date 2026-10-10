"""Original displacement-triggered Cinetosis preserves lethal settlement."""
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


def cinetosis_turn_runtime(character, monster, fight, deck, rng):
    """Actual turn/resource/expiry providers; never refill resources directly."""
    from combat_audit_turns import advance_actual_turn
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_server_spell import (
        prepare_server_turn_end,
        prepare_server_turn_start,
        server_runtime,
    )

    return RuntimeMessages(
        fight,
        turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
            character, {-7: monster}, preview, deck, rng=rng, **boundary
        ),
        turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
            character, {-7: monster}, preview, deck, rng=rng, **boundary
        ),
        expiration_runtime_factory=lambda *, action_id: server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=action_id,
            critical=False,
            rng=rng,
        )[0],
    )


def initialized_cinetosis_fixture(spells, *, monster_reference=5525, monster_level=1):
    """Original Ready, native start/turn boundaries and legal pull geometry."""
    origin = (-8, -7, -1)
    terrain = native.bounded_arena(
        native.map_geometry(1134), origin, [(-7, -7, -1)], radius=12
    )
    # An adjacent recipient does not move under native pull, so it must
    # not emit2128. Place the real NPC before Ready on a legal aligned
    # cell at least two cells away; never manufacture a death or HP loss.
    pull_terrain = dict(
        terrain,
        cells={
            c
            for c in terrain["cells"]
            if abs(c[0] - origin[0]) + abs(c[1] - origin[1]) >= 2
            and (c[0] == origin[0] or c[1] == origin[1])
            and c[2] == origin[2]
        },
    )
    cell = dict(
        native.target_candidates(
            native.catalog()["spells"]["5041"],
            200,
            pull_terrain,
            origin,
            native=native.native_casting_baseline(
                native.native_casting_catalog()["5041"], 200
            ),
            spell_reference=5041,
        )
    )["enemy"]
    character, monster, original = native.fixture(
        11,
        200,
        cell,
        terrain,
        origin,
        monster_reference=monster_reference,
        monster_level=monster_level,
    )
    deck, rng = encode_deck(spells), random.Random(0)
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
    from combat_audit_turns import advance_actual_turn

    turns = cinetosis_turn_runtime(character, monster, fight, deck, rng)
    while turns.fight.current.id != 7:
        advance_actual_turn(turns)
    fight = turns.fight

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

    return character, monster, fight, deck, rng, los, terrain


class NativeLethalReactionTests(unittest.TestCase):
    def test_native_cinetosis_displacement_preserves_lethal_hit_and_victory(self):
        (
            character,
            monster,
            fight,
            deck,
            rng,
            los,
            terrain,
        ) = initialized_cinetosis_fixture([5041, 5030])
        self.assertEqual(fight.actors[-7].hp, 12)
        cell = fight.actors[-7].position
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
