"""Native combat source regressions, with no resource inflation."""
import struct
import unittest
from unittest.mock import patch
from random import Random
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
)
from wakfu_server.combat_snapshot_wire import snapshot_characteristics
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_remote_effects import active_actor_effects
from wakfu_server.equipment_stats import effective_character, combat_resources
from wakfu_server.health import maximum
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


def fixture(
    breed,
    level,
    *,
    allies=(),
    enemies=(),
    enemy_position=(4, 0, 0),
    origin=(0, 0, 0),
    native_terrain=False,
    npc_reference=4085,
    npc_level=23,
):
    def cell(relative):
        return tuple(origin[index] + relative[index] for index in range(3))

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
        origin,
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
    participants = [(-7, 1, enemy_position)]
    participants += [(-20 - i, 1, pos) for i, pos in enumerate(enemies)]
    participants += [(-8 - i, 0, pos) for i, pos in enumerate(allies)]
    for identity, team, pos in participants:
        pos = cell(pos)
        m = owned_instance(
            npc_reference,
            npc_level,
            identity,
            map_id=1134,
            x=pos[0],
            y=pos[1],
            z=pos[2],
            team=team,
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
    terrain = None
    if native_terrain:
        from wakfu_server.combat_terrain import local_arena

        terrain = local_arena(
            1134,
            78,
            cell((0, 0, 0)),
            [actor.position for actor in actors if actor.id != 7],
            relocate_monsters=False,
            compact=False,
        )
    f = Fight(
        78,
        actors,
        terrain["validated_cells"]
        if terrain is not None
        else {cell((x, y, 0)) for x in range(-6, 10) for y in range(-6, 7)},
        {
            0: {a.position for a in actors if a.team == 0},
            1: {a.position for a in actors if a.team == 1},
        },
    )
    initialize_global_pv_collections(f, tuple(f.actors))
    player.direction = 0
    f.native_qi_snapshot = (
        {key: terrain[key] for key in ("x", "y", "width", "height", "cell_masks")}
        if terrain is not None
        else dict(
            x=origin[0] - 6,
            y=origin[1] - 6,
            width=16,
            height=13,
            cell_masks=[128] * (16 * 13),
        )
    )
    if terrain is not None:
        f.edges = set(terrain["valid_edges"])
        f.native_qi_surface_provenance = dict(terrain["native_qi_surface_provenance"])
    initialize_fight_snapshots(
        f,
        characters={7: c},
        monsters=monsters,
        wp_resources={
            7: (r["wp"], r["wp"]),
            **{
                identity: (monster["wp"], monster["wp"])
                for identity, monster in monsters.items()
            },
        },
        running_effects={identity: () for identity in f.actors},
        initial_effect_uid=1,
    )
    f.ready(3)
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
    def test_zobal_acrobatism_uses_exact_range_six_empty_native_cell(self):
        origin = (-8, -7, -1)
        destination = (-14, -7, -1)
        c, monsters, f = fixture(
            14,
            200,
            origin=origin,
            enemy_position=(-6, 1, 0),
            native_terrain=True,
        )
        self.assertEqual(
            abs(origin[0] - destination[0]) + abs(origin[1] - destination[1]), 6
        )
        self.assertIn(destination, f.walkable)
        self.assertNotIn(destination, {actor.position for actor in f.actors.values()})
        deck = encode_deck([7087])
        ready, _ = prepare_server_initialization(
            c,
            monsters,
            f,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        ready = owned_turn(c, monsters, ready, deck)
        result = cast(c, monsters, ready, deck, 7087, destination, 2)
        self.assertEqual(result.plan["spell_id"], 7087)
        self.assertEqual(result.fight.actors[7].position, destination)

    def test_ouginak_cazador_hits_native_obstacle_at_legal_range(self):
        c, monsters, f = fixture(15, 200, origin=(-4, -18, 0), enemy_position=(3, 0, 0))
        deck = encode_deck([6284])
        ready, _ = prepare_server_initialization(
            c,
            monsters,
            f,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        ready = owned_turn(c, monsters, ready, deck)
        target = ready.actors[-7].position
        result = cast(c, monsters, ready, deck, 6284, target, 2)
        self.assertEqual(result.plan["spell_id"], 6284)
        caster = result.fight.actors[7]
        enemy = result.fight.actors[-7]
        self.assertNotEqual(caster.position, ready.actors[7].position)
        self.assertIn(7555, [entry.reference for entry in enemy.state_ledger.entries])
        self.assertNotEqual(enemy.effect_stats[8], ready.actors[-7].effect_stats[8])

    def test_ouginak_persecucion_grants_and_casts_perseguidor_on_other_obstacle(self):
        c, monsters, f = fixture(
            15,
            200,
            origin=(-4, -18, 0),
            enemy_position=(0, -3, 0),
            allies=((1, 0, 0), (2, 0, 0), (1, 1, 0), (1, -1, 0), (0, 1, 0)),
            enemies=((-3, 0, 0),),
        )
        deck = encode_deck([7551, 6285])
        ready, _ = prepare_server_initialization(
            c,
            monsters,
            f,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        ready = owned_turn(c, monsters, ready, deck)
        gain = cast(c, monsters, ready, deck, 7551, ready.actors[7].position, 2)
        self.assertEqual(gain.fight.actors[7].effect_stats[117], 20)
        pursuit_target = gain.fight.actors[-7].position
        pursuit = cast(c, monsters, gain.fight, deck, 6285, pursuit_target, 3)
        self.assertEqual(pursuit.plan["spell_id"], 6285)
        self.assertIn(6856, granted_spells(pursuit.fight, 7))
        self.assertTrue(
            any(
                entry.reference == 7524
                for entry in pursuit.fight.actors[7].state_ledger.entries
            )
        )
        self.assertTrue(
            any(
                entry.reference == 7527
                for entry in pursuit.fight.actors[-7].state_ledger.entries
            )
        )

        other_target = pursuit.fight.actors[-20].position
        pursuer = cast(
            c, monsters, pursuit.fight, deck, 6856, other_target, 4, granted=True
        )
        self.assertEqual(pursuer.plan["spell_id"], 6856)
        self.assertEqual(pursuer.fight.actors[7].effect_stats[117], 15)
        self.assertNotIn(
            7524,
            [entry.reference for entry in pursuer.fight.actors[7].state_ledger.entries],
        )
        self.assertIn(
            7537,
            [entry.reference for entry in pursuer.fight.actors[7].state_ledger.entries],
        )
        self.assertIn(
            7527,
            [
                entry.reference
                for entry in pursuer.fight.actors[-7].state_ledger.entries
            ],
        )

    def test_ouginak_native_ally_gain_then_amain_consumes_resource(self):
        for level in (90, 200):
            with self.subTest(level=level):
                c, monsters, f = fixture(
                    15,
                    level,
                    origin=(-4, -18, 0),
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
                player_cell = ready.actors[7].position
                gain = cast(c, monsters, ready, deck, 7551, player_cell, 2)
                self.assertEqual(gain.fight.actors[7].effect_stats[117], 20)
                self.assertEqual(wire_value(gain.fight.actors[7], 117, c), 20)
                ally_cell = (player_cell[0] + 1, player_cell[1], player_cell[2])
                consumed = cast(c, monsters, gain.fight, deck, 6288, ally_cell, 3)
                self.assertEqual(consumed.fight.actors[7].effect_stats[117], 0)
                self.assertEqual(wire_value(consumed.fight.actors[7], 117, c), 0)
                self.assertGreater(consumed.fight.actors[-9].effect_stats[97], 0)
                self.assertEqual(consumed.plan["costs"]["ap"], 2)
                self.assertTrue(gain.packets and consumed.packets)

    def test_ouginak_manada_form_lifecycle_uses_native_resource_and_removes_visual(
        self,
    ):
        c, monsters, f = fixture(
            15,
            90,
            origin=(-4, -18, 0),
            allies=((-1, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (-1, 1, 0)),
        )
        deck = encode_deck([7551, 6288])
        ready, _ = prepare_server_initialization(
            c,
            monsters,
            f,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        ready = owned_turn(c, monsters, ready, deck)
        player_cell = ready.actors[7].position
        gain = cast(c, monsters, ready, deck, 7551, player_cell, 2)
        self.assertEqual(gain.fight.actors[7].effect_stats[117], 20)
        self.assertIn(6855, granted_spells(gain.fight, 7))

        form = cast(c, monsters, gain.fight, deck, 6855, player_cell, 3, granted=True)
        self.assertEqual(form.plan["spell_id"], 6855)
        self.assertTrue(
            any(
                entry.reference == 7526
                for entry in form.fight.actors[7].state_ledger.entries
            )
        )
        visual = {
            uid: row
            for uid, row in form.fight.native_owned_group_effects.items()
            if row["invocation"]["reference"] == 339778
        }
        self.assertEqual(
            len(visual),
            1,
            [
                (
                    uid,
                    row["invocation"]["reference"],
                    row["invocation"].get("state_uid"),
                )
                for uid, row in form.fight.native_owned_group_effects.items()
            ],
        )
        visual_uid = next(iter(visual))
        self.assertIn(12613, [opcode for opcode, _ in form.packets])
        effect_snapshot = active_actor_effects(form.fight, 7)
        self.assertIn(bytes.fromhex(visual[visual_uid]["payload"]), effect_snapshot)

        ally_cell = (player_cell[0] + 1, player_cell[1], player_cell[2])
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        activations = []
        original_activation = EffectDispatcher.execute_activation

        def observe_activation(dispatcher, invocation, *args, **kwargs):
            activations.append(
                (invocation.reference, invocation.caster_id, invocation.target_id)
            )
            return original_activation(dispatcher, invocation, *args, **kwargs)

        with patch.object(EffectDispatcher, "execute_activation", observe_activation):
            consumed = cast(c, monsters, form.fight, deck, 6288, ally_cell, 4)
        self.assertIn(
            339923, {reference for reference, _, _ in activations}, activations
        )
        self.assertEqual(consumed.fight.actors[7].effect_stats[117], 0)
        self.assertFalse(
            any(
                entry.reference == 7526
                for entry in consumed.fight.actors[7].state_ledger.entries
            )
        )
        self.assertNotIn(visual_uid, consumed.fight.native_owned_group_effects)
        removals = [payload for opcode, payload in consumed.packets if opcode == 13560]
        self.assertTrue(removals)
        self.assertIn(
            (7, visual_uid),
            [struct.unpack(">qq", payload[-16:]) for payload in removals],
        )

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
        self.assertEqual(
            toggle.plan["extra_resource_payment"],
            (dict(stat_id=123, requested_delta=-1, actual_delta=-1),),
        )
        self.assertEqual(toggle.fight.actors[7].effect_stats[123], 2)
        self.assertEqual(wire_value(toggle.fight.actors[7], 123, c), 2)
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
        for expected, expected_wp in ((1, 4), (0, 5)):
            old_turn = runtime.fight.turn_id
            packets = runtime.end_turn(3, 7, runtime.fight.current.turn_count)
            self.assertEqual(runtime.fight.actors[7].effect_stats[123], expected)
            self.assertEqual(wire_value(runtime.fight.actors[7], 123, c), expected)
            self.assertEqual(runtime.fight.actors[7].effect_stats[4], expected_wp)
            self.assertEqual(wire_value(runtime.fight.actors[7], 4, c), expected_wp)
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
