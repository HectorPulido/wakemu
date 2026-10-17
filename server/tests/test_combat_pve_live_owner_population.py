"""Regression for retained KO participants versus living primary owners."""
import unittest
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Session
from wakfu_server.combat_pve_withdraw import live_owner_accounts, has_other_live_owner
from wakfu_server.combat_abandon import _participant


class LivePvEOwnerPopulationTests(unittest.TestCase):
    def fixture(self):
        owner = Actor(15, 0, (0, 0, 0), 1247, 6, 3, 100, 1, 2, True)
        historical = Actor(31, 0, (1, 0, 0), 50, 6, 3, 90, 1, 13, True)
        fixture = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "native_sram_double227_owner_population.json"
            ).read_text()
        )
        summon = Actor(208, 0, (2, 0, 0), 661, 6, 3, 80, 200, 2, True)
        summon.native_summon_source = deepcopy(fixture["native_summon_source"])
        fight = Fight(
            227,
            [owner, historical, summon, Actor(-200, 1, (3, 0, 0), 50, 3, 3, 10, 1)],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0), (2, 0, 0)}, 1: {(3, 0, 0)}},
        )
        fight.native_summon_registrations = {
            208: deepcopy(fixture["native_summon_registration"])
        }

        fight.ready(2)
        fight.ready(13)
        fight.apply_effect_damage(-200, 31, 50)
        historical.pve_withdrawn = True
        return fight, Session(2, 15, "owner", 1134, 0)

    def test_retained_returned_ko_and_alive_registered_summon_leave_one_owner(self):
        fight, session = self.fixture()
        before = {a.id: (a.hp, a.position) for a in fight.actors.values()}
        self.assertEqual(live_owner_accounts(fight), {2})
        self.assertFalse(has_other_live_owner(fight, session))
        self.assertIs(
            _participant(2, {"id": 15}, SimpleNamespace(fight=fight)), fight.actors[15]
        )
        self.assertEqual(
            {a.id: (a.hp, a.position) for a in fight.actors.values()}, before
        )

    def test_dead_requester_cannot_abort_the_other_surviving_owner(self):
        fight, _ = self.fixture()
        fight.actors[31].pve_withdrawn = False
        dead_session = Session(13, 31, "dead-owner", 1134, 0)
        self.assertTrue(has_other_live_owner(fight, dead_session))
        with self.assertRaisesRegex(ValueError, "foreign abandon"):
            _participant(13, {"id": 31}, SimpleNamespace(fight=fight))
        self.assertEqual(fight.actors[15].hp, 1247)
        self.assertEqual(fight.phase, "active")

    def test_foreign_and_already_withdrawn_requests_cannot_select_full_abort(self):
        fight, _ = self.fixture()
        for session in (
            Session(13, 15, "foreign", 1134, 0),
            Session(13, 31, "returned", 1134, 0),
            Session(2, 208, "summon-not-primary", 1134, 0),
        ):
            with self.subTest(actor=session.character_id, owner=session.account_id):
                with self.assertRaisesRegex(ValueError, "Invalid PvE exit owner"):
                    has_other_live_owner(fight, session)
        self.assertEqual(fight.actors[15].hp, 1247)

    def test_heroes_are_grouped_by_account_but_foreign_live_hero_blocks_abort(self):
        fight, session = self.fixture()
        hero = Actor(32, 0, (1, 0, 0), 20, 6, 3, 70, 1, 2, True)
        fight.actors[32] = hero
        self.assertEqual(live_owner_accounts(fight), {2})
        self.assertFalse(has_other_live_owner(fight, session))
        hero.owner_id = 13
        self.assertEqual(live_owner_accounts(fight), {2, 13})
        self.assertTrue(has_other_live_owner(fight, session))
        with self.assertRaisesRegex(ValueError, "foreign abandon"):
            _participant(2, {"id": 15}, SimpleNamespace(fight=fight))
        self.assertEqual(fight.actors[15].hp, 1247)

    def test_already_returned_primary_cannot_reenter_abandon_continuation(self):
        fight, _ = self.fixture()
        before = (fight.phase, fight.actors[15].hp, fight.actors[31].hp)
        with self.assertRaisesRegex(ValueError, "foreign abandon"):
            _participant(13, {"id": 31}, SimpleNamespace(fight=fight))
        self.assertEqual(
            (fight.phase, fight.actors[15].hp, fight.actors[31].hp), before
        )


from postgres_case import PostgresCase


class LastLiveOwnerAbandonIntegrationTests(PostgresCase):
    def test_durable_abort_and_native_return_retire_ko_history_and_alive_double(self):
        import struct
        from collections import deque
        from test_combat_abandon import setup_abandon_state
        from wakfu_server import combat_abandon
        from wakfu_server.combat_shared import Registry

        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        session = Session(account, character["id"], generation, 1134, 0)
        registry = Registry(lambda candidate: candidate == session)
        shared = registry.register(fight, session, runtime=runtime)
        fight.ready(account)
        self.assertEqual(fight.phase, "active")
        fixture = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "native_sram_double227_owner_population.json"
            ).read_text()
        )
        # Replay the captured native level/type/registration, rebinding only
        # instance ownership to the isolated test's real selected character.
        source = deepcopy(fixture["native_summon_source"])
        source.update(caster_id=character["id"], controller_id=character["id"])
        registration = deepcopy(fixture["native_summon_registration"])
        registration.update(caster_id=character["id"], controller_id=character["id"])
        registration["authority"]["native_controller_id"] = character["id"]
        registration["authority"]["summon_root_id"] = character["id"]
        for key in ("dpr_id", "dpu_id"):
            registration["authority"]["targeting"][key] = character["id"]
        double = Actor(208, 0, (0, 1, 0), 661, 6, 3, 80, 200, account, True)
        double.native_summon_source = source
        dead = Actor(31, 0, (1, 1, 0), 50, 6, 3, 90, 1, 13, True)
        fight.walkable.update({(0, 1, 0), (1, 1, 0)})
        fight.actors.update({31: dead, 208: double})
        fight.native_summon_registrations = {208: registration}
        historical = Session(13, 31, "returned-history", 1134, 0)
        shared.participants[13] = historical
        shared.returned.add(13)
        shared.outboxes[13] = deque()
        registry.by_actor.update({31: fight.id, 208: fight.id})
        registry.by_character[31] = fight.id
        fight.apply_effect_damage(-200, 31, 50)
        dead.pve_withdrawn = True
        before_hp = fight.actors[character["id"]].hp
        self.assertFalse(has_other_live_owner(fight, session))
        self.assertEqual(double.native_summon_source["level"], 200)
        result = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        self.assertTrue(result["applied"])
        self.assertEqual([opcode for opcode, _ in result["packets"]], [12238, 13420])
        self.assertEqual(fight.phase, "finished")
        self.assertIsNone(fight.winner)
        self.assertFalse(registry.retire_abandoned_single_owner(fight.id, session))
        with store.connection() as db:
            status = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
            ).fetchone()["status"]
        self.assertEqual(status, "aborted")
        returned = combat_abandon.return_to_world(
            store,
            account,
            generation,
            character,
            runtime,
            struct.pack(">iB", fight.id, 1),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        self.assertTrue(runtime.abandon_returned)
        self.assertTrue(returned["packets"])
        self.assertEqual(fight.actors[character["id"]].hp, before_hp)
        self.assertEqual((dead.hp, double.hp), (0, 661))
        self.assertTrue(registry.retire_abandoned_single_owner(fight.id, session))
        self.assertNotIn(fight.id, registry.fights)
        self.assertFalse(any(value == fight.id for value in registry.by_actor.values()))
        self.assertFalse(
            any(value == fight.id for value in registry.by_character.values())
        )
        repeated = combat_abandon.return_to_world(
            store,
            account,
            generation,
            character,
            runtime,
            struct.pack(">iB", fight.id, 1),
            wp=6,
        )
        self.assertFalse(repeated["applied"])
        self.assertEqual(repeated["packets"], [])


class UnreturnedKOExitClassificationTests(unittest.TestCase):
    def test_ko_population_alone_does_not_grant_native_abandon_authority(self):
        fight, session = LivePvEOwnerPopulationTests().fixture()
        fight.actors[31].pve_withdrawn = False
        before = (fight.phase, tuple(fight.order), fight.actors[15].hp)
        self.assertFalse(has_other_live_owner(fight, session))
        with self.assertRaisesRegex(ValueError, "foreign abandon"):
            _participant(2, {"id": 15}, SimpleNamespace(fight=fight))
        self.assertEqual((fight.phase, tuple(fight.order), fight.actors[15].hp), before)


class ActualWorldAbandonOwnerGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ast

        path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        callback = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "abandoned"
            and "Only a single-owner PvE fight can use abandon return"
            in ast.unparse(node)
        )
        cls.callback = compile(
            ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[])),
            str(path),
            "exec",
        )
        logout = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "shared_entry.runtime" in ast.unparse(node.test)
            and "abandon_owner" in ast.unparse(node.test)
            and "not shared_entry.connected" in ast.unparse(node.test)
        )
        cls.logout = compile(ast.Expression(logout.test), str(path), "eval")

    def fixture(self):
        fight, session = LivePvEOwnerPopulationTests().fixture()
        fight.phase = "finished"
        fight.winner = None
        shared = SimpleNamespace(
            fight=fight,
            is_duel=False,
            withdrawals={},
            settlement_ready=False,
            participants={2: session, 13: Session(13, 31, "returned", 1134, 0)},
            connected=set(),
            runtime=SimpleNamespace(abandon_owner=(2, 15)),
        )
        return fight, session, shared

    def test_actual_native_ack_guard_accepts_last_live_owner_with_retained_history(
        self,
    ):
        fight, session, shared = self.fixture()
        context = dict(
            abandoned=True,
            shared_state=shared,
            account_id=2,
            combat_session=session,
            has_other_live_owner=has_other_live_owner,
        )
        exec(self.callback, context)
        self.assertEqual((fight.actors[31].hp, fight.actors[208].hp), (0, 661))
        shared.participants[2] = Session(2, 15, "replacement", 1134, 0)
        with self.assertRaises(ValueError):
            exec(self.callback, context)
        self.assertEqual(fight.actors[15].hp, 1247)

    def test_actual_logout_guard_uses_survivors_and_preserves_owned_continuation(self):
        fight, session, shared = self.fixture()
        context = dict(
            shared_entry=shared,
            combat_session=session,
            has_other_live_owner=has_other_live_owner,
        )
        self.assertTrue(eval(self.logout, context))
        shared.runtime.abandon_owner = (13, 31)
        self.assertFalse(eval(self.logout, context))
        shared.runtime.abandon_owner = (2, 15)
        shared.connected.add(2)
        self.assertFalse(eval(self.logout, context))
        self.assertEqual((fight.actors[15].hp, fight.actors[208].hp), (1247, 661))
