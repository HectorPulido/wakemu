"""A source receipt freezes the real group through ordinary ecology moves."""

from contextlib import nullcontext
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import source_quest_encounters
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server import monster_idle_distribution_store as idle
from wakfu_server.npc_actor_identity import MINIMUM


class SourceQuestEcologyMovementTests(unittest.TestCase):
    personal_id = 1792127516283481
    other_id = personal_id + 1
    scope = (943, 0)

    def setUp(self):
        member = dict(id=-MINIMUM, ref=3568, x=-192, y=39, z=-60)
        self.receipt = dict(
            schema=source_quest_encounters.SCHEMA,
            owner=7,
            group_key=[*self.scope, self.personal_id],
            members=[member],
        )
        # The exact receipt still identifies the group after an earlier move.
        self.members = {
            self.personal_id: [dict(member, x=-212, y=-44, z=0)],
            self.other_id: [dict(member, id=-MINIMUM - 1, x=-170)],
        }
        self.moves = [
            dict(
                group_id=group_id,
                expected_members=deepcopy(members),
                moved_members=[dict(row, x=row["x"] + 1) for row in members],
            )
            for group_id, members in self.members.items()
        ]
        self.updated_groups = []
        self.db = MagicMock()
        self.db.execute.side_effect = self.query
        self.store = MagicMock()
        self.store.connection.side_effect = lambda: nullcontext(self.db)

    @staticmethod
    def cursor(*, row=None, rows=()):
        result = MagicMock()
        result.fetchone.return_value = row
        result.fetchall.return_value = list(rows)
        result.__iter__.return_value = iter(rows)
        return result

    def query(self, sql, params=()):
        if sql.startswith("SELECT pg_advisory_xact_lock"):
            return self.cursor()
        if sql.startswith("SELECT * FROM monster_idle_distribution_runs"):
            return self.cursor(row=dict(id=505, status="pending"))
        if sql.startswith("SELECT * FROM monster_idle_distribution_moves"):
            return self.cursor(
                rows=[dict(move, ordinal=i) for i, move in enumerate(self.moves)]
            )
        if sql.startswith("SELECT group_id,members FROM combat_groups"):
            return self.cursor(
                rows=[
                    dict(group_id=group_id, members=members)
                    for group_id, members in self.members.items()
                ]
            )
        if sql.startswith("SELECT group_payload FROM planting_growth_outbox"):
            return self.cursor()
        if sql.startswith("SELECT members,instance_id FROM combat_groups"):
            return self.cursor(row=dict(members=self.members[params[2]], instance_id=0))
        if sql.startswith("SELECT 1 FROM character_achievement_events"):
            keys, schema, key = params
            actor_key = f"quest-source-actor:{-self.receipt['members'][0]['id']}"
            matched = (
                actor_key in keys
                and schema == self.receipt["schema"]
                and key.obj == self.receipt["group_key"]
            )
            return self.cursor(row={"protected": 1} if matched else None)
        if sql.startswith("UPDATE combat_groups SET members"):
            group_id = params[3]
            self.updated_groups.append(group_id)
            self.members[group_id] = params[0].obj
            return self.cursor(row={"group_id": group_id})
        if sql.startswith("UPDATE monster_idle_distribution_"):
            return self.cursor()
        raise AssertionError(sql)

    def test_idle_commit_protects_source_group_and_moves_unowned_same_breed(self):
        proposal = dict(
            world_epoch="test-epoch",
            scope=list(self.scope),
            empty_generation=1,
            run_id=505,
            chunk_index=0,
        )
        prepared = dict(proposal=proposal, moves=self.moves, radii={"3568": 0})

        outcomes = idle.commit(
            self.store, None, proposal, episode_current=True, prepared=prepared
        )

        self.assertEqual(
            outcomes,
            [
                dict(group_id=self.personal_id, status="skipped"),
                dict(group_id=self.other_id, status="applied"),
            ],
        )
        self.assertEqual(
            self.members[self.personal_id], self.moves[0]["expected_members"]
        )
        self.assertEqual(self.members[self.other_id], self.moves[1]["moved_members"])
        self.assertEqual(self.updated_groups, [self.other_id])

    def test_wander_cas_uses_the_same_receipt_without_blocking_the_breed(self):
        groups = PersistentGroups(self.store)
        with patch("wakfu_server.combat_group_store.Groups"):
            for move in self.moves:
                expected = move["group_id"] == self.other_id
                result = groups.move_members(
                    (*self.scope, move["group_id"]),
                    move["expected_members"],
                    move["moved_members"],
                )
                self.assertEqual(result, expected)

        self.assertEqual(self.updated_groups, [self.other_id])
