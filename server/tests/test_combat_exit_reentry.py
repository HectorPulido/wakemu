"""Serving helpers over isolated PostgreSQL: exits cannot poison the next Ready."""
import ast
import struct
import tempfile
import test_combat_abandon as abandon_fixture
import unittest
from pathlib import Path
from unittest.mock import patch
import test_combat_rewards as reward_fixture
from postgres_case import PostgresCase
from wakfu_server import combat_abandon
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_lifecycle import prepare_finish, return_to_world
from wakfu_server.combat_rewards import Policy
from wakfu_server import health_store


class SharedPveAbandonDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        cls.session_ast = next(
            node
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )

    @staticmethod
    def _opcode_branch(root, opcode):
        for node in ast.walk(root):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if isinstance(test, ast.Compare) and any(
                isinstance(part, ast.Constant) and part.value == opcode
                for part in test.comparators
            ):
                return node
            if isinstance(test, ast.BoolOp) and any(
                isinstance(part, ast.Compare)
                and any(
                    isinstance(item, ast.Constant) and item.value == opcode
                    for item in part.comparators
                )
                for part in test.values
            ):
                return node
        raise AssertionError(f"dispatcher has no opcode {opcode} branch")

    @staticmethod
    def _calls(node):
        return {
            call.func.id if isinstance(call.func, ast.Name) else call.func.attr
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
        }

    def test_single_owner_shared_pve_13952_persists_abort_before_send(self):
        branch = self._opcode_branch(self.session_ast, 13952)
        calls = self._calls(branch)
        self.assertIn("prepare_abandon", calls)
        self.assertIn("checkpoint_fight", calls)
        self.assertIn("prepare_delivery", calls)
        self.assertIn("retire_abandoned_single_owner", self._calls(self.session_ast))

    def test_shared_abandon_return_skips_settlement_and_retires_registry(self):
        branch = self._opcode_branch(self.session_ast, 12925)
        calls = self._calls(branch)
        self.assertIn("return_abandon", calls)
        self.assertIn("retire_abandoned_single_owner", calls)
        self.assertIn("mark_returned", calls)
        self.assertIn("finish", calls)
        self.assertIn("retire_disconnected_pve", self._calls(self.session_ast))
        self.assertIn("retire_disconnected_abandon", self._calls(self.session_ast))
        self.assertIn("clear_disconnect_abort", self._calls(self.session_ast))


def fresh_ready(character, account, identity):
    cells = {(0, 0, 0), (1, 0, 0)}
    fight = Fight(
        identity,
        [
            Actor(
                character["id"],
                0,
                (0, 0, 0),
                character["hp"],
                6,
                3,
                0,
                account,
                1,
                True,
            ),
            Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
        ],
        cells,
        {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
    )
    # This test isolates serving transitions, not a breed initialization audit.
    preview, runtime, packets = prepare_ready(
        fight,
        account,
        True,
        initialize=lambda preview, action: (preview, ()),
        stats_serializer=lambda actor: b"",
        effects_serializer=lambda: b"\0\0",
    )
    return fight, preview, runtime, packets


class ExitReentryTests(PostgresCase):
    def _shared_pve_roster(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.fight_store import create, join_participant
        from wakfu_server.monsters import owned_instance

        self.store.clock = lambda: 1000
        owners = []
        for name in ("shared-owner-a", "shared-owner-b"):
            account = self.store.register(name, "local-password")["id"]
            generation = self.store.begin_session(account)
            character = self.store.create_character(account, name)
            character = self.store.select_character(
                account, generation, character["id"]
            )
            character = health_store.initialize(
                self.store, account, generation, character["id"], coefficient=0
            )
            owners.append((account, generation, character))

        account_a, generation_a, char_a = owners[0]
        account_b, generation_b, char_b = owners[1]
        fight_id = create(self.store, account_a, generation_a, char_a["id"])
        member = owned_instance(5525, 1, -200, map_id=char_a["map_id"], x=3, y=0, z=0)
        fight = Fight(
            fight_id,
            [
                Actor(
                    char_a["id"],
                    0,
                    (0, 0, 0),
                    char_a["hp"],
                    6,
                    3,
                    100,
                    1,
                    account_a,
                    True,
                    max_hp=char_a["max_hp"],
                ),
                Actor(
                    member["id"],
                    1,
                    (3, 0, 0),
                    member["hp"],
                    4,
                    2,
                    10,
                    member["level"],
                    max_hp=member["max_hp"],
                ),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        groups = PersistentGroups(self.store)
        group_key = (char_a["map_id"], char_a.get("instance_id", 0), 501)
        groups.register(*group_key, [member])
        group_lease, _ = groups.claim(group_key, generation_a, fight_id)

        adapter = CombatSessionAdapter(self.store)
        session_a = adapter.session(account_a, generation_a, char_a)
        shared = adapter.register(
            session_a,
            fight,
            runtime=None,
            group_lease=group_lease,
            join_context={"monsters": [member]},
        )
        session_b = adapter.session(account_b, generation_b, char_b)

        def persist_member(candidate, actor, current_shared, session):
            with self.store.connection() as db:
                join_participant(
                    self.store,
                    db,
                    session.account_id,
                    session.generation,
                    session.character_id,
                    fight_id,
                    target_character_id=char_a["id"],
                    team=0,
                )

        adapter.registry.join(
            session_b,
            struct.pack(">qB", char_a["id"], 0),
            Actor(
                char_b["id"],
                0,
                (1, 0, 0),
                char_b["hp"],
                6,
                3,
                90,
                1,
                account_b,
                True,
                max_hp=char_b["max_hp"],
            ),
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: (),
            persist_member=persist_member,
        )
        return self.store, adapter, groups, shared, (session_a, session_b), owners

    def test_single_owner_shared_pve_abandon_returns_and_retires_durable_registry(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            runtime,
        ) = abandon_fixture.setup_abandon_state(self.store)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (generation, fight.id, character["id"]),
            )
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.fight_checkpoint_store import Checkpoints
        from wakfu_server.fight_store import activate, create

        adapter = CombatSessionAdapter(store)
        owner = adapter.session(account, generation, character)
        shared = adapter.register(owner, fight, runtime=runtime)
        checkpoints = Checkpoints(store)

        abandoned = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        revision, terminal = checkpoints.save_shared(
            shared, account, generation, status="aborted"
        )
        self.assertTrue(terminal)
        self.assertGreater(revision, 0)
        returned = combat_abandon.return_to_world(
            store,
            account,
            generation,
            abandoned["character"],
            runtime,
            struct.pack(">iB", fight.id, 1),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        self.assertTrue(adapter.registry.retire_abandoned_single_owner(fight.id, owner))
        self.assertNotIn(fight.id, adapter.registry.fights)
        self.assertNotIn(character["id"], adapter.registry.by_actor)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["count"],
                0,
            )
        next_fight = create(store, account, generation, character["id"])
        activate(store, account, generation, character["id"], next_fight)

    def test_last_shared_pve_disconnect_persists_abort_before_registry_cleanup(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            runtime,
        ) = abandon_fixture.setup_abandon_state(self.store)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (generation, fight.id, character["id"]),
            )
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_health import persist_aborted_fight
        from wakfu_server.fight_store import activate, create

        adapter = CombatSessionAdapter(store)
        owner = adapter.session(account, generation, character)
        adapter.register(owner, fight, runtime=runtime)
        fight.ready(account)
        fight.actors[character["id"]].hp -= 5
        self.assertEqual(adapter.disconnect(owner), [fight.id])
        shared = adapter.registry.lookup(fight.id)
        self.assertTrue(shared.disconnect_abort_pending)

        exited = persist_aborted_fight(store, account, generation, character, fight)
        self.assertIsNotNone(exited)
        self.assertTrue(adapter.registry.retire_disconnected_pve(fight.id, owner))
        self.assertNotIn(fight.id, adapter.registry.fights)
        self.assertEqual(
            store.character(account, character["id"])["hp"], character["hp"] - 5
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
        next_fight = create(store, account, generation, character["id"])
        activate(store, account, generation, character["id"], next_fight)

    def test_abort_persistence_failure_keeps_registry_and_blocks_new_fight(self):
        (
            store,
            account,
            generation,
            character,
            fight,
            runtime,
        ) = abandon_fixture.setup_abandon_state(self.store)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (generation, fight.id, character["id"]),
            )
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_health import persist_aborted_fight
        from wakfu_server.combat_state import Actor, Fight

        adapter = CombatSessionAdapter(store)
        owner = adapter.session(account, generation, character)
        adapter.register(owner, fight, runtime=runtime)
        adapter.disconnect(owner)
        shared = adapter.registry.lookup(fight.id)
        before = store.character(account, character["id"])

        with patch.object(
            store, "connection", side_effect=RuntimeError("db unavailable")
        ):
            with self.assertRaisesRegex(RuntimeError, "db unavailable"):
                persist_aborted_fight(store, account, generation, character, fight)

        self.assertTrue(shared.disconnect_abort_pending)
        # The dispatcher retires only inside the successful-result branch; a
        # failed barrier clears the claim but leaves its indexes registered.
        adapter.registry.clear_disconnect_abort(fight.id)
        self.assertIn(character["id"], adapter.registry.by_actor)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "placement",
            )
        self.assertEqual(store.character(account, character["id"])["hp"], before["hp"])
        conflicting_fight = Fight(
            fight.id + 1,
            [
                Actor(
                    character["id"],
                    0,
                    (0, 0, 0),
                    character["hp"],
                    6,
                    3,
                    0,
                    account,
                    1,
                    True,
                ),
                Actor(-201, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        with self.assertRaisesRegex(ValueError, "already registered"):
            adapter.registry.register(conflicting_fight, owner)

    def test_abandon_return_allows_native_transport_and_new_durable_fight(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                generation,
                character,
                fight,
                runtime,
            ) = abandon_fixture.setup_abandon_state(self.store)
            origin = dict(map_id=1134, instance_id=0, x=-10, y=-11, z=-1)
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        origin["map_id"],
                        origin["instance_id"],
                        origin["x"],
                        origin["y"],
                        origin["z"],
                        character["id"],
                    ),
                )
            character = store.character(account, character["id"])

            from wakfu_server.combat_group_store import PersistentGroups
            from wakfu_server.monsters import owned_instance

            groups = PersistentGroups(store)
            group_key = groups.register(
                1134,
                0,
                501,
                [owned_instance(5525, 1, -201, map_id=1134, x=-7, y=-7, z=-1)],
            )
            group_lease, _ = groups.claim(group_key, generation, fight.id)

            abandoned = combat_abandon.prepare(
                store, account, generation, character, runtime, b""
            )
            from wakfu_server.fight_checkpoint_store import Checkpoints

            checkpoints = Checkpoints(store)
            revision = checkpoints.save(account, generation, fight, runtime=runtime)
            checkpoints.end(
                account,
                generation,
                fight.id,
                expected_revision=revision,
                status="aborted",
            )
            returned = combat_abandon.return_to_world(
                store,
                account,
                generation,
                abandoned["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertTrue(returned["applied"])
            # Match the post-callback group release performed by the world handler.
            self.assertTrue(groups.finish(group_lease, defeated=False))
            self.assertEqual(len(groups.available(1134, 0)), 1)
            self.assertEqual(
                tuple(
                    returned["character"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                tuple(origin[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            )

            from wakfu_server.native_transports import resolve
            from wakfu_server.transport_discovery import known_all
            from wakfu_server.fight_store import create, activate

            destination_id = next(
                identity for identity in known_all()[1] if identity != 31316
            )
            route = resolve(
                returned["character"],
                struct.pack(">qq", 31316, destination_id),
                known_ids=known_all()[1],
                waive_criteria=True,
            )
            moved = store.transition_map(
                account,
                generation,
                character["id"],
                returned["character"],
                route["destination"],
            )
            self.assertEqual(moved["map_id"], route["destination"]["map_id"])

            next_fight = create(store, account, generation, character["id"])
            activate(store, account, generation, character["id"], next_fight)
            with store.connection() as db:
                states = {
                    row["id"]: row["status"]
                    for row in db.execute(
                        "SELECT id,status FROM combat_fights WHERE id=ANY(%s)",
                        ([fight.id, next_fight],),
                    )
                }
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards WHERE fight_id=%s",
                        (fight.id,),
                    ).fetchone()["count"],
                    0,
                )
            self.assertEqual(states, {fight.id: "aborted", next_fight: "active"})
            self.assertEqual(checkpoints.read(account, fight.id)["status"], "aborted")

    def test_disconnect_without_return_callback_keeps_abort_terminal_and_recoverable(
        self,
    ):
        (
            store,
            account,
            generation,
            character,
            fight,
            runtime,
        ) = abandon_fixture.setup_abandon_state(self.store)
        fight.ready(account)
        fight.actors[character["id"]].hp -= 5
        abandoned = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        from wakfu_server.fight_checkpoint_store import Checkpoints

        checkpoints = Checkpoints(store)
        revision = checkpoints.save(account, generation, fight, runtime=runtime)
        checkpoints.end(
            account,
            generation,
            fight.id,
            expected_revision=revision,
            status="aborted",
        )
        self.assertEqual(abandoned["character"]["hp"], character["hp"] - 5)
        self.assertEqual(checkpoints.read(account, fight.id)["status"], "aborted")

        restarted = self.reopen()
        recovery = Checkpoints(restarted)
        from wakfu_server.fight_store import create, activate

        self.assertEqual(recovery.recover_interrupted(), 0)
        self.assertEqual(recovery.read(account, fight.id)["status"], "aborted")
        self.assertEqual(
            restarted.character(account, character["id"])["hp"], character["hp"] - 5
        )
        next_generation = restarted.begin_session(account)
        restarted.select_character(account, next_generation, character["id"])
        next_fight = create(restarted, account, next_generation, character["id"])
        activate(restarted, account, next_generation, character["id"], next_fight)
        with restarted.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (next_fight,)
                ).fetchone()["status"],
                "active",
            )

    def test_active_abort_return_and_new_ready_preserve_own_damage(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                generation,
                char,
                fight,
                runtime,
            ) = abandon_fixture.setup_abandon_state(self.store)
            fight.ready(account)
            fight.actors[char["id"]].hp -= 5
            runtime.awaiting_ack = 1
            runtime.pending = [(1, b"old pending")]
            aborted = combat_abandon.prepare(
                store, account, generation, char, runtime, b""
            )
            returned = combat_abandon.return_to_world(
                store,
                account,
                generation,
                aborted["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertEqual(returned["character"]["hp"], char["hp"] - 5)
            source, next_fight, next_runtime, packets = fresh_ready(
                returned["character"], account, fight.id + 1
            )
            self.assertEqual(
                (source.phase, next_fight.phase, fight.phase),
                ("placement", "active", "finished"),
            )
            self.assertEqual(next_fight.actors[char["id"]].hp, char["hp"] - 5)
            self.assertIsNone(next_runtime.awaiting_ack)
            self.assertFalse(hasattr(next_runtime, "abandon_owner"))
            self.assertEqual([op for op, _ in packets].count(12514), 1)
            self.assertEqual(runtime.pending, [])

    def test_victory_return_and_new_ready_do_not_reuse_finished_fsm(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = reward_fixture.setup_reward_state(self.store)
            char = health_store.initialize(
                store, account, generation, char["id"], coefficient=0
            )
            from wakfu_server.combat_runtime_messages import RuntimeMessages

            runtime = RuntimeMessages(fight)
            fight.actors[char["id"]].hp = char["hp"]
            fight.actors[char["id"]].max_hp = char["max_hp"]
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }
            done = prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy=Policy(),
            )
            result = return_to_world(
                store,
                account,
                generation,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 0),
                wp=6,
            )
            source, next_fight, next_runtime, packets = fresh_ready(
                result["character"], account, fight.id + 1
            )
            self.assertEqual(
                (fight.phase, source.phase, next_fight.phase),
                ("finished", "placement", "active"),
            )
            self.assertEqual(
                next_fight.actors[char["id"]].hp, result["character"]["hp"]
            )
            self.assertEqual(next_fight.ready_owners, {account})
            self.assertFalse(hasattr(next_runtime, "abandon_owner"))

    def test_last_shared_pve_disconnect_saves_every_owner_hp_and_restores_starter_group(
        self,
    ):
        from wakfu_server.combat_health import persist_aborted_shared_fight

        store, adapter, groups, shared, sessions, owners = self._shared_pve_roster()
        session_a, session_b = sessions
        char_a, char_b = owners[0][2], owners[1][2]
        shared.fight.ready(session_a.account_id)
        shared.fight.actors[char_a["id"]].hp -= 5
        shared.fight.actors[char_b["id"]].hp -= 9
        self.assertEqual(adapter.disconnect(session_a), [shared.fight.id])
        store.end_session(session_a.account_id, session_a.generation)
        self.assertEqual(adapter.disconnect(session_b), [shared.fight.id])
        self.assertTrue(shared.disconnect_abort_pending)

        saved = persist_aborted_shared_fight(store, shared, groups=groups)
        self.assertTrue(saved[char_a["id"]]["applied"])
        self.assertTrue(saved[char_b["id"]]["applied"])
        self.assertEqual(
            store.character(session_a.account_id, char_a["id"])["hp"], char_a["hp"] - 5
        )
        self.assertEqual(
            store.character(session_b.account_id, char_b["id"])["hp"], char_b["hp"] - 9
        )
        self.assertTrue(
            adapter.registry.retire_disconnected_pve(shared.fight.id, session_b)
        )
        self.assertNotIn(shared.fight.id, adapter.registry.fights)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s",
                    (shared.fight.id,),
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM fight_health_exits "
                    "WHERE fight_id=%s AND reason='abort'",
                    (shared.fight.id,),
                ).fetchone()["count"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_groups WHERE map_id=%s "
                    "AND instance_id=%s AND group_id=501",
                    (char_a["map_id"], char_a.get("instance_id", 0)),
                ).fetchone()["status"],
                "available",
            )
        retry = persist_aborted_shared_fight(store, shared, groups=groups)
        self.assertFalse(retry[char_a["id"]]["applied"])
        self.assertFalse(retry[char_b["id"]]["applied"])

    def test_shared_abort_rejects_character_hp_changed_since_durable_join_baseline(
        self,
    ):
        from wakfu_server.combat_health import persist_aborted_shared_fight

        store, adapter, groups, shared, sessions, owners = self._shared_pve_roster()
        session_a, session_b = sessions
        char_a = owners[0][2]
        adapter.disconnect(session_a)
        store.end_session(session_a.account_id, session_a.generation)
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=hp-1,hp_damage=hp_damage+1 WHERE id=%s",
                (char_a["id"],),
            )
        shared.fight.actors[char_a["id"]].hp -= 4
        adapter.disconnect(session_b)
        with self.assertRaisesRegex(ValueError, "health changed since fight entry"):
            persist_aborted_shared_fight(store, shared, groups=groups)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s",
                    (shared.fight.id,),
                ).fetchone()["status"],
                "placement",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM fight_health_exits WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()["count"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_groups WHERE map_id=%s "
                    "AND instance_id=%s AND group_id=501",
                    (char_a["map_id"], char_a.get("instance_id", 0)),
                ).fetchone()["status"],
                "fighting",
            )
        self.assertTrue(shared.disconnect_abort_pending)

    def test_shared_abort_rejects_replaced_generation_for_earlier_disconnected_owner(
        self,
    ):
        from wakfu_server.combat_health import persist_aborted_shared_fight

        store, adapter, groups, shared, sessions, owners = self._shared_pve_roster()
        session_a, session_b = sessions
        adapter.disconnect(session_a)
        store.end_session(session_a.account_id, session_a.generation)
        replacement_generation = store.begin_session(session_a.account_id)
        store.select_character(
            session_a.account_id, replacement_generation, session_a.character_id
        )
        self.assertNotEqual(replacement_generation, session_a.generation)
        adapter.disconnect(session_b)
        with self.assertRaisesRegex(ValueError, "generation was replaced"):
            persist_aborted_shared_fight(store, shared, groups=groups)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s",
                    (shared.fight.id,),
                ).fetchone()["status"],
                "placement",
            )

    def test_shared_abort_serializes_absent_session_against_new_login(self):
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        from wakfu_server import combat_health

        store, adapter, groups, shared, sessions, owners = self._shared_pve_roster()
        session_a, session_b = sessions
        char_a = owners[0][2]
        adapter.disconnect(session_a)
        store.end_session(session_a.account_id, session_a.generation)
        shared.fight.actors[char_a["id"]].hp -= 5
        adapter.disconnect(session_b)

        entered, continue_abort = threading.Event(), threading.Event()
        actual_persist = combat_health.persist

        def gated_persist(*args, **kwargs):
            entered.set()
            if not continue_abort.wait(5):
                raise RuntimeError("abort test gate timed out")
            return actual_persist(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch.object(combat_health, "persist", side_effect=gated_persist):
                abort_result = pool.submit(
                    combat_health.persist_aborted_shared_fight,
                    store,
                    shared,
                    groups=groups,
                )
                self.assertTrue(entered.wait(5))
                replacement = pool.submit(store.begin_session, session_a.account_id)
                time.sleep(0.2)
                self.assertFalse(replacement.done())
                continue_abort.set()
                saved = abort_result.result(timeout=5)
                new_generation = replacement.result(timeout=5)

        self.assertTrue(saved[char_a["id"]]["applied"])
        self.assertNotEqual(new_generation, session_a.generation)
        self.assertEqual(
            store.character(session_a.account_id, char_a["id"])["hp"],
            char_a["hp"] - 5,
        )
