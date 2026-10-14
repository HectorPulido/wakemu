"""Actual replacement session regains a living summon's paid action authority."""
import os
import random
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SummonReconnectControlAuthorityTests(unittest.TestCase):
    def exercise(self, reconnect_on_summon):
        import test_combat_spell_transaction as fixtures
        import test_aniripsa_grant_summon_pipeline as turns
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_shared import Registry, Session, Transition
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_summon_spellbook import (
            actor_action_book,
            resolve_controlled_action,
        )
        from wakfu_server.combat_cast_delivery_source import connected_action_source
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_summon_retirement import retired_summon_ids

        from wakfu_server import combat_actor_snapshot as snapshots

        build_npc = snapshots.build_npc_snapshot

        def complete_npc_source(monster, actor, **kwargs):
            # The maintained fixture's selected native profile is 5525/level1.
            # Complete its source row before snapshot/QI initialization, so
            # the real reconnect serializer receives the same native level.
            self.assertEqual(monster["ref"], 5525)
            self.assertEqual(actor.effective_level, 1)
            monster["level"] = 1
            return build_npc(monster, actor, **kwargs)

        with patch.object(snapshots, "build_npc_snapshot", complete_npc_source):
            (
                character,
                monster,
                fight,
            ) = fixtures.SpellTransactionTests().native_server_fixture(
                2,
                200,
                native_qi=True,
                target_hp=20000,
                target_distance=3,
                target_ref=5525,
                target_level=1,
                variation_seed=17,
            )
        deck = encode_deck([7307, 7317])
        rng = random.Random(7)
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
        data = [character, monster, fight, deck, rng]
        lifecycle = turns.AniripsaGrantSummonPipelineTests()

        def reach(identity):
            for _ in range(30):
                if data[2].current.id == identity:
                    return
                lifecycle.end_current_turn(data[2], tuple(data))
            self.fail("Lawful actor turn did not arrive")

        def cast(current, actor_id, uid, cell, account=3):
            source, selected = connected_action_source(
                current, {7: character}, {7: deck}, 7, account, actor_id
            )
            return prepare_server_spell(
                struct.pack(">qqiih", actor_id, uid, *cell),
                source,
                {-7: monster},
                current,
                account,
                selected,
                action_id=60,
                line_of_sight=lambda *_: True,
                critical=False,
                rng=rng,
            )

        reach(7)
        uid = granted_spells(data[2], 7)[7350]["uid"]
        owner = data[2].actors[7]
        occupied = {actor.position for actor in data[2].actors.values()}
        cells = sorted(
            cell
            for cell in data[2].walkable
            if cell not in occupied
            and sum(abs(cell[i] - owner.position[i]) for i in (0, 1)) == 1
        )
        self.assertTrue(cells)
        tx = cast(data[2], 7, uid, cells[0])
        summon_id = next(iter(set(tx.fight.actors) - set(data[2].actors)))
        data[2] = tx.fight
        reach(summon_id if reconnect_on_summon else 7)
        fight = data[2]
        old = Session(3, 7, "old", 1134, 0)
        replacement = Session(3, 7, "new", 1134, 0)
        live = {old}
        registry = Registry(lambda session: session in live)
        runtime = RuntimeMessages(fight)
        # Publish the actual summon-constructor actions through the native
        # allocator before reconnect; a fresh counter-zero runtime has never
        # delivered this initialized fight.
        runtime.prepare_delivery(tuple(tx.packets))
        runtime._arm_turn()
        self.assertGreater(runtime.native_action_id, 0)
        arena = dict(
            fight.native_qi_snapshot,
            map_id=1134,
            instance_id=0,
            min_z=min(cell[2] for cell in fight.walkable),
            max_z=max(cell[2] for cell in fight.walkable),
        )
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        class Store:
            def character(self, account_id, character_id):
                if (account_id, character_id) != (3, 7):
                    raise ValueError("Foreign current player snapshot")
                return character

        adapter = CombatSessionAdapter(Store())
        adapter.registry = registry
        shared = registry.register(
            fight,
            old,
            runtime=runtime,
            join_context={
                "arena": arena,
                "terrain_effect_id": 46,
                "terrain_instance_id": -300,
                "leaders": {0: 7, 1: -7},
                "monsters": {-7: monster},
            },
        )
        before = snapshot(fight)
        book = actor_action_book(fight.actors[summon_id])
        registry.disconnect(old)
        live.remove(old)
        live.add(replacement)
        fenced = []
        initial_presentations = []

        def initial_bootstrap(current, state, session):
            packets = owned_snapshot(
                current, state, session, actor_payload=adapter.actor_payload
            )
            initial_presentations.extend(packets)
            return packets

        registry.takeover(
            fight.id,
            replacement,
            initial_bootstrap,
            recover_disconnected=True,
            persist_takeover=fenced.append,
        )
        self.assertEqual(fenced, [old])
        self.assertIs(shared.fight, fight)
        self.assertIs(shared.fight.actors[summon_id], fight.actors[summon_id])
        self.assertEqual(snapshot(shared.fight), before)
        self.assertEqual(actor_action_book(shared.fight.actors[summon_id]), book)
        self.assertEqual(shared.participants[3], replacement)
        from wakfu_server.combat_wire import decode_actor_state
        from wakfu_server.combat_summon_stats import registered_summon_stats

        stats_packets = [
            decode_actor_state(opcode, body)
            for opcode, body in initial_presentations
            if opcode == 12873
        ]
        restored = [row for row in stats_packets if row["actor_id"] == summon_id]
        self.assertEqual(len(restored), 1)
        self.assertEqual(
            restored[0]["state"],
            registered_summon_stats(fight.actors[summon_id], fight, 1134),
        )
        profile, ai_control, level, additional_count = struct.unpack_from(
            ">hBhH", restored[0]["state"], len(restored[0]["state"]) - 27
        )
        self.assertEqual(profile, 1620)
        self.assertEqual(
            ai_control, int(fight.actors[summon_id].native_controlled_by_ai)
        )
        self.assertEqual(level, fight.actors[summon_id].native_summon_source["level"])
        self.assertEqual(additional_count, 0)
        self.assertEqual(
            {row["reference"] for row in book["actions"]},
            {7351, 7352, 7353, 7354, 7355},
        )
        effect_packets = [
            decode_actor_state(opcode, body)
            for opcode, body in initial_presentations
            if opcode == 13912
        ]
        self.assertEqual(
            len([row for row in effect_packets if row["actor_id"] == summon_id]), 1
        )
        from wakfu_server.combat_remote_effects import decode_remote_effects
        from wakfu_server.combat_effect_removal import _identity_fields

        actual_remote = next(
            row["state"] for row in effect_packets if row["actor_id"] == summon_id
        )
        remote_records = decode_remote_effects(actual_remote)
        remote_uids = [_identity_fields(row.payload)[1] for row in remote_records]
        expected_uids = {
            uid
            for uid, row in fight.native_retained_records.items()
            if row["manager_id"] == summon_id
        }
        self.assertEqual(set(remote_uids), expected_uids)
        self.assertEqual(len(remote_uids), len(expected_uids))
        self.assertTrue(
            {entry.uid for entry in fight.actors[summon_id].state_ledger.entries}
            <= expected_uids
        )
        born = fight.native_summon_creation_deliveries[summon_id]
        self.assertEqual(
            initial_presentations.count(
                (born["opcode"], bytes.fromhex(born["payload_hex"]))
            ),
            1,
        )
        with self.assertRaises(ValueError):
            registry.execute(fight.id, old, summon_id, lambda *_: ())
        foreign = Session(4, 8, "foreign", 1134, 0)
        live.add(foreign)
        with self.assertRaises(ValueError):
            registry.execute(fight.id, foreign, summon_id, lambda *_: ())
        with self.assertRaises(ValueError):
            connected_action_source(
                shared.fight, {7: character}, {7: deck}, 7, 4, summon_id
            )

        # The owner-turn reconnect must preserve control until the actual
        # summon turn arrives; no timeline index is manually rewritten.
        if not reconnect_on_summon:
            data[2] = shared.fight
            reach(summon_id)
            shared.fight = data[2]
            shared.runtime.fight = shared.fight
            shared.runtime._arm_turn()
        current = shared.fight
        self.assertEqual(current.current.id, summon_id)
        actions = actor_action_book(current.actors[summon_id])["actions"]
        self.assertIn(7351, {row["reference"] for row in actions})
        resolve_controlled_action(current, current.actors[summon_id], 7, 3, 7351)
        origin = current.actors[summon_id].position
        choices = sorted(
            cell
            for cell in current.walkable
            if cell not in {a.position for a in current.actors.values() if a.hp > 0}
            and sum(abs(cell[i] - origin[i]) for i in (0, 1)) == 1
            and cell[2] == origin[2]
        )
        self.assertTrue(choices)
        mp = current.actors[summon_id].mp

        def move(candidate, candidate_runtime):
            candidate.move(3, summon_id, [choices[0]])
            candidate_runtime.fight = candidate
            return Transition(candidate, candidate_runtime, ())

        registry.execute(fight.id, replacement, summon_id, move)
        self.assertEqual(shared.fight.actors[summon_id].mp, mp - 1)
        wp = shared.fight.actors[summon_id].effect_stats[4]
        ids = set(shared.fight.actors)

        def exchange(candidate, candidate_runtime):
            result = cast(candidate, summon_id, 7351, candidate.actors[7].position)
            candidate_runtime.fight = result.fight
            return Transition(result.fight, candidate_runtime, tuple(result.packets))

        registry.execute(fight.id, replacement, summon_id, exchange)
        self.assertEqual(shared.fight.actors[summon_id].effect_stats[4], wp - 1)
        self.assertEqual(set(shared.fight.actors), ids)
        self.assertEqual(actor_action_book(shared.fight.actors[summon_id]), book)
        self.assertNotIn(summon_id, {7: deck})
        before_retire = shared.fight

        def nova(candidate, candidate_runtime):
            result = cast(candidate, summon_id, 7355, candidate.actors[7].position)
            candidate_runtime.fight = result.fight
            return Transition(result.fight, candidate_runtime, tuple(result.packets))

        registry.execute(fight.id, replacement, summon_id, nova)
        self.assertIn(summon_id, retired_summon_ids(shared.fight))
        with self.assertRaises(ValueError):
            registry.execute(fight.id, replacement, summon_id, lambda *_: ())
        self.assertEqual(set(shared.fight.actors), ids)
        self.assertGreater(before_retire.actors[summon_id].hp, 0)
        from wakfu_server.combat_qi_fight import current_registry

        current_registry(shared.fight)
        self.assertFalse(
            any(
                row and row["identity"] == ["actor", summon_id]
                for row in shared.fight.native_qi_slots
            )
        )
        retired_birth = before_retire.native_summon_creation_deliveries[summon_id]
        resumed = Session(3, 7, "after-retirement", 1134, 0)
        registry.disconnect(replacement)
        live.remove(replacement)
        live.add(resumed)
        presentations = []

        def bootstrap_retired(current, state, session):
            packets = owned_snapshot(
                current, state, session, actor_payload=adapter.actor_payload
            )
            presentations.extend(packets)
            return packets

        registry.takeover(
            fight.id,
            resumed,
            bootstrap_retired,
            recover_disconnected=True,
            persist_takeover=lambda _: None,
        )
        self.assertNotIn(
            (retired_birth["opcode"], bytes.fromhex(retired_birth["payload_hex"])),
            presentations,
        )
        with self.assertRaises(ValueError):
            registry.execute(fight.id, resumed, summon_id, lambda *_: ())
        from wakfu_server.combat_spectator_snapshot import current_snapshot

        # The fixture's spell operation advances the Fight directly. Arm its
        # actual current-turn timer with the native runtime policy before
        # invoking the spectator caller's explicit deadline contract.
        shared.runtime._arm_turn()
        import time

        deadline_ms = int(
            time.time() * 1000
            + max(0.0, shared.runtime.turn_deadline - shared.runtime.clock()) * 1000
        )
        after_retirement = snapshot(shared.fight)
        spectator = current_snapshot(
            shared.fight,
            shared,
            actor_payload=lambda current, actor: adapter.actor_payload(
                current, actor, resumed
            ),
            deadline_ms=deadline_ms,
        )
        self.assertNotIn(
            (retired_birth["opcode"], bytes.fromhex(retired_birth["payload_hex"])),
            spectator,
        )
        from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap

        roster = decode_spectator_bootstrap(spectator[0][1])["participants"]
        self.assertNotIn(summon_id, {row["actor_id"] for row in roster})
        self.assertEqual({row["actor_id"] for row in roster}, {7, -7})
        for opcode, body in spectator:
            if opcode in (13912, 12873):
                self.assertNotEqual(
                    decode_actor_state(opcode, body)["actor_id"], summon_id
                )
        self.assertEqual(snapshot(shared.fight), after_retirement)

    def test_owner_turn_reconnect_retains_summon_paid_authority(self):
        self.exercise(False)

    def test_summon_turn_reconnect_restores_paid_authority(self):
        self.exercise(True)
