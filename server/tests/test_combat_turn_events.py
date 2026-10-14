import unittest
from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_turn_events import deliver_turn_end, deliver_turn_start
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot


class OwnedTurnEndTests(unittest.TestCase):
    def test_out_of_play_wave_history_does_not_receive_global_turn_events(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )
        from wakfu_server.combat_native_actor_lookup import native_actor_population

        fight, dispatcher, seen = self.fixture()
        initialize_global_pv_collections(fight, tuple(fight.actors))
        # A defeated wave stays registered for corpse/effect history. Its
        # retained state must not receive global1002 outside the PV population.
        fight.actors[-7].hp = 0
        set_global_fighter_status(fight, -7, "OUT_OF_PLAY")
        contexts = {actor.id: {} for actor in native_actor_population(fight)}

        def replay(event, **kwargs):
            if event.manager_actor_id not in contexts:
                raise ValueError("Missing native context for caster or target")
            seen.append(event)
            return ()

        dispatcher.replay_event = replay
        deliver_turn_end(dispatcher, actor_id=7)
        self.assertEqual(
            [(event.manager_actor_id, event.channel) for event in seen],
            [(7, 6), (7, 60), (7, 61)],
        )

    def test_off_play_registered_actor_still_receives_global_turn_event(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )

        fight, dispatcher, seen = self.fixture()
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, -7, "OFF_PLAY")
        deliver_turn_end(dispatcher, actor_id=7)
        self.assertIn(
            (-7, 61), [(event.manager_actor_id, event.channel) for event in seen]
        )

    def fixture(self):
        a = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 20, 3, True)
        b = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        f = Fight(
            77, [a, b], {a.position, b.position}, {0: {a.position}, 1: {b.position}}
        )
        f.ready(3)
        a.native_turn_suppression_bits = 0  # Actual fresh eGj BitSet snapshot.
        b.native_turn_suppression_bits = 0
        f.native_start_event_delivered = True
        seen = []
        d = SimpleNamespace(
            native_retention=SimpleNamespace(fight=f),
            native_clone_authority=object(),
            replay_event=lambda e, **kw: (seen.append(e) or (True,)),
        )
        return f, d, seen

    def test_end_actor_local_roles_global_roster_and_checkpoint_once(self):
        f, d, seen = self.fixture()
        deliver_turn_end(d, actor_id=7)
        self.assertEqual(
            [(x.manager_actor_id, x.channel) for x in seen],
            [(7, 6), (7, 60), (7, 61), (-7, 61)],
        )
        self.assertTrue(all(x.uid is None and x.event_ids == (1002,) for x in seen))
        self.assertTrue(snapshot(f)["native_turn_event_deliveries"])
        with self.assertRaises(ValueError):
            deliver_turn_end(d, actor_id=7)
        self.assertEqual(len(seen), 4)

    def test_start_and_end_are_distinct_checkpoint_boundaries(self):
        f, d, seen = self.fixture()
        deliver_turn_start(d, actor_id=7)
        deliver_turn_end(d, actor_id=7)
        self.assertEqual([x.event_ids for x in seen], [(1001,)] * 4 + [(1002,)] * 4)
        markers = snapshot(f)["native_turn_event_deliveries"]
        self.assertEqual(set(markers), {"1:7:start", "1:7:end"})
        with self.assertRaises(ValueError):
            deliver_turn_start(d, actor_id=7)
        self.assertEqual(len(seen), 8)

    def test_start_hook_after_expiry_not_repeated_by_ack_or_recovery(self):
        f, d, seen = self.fixture()
        calls = []

        def provider(original, **kw):
            calls.append(("event", kw["actor_id"]))
            candidate = deepcopy(original)
            candidate.native_turn_event_deliveries[
                f"{candidate.turn_id}:{kw['actor_id']}:start"
            ] = {"event_id": 1001}
            return candidate, ()

        runtime = RuntimeMessages(f, turn_start_provider=provider)

        def expiry(**kw):
            calls.append(("expiry", kw["actor_id"], kw.get("round_cleanup", False)))
            return []

        runtime._expire_owned = expiry
        runtime.turn_started()
        first_calls = list(calls)
        runtime.turn_started()
        self.assertEqual(calls, first_calls)
        self.assertEqual([x for x in calls if x[0] == "event"], [("event", 7)])
        runtime.end_turn(3, 7, 1)
        boundary_calls = list(calls)
        runtime.acknowledge_turn((1).to_bytes(4, "big"))
        self.assertEqual(calls, boundary_calls)
        runtime.recover(3, (77).to_bytes(4, "big"), now_ms=1)
        self.assertEqual(calls, boundary_calls)
        self.assertEqual(calls[0], ("expiry", 7, True))
        self.assertEqual(calls[1], ("expiry", 7, False))
        self.assertEqual(calls[2], ("event", 7))

    def test_fresh_state_listener_registration_keeps_immediate_recursion_guard(self):
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
            UnsupportedEffectExecution,
        )

        d = object.__new__(EffectDispatcher)
        d.effects = {
            "343079": {
                "effect_class": 330,
                "minimum_level": 0,
                "maximum_level": 32767,
            }
        }
        d.group_retention = SimpleNamespace(
            is_subscription=lambda effect, inv: inv.reference == 343079
        )
        calls = []
        d.execute = lambda inv, **kw: calls.append((inv, kw)) or True
        inv = EffectInvocation(343079, 1, 7, 7, (0, 0, 0), state_uid=4)
        self.assertTrue(d.register_subscription(inv))
        self.assertEqual(calls, [(inv, {"ancestors": ()})])
        with self.assertRaises(UnsupportedEffectExecution):
            d.register_subscription(EffectInvocation(1, 1, 7, 7, (0, 0, 0)))
        # Registration is tested above; full execution is covered by the
        # dispatcher pipeline tests. Keep this synthetic fixture scoped to
        # the recursion identity contract rather than bypassing construction.
        d._active_execution_keys = ((343079, 4), (343079, 4))
        self.assertTrue(d._recursive_identity(inv, (343079,)))
        no_state = EffectInvocation(343079, 1, 7, 7, (0, 0, 0))
        d._active_execution_keys = ((343079, None), (343079, None))
        self.assertTrue(d._recursive_identity(no_state, (343079,)))
        d._active_execution_keys = ((343079, 3), (343079, 4))
        self.assertFalse(d._recursive_identity(inv, (343079,)))

    def test_failed_start_reaction_rolls_back_expiration_and_runtime_marker(self):
        f, d, seen = self.fixture()
        before = snapshot(f)

        def provider(candidate, **kw):
            self.assertEqual(candidate.actors[7].hp, 50)
            raise ValueError("unsupported start reaction")

        runtime = RuntimeMessages(f, turn_start_provider=provider)

        def expiry(candidate, **kw):
            candidate.fight.actors[7].hp = 50
            return []

        with patch.object(RuntimeMessages, "_expire_owned", expiry):
            with self.assertRaisesRegex(ValueError, "start reaction"):
                runtime.turn_started()
        self.assertEqual(snapshot(f), before)
        self.assertEqual(runtime.round, 0)
        self.assertEqual(runtime.action_id, 0)
        self.assertIsNone(runtime.area_started_turn)
        self.assertIsNone(runtime.awaiting_ack)

    def test_wrong_actor_or_missing_initialization_never_delivers(self):
        f, d, seen = self.fixture()
        with self.assertRaises(ValueError):
            deliver_turn_end(d, actor_id=-7)
        f.native_start_event_delivered = False
        with self.assertRaises(ValueError):
            deliver_turn_end(d, actor_id=7)
        self.assertFalse(seen)

    def test_end_reaction_before_expiration_and_failed_expiry_rolls_back(self):
        f, d, seen = self.fixture()
        before = snapshot(f)
        order = []

        def provider(original, **kw):
            candidate = deepcopy(original)
            candidate.actors[7].hp = 50
            candidate.native_turn_event_deliveries = {"1:7:end": {"event_id": 1002}}
            order.append("event")
            return candidate, ()

        runtime = RuntimeMessages(f, turn_end_provider=provider)

        def expiry(candidate, **kw):
            order.append("expiry")
            self.assertEqual(candidate.actors[7].hp, 50)
            raise ValueError("invalid state timer")

        with patch(
            "wakfu_server.combat_timed_expiration.prepare_timed_expiration", expiry
        ):
            with self.assertRaisesRegex(ValueError, "timer"):
                runtime.end_turn(3, 7, 1)
        self.assertEqual(order, ["event", "expiry"])
        self.assertEqual(snapshot(f), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertIsNone(runtime.awaiting_ack)

    def test_ack_does_not_repeat_end_callback(self):
        f, d, seen = self.fixture()
        calls = []

        def provider(original, **kw):
            calls.append(kw["actor_id"])
            return deepcopy(original), ()

        runtime = RuntimeMessages(f, turn_end_provider=provider)
        runtime.end_turn(3, 7, 1)
        runtime.acknowledge_turn((1).to_bytes(4, "big"))
        self.assertEqual(calls, [7])


class RealNativeTurnEndReactionTests(unittest.TestCase):
    def initialized(self, breed, passives):
        from server.tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck
        from random import Random

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            breed, 20, native_qi=True
        )
        deck = encode_deck((), passives)
        fight, _ = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(1),
            fight_start=True,
        )
        fight.native_table_turn = 1  # RuntimeMessages13477 precedes the end boundary.
        return character, {monster["id"]: monster}, fight, deck

    def test_yopuka_charge_then_owned_end_turn_uses_actual_trigger_identity(self):
        import struct, random
        from server.tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_end,
        )
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_actor_snapshot import build_npc_snapshot
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.spells import encode_deck

        for level in (20, 200):
            with self.subTest(level=level):
                from wakfu_server.combat_bootstrap import create_placement
                from wakfu_server.combat_wire import arena as encode_arena
                from wakfu_server.combat_actor_snapshot import (
                    initialize_fight_snapshots,
                )
                from wakfu_server.health import maximum

                character = dict(
                    id=7,
                    account_id=3,
                    name="Turn regression",
                    breed=8,
                    level=level,
                    hp=maximum(8, level),
                    max_hp=maximum(8, level),
                    map_id=1134,
                    instance_id=0,
                    x=-8,
                    y=-7,
                    z=-1,
                    builds={},
                    inventory_items=[],
                )
                monster = owned_instance(4085, 23, -7, map_id=1134, x=-6, y=-7, z=-1)
                terrain = local_arena(1134, 7, (-8, -7, -1), (-6, -7, -1))
                placement = {0: {(-8, -7, -1)}, 1: {(-6, -7, -1)}}
                arena = encode_arena(1134, 0, terrain["validated_cells"], placement)
                arena.update(
                    validated_cells=terrain["validated_cells"],
                    valid_edges=terrain["valid_edges"],
                    placement_cells=placement,
                )
                fight, _ = create_placement(
                    character,
                    monster,
                    arena,
                    fight_id=78,
                    player_ap=6,
                    player_mp=4,
                    player_wp=6,
                    player_initiative=0,
                    terrain_effect_id=46,
                    terrain_instance_id=-300,
                )
                initialize_fight_snapshots(
                    fight,
                    characters={7: character},
                    monsters={-7: monster},
                    wp_resources={7: (6, 6), -7: (0, 0)},
                    running_effects={7: (), -7: ()},
                    initial_effect_uid=1,
                )
                fight.actors[7].direction = 0
                fight.actors[-7].direction = 3
                fight.ready(3)
                deck = encode_deck([4783])
                fight, _ = prepare_server_initialization(
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=1,
                    rng=random.Random(1),
                    fight_start=True,
                )
                # Install at actual first-turn boundary before the native
                # creature's higher initiative first turn is passed.
                while not fight.current.controlled:
                    fight.end_server_turn(fight.current.id, fight.turn_id)
                fight.native_table_turn = fight.current.turn_count
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | 4783, -6, -7, -1),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(1),
                )
                self.assertLess(transaction.fight.actors[-7].hp, monster["hp"])
                self.assertEqual(transaction.fight.phase, "active")
                fight = transaction.fight
                before = snapshot(fight)
                runtime = RuntimeMessages(
                    fight,
                    turn_end_provider=lambda preview, **kw: prepare_server_turn_end(
                        character, {-7: monster}, preview, deck, **kw
                    ),
                )
                packets = runtime.end_turn(3, 7, fight.current.turn_count)
                self.assertIn(12502, [op for op, _ in packets])
                self.assertEqual(fight.current.id, -7)
                self.assertEqual(runtime.awaiting_ack, before["turn_id"])
                runtime.acknowledge_turn(struct.pack(">i", before["turn_id"]))
                self.assertIsNone(runtime.awaiting_ack)

    def test_sacro_actual_berserker_recalculates_at_start_without_mutating_original(
        self,
    ):
        from wakfu_server.combat_server_spell import prepare_server_turn_start

        character, monsters, fight, deck = self.initialized(11, [5051])
        actor = fight.actors[7]
        actor.hp = actor.max_hp // 2
        actor.effect_stats[1] = actor.hp
        before = snapshot(fight)
        preview, packets = prepare_server_turn_start(
            character, monsters, fight, deck, actor_id=7, action_id=2
        )
        old = next(e.level for e in actor.state_ledger.entries if e.reference == 9313)
        new = next(
            e.level
            for e in preview.actors[7].state_ledger.entries
            if e.reference == 9313
        )
        self.assertNotEqual(old, new)
        self.assertEqual(new, 50)
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)

    def test_hupper_original_heart_of_fire_start_branch_removes_mode(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        character, monsters, fight, deck = self.initialized(19, [])
        factory, _ = server_runtime(
            character, monsters, deck, action_id=2, critical=False
        )
        dispatcher, _ = factory(
            fight,
            {
                "spell_id": 5588,
                "evaluation_level": 20,
                "native_retained_container": {"present": False},
            },
        )
        # Original5588 applicator, preserving its criterion and state parameters.
        dispatcher.execute(EffectInvocation(416488, 20, 7, 7, fight.actors[7].position))
        fight.actors[7].effect_stats[111] = 40
        self.assertTrue(
            any(e.reference == 4121 for e in fight.actors[7].state_ledger.entries)
        )
        before = snapshot(fight)
        preview, packets = prepare_server_turn_start(
            character, monsters, fight, deck, actor_id=7, action_id=3
        )
        self.assertFalse(
            any(e.reference == 4121 for e in preview.actors[7].state_ledger.entries)
        )
        self.assertEqual(preview.actors[7].effect_stats[111], 40)
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)
