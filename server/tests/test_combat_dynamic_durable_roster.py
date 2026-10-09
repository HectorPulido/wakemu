"""Registered class actors remain in snapshots, outside durable PC membership."""
from contextlib import nullcontext
from dataclasses import asdict
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.fight_store import settle_shared
from wakfu_server.combat_abandon import _participant
from wakfu_server.combat_health import persist_aborted_shared_fight


class Cursor:
    def __init__(self, rows=()):
        self.rows = tuple(rows)

    def __iter__(self):
        return iter(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class DurableDB:
    def __init__(self):
        self.statements = []
        self.members = [
            dict(
                character_id=6,
                account_id=9,
                team=0,
                session_generation="current",
                withdrawn=False,
            )
        ]

    def execute(self, sql, params):
        self.statements.append((sql, params))
        if "SELECT status FROM combat_fights" in sql:
            return Cursor([dict(status="active")])
        if "SELECT session_generation FROM combat_fight_participants" in sql:
            return Cursor([dict(session_generation="current")])
        if "FROM combat_fight_participants" in sql:
            return Cursor(self.members)
        if "SELECT id FROM characters" in sql:
            return Cursor([dict(id=6)])
        return Cursor()


class DynamicDurableRosterTests(unittest.TestCase):
    def fixture(self):
        owner = Actor(6, 0, (0, 0, 0), 100, 6, 3, 100, 200, owner_id=9, controlled=True)
        enemy = Actor(-7, 1, (2, 0, 0), 50, 4, 3, 10, 1)
        beacon = Actor(222, 0, (1, 0, 0), 20, 0, 0, 0, 200, owner_id=9, controlled=True)
        fight = Fight(
            47,
            [owner, enemy],
            {owner.position, enemy.position, beacon.position},
            {0: {owner.position}, 1: {enemy.position}},
        )
        fight.actors[beacon.id] = beacon
        beacon.native_controller_id = owner.id
        beacon.native_summon_source = dict(
            ref=297,
            level=200,
            caster_id=6,
            controller_id=6,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        authority = NativeActorAuthority(
            targeting={},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=297,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=False,
            is_summon=True,
            native_real_level=200,
            native_controller_id=6,
        )
        fight.native_summon_registrations = {
            222: dict(
                actor_id=222, caster_id=6, controller_id=6, authority=asdict(authority)
            )
        }
        return fight, DurableDB()

    def test_checkpoint_accepts_registered_beacon_but_preserves_all_actors(self):
        fight, db = self.fixture()
        Checkpoints._validate_roster(db, fight)
        self.assertEqual(set(fight.actors), {6, -7, 222})
        self.assertEqual(db.members[0]["character_id"], 6)

    def test_abandon_ownership_counts_characters_and_rejects_summon_identity(self):
        fight, _ = self.fixture()
        runtime = SimpleNamespace(fight=fight)
        self.assertIs(_participant(9, {"id": 6}, runtime), fight.actors[6])
        with self.assertRaises(ValueError):
            _participant(9, {"id": 222}, runtime)
        fight.native_summon_registrations.clear()
        with self.assertRaises(ValueError):
            _participant(9, {"id": 6}, runtime)

    def test_disconnect_abort_validates_pc_roster_before_durable_status_fence(self):
        fight, db = self.fixture()
        shared = SimpleNamespace(
            fight=fight,
            participants={
                9: SimpleNamespace(account_id=9, character_id=6, generation="current")
            },
        )
        original_execute = db.execute

        def finished_status(sql, params):
            if "SELECT status FROM combat_fights" in sql:
                return Cursor([dict(status="finished")])
            return original_execute(sql, params)

        db.execute = finished_status
        store = SimpleNamespace(connection=lambda: nullcontext(db))
        with self.assertRaisesRegex(ValueError, "not available for abort"):
            persist_aborted_shared_fight(store, shared)
        fight.actors[222].owner_id = 10
        with self.assertRaises(ValueError):
            persist_aborted_shared_fight(store, shared)

    def test_settlement_keeps_beacon_and_monster_in_terminal_snapshot(self):
        fight, db = self.fixture()
        fight.phase, fight.winner = "finished", 0
        store = SimpleNamespace(
            connection=lambda: nullcontext(db),
            lock_character=lambda *args: None,
            now=lambda: 0,
        )
        seen = []
        result = settle_shared(
            store,
            9,
            "current",
            6,
            fight,
            lambda connection, members, actual: seen.append((members, actual))
            or ("settled",),
        )
        self.assertEqual(result, ("settled",))
        self.assertEqual([r["character_id"] for r in seen[0][0]], [6])
        terminal = next(
            params[3].obj
            for sql, params in db.statements
            if sql.startswith("INSERT INTO fight_checkpoints")
        )
        self.assertEqual(set(terminal["actors"]), {"6", "-7", "222"})
        self.assertIn("222", terminal["native_summon_registrations"])

    def test_unregistered_controlled_actor_and_changed_owner_remain_rejected(self):
        for change in ("unregistered", "owner", "durable_owner"):
            fight, db = self.fixture()
            if change == "unregistered":
                fight.native_summon_registrations.clear()
            elif change == "owner":
                fight.actors[222].owner_id = 10
            else:
                db.members[0]["account_id"] = 10
            with self.subTest(change=change), self.assertRaises(ValueError):
                Checkpoints._validate_roster(db, fight)
            fight.phase, fight.winner = "finished", 0
            store = SimpleNamespace(
                connection=lambda: nullcontext(db),
                lock_character=lambda *args: None,
                now=lambda: 0,
            )
            with self.subTest(settlement_change=change), self.assertRaises(ValueError):
                settle_shared(
                    store,
                    9,
                    "current",
                    6,
                    fight,
                    lambda *args: self.fail("Invalid roster was settled"),
                )
