"""Detached individual PvE withdrawal candidates preserve shared combat."""
import struct
import unittest
from copy import deepcopy
from unittest.mock import patch

from wakfu_server.combat_pve_withdraw import plan
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Session, Registry, Transition
from wakfu_server.combat_state import Actor, Fight
from postgres_case import PostgresCase


class WithdrawalPlanTests(unittest.TestCase):
    def test_private_return_preserves_registered_summon_controller_authority(self):
        from dataclasses import asdict
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority
        from wakfu_server.combat_abandon import _participant

        beacon = Actor(222, 0, (1, 0, 0), 20, 0, 0, 0, 1, 2, True)
        beacon.native_controller_id = 20
        beacon.native_summon_source = dict(
            # Published native-actor-properties.json NPC profile1422 carries
            # timeline-exclusion property114 (exact catalog set below).
            ref=1422,
            level=1,
            caster_id=20,
            controller_id=20,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        authority = NativeActorAuthority(
            targeting={},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=1422,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=False,
            is_summon=True,
            native_real_level=1,
            native_controller_id=20,
        )
        self.fight.actors[222] = beacon
        self.fight.native_summon_registrations = {
            222: dict(
                actor_id=222,
                caster_id=20,
                controller_id=20,
                authority=asdict(authority),
                fight_properties=frozenset((28, 70, 15, 88, 78, 1, 114)),
            )
        }
        result = plan(self.session, self.fight, self.runtime)
        private = result.private_runtime
        self.assertTrue(private.fight.actors[20].controlled)
        self.assertTrue(private.fight.actors[222].controlled)
        self.assertTrue(private.fight.actors[20].pve_withdrawn)
        self.assertEqual(_participant(1, {"id": 10}, private).id, 10)
        self.assertFalse(getattr(self.fight.actors[20], "pve_withdrawn", False))

    def setUp(self):
        self.session = Session(1, 10, "owner", 527, 0)
        self.fight = Fight(
            77,
            [
                Actor(10, 0, (0, 0, 0), 45, 6, 3, 100, 1, 1, True),
                Actor(20, 0, (1, 0, 0), 55, 6, 3, 90, 1, 2, True),
                Actor(-200, 1, (2, 0, 0), 25, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        self.fight.ready(1)
        self.fight.ready(2)
        self.runtime = RuntimeMessages(self.fight)

    def test_active_owner_leaves_without_finishing_other_players_fight(self):
        result = plan(self.session, self.fight, self.runtime)
        self.assertEqual(result.fight.phase, "active")
        self.assertIsNone(result.fight.winner)
        self.assertEqual(result.fight.actors[20].hp, 55)
        self.assertEqual(result.fight.actors[-200].hp, 25)
        self.assertEqual(result.fight.actors[10].hp, 0)
        self.assertNotIn(10, result.fight.order)
        self.assertEqual(result.initial_actor.hp, 45)
        self.assertEqual(self.fight.actors[10].hp, 45)
        self.assertEqual(self.runtime.action_id, 0)

    def test_withdrawn_character_wire_snapshot_tracks_zero_hp(self):
        from test_combat_actor_snapshot import ActorSnapshotTests
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        character, actor = ActorSnapshotTests().player()
        character["id"] = actor.id = 10
        actor.owner_id = self.session.account_id
        actor.team = 0
        actor.position = (0, 0, 0)
        build_player_snapshot(
            character, actor, wp_current=6, wp_maximum=6, running_effects=()
        ).install(actor)
        self.fight.actors[10] = actor
        self.assertEqual(actor.effect_stats[1], actor.hp)

        result = plan(self.session, self.fight, self.runtime)

        withdrawn = result.fight.actors[10]
        self.assertTrue(withdrawn.pve_withdrawn)
        self.assertEqual(withdrawn.hp, 0)
        self.assertEqual(withdrawn.effect_stats[1], 0)
        self.assertTrue(snapshot_characteristics(withdrawn))

    def test_private_terminal_is_absent_from_public_packets(self):
        result = plan(self.session, self.fight, self.runtime)
        self.assertEqual(
            [opcode for opcode, _ in result.private_packets], [12238, 13420]
        )
        self.assertNotIn(12238, [opcode for opcode, _ in result.public_packets])
        body = result.private_packets[0][1]
        self.assertEqual(body[12], 0)
        self.assertEqual(struct.unpack_from(">q", body, 14)[0], 10)
        self.assertEqual(result.private_runtime.fight.phase, "finished")
        self.assertEqual(result.runtime.fight.phase, "active")

    def test_last_alive_owner_uses_full_abandonment(self):
        self.fight.actors[20].hp = 0
        with self.assertRaisesRegex(ValueError, "Last PvE owner"):
            plan(self.session, self.fight, self.runtime)
        self.assertEqual(self.fight.actors[10].hp, 45)

    def test_stale_runtime_does_not_change_either_authoritative_object(self):
        self.runtime.fight = object()
        with self.assertRaisesRegex(ValueError, "runtime"):
            plan(self.session, self.fight, self.runtime)
        self.assertEqual(self.fight.phase, "active")
        self.assertEqual(self.fight.actors[10].hp, 45)

    def test_foreign_owner_cannot_withdraw_actor(self):
        with self.assertRaisesRegex(ValueError, "owner"):
            plan(Session(3, 10, "foreign", 527, 0), self.fight, self.runtime)

    def registry(self):
        other = Session(2, 20, "other", 527, 0)
        registry = Registry(lambda session: session in (self.session, other))
        # register requires one initial controlled owner; admission is already
        # covered separately. Install the admitted runtime for this transition.
        actor = self.fight.actors.pop(20)
        shared = registry.register(self.fight, self.session, runtime=self.runtime)
        self.fight.actors[20] = actor
        shared.participants[2] = other
        shared.connected.add(2)
        from collections import deque

        shared.outboxes[2] = deque()
        registry.by_actor[20] = registry.by_character[20] = self.fight.id
        return registry, shared, other

    def test_persistence_failure_does_not_commit_candidate_or_outboxes(self):
        registry, shared, _ = self.registry()

        def fail(original):
            self.assertIs(original, self.fight)
            self.assertEqual(original.actors[10].hp, 45)
            raise RuntimeError("transaction rolled back")

        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            registry.withdraw_pve(self.session, persist=fail)
        self.assertIs(shared.fight, self.fight)
        self.assertEqual(shared.connected, {1, 2})
        self.assertEqual(shared.withdrawals, {})
        self.assertFalse(shared.outboxes[2])

    def test_native_return_frees_withdrawn_owner_but_retains_encounter(self):
        registry, shared, other = self.registry()
        registry.withdraw_pve(
            self.session, persist=lambda original: {"character": {"hp": 45}}
        )
        self.assertEqual(shared.connected, {2})
        self.assertIn(77, registry.fights)
        self.assertIn(10, registry.by_character)
        self.assertNotIn(
            12238,
            [opcode for batch in shared.outboxes[2] for opcode, _ in batch.packets],
        )
        registry.return_withdrawn_pve(77, self.session, persist=lambda: {"hp": 45})
        self.assertNotIn(10, registry.by_character)
        self.assertNotIn(10, registry.by_actor)
        self.assertEqual(registry.by_character[20], 77)
        # A later finish of this historical encounter cannot erase this owner's
        # reservation for a subsequent fight.
        registry.by_actor[10] = registry.by_character[10] = 88
        shared.fight.phase = "finished"
        registry.remove_finished(77, lambda _: None)
        self.assertEqual(registry.by_actor[10], 88)
        self.assertEqual(registry.by_character[10], 88)

    def test_withdrawn_owner_no_longer_blocks_an_already_received_ack(self):
        registry, shared, other = self.registry()
        shared.ack.arm(4, (self.session, other))
        shared.ack.accept(other, struct.pack(">i", 4))
        shared.runtime.awaiting_ack = 4
        shared.runtime.pending = [(13420, struct.pack(">i", 77))]
        registry.withdraw_pve(
            self.session, persist=lambda original: {"character": {"hp": 45}}
        )
        self.assertIsNone(shared.ack.turn)
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertEqual(shared.connected, {2})

    def test_other_owner_ack_is_still_required_after_withdrawal(self):
        registry, shared, other = self.registry()
        shared.ack.arm(4, (self.session, other))
        shared.runtime.awaiting_ack = 4
        shared.runtime.pending = [(13420, struct.pack(">i", 77))]
        registry.withdraw_pve(
            self.session, persist=lambda original: {"character": {"hp": 45}}
        )
        self.assertEqual(shared.ack.expected, {2: "other"})
        self.assertEqual(shared.runtime.awaiting_ack, 4)
        self.assertFalse(shared.ack.complete)

    def test_ack_and_hp_candidates_are_discarded_together_on_storage_failure(self):
        registry, shared, other = self.registry()
        shared.ack.arm(4, (self.session, other))
        shared.ack.accept(other, struct.pack(">i", 4))
        shared.runtime.awaiting_ack = 4
        shared.runtime.pending = [(13420, struct.pack(">i", 77))]

        def fail(original):
            raise RuntimeError("storage unavailable")

        with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
            registry.withdraw_pve(self.session, persist=fail)
        self.assertEqual(shared.ack.expected, {1: "owner", 2: "other"})
        self.assertEqual(shared.runtime.awaiting_ack, 4)
        self.assertEqual(shared.fight.actors[10].hp, 45)

    def test_placement_withdrawal_keeps_remaining_owner_placement(self):
        registry, shared, _ = self.registry()
        self.fight.phase = "placement"
        self.fight.ready_owners = set()
        self.fight.order = []
        shared.runtime = None
        registry.withdraw_pve(
            self.session, persist=lambda original: {"character": {"hp": 45}}
        )
        self.assertEqual(shared.fight.phase, "placement")
        self.assertTrue(shared.fight.actors[10].pve_withdrawn)
        self.assertEqual(shared.fight.actors[20].hp, 55)

    def test_last_unready_owner_withdrawing_starts_already_ready_teammate(self):
        registry, shared, _ = self.registry()
        self.fight.phase = "placement"
        self.fight.ready_owners = {2}
        self.fight.order = []
        shared.runtime = None

        def ready(shared, fight, runtime):
            candidate = deepcopy(fight)
            historical = candidate.actors.pop(10)
            candidate.ready(2)
            candidate.actors[10] = historical
            return Transition(candidate, RuntimeMessages(candidate), ())

        registry.withdraw_pve(
            self.session,
            persist=lambda original: {"character": {"hp": 45}},
            placement_ready=ready,
        )
        self.assertEqual(shared.fight.phase, "active")
        self.assertNotIn(10, shared.fight.order)
        self.assertIn(20, shared.fight.order)

    def test_ready_adapter_keeps_withdrawn_owner_out_of_engine_initialization(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_ready import prepare_ready

        adapter = CombatSessionAdapter(object())
        self.fight.phase = "placement"
        self.fight.ready_owners = set()
        self.fight.order = []
        self.fight.actors[10].hp = 0
        self.fight.actors[10].pve_withdrawn = True
        sources = ({20: {"id": 20, "name": "Other"}}, {20: b""})

        def real_ready(fight, owner, ready, **kwargs):
            self.assertNotIn(10, fight.actors)
            return prepare_ready(
                fight,
                owner,
                ready,
                initialize=lambda preview, action: (preview, ()),
                stats_serializer=lambda actor: b"",
                effects_serializer=lambda: b"",
            )

        with patch.object(adapter, "player_sources", return_value=sources), patch(
            "wakfu_server.combat_ready.prepare_ready",
            side_effect=real_ready,
        ):
            transition = adapter.ready_transition(
                Session(2, 20, "other", 527, 0),
                self.fight,
                None,
                True,
                {},
                fight_start=False,
            )
        self.assertEqual(transition.fight.phase, "active")
        self.assertNotIn(10, transition.fight.order)
        self.assertEqual(transition.fight.actors[10].hp, 0)
        self.assertTrue(transition.fight.actors[10].pve_withdrawn)
        self.assertEqual(self.fight.phase, "placement")


class WithdrawalPostgresTests(PostgresCase):
    def test_account_withdrawal_retires_and_persists_all_owned_heroes(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = self.state(marker=True)
        hero = store.create_character(account, "Withdraw Hero")
        position = (3, 0, 0)
        fight.walkable.add(position)
        fight.placement[0].add(position)
        fight.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            position,
            hero["hp"] - 4,
            6,
            3,
            80,
            hero["level"],
            account,
            True,
            max_hp=hero["max_hp"],
        )
        adapter.registry.by_character[hero["id"]] = fight.id
        adapter.registry.by_actor[hero["id"]] = fight.id
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (fight.id, hero["id"], account, generation),
            )
        receipt = adapter.withdraw_pve(owner, character, b"")
        self.assertEqual(shared.fight.phase, "placement")
        self.assertTrue(shared.fight.actors[hero["id"]].pve_withdrawn)
        self.assertEqual(shared.fight.actors[hero["id"]].hp, 0)
        self.assertEqual(store.character(account, hero["id"])["hp"], hero["hp"] - 4)
        with store.connection() as db:
            ids = {
                row["character_id"]
                for row in db.execute(
                    "SELECT character_id FROM combat_pve_withdrawals WHERE account_id=%s",
                    (account,),
                )
            }
        self.assertEqual(ids, {character["id"], hero["id"]})
        adapter.return_withdrawn_pve(
            owner, fight.id, receipt["character"], struct.pack(">iB", fight.id, 1), wp=6
        )
        self.assertNotIn(hero["id"], adapter.registry.by_character)
        self.assertNotIn(character["id"], adapter.registry.by_character)
        self.assertEqual(adapter.registry.by_character[other["id"]], fight.id)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_pve_withdrawals "
                    "WHERE account_id=%s AND returned_at IS NULL",
                    (account,),
                ).fetchone()["n"],
                0,
            )

    def state(self, *, marker=False):
        import test_combat_abandon as fixture
        from collections import deque
        from wakfu_server import health_store
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        (
            store,
            account,
            generation,
            character,
            fight,
            runtime,
        ) = fixture.setup_abandon_state(self.store)
        other_account = store.register("other", "local-password")["id"]
        other_generation = store.begin_session(other_account)
        other = store.create_character(other_account, "Other")
        other = store.select_character(other_account, other_generation, other["id"])
        other = health_store.initialize(
            store, other_account, other_generation, other["id"], coefficient=0
        )
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants "
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (
                    fight.id,
                    other["id"],
                    other_account,
                    other_generation,
                    other["hp"],
                    other["max_hp"],
                    other["hp_damage"],
                    other["health_dead"],
                ),
            )
        adapter = CombatSessionAdapter(store)
        owner = adapter.session(account, generation, character)
        teammate = adapter.session(other_account, other_generation, other)
        if marker:
            fight.phase = "placement"
            fight.ready_owners.clear()
            fight.order.clear()
            runtime = None
            fight.walkable.add((2, 0, 0))
            fight.placement[0].add((2, 0, 0))
        shared = adapter.register(
            owner,
            fight,
            runtime=runtime,
            join_context=(
                {
                    "leaders": {0: character["id"], 1: -200},
                    "world_marker_cells": ((character["x"], character["y"]),),
                    "arena": {},
                    "terrain_effect_id": 46,
                    "terrain_instance_id": 1,
                    "duration_ms": 120000,
                }
                if marker
                else None
            ),
        )
        fight.actors[other["id"]] = Actor(
            other["id"],
            0,
            (2, 0, 0) if marker else (0, 0, 0),
            other["hp"],
            6,
            3,
            90,
            1,
            other_account,
            True,
        )
        shared.participants[other_account] = teammate
        shared.connected.add(other_account)
        shared.outboxes[other_account] = deque()
        adapter.registry.by_actor[other["id"]] = adapter.registry.by_character[
            other["id"]
        ] = fight.id
        if not marker:
            fight.ready(account)
            fight.ready(other_account)
        fight.actors[character["id"]].hp -= 5
        return (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        )

    def test_surrender_preserves_live_encounter_and_actual_wounds(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = self.state()

        receipt = adapter.withdraw_pve(owner, character, b"")
        self.assertEqual(receipt["character"]["hp"], character["hp"] - 5)
        self.assertFalse(receipt["character"]["health_dead"])
        self.assertEqual(shared.fight.phase, "active")
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "placement",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS n FROM combat_pve_withdrawals"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )
        returned = adapter.return_withdrawn_pve(
            owner, fight.id, receipt["character"], struct.pack(">iB", fight.id, 1), wp=6
        )
        self.assertEqual(returned["character"]["hp"], character["hp"] - 5)
        self.assertNotIn(character["id"], adapter.registry.by_character)
        self.assertEqual(adapter.registry.by_character[other["id"]], fight.id)
        with store.connection() as db:
            self.assertIsNotNone(
                db.execute("SELECT returned_at FROM combat_pve_withdrawals").fetchone()[
                    "returned_at"
                ]
            )

        from wakfu_server.fight_checkpoint_store import Checkpoints
        from wakfu_server.fight_store import create

        checkpoints = Checkpoints(store)
        with self.assertRaisesRegex(ValueError, "participant"):
            checkpoints.save_shared(shared, account, generation)
        # A voluntary withdrawal has a durable exclusion receipt, so this
        # owner can begin another encounter while the teammate continues.
        next_identity = create(store, account, generation, character["id"])
        self.assertNotEqual(next_identity, fight.id)

        from wakfu_server.combat_lifecycle import prepare_finish_shared
        from wakfu_server.combat_rewards import Policy

        shared.fight.actors[-200].hp = 0
        shared.fight.phase, shared.fight.winner = "finished", 0
        metadata = {
            character["id"]: dict(
                kind="player",
                account_id=account,
                name=character["name"],
                breed=character["breed"],
                is_male=True,
            ),
            other["id"]: dict(
                kind="player",
                account_id=other_account,
                name=other["name"],
                breed=other["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        policy_owners = []

        def policy(db, member, source):
            policy_owners.append(member["account_id"])
            return Policy(10, 5)

        batches = prepare_finish_shared(
            store,
            other_account,
            other_generation,
            other["id"],
            shared.runtime,
            metadata,
            duration_ms=100,
            fight_instance_id=fight.id,
            policy_resolver=policy,
            expected_accounts={account, other_account},
        )
        self.assertEqual(policy_owners, [other_account])
        self.assertEqual(batches[account], ())
        self.assertTrue(batches[other_account])
        self.assertEqual(
            store.character(account, character["id"])["kamas"], character["kamas"]
        )
        self.assertEqual(
            store.character(other_account, other["id"])["kamas"], other["kamas"] + 5
        )
        with store.connection() as db:
            rows = list(db.execute("SELECT character_id FROM fight_rewards"))
            self.assertEqual([row["character_id"] for row in rows], [other["id"]])

    def test_withdrawn_marker_leader_ack_then_durable_join_uses_retained_target_row(
        self,
    ):
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = self.state(marker=True)

        receipt = adapter.withdraw_pve(owner, character, b"")
        self.assertEqual(shared.fight.phase, "placement")
        returned = adapter.return_withdrawn_pve(
            owner,
            fight.id,
            receipt["character"],
            struct.pack(">iB", fight.id, 1),
            wp=6,
        )
        self.assertEqual(returned["character"]["id"], character["id"])
        self.assertNotIn(character["id"], adapter.registry.by_actor)
        self.assertEqual(adapter.registry.join_aliases[character["id"]], {fight.id})

        third_account = store.register("alias-joiner", "local-password")["id"]
        third_generation = store.begin_session(third_account)
        third_character = store.create_character(third_account, "AliasJoiner")
        third_character = store.select_character(
            third_account, third_generation, third_character["id"]
        )
        third = adapter.session(third_account, third_generation, third_character)
        stale = Session(
            third_account,
            third_character["id"],
            "stale-generation",
            third_character["map_id"],
            third_character.get("instance_id", 0),
        )
        with self.assertRaisesRegex(ValueError, "Stale combat session"):
            adapter.join(
                stale,
                struct.pack(">qB", character["id"], 0),
                Actor(
                    third_character["id"],
                    0,
                    (0, 0, 0),
                    third_character["hp"],
                    6,
                    3,
                    90,
                    1,
                    third_account,
                    True,
                ),
                actor_payload=lambda *_args: (b"", b""),
                bootstrap_packets=lambda *_args: ((12847, b"bootstrap"),),
            )
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM combat_fight_participants "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight.id, third_character["id"]),
                ).fetchone()
            )

        joined = adapter.join(
            third,
            struct.pack(">qB", character["id"], 0),
            Actor(
                third_character["id"],
                0,
                (0, 0, 0),
                third_character["hp"],
                6,
                3,
                90,
                1,
                third_account,
                True,
            ),
            actor_payload=lambda *_args: (b"", b""),
            bootstrap_packets=lambda *_args: ((12847, b"bootstrap"),),
        )
        self.assertIs(joined, shared)
        with store.connection() as db:
            target = db.execute(
                "SELECT p.account_id,p.team,p.session_generation,w.returned_at "
                "FROM combat_fight_participants p "
                "JOIN combat_pve_withdrawals w "
                "ON w.fight_id=p.fight_id AND w.character_id=p.character_id "
                "WHERE p.fight_id=%s AND p.character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            admitted = db.execute(
                "SELECT account_id,team,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s AND character_id=%s",
                (fight.id, third_character["id"]),
            ).fetchone()
        self.assertEqual(target["account_id"], account)
        self.assertEqual(target["team"], 0)
        self.assertEqual(target["session_generation"], generation)
        self.assertIsNotNone(target["returned_at"])
        self.assertEqual(admitted["account_id"], third_account)
        self.assertEqual(admitted["team"], 0)
        self.assertEqual(admitted["session_generation"], third_generation)

    def test_replacement_lease_returns_to_world_after_unsent_private_terminal(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = self.state()
        # Prepare durable withdrawal, but neither12238 nor12925 reaches the
        # old socket. Recovery must not revive the combat participant.
        receipt = adapter.withdraw_pve(owner, character, b"")
        store.end_session(account, generation)
        replacement_generation = store.begin_session(account)
        replacement_character = store.select_character(
            account, replacement_generation, character["id"]
        )
        replacement = adapter.session(
            account, replacement_generation, replacement_character
        )
        restored = adapter.recover_withdrawn_pve(replacement)
        self.assertEqual(restored["hp"], character["hp"] - 5)
        self.assertEqual(shared.fight.phase, "active")
        self.assertNotIn(character["id"], adapter.registry.by_character)
        self.assertEqual(adapter.registry.by_character[other["id"]], fight.id)
        self.assertEqual(shared.connected, {other_account})
        with self.assertRaisesRegex(ValueError, "owned PvE withdrawal"):
            adapter.return_withdrawn_pve(
                owner,
                fight.id,
                receipt["character"],
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
        with store.connection() as db:
            row = db.execute(
                "SELECT session_generation,returned_at FROM combat_pve_withdrawals"
            ).fetchone()
            self.assertEqual(row["session_generation"], replacement_generation)
            self.assertIsNotNone(row["returned_at"])
            self.assertEqual(
                db.execute(
                    "SELECT session_generation FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["session_generation"],
                generation,
            )

    def test_private_return_survives_registry_retirement(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = self.state()
        receipt = adapter.withdraw_pve(owner, character, b"")
        with adapter.registry.lock:
            adapter.registry._remove_locked(adapter.registry, shared)
        returned = adapter.return_withdrawn_pve(
            owner,
            fight.id,
            receipt["character"],
            struct.pack(">iB", fight.id, 1),
            wp=6,
            pending=receipt,
        )
        self.assertEqual(returned["character"]["hp"], character["hp"] - 5)
        with store.connection() as db:
            self.assertIsNotNone(
                db.execute("SELECT returned_at FROM combat_pve_withdrawals").fetchone()[
                    "returned_at"
                ]
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )

    def test_replacement_lease_recovers_without_registry_after_process_restart(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = self.state()
        adapter.withdraw_pve(owner, character, b"")
        with adapter.registry.lock:
            adapter.registry._remove_locked(adapter.registry, shared)
        store.end_session(account, generation)
        replacement_generation = store.begin_session(account)
        replacement_character = store.select_character(
            account, replacement_generation, character["id"]
        )
        replacement = adapter.session(
            account, replacement_generation, replacement_character
        )
        restored = adapter.recover_withdrawn_pve(replacement)
        self.assertEqual(restored["hp"], character["hp"] - 5)
        self.assertIsNone(adapter.recover_withdrawn_pve(replacement))
        with store.connection() as db:
            row = db.execute(
                "SELECT session_generation,returned_at FROM combat_pve_withdrawals"
            ).fetchone()
            self.assertEqual(row["session_generation"], replacement_generation)
            self.assertIsNotNone(row["returned_at"])
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "placement",
            )

    def test_last_teammate_abandons_before_first_withdrawal_ack(self):
        from wakfu_server import combat_abandon

        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = self.state()
        first = adapter.withdraw_pve(owner, character, b"")
        teammate = shared.participants[other_account]
        last = combat_abandon.prepare(
            store, other_account, other_generation, other, shared.runtime, b""
        )
        combat_abandon.return_to_world(
            store,
            other_account,
            other_generation,
            last["character"],
            shared.runtime,
            struct.pack(">iB", fight.id, 1),
            wp=6,
        )
        self.assertTrue(
            adapter.registry.retire_abandoned_single_owner(fight.id, teammate)
        )
        self.assertNotIn(other["id"], adapter.registry.by_character)
        self.assertNotIn(-200, adapter.registry.by_actor)
        # Retain only the pending private continuation; no active actor/group
        # reservation survives the last teammate's complete abandonment.
        self.assertIn(fight.id, adapter.registry.fights)
        returned = adapter.return_withdrawn_pve(
            owner,
            fight.id,
            first["character"],
            struct.pack(">iB", fight.id, 1),
            wp=6,
        )
        self.assertEqual(returned["character"]["hp"], character["hp"] - 5)
        self.assertNotIn(fight.id, adapter.registry.fights)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )


if __name__ == "__main__":
    unittest.main()
