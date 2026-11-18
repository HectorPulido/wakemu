"""Quest ally admission requires the exact durable owned dungeon evidence."""

from contextlib import contextmanager
from copy import deepcopy
import unittest

from wakfu_server.achievements import astrub_cat_story_authority as authority
from wakfu_server.combat_mission_allies import MissionAlliesAdmission


class Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return deepcopy(self.value)


class Database:
    def __init__(self):
        self.character = dict(id=7, account_id=2, map_id=312, instance_id=99)
        self.state = dict(running=[5568], completed=[], objectives=[11510])
        self.run = dict(
            instance_id=99,
            party_id=4,
            status="active",
            context_route_key=authority.ROUTE_KEY,
            context_policy_version=4,
            template_id=1000312,
            definition_id=1000312,
            start_map_id=312,
            entry_map_id=527,
            entry_object_id=18736,
            entry_destination_id=713,
        )
        self.member = dict(instance_id=99, party_id=4, character_id=7, status="active")
        self.progress = dict(
            instance_id=99,
            party_id=4,
            current_room=1,
            status="active",
            rooms=[
                dict(order=order, monsters=members)
                for order, members in (
                    (1, [dict(ref_id=2616, count=3)]),
                    (2, [dict(ref_id=2616, count=2), dict(ref_id=2617, count=1)]),
                    (
                        3,
                        [
                            dict(ref_id=1816, count=1),
                            dict(ref_id=2616, count=1),
                            dict(ref_id=2617, count=1),
                        ],
                    ),
                )
            ],
        )
        self.configuration = dict(
            topology=dict(asset_map_id=312),
            compiled_plan=dict(asset_map_id=312, definition_id=1000312),
            route=dict(key=authority.ROUTE_KEY),
        )
        self.receipts = {
            authority.start_key(99): dict(
                schema=authority.START_SCHEMA,
                owner=7,
                instance_id=99,
                cat_ids=list(range(12)),
            ),
            authority.callback_key(99, 23920): dict(owner=7, event=23920),
        }
        self.spawn = dict(instance_id=99, room_order=1, asset_map_id=312, group_id=501)
        self.members = [
            dict(id=-101 - i, ref=2616, x=5 + i, y=2, z=0, map_id=312, instance_id=99)
            for i in range(3)
        ]
        self.group = dict(members=deepcopy(self.members), status="available")
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if "FROM character_achievement_progress" in sql:
            return Result(dict(state=self.state))
        if "FROM character_achievement_events" in sql:
            return Result(
                None
                if params[1] not in self.receipts
                else dict(payload=self.receipts[params[1]])
            )
        if "FROM dungeon_instances " in sql:
            return Result(self.run)
        if "FROM dungeon_instance_members " in sql:
            return Result(self.member if params == (99, 7, 2) else None)
        if "FROM dungeon_room_runs " in sql:
            return Result(self.progress)
        if "FROM dungeon_runtime_configurations " in sql:
            return Result(dict(configuration=self.configuration))
        if "FROM dungeon_room_spawn_receipts " in sql:
            return Result(self.spawn)
        if "FROM combat_groups " in sql:
            return Result(
                self.group if params == (312, 99, self.spawn["group_id"]) else None
            )
        raise AssertionError(sql)

    @contextmanager
    def connection(self):
        yield self


class AstrubCatStoryAuthorityTests(unittest.TestCase):
    def test_exact_scope_admits_native_ally_without_writes_or_row_locks(self):
        db = Database()
        scope = authority.context(db, db.character)
        self.assertEqual((scope["instance"], scope["room"]), (99, 1))
        admission = authority.combat_helper_admission(db, db.character, db.members)
        self.assertIs(type(admission), MissionAlliesAdmission)
        self.assertEqual(
            (admission.principal_id, admission.account_id, admission.room), (7, 2, 1)
        )
        self.assertTrue(
            all(
                sql.lstrip().startswith("SELECT ") and "FOR UPDATE" not in sql
                for sql, _ in db.queries
            )
        )

    def test_unrelated_visits_never_admit_story_allies(self):
        for change in (dict(map_id=527), dict(instance_id=0)):
            db = Database()
            self.assertIsNone(
                authority.combat_helper_admission(
                    db, dict(db.character, **change), db.members
                )
            )
            self.assertEqual(db.queries, [])
        db = Database()
        db.state["running"] = []
        self.assertIsNone(authority.context(db, db.character))
        db = Database()
        db.run["context_route_key"] = "another-owned-dungeon"
        self.assertIsNone(authority.context(db, db.character))

    def test_related_scope_rejects_wrong_party_configuration_and_roster(self):
        mutations = (
            lambda d: d.member.update(party_id=5),
            lambda d: d.member.update(status="returned"),
            lambda d: d.run.update(context_policy_version=3),
            lambda d: d.run.update(status="closed"),
            lambda d: d.progress.update(party_id=8),
            lambda d: d.configuration["compiled_plan"].update(asset_map_id=527),
            lambda d: d.progress["rooms"][0]["monsters"][0].update(count=2),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                db = Database()
                mutation(db)
                with self.assertRaises(ValueError):
                    authority.combat_helper_admission(db, db.character, db.members)

    def test_combat_requires_intro_callback_and_exact_live_spawn_members(self):
        mutations = (
            lambda d: d.receipts.pop(authority.start_key(99)),
            lambda d: d.receipts[authority.start_key(99)].update(owner=8),
            lambda d: d.receipts[authority.start_key(99)].update(instance_id=100),
            lambda d: d.receipts.pop(authority.callback_key(99, 23920)),
            lambda d: d.spawn.update(asset_map_id=527),
            lambda d: d.group.update(status="defeated"),
            lambda d: d.group["members"][0].update(id=-999),
            lambda d: d.group["members"][0].update(ref=2617),
            lambda d: d.group["members"][0].update(x=99),
            lambda d: d.group["members"][0].update(instance_id=100),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                db = Database()
                mutation(db)
                with self.assertRaises(ValueError):
                    authority.combat_helper_admission(db, db.character, db.members)

    def test_completed_or_unavailable_quest_reentry_never_reclaims_a_story_without_receipt(
        self,
    ):
        for state in (
            dict(running=[], completed=[5568], objectives=[11510, 11515]),
            dict(running=[], completed=[], objectives=[]),
            None,
        ):
            with self.subTest(state=state):
                db = Database()
                db.state = deepcopy(state)
                db.receipts.clear()
                # Ordinary repeat visits may use a generated roster. No old
                # quest may bind its cutscene/ally authority to that new run.
                for order, room in enumerate(db.progress["rooms"], 1):
                    room["monsters"] = [dict(ref_id=2616, count=order)]
                before = deepcopy(db.__dict__)
                self.assertIsNone(
                    authority.context(db, db.character, allow_finished=True)
                )
                self.assertTrue(
                    all(sql.lstrip().startswith("SELECT ") for sql, _ in db.queries)
                )
                self.assertFalse(any("FROM dungeon_" in sql for sql, _ in db.queries))
                for field in ("state", "progress", "run", "receipts", "member"):
                    self.assertEqual(getattr(db, field), before[field])

    def test_finished_scope_is_explicit_and_still_requires_owned_membership(self):
        db = Database()
        db.run["status"] = db.progress["status"] = "completed"
        db.state["objectives"].append(11515)
        self.assertIsNone(authority.context(db, db.character))
        self.assertEqual(
            authority.context(db, db.character, allow_finished=True)["room"], 1
        )
        db.member["status"] = "returned"
        with self.assertRaises(ValueError):
            authority.context(db, db.character, allow_finished=True)
