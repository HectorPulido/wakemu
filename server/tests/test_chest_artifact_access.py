"""Exploration projections unlock only the owned native chest artifact gate."""

import unittest

from wakfu_server.achievements.chest_open import _artifact
from wakfu_server.exploration_secrets import ITEM_REFS, SETTING


class PolicyDatabase:
    def __init__(self, enabled):
        self.enabled = enabled
        self.queries = []

    def execute(self, query, parameters):
        if query != "SELECT value FROM settings WHERE name=%s" or parameters != (
            SETTING,
        ):
            raise AssertionError(
                "Artifact projection must only read its current policy"
            )
        self.queries.append(query)
        return self

    def fetchone(self):
        return dict(value=dict(version=1, unlock_all=self.enabled))


class ChestArtifactAccessTests(unittest.TestCase):
    def character(self, **changes):
        return dict(
            dict(
                id=7,
                account_id=3,
                quest_items=[],
                account_quest_items=[],
                exploration_secrets=dict(account_item_refs=(), world_properties=()),
            ),
            **changes,
        )

    def test_all_eleven_projected_artifacts_use_current_policy_without_owned_items(
        self,
    ):
        db = PolicyDatabase(True)
        character = self.character()
        for reference in ITEM_REFS:
            with self.subTest(reference=reference):
                self.assertEqual(_artifact(db, character, reference), [reference])
        self.assertEqual(len(db.queries), 11)
        self.assertEqual(character["account_quest_items"], [])
        self.assertEqual(character["exploration_secrets"]["account_item_refs"], ())

    def test_disabled_policy_does_not_trust_stale_or_forged_projection(self):
        db = PolicyDatabase(False)
        character = self.character(
            exploration_secrets=dict(
                account_item_refs=ITEM_REFS, world_properties=(85, 105, 117, 118)
            )
        )
        for reference in ITEM_REFS:
            with self.subTest(reference=reference), self.assertRaisesRegex(
                ValueError, "owned artifact"
            ):
                _artifact(db, character, reference)

    def test_owned_artifact_remains_available_when_projection_is_disabled(self):
        db = PolicyDatabase(False)
        for key, owner_key, owner in (
            ("quest_items", "character_id", 7),
            ("account_quest_items", "account_id", 3),
        ):
            character = self.character(
                **{
                    key: [
                        dict(reference=ITEM_REFS[0], quantity=1, **{owner_key: owner})
                    ]
                }
            )
            with self.subTest(inventory=key):
                self.assertEqual(_artifact(db, character, ITEM_REFS[0]), [ITEM_REFS[0]])

    def test_unrelated_artifact_keeps_owned_item_requirement_and_no_policy_read(self):
        db = PolicyDatabase(True)
        reference = 29431
        with self.assertRaisesRegex(ValueError, "owned artifact"):
            _artifact(db, self.character(), reference)
        for key, owner_key, owner in (
            ("quest_items", "character_id", 7),
            ("account_quest_items", "account_id", 3),
        ):
            character = self.character(
                **{key: [dict(reference=reference, quantity=1, **{owner_key: owner})]}
            )
            self.assertEqual(_artifact(db, character, reference), [reference])
        self.assertEqual(db.queries, [])

    def test_foreign_owned_account_state_cannot_authorize_an_artifact(self):
        reference = ITEM_REFS[0]
        character = self.character(
            account_quest_items=[dict(account_id=99, reference=reference, quantity=1)]
        )
        for enabled in (True, False):
            with self.subTest(enabled=enabled), self.assertRaisesRegex(
                ValueError, "Foreign"
            ):
                _artifact(PolicyDatabase(enabled), character, reference)
        with self.assertRaisesRegex(ValueError, "owned artifact"):
            _artifact(
                PolicyDatabase(False),
                self.character(
                    quest_items=[dict(character_id=99, reference=reference, quantity=1)]
                ),
                reference,
            )

    def test_no_artifact_gate_does_not_require_items_or_read_policy(self):
        db = PolicyDatabase(False)
        self.assertEqual(_artifact(db, self.character(), None), [])
        self.assertEqual(db.queries, [])


if __name__ == "__main__":
    unittest.main()
