"""Native slot-management framing, ownership, transaction and reconnect cases."""
from copy import deepcopy
from dataclasses import replace
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase

from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.characters.captured_roster_management import (
    decode_request,
    release_slot,
    rename_slot,
    manage,
)


def populated(owner_id=7):
    slots = [None] * 10
    slots[2], slots[6] = CapturedCreature(2, 1152, "Alpha"), CapturedCreature(
        6, 4, "Beta"
    )
    return OwnedCapturedRoster(owner_id, tuple(slots), (True,) * 10, 6)


def rename_body(owner_id, slot, name, flag=1):
    raw = name.encode("utf-8")
    return struct.pack(">qbB", owner_id, slot, len(raw)) + raw + bytes((flag,))


class CapturedManagementTests(unittest.TestCase):
    def test_release_and_rename_have_distinct_original_native_layouts(self):
        self.assertEqual(
            decode_request(12014, bytes.fromhex("060000000000000007")), (7, 6, None)
        )
        self.assertEqual(
            decode_request(13068, rename_body(7, 6, "Étoile")), (7, 6, "Étoile")
        )
        self.assertEqual(
            rename_body(7, 6, "Étoile"),
            bytes.fromhex("00000000000000070607c389746f696c6501"),
        )  # Exact original cnv writer oracle.
        # Reversed fields can still form syntactically valid bytes. Decode the
        # native layout; ownership validation rejects the resulting foreign ID.
        self.assertEqual(
            decode_request(12014, struct.pack(">qb", 7, 6)), (1798, 0, None)
        )

    def test_malformed_frames_utf8_slots_and_unqualified_flag_are_rejected(self):
        valid = rename_body(7, 6, "Alpha")
        bad = [
            (12014, b""),
            (12014, struct.pack(">bq", -1, 7)),
            (12014, struct.pack(">bq", 10, 7)),
            (12014, struct.pack(">bq", 2, 0)),
            (13068, valid[:-1]),
            (13068, valid + b"x"),
            (13068, struct.pack(">qbB", 7, 2, 1) + b"\xff\x01"),
            (13068, rename_body(7, 2, "Alpha", 0)),
            (999, valid),
        ]
        for opcode, body in bad:
            with self.subTest(opcode=opcode, body=body), self.assertRaises(ValueError):
                decode_request(opcode, body)

    def test_release_matches_native_lowest_selected_and_empty_fallback(self):
        roster = populated()
        after = release_slot(roster, 6)
        self.assertEqual(after.selected_slot, 2)
        self.assertIsNone(after.slots[6])
        self.assertFalse(after.available[6])
        self.assertEqual(after.slots[2], roster.slots[2])
        self.assertEqual(roster.selected_slot, 6)
        empty = release_slot(after, 2)
        self.assertEqual(empty.selected_slot, -1)
        self.assertEqual(empty.free_slots, 10)
        self.assertEqual(release_slot(roster, 2).selected_slot, 6)

    def test_unavailable_descriptor_release_and_rename_preserve_native_policy(self):
        roster = replace(populated(), available=(False,) * 10)
        self.assertIsNone(release_slot(roster, 6).slots[6])
        renamed = rename_slot(roster, 6, "Étoile")
        self.assertEqual(renamed.available, roster.available)
        self.assertEqual(renamed.selected_slot, roster.selected_slot)
        self.assertEqual(renamed.slots[6].profile_id, roster.slots[6].profile_id)
        self.assertEqual(renamed.slots[6].name, "Étoile")
        with self.assertRaises(ValueError):
            rename_slot(roster, 0, "Missing")

    def test_foreign_owner_and_breed_reject_before_database_or_fight_mutation(self):
        store = SimpleNamespace(
            connection=lambda: self.fail("Foreign request touched storage")
        )
        owner = dict(id=7, account_id=8, breed=2)
        for character, account in (
            (owner, 9),
            ({**owner, "breed": 15}, 8),
            ({**owner, "id": 9}, 8),
        ):
            with self.subTest(character=character, account=account), self.assertRaises(
                ValueError
            ):
                manage(
                    store, account, "lease", character, 12014, struct.pack(">bq", 6, 7)
                )

    def test_combat_release_clears_only_exact_descriptor_binding_and_keeps_actors(self):
        owner = dict(
            id=7, account_id=8, breed=2, captured_roster=populated().to_record()
        )
        active_summon = SimpleNamespace(id=101)
        fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(controlled=True, owner_id=8),
                101: active_summon,
            },
            native_captured_rosters={"7": owner["captured_roster"]},
            native_captured_descriptor_actor_ids={"7": {"2": 100, "6": 101}},
        )
        before = deepcopy(owner)
        result = manage(
            None, 8, "lease", owner, 12014, struct.pack(">bq", 6, 7), fight=fight
        )
        self.assertIsNone(result["slots"][6])
        self.assertEqual(
            fight.native_captured_descriptor_actor_ids, {"7": {"2": 100, "6": None}}
        )
        self.assertIs(fight.actors[101], active_summon)
        self.assertEqual(owner, before)
        self.assertEqual(fight.native_captured_roster_updates["7"], result)

    def test_combat_rename_keeps_active_binding_and_malformed_binding_rejects_atomically(
        self,
    ):
        owner = dict(
            id=7, account_id=8, breed=2, captured_roster=populated().to_record()
        )
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(controlled=True, owner_id=8)},
            native_captured_rosters={"7": owner["captured_roster"]},
            native_captured_descriptor_actor_ids={"7": {"6": 101}},
        )
        result = manage(
            None, 8, "lease", owner, 13068, rename_body(7, 6, "Étoile"), fight=fight
        )
        self.assertEqual(result["slots"][6]["name"], "Étoile")
        self.assertEqual(fight.native_captured_descriptor_actor_ids, {"7": {"6": 101}})
        fight.native_captured_descriptor_actor_ids = {"7": {"6": True}}
        before = deepcopy(vars(fight))
        with self.assertRaises(ValueError):
            manage(
                None, 8, "lease", owner, 12014, struct.pack(">bq", 6, 7), fight=fight
            )
        self.assertEqual(vars(fight), before)


class CapturedManagementPersistenceTests(PostgresCase):
    def owner(self):
        from wakfu_server.characters.captured_roster_store import save

        self.store.clock = lambda: 1000
        account = self.store.register("manager", "local-password")["id"]
        generation = self.store.begin_session(account)
        owner = self.store.create_character(account, "Captured Manager", breed=2)
        owner = self.store.select_character(account, generation, owner["id"])
        with self.store.connection() as db:
            save(db, owner, populated(owner["id"]))
        return generation, self.store.character(account, owner["id"])

    def test_owned_rename_release_persist_and_reopen_with_native_selection_fallback(
        self,
    ):
        generation, owner = self.owner()
        original = deepcopy(owner)
        renamed = manage(
            self.store,
            owner["account_id"],
            generation,
            owner,
            13068,
            rename_body(owner["id"], 6, "Étoile"),
        )
        self.assertEqual(renamed["slots"][6]["name"], "Étoile")
        released = manage(
            self.store,
            owner["account_id"],
            generation,
            owner,
            12014,
            struct.pack(">bq", 6, owner["id"]),
        )
        self.assertEqual(released["selected_slot"], 2)
        reopened = self.reopen().character(owner["account_id"], owner["id"])
        self.assertEqual(reopened["captured_roster"], released)
        self.assertEqual(owner, original)
        self.assertEqual(
            reopened["captured_roster"]["slots"][2],
            original["captured_roster"]["slots"][2],
        )

    def test_database_failure_and_replaced_lease_never_publish_optimistic_component(
        self,
    ):
        generation, owner = self.owner()
        from wakfu_server.characters.captured_roster_store import save as actual_save

        before = deepcopy(owner)

        def fail_after_write(db, character, roster):
            actual_save(db, character, roster)
            raise RuntimeError("rollback")

        with patch(
            "wakfu_server.characters.captured_roster_management.save",
            side_effect=fail_after_write,
        ):
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                manage(
                    self.store,
                    owner["account_id"],
                    generation,
                    owner,
                    12014,
                    struct.pack(">bq", 6, owner["id"]),
                )
        self.assertEqual(owner, before)
        self.assertEqual(
            self.reopen().character(owner["account_id"], owner["id"])[
                "captured_roster"
            ],
            before["captured_roster"],
        )
        self.store.begin_session(owner["account_id"])
        with self.assertRaises(ValueError):
            manage(
                self.store,
                owner["account_id"],
                generation,
                owner,
                12014,
                struct.pack(">bq", 6, owner["id"]),
            )
        self.assertEqual(owner, before)

    def dispatch_scope(self, owner, generation, opcode, body, **overrides):
        logs = []
        scope = dict(
            STORE=self.store,
            loaded=True,
            character=owner,
            account_id=owner["account_id"],
            generation=generation,
            opcode=opcode,
            body=body,
            combat_session=None,
            fight=None,
            record=lambda **fields: logs.append(fields),
        )
        scope.update(overrides)
        return scope, logs

    def dispatch_code(self):
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        expected = ast.dump(
            ast.parse("opcode in (12014, 13068) and loaded", mode="eval").body
        )
        branches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and ast.dump(node.test) == expected
        ]
        self.assertEqual(len(branches), 1)
        # Preserve the actual loaded/packet guard and whole route body. Other
        # session elif branches do not belong to this selected dispatch.
        branch = ast.If(test=branches[0].test, body=branches[0].body, orelse=[])
        return compile(
            ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[])),
            str(source),
            "exec",
        )

    def test_actual_world_dispatch_persists_both_native_requests_and_publishes_after_commit(
        self,
    ):
        generation, owner = self.owner()
        for opcode, body in (
            (13068, rename_body(owner["id"], 6, "Étoile")),
            (12014, struct.pack(">bq", 6, owner["id"])),
        ):
            with self.subTest(opcode=opcode):
                before = deepcopy(owner)
                scope, logs = self.dispatch_scope(owner, generation, opcode, body)
                with patch.object(
                    self.store, "lock_character", wraps=self.store.lock_character
                ) as lock:
                    exec(self.dispatch_code(), scope)
                self.assertEqual(logs[-1]["event"], "symbiot_management")
                self.assertEqual(logs[-1]["opcode"], opcode)
                self.assertEqual(logs[-1]["actor_id"], owner["id"])
                self.assertTrue(lock.called)
                loaded = self.reopen().character(owner["account_id"], owner["id"])
                self.assertEqual(owner["captured_roster"], loaded["captured_roster"])
                self.assertNotEqual(owner["captured_roster"], before["captured_roster"])
        self.assertEqual(owner["captured_roster"]["selected_slot"], 2)
        self.assertIsNone(owner["captured_roster"]["slots"][6])

    def test_actual_dispatch_loaded_foreign_and_malformed_guards_preserve_owned_state(
        self,
    ):
        generation, owner = self.owner()
        original = deepcopy(owner)
        for loaded, opcode, body, expected in (
            (False, 12014, struct.pack(">bq", 6, owner["id"]), None),
            (True, 12014, b"bad", "symbiot_management_rejected"),
            (
                True,
                12014,
                struct.pack(">bq", 6, owner["id"] + 1000),
                "symbiot_management_rejected",
            ),
            (
                True,
                13068,
                rename_body(owner["id"] + 1000, 6, "Other"),
                "symbiot_management_rejected",
            ),
        ):
            with self.subTest(loaded=loaded, opcode=opcode):
                scope, logs = self.dispatch_scope(
                    owner, generation, opcode, body, loaded=loaded
                )
                with patch.object(
                    self.store, "lock_character", wraps=self.store.lock_character
                ) as lock:
                    exec(self.dispatch_code(), scope)
                lock.assert_not_called()
                self.assertEqual(logs[-1]["event"] if logs else None, expected)
                self.assertEqual(owner, original)
                self.assertEqual(
                    self.reopen().character(owner["account_id"], owner["id"])[
                        "captured_roster"
                    ],
                    original["captured_roster"],
                )
        self.store.begin_session(owner["account_id"])
        scope, logs = self.dispatch_scope(
            owner, generation, 12014, struct.pack(">bq", 6, owner["id"])
        )
        exec(self.dispatch_code(), scope)
        self.assertEqual(logs[-1]["event"], "symbiot_management_rejected")
        self.assertEqual(owner, original)

    def shared_dispatch_fixture(self, owner, generation):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        adapter = CombatSessionAdapter(self.store)
        session = adapter.session(owner["account_id"], generation, owner)
        with self.store.connection() as db:
            identity = db.execute(
                "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
                "entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (
                    identity,
                    owner["id"],
                    owner["account_id"],
                    generation,
                    owner["hp"],
                    owner["max_hp"],
                    owner["hp_damage"],
                    owner["health_dead"],
                ),
            )
        fight = Fight(
            identity,
            [
                Actor(
                    owner["id"],
                    0,
                    (0, 0, 0),
                    owner["hp"],
                    6,
                    3,
                    1,
                    owner["level"],
                    owner["account_id"],
                    True,
                    max_hp=owner["max_hp"],
                ),
                Actor(-7, 1, (1, 0, 0), 30, 6, 3, 100, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.native_captured_rosters = {
            str(owner["id"]): deepcopy(owner["captured_roster"])
        }
        fight.native_captured_descriptor_actor_ids = {
            str(owner["id"]): {"2": None, "6": None}
        }
        shared = adapter.register(session, fight, runtime=RuntimeMessages(fight))
        fight.ready(owner["account_id"])
        self.assertEqual(fight.current.id, -7)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
            )
        return adapter, session, shared, fight

    def test_actual_shared_dispatch_uses_registry_candidate_off_turn_and_real_checkpoint(
        self,
    ):
        from wakfu_server.fight_checkpoint_store import Checkpoints

        generation, owner = self.owner()
        adapter, session, shared, original = self.shared_dispatch_fixture(
            owner, generation
        )
        original_record = deepcopy(original.native_captured_rosters)
        checkpoints = Checkpoints(self.store)
        for opcode, body in (
            (13068, rename_body(owner["id"], 6, "Étoile")),
            (12014, struct.pack(">bq", 6, owner["id"])),
        ):
            with self.subTest(opcode=opcode):
                current = shared.fight
                scope, logs = self.dispatch_scope(
                    owner,
                    generation,
                    opcode,
                    body,
                    combat_session=session,
                    fight=current,
                    COMBAT_SESSIONS=adapter,
                )
                scope["refresh_shared_combat"] = lambda: scope.update(
                    fight=shared.fight
                )
                scope["checkpoint_fight"] = lambda: checkpoints.save_shared(
                    shared, owner["account_id"], generation
                )
                with patch.object(
                    adapter, "execute", wraps=adapter.execute
                ) as execution:
                    exec(self.dispatch_code(), scope)
                self.assertFalse(execution.call_args.kwargs["require_turn"])
                self.assertIsNot(shared.fight, current)
                self.assertEqual(shared.fight.current.id, -7)
                self.assertEqual(logs[-1]["event"], "symbiot_management")
                loaded = self.reopen().character(owner["account_id"], owner["id"])
                self.assertEqual(loaded["captured_roster"], owner["captured_roster"])
                self.assertFalse(
                    any(batch.packets for batch in shared.outboxes[owner["account_id"]])
                )
        self.assertEqual(original.native_captured_rosters, original_record)
        self.assertIsNone(
            shared.fight.native_captured_rosters[str(owner["id"])]["slots"][6]
        )
        with self.store.connection() as db:
            checkpoint = db.execute(
                "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (shared.fight.id,),
            ).fetchone()["snapshot"]
            self.assertEqual(
                checkpoint["native_captured_rosters"][str(owner["id"])],
                owner["captured_roster"],
            )

    def test_actual_shared_dispatch_async_checkpoint_failure_retains_dirty_intent_not_false_rollback(
        self,
    ):
        from wakfu_server.checkpoint_worker import CheckpointWorker
        from wakfu_server.fight_checkpoint_store import Checkpoints

        generation, owner = self.owner()
        adapter, session, shared, original = self.shared_dispatch_fixture(
            owner, generation
        )
        before = deepcopy(owner["captured_roster"])
        checkpoints = Checkpoints(self.store)
        worker = CheckpointWorker(checkpoints, workers=1)
        self.addCleanup(worker.close)
        scope, logs = self.dispatch_scope(
            owner,
            generation,
            12014,
            struct.pack(">bq", 6, owner["id"]),
            combat_session=session,
            fight=shared.fight,
            COMBAT_SESSIONS=adapter,
        )
        scope["refresh_shared_combat"] = lambda: scope.update(fight=shared.fight)
        scope["checkpoint_fight"] = lambda: worker.submit(
            shared, owner["account_id"], generation
        )
        with patch.object(
            checkpoints,
            "save_prepared",
            side_effect=ValueError("uncommitted checkpoint"),
        ):
            exec(self.dispatch_code(), scope)
            with self.assertRaisesRegex(ValueError, "Asynchronous checkpoint failed"):
                worker.flush_fight(shared.fight.id, timeout=3)
        self.assertEqual(logs[-1]["event"], "symbiot_management")
        self.assertIsNot(shared.fight, original)
        self.assertIsNone(owner["captured_roster"]["slots"][6])
        self.assertEqual(
            self.reopen().character(owner["account_id"], owner["id"])[
                "captured_roster"
            ],
            before,
        )
        self.assertEqual(original.native_captured_rosters[str(owner["id"])], before)
        self.assertEqual(
            shared.fight.native_captured_roster_updates[str(owner["id"])],
            owner["captured_roster"],
        )
        with worker.condition:
            self.assertIn(shared.fight.id, worker.pending)
            self.assertIn(shared.fight.id, worker.failed_fights)
            self.assertEqual(worker.states[shared.fight.id]["committed"], 0)
        self.assertFalse(
            any(batch.packets for batch in shared.outboxes[owner["account_id"]])
        )
