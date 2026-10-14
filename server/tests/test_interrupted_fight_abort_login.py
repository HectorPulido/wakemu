"""Startup abort frees selected characters and dungeon retry reservations."""

import test_dungeon_abort_binding as dungeon_fixture
from postgres_case import PostgresCase
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server import fight_store


class InterruptedFightLoginTests(PostgresCase):
    def setUp(self):
        PostgresCase.setUp(self)
        self.store.clock = lambda: 1000
        self.account = self.store.register("startup-abort", "testing-local")["id"]
        self.character = self.store.create_character(self.account, "Startup Hero")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        from wakfu_server.combat_state import Actor, Fight

        player = Actor(
            self.character, 0, (0, 0, 0), 60, 6, 3, 10, 1, self.account, True
        )
        enemy = Actor(-200, 1, (1, 0, 0), 12, 6, 3, 5, 1)
        identity = fight_store.create(
            self.store, self.account, self.generation, self.character
        )
        fight_store.activate(
            self.store, self.account, self.generation, self.character, identity
        )
        self.fight = Fight(
            identity,
            [player, enemy],
            {player.position, enemy.position},
            {0: {player.position}, 1: {enemy.position}},
        )
        self.fight.ready(self.account)
        self.checkpoints = Checkpoints(self.store)

    def test_startup_abort_allows_fresh_login_and_new_active_fight(self):
        actor = self.fight.actors[self.character]
        actor.ap -= 2
        actor.mp -= 1
        self.checkpoints.save(self.account, self.generation, self.fight)
        before = self.store.character(self.account, self.character)

        restarted = self.reopen()
        recovery = Checkpoints(restarted)
        self.assertEqual(recovery.recover_interrupted(), 1)
        self.assertEqual(recovery.recover_interrupted(), 0)
        snapshot = recovery.read(self.account, self.fight.id)
        self.assertEqual(snapshot["status"], "aborted")
        self.assertEqual(snapshot["snapshot"]["actors"][str(self.character)]["ap"], 4)
        self.assertEqual(snapshot["snapshot"]["actors"][str(self.character)]["mp"], 2)

        generation = restarted.begin_session(self.account)
        restarted.select_character(self.account, generation, self.character)
        character = restarted.character(self.account, self.character)
        self.assertEqual(character["hp"], before["hp"])
        adapter = CombatSessionAdapter(restarted)
        adapter.session(self.account, generation, character)
        self.assertIsNone(adapter.lookup_character(self.character))
        identity = fight_store.create(
            restarted, self.account, generation, self.character
        )
        fight_store.activate(
            restarted, self.account, generation, self.character, identity
        )
        with restarted.connection() as db:
            statuses = {
                row["id"]: row["status"]
                for row in db.execute(
                    "SELECT id,status FROM combat_fights WHERE id=ANY(%s)",
                    ([self.fight.id, identity],),
                )
            }
        self.assertEqual(statuses, {self.fight.id: "aborted", identity: "active"})


class InterruptedDungeonRetryTests(PostgresCase):
    install_context_policy = (
        dungeon_fixture.DungeonAbortBindingTests.install_context_policy
    )
    player = dungeon_fixture.DungeonAbortBindingTests.player
    party = dungeon_fixture.DungeonAbortBindingTests.party
    create = dungeon_fixture.DungeonAbortBindingTests.create

    def setUp(self):
        PostgresCase.setUp(self)
        from types import SimpleNamespace
        from wakfu_server.maps.dungeon_progression import initialize_run

        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="a" * 64,
            rooms=(SimpleNamespace(order=1, monsters=(monster,)),),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

    make_bound_fight = dungeon_fixture.DungeonAbortBindingTests.make_bound_fight

    def test_actual_startup_abort_reconciles_room_and_allows_login_retry(self):
        from wakfu_server.maps.dungeon_fight_binding import reconcile_aborted_encounters

        identity = self.make_bound_fight()
        restarted = self.reopen()
        Checkpoints(restarted).recover_interrupted()
        with restarted.connection() as db:
            results = reconcile_aborted_encounters(db)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["aborted"])
            self.assertEqual(results[0]["current_room"], 1)
            self.assertEqual(results[0]["revision"], 1)
            self.assertEqual(reconcile_aborted_encounters(db), ())

        member = self.members[0]
        # Retry through the reopened process, including its session clock.
        self.store = restarted
        generation = restarted.begin_session(member["account"])
        restarted.select_character(
            member["account"], generation, member["character"]["id"]
        )
        member["generation"] = generation
        replacement = self.make_bound_fight()
        with restarted.connection() as db:
            rows = {
                row["fight_id"]: row["status"]
                for row in db.execute(
                    "SELECT fight_id,status FROM dungeon_room_encounters "
                    "WHERE fight_id=ANY(%s)",
                    ([identity, replacement],),
                )
            }
        self.assertEqual(rows, {identity: "aborted", replacement: "active"})
