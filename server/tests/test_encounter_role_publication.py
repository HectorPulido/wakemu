"""Exact affiliation publications use immutable existing role storage."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from postgres_case import PostgresCase
from tools import publish_encounter_roles as publisher

SOURCE = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/owned_story_profiles/bovis-lair-1002.roles.json"
)


def document():
    return json.loads(SOURCE.read_text())


class EncounterRolePublicationTests(unittest.TestCase):
    def test_exact_native_scopes_reject_duplicate_or_malformed_affiliations(self):
        self.assertEqual(len(publisher.validate(document())), 4)
        for key, value in [
            ("player_team", True),
            ("npc_team", 1),
            ("monster_references", [3841, 3840]),
        ]:
            malformed = document()
            malformed["roles"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                publisher.validate(malformed)
        duplicated = document()
        duplicated["roles"].append(deepcopy(duplicated["roles"][0]))
        with self.assertRaises(ValueError):
            publisher.validate(duplicated)


class EncounterRolePublicationPostgresTests(PostgresCase):
    def test_idempotent_exact_roles_preserve_other_scopes_and_refuse_immutable_drift(
        self,
    ):
        with self.store.connection() as db:
            before = db.execute(
                "SELECT * FROM encounter_role_active ORDER BY map_id,monster_references"
            ).fetchall()
            expected = publisher.install(db, document())
            self.assertEqual(expected["roles"], 4)
            self.assertEqual(publisher.install(db, document()), expected)
            for row in before:
                actual = db.execute(
                    "SELECT * FROM encounter_role_active WHERE map_id=%s AND monster_references=%s::integer[]",
                    (row["map_id"], row["monster_references"]),
                ).fetchone()
                self.assertEqual(actual, row)
            for row in document()["roles"]:
                actual = db.execute(
                    "SELECT * FROM encounter_role_versions WHERE policy=%s",
                    (row["policy"],),
                ).fetchone()
                self.assertEqual((actual["player_team"], actual["npc_team"]), (1, 0))
            changed = document()
            changed["roles"][0]["authority"] += " changed"
            with self.assertRaisesRegex(ValueError, "Immutable"), db.transaction():
                publisher.install(db, changed)
            changed = document()
            changed["roles"][0]["policy"] += "-foreign"
            with self.assertRaisesRegex(ValueError, "already owns"), db.transaction():
                publisher.install(db, changed)


if __name__ == "__main__":
    unittest.main()
