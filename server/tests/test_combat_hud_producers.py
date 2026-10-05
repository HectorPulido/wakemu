"""Native117/123 sources; synthetic flat arena/LOS only, no resource inflation."""
import struct
import unittest
from random import Random
from wakfu_server.combat_actor_snapshot import build_player_snapshot, build_npc_snapshot
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
)
from wakfu_server.combat_snapshot_wire import snapshot_characteristics
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.equipment_stats import effective_character, combat_resources
from wakfu_server.health import maximum
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


def fixture(breed, level, *, allies=()):
    c = effective_character(
        dict(
            id=7,
            account_id=3,
            breed=breed,
            level=level,
            hp=maximum(breed, level),
            max_hp=maximum(breed, level),
            map_id=1134,
            builds={},
            inventory_items=[],
        )
    )
    r = combat_resources(c)
    player = Actor(
        7,
        0,
        (0, 0, 0),
        c["hp"],
        r["ap"],
        r["mp"],
        r["initiative"],
        level,
        3,
        True,
        max_hp=c["max_hp"],
    )
    monsters = {}
    actors = [player]
    for identity, team, pos in [(-7, 1, (4, 0, 0))] + [
        (-8 - i, 0, pos) for i, pos in enumerate(allies)
    ]:
        m = owned_instance(
            4085, 23, identity, map_id=1134, x=pos[0], y=pos[1], z=pos[2], team=team
        )
        a = Actor(
            identity,
            team,
            pos,
            m["hp"],
            m["ap"],
            m["mp"],
            m["initiative"],
            23,
            max_hp=m["max_hp"],
        )
        a.direction = 3
        monsters[identity] = m
        actors.append(a)
    f = Fight(
        78,
        actors,
        {(x, y, 0) for x in range(-6, 10) for y in range(-6, 7)},
        {0: {a.position for a in actors if a.team == 0}, 1: {(4, 0, 0)}},
    )
    f.ready(3)
    player.direction = 0
    build_player_snapshot(
        c, player, wp_current=r["wp"], wp_maximum=r["wp"], running_effects=()
    ).install(player)
    for a in actors[1:]:
        m = monsters[a.id]
        build_npc_snapshot(
            m, a, wp_current=m["wp"], wp_maximum=m["wp"], running_effects=()
        ).install(a)
    f.native_effect_uid_next = 1
    f.native_obstacle_cells = frozenset()
    return c, monsters, f


def owned_turn(c, monsters, f, deck):
    # NPCs keep native INIT and play before the unequipped player. The test
    # explicitly passes their real turns; it never raises player initiative.
    while f.current.id != 7:
        identity = f.current.id
        f, _ = prepare_server_turn_end(
            c,
            monsters,
            f,
            deck,
            actor_id=identity,
            action_id=100 + f.turn_id,
            rng=Random(7),
        )
        f.end_server_turn(identity, f.turn_id)
    return f


def wire_value(actor, identity, character):
    data = snapshot_characteristics(actor)
    rows = [
        struct.unpack_from(">Biiii", data, 2 + 17 * i)
        for i in range(struct.unpack_from(">H", data)[0])
    ]
    value = next(row[1] for row in rows if row[0] == identity)
    from wakfu_server.combat_actor import actual_actor_stats

    blob = actual_actor_stats(
        character,
        actor,
        78,
        wp_current=actor.effect_stats[4],
        wp_maximum=actor.effect_maxima[4],
    )
    for offset in (39, 39 + len(data) + 4):
        count = struct.unpack_from(">H", blob, offset)[0]
        values = {
            struct.unpack_from(">Biiii", blob, offset + 2 + 17 * i)[
                0
            ]: struct.unpack_from(">Biiii", blob, offset + 2 + 17 * i)[1]
            for i in range(count)
        }
        if values[identity] != value:
            raise AssertionError("native player snapshot sections disagree")
    return value


def cast(c, monsters, f, deck, spell, target, action, *, granted=False):
    before = snapshot(f)
    result = prepare_server_spell(
        struct.pack(">qqiih", 7, spell if granted else (7 << 32) | spell, *target),
        c,
        monsters,
        f,
        3,
        deck,
        action_id=action,
        critical=False,
        line_of_sight=lambda *args: True,
        rng=Random(7),
    )
    if snapshot(f) != before:
        raise AssertionError("original fight mutated")
    return result


class NativeHudProducerTests(unittest.TestCase):
    def test_ouginak_native_ally_gain_then_amain_consumes_resource(self):
        for level in (90, 200):
            with self.subTest(level=level):
                c, monsters, f = fixture(
                    15,
                    level,
                    allies=((-1, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (-1, 1, 0)),
                )
                deck = encode_deck([7551, 6288])
                before = snapshot(f)
                ready, packets = prepare_server_initialization(
                    c,
                    monsters,
                    f,
                    3,
                    deck,
                    action_id=1,
                    rng=Random(7),
                    fight_start=True,
                )
                self.assertEqual(snapshot(f), before)
                ready = owned_turn(c, monsters, ready, deck)
                self.assertEqual(ready.actors[7].effect_stats[117], 0)
                gain = cast(c, monsters, ready, deck, 7551, (0, 0, 0), 2)
                self.assertEqual(gain.fight.actors[7].effect_stats[117], 20)
                self.assertEqual(wire_value(gain.fight.actors[7], 117, c), 20)
                consumed = cast(c, monsters, gain.fight, deck, 6288, (1, 0, 0), 3)
                self.assertEqual(consumed.fight.actors[7].effect_stats[117], 0)
                self.assertEqual(wire_value(consumed.fight.actors[7], 117, c), 0)
                self.assertGreater(consumed.fight.actors[-9].effect_stats[97], 0)
                self.assertEqual(consumed.plan["costs"]["ap"], 2)
                self.assertTrue(gain.packets and consumed.packets)

    def test_steamer_opening_converts_half_native_wp_to_sp_and_grants(self):
        for level in (20, 200):
            with self.subTest(level=level):
                c, monsters, f = fixture(16, level)
                deck = encode_deck([])
                before = snapshot(f)
                opening = f.actors[7].effect_stats[4]
                ready, packets = prepare_server_initialization(
                    c,
                    monsters,
                    f,
                    3,
                    deck,
                    action_id=1,
                    rng=Random(7),
                    fight_start=True,
                )
                self.assertEqual(snapshot(f), before)
                self.assertEqual(ready.actors[7].effect_stats[123], opening // 2)
                self.assertEqual(
                    ready.actors[7].effect_stats[4], opening - opening // 2
                )
                self.assertEqual(wire_value(ready.actors[7], 123, c), opening // 2)
                self.assertTrue(
                    {7008, 7700, 6923, 6924}.issubset(granted_spells(ready, 7))
                )
                self.assertTrue(packets)

    @unittest.skipUnless(
        __import__("os").environ.get("WAKFU_NATIVE_GRANTED_CAST") == "1",
        "native granted casting requires its explicit startup flag",
    )
    def test_steamer_casts_original_granted_stasis_toggle_with_owned_uid(self):
        c, monsters, f = fixture(16, 200)
        deck = encode_deck([])
        ready, _ = prepare_server_initialization(
            c, monsters, f, 3, deck, action_id=1, rng=Random(7), fight_start=True
        )
        ready = owned_turn(c, monsters, ready, deck)
        toggle = cast(c, monsters, ready, deck, 6923, (0, 0, 0), 2, granted=True)
        self.assertEqual(toggle.plan["costs"]["ap"], 1)
        self.assertEqual(toggle.plan["evaluation_level"], 200)
        self.assertIn(
            7647, {s.reference for s in toggle.fight.actors[7].state_ledger.entries}
        )
        self.assertEqual(toggle.fight.actors[7].effect_stats[123], 3)
        self.assertEqual(wire_value(toggle.fight.actors[7], 123, c), 3)
        self.assertTrue(toggle.packets)

        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
        )

        runtime = RuntimeMessages(
            toggle.fight,
            turn_start_provider=lambda preview, **kw: prepare_server_turn_start(
                c, monsters, preview, deck, **kw
            ),
            turn_end_provider=lambda preview, **kw: prepare_server_turn_end(
                c, monsters, preview, deck, **kw
            ),
        )
        runtime.turn_started()
        for expected in (2, 0):
            old_turn = runtime.fight.turn_id
            packets = runtime.end_turn(3, 7, runtime.fight.current.turn_count)
            self.assertEqual(runtime.fight.actors[7].effect_stats[123], expected)
            self.assertEqual(wire_value(runtime.fight.actors[7], 123, c), expected)
            self.assertEqual(runtime.fight.actors[7].effect_stats[4], 3)
            self.assertEqual(wire_value(runtime.fight.actors[7], 4, c), 3)
            self.assertTrue(packets)
            runtime.acknowledge_turn(struct.pack(">i", old_turn))
            if expected:
                self.assertEqual(
                    next(
                        e.level
                        for e in runtime.fight.actors[7].state_ledger.entries
                        if e.reference == 7647
                    ),
                    2,
                )
                while runtime.fight.current.id != 7:
                    old_turn = runtime.fight.turn_id
                    runtime.end_server_turn(runtime.fight.current.id, old_turn)
                    runtime.acknowledge_turn(struct.pack(">i", old_turn))
        self.assertNotIn(
            7647, {e.reference for e in runtime.fight.actors[7].state_ledger.entries}
        )
