"""Tests for complete authority loading from one repeatable read snapshot."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.native.native_store import load_authorities


class FakeDB:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)


class FakeStore:
    def __init__(self, characters):
        self.characters = characters
        self.db = FakeDB()
        self.connection_entries = 0
        self.character_calls = []

    class _Connection:
        def __init__(self, store):
            self.store = store

        def __enter__(self):
            self.store.connection_entries += 1
            return self.store.db

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    def connection(self):
        return self._Connection(self)

    def character(self, account_owner, identity, db):
        self.character_calls.append((account_owner, identity, db))
        return deepcopy(self.characters[identity])


def participant(identity, owner, level, *, controlled=True):
    return SimpleNamespace(
        id=identity, owner_id=owner, controlled=controlled, effective_level=level
    )


def character(identity, account, level, active_build, builds):
    return {
        "id": identity,
        "account_id": account,
        "effective_level": level,
        "active_build_index": active_build,
        "builds": builds,
        "breed": identity,
        "future_character_field": {"binary": b"\x00future\xff", "extension": [1, 2]},
    }


def setup_fixture():
    pc1 = character(
        1,
        101,
        40,
        2,
        {
            0: {"deck": "00000000", "sheet": b"inactive-build-zero"},
            2: {"deck": "01000000aabbccdd", "sheet": b"selected-build-one"},
        },
    )
    pc2 = character(
        2,
        202,
        30,
        1,
        {
            0: {"deck": "00000000", "sheet": b"inactive"},
            1: {"deck": "00000000", "aptitudes": b"future-aptitudes"},
        },
    )
    actors = {
        1: participant(1, 101, 40),
        2: participant(2, 202, 30),
        3: participant(3, None, 20, controlled=False),
        4: participant(4, None, 20, controlled=False),
    }
    registrations = {4: {"ownerId": 1, "future_registration": b"preserve-me"}}
    runtime = SimpleNamespace(
        fight=SimpleNamespace(actors=actors, native_summon_registrations=registrations)
    )
    store = FakeStore({1: pc1, 2: pc2})
    monsters = {
        3: {"id": 3, "ref": 777, "future_descriptor": b"npc-full"},
        999: {"id": 999, "ref": 1},
    }
    return runtime, store, monsters


class NativeStoreTests(unittest.TestCase):
    def test_unsaved_permanent_default_build_uses_native_deck_without_inventing_saved_rows(
        self,
    ):
        runtime, store, monsters = setup_fixture()
        store.characters[1]["active_build_index"] = 0
        store.characters[1]["builds"] = {}
        expected = deepcopy(store.characters[1])
        with patch(
            "wakfu_server.spells.default_deck", return_value=b"native-default"
        ) as default:
            loaded = load_authorities(runtime, store, monsters, viewer_id=1)
        self.assertEqual(loaded["characters"][1], expected)
        self.assertEqual(loaded["decks"][1], b"native-default")
        default.assert_called_once_with(expected)

    def test_absent_non_default_selected_build_is_rejected(self):
        runtime, store, monsters = setup_fixture()
        store.characters[1]["active_build_index"] = 99
        with self.assertRaisesRegex(ValueError, "Selected native build is absent"):
            load_authorities(runtime, store, monsters, viewer_id=1)

    def test_multi_pc_uses_selected_build_preserves_extensions_and_one_db_snapshot(
        self,
    ):
        runtime, store, monsters = setup_fixture()
        store.characters[2]["builds"][1]["deck"] = ""
        fallback_deck = b"default-for-selected-empty-deck"
        with patch(
            "wakfu_server.spells.default_deck", return_value=fallback_deck
        ) as default:
            loaded = load_authorities(runtime, store, monsters, viewer_id=1)

        self.assertEqual(store.connection_entries, 1)
        self.assertEqual(
            store.db.statements,
            ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"],
        )
        self.assertEqual([call[1] for call in store.character_calls], [1, 2])
        self.assertTrue(all(call[2] is store.db for call in store.character_calls))
        self.assertEqual(loaded["characters"].keys(), {1, 2})
        self.assertEqual(loaded["characters"][1]["active_build_index"], 2)
        self.assertEqual(loaded["decks"][1], bytes.fromhex("01000000aabbccdd"))
        self.assertEqual(loaded["decks"][2], fallback_deck)
        default.assert_called_once_with(loaded["characters"][2])
        self.assertEqual(
            loaded["characters"][1]["future_character_field"],
            {"binary": b"\x00future\xff", "extension": [1, 2]},
        )
        self.assertEqual(
            loaded["characters"][2]["builds"][1]["aptitudes"], b"future-aptitudes"
        )
        self.assertEqual(loaded["monsters"], {3: monsters[3]})
        self.assertEqual(loaded["monsters"][3]["future_descriptor"], b"npc-full")
        self.assertEqual(
            loaded["registrations"], runtime.fight.native_summon_registrations
        )
        self.assertEqual([identity for _, identity, _ in store.character_calls], [1, 2])

    def test_missing_owner_and_wrong_owner_are_rejected(self):
        runtime, store, monsters = setup_fixture()
        runtime.fight.actors[2].owner_id = None
        with self.assertRaisesRegex(
            ValueError, "Missing authoritative participant account"
        ):
            load_authorities(runtime, store, monsters, viewer_id=1)
        self.assertEqual([identity for _, identity, _ in store.character_calls], [1])

        runtime, store, monsters = setup_fixture()
        store.characters[2]["account_id"] = 999
        with self.assertRaisesRegex(ValueError, "ownership mismatch"):
            load_authorities(runtime, store, monsters, viewer_id=1)

    def test_character_identity_mismatch_and_selected_level_mismatch_are_rejected(self):
        runtime, store, monsters = setup_fixture()
        store.characters[1]["id"] = 99
        with self.assertRaisesRegex(ValueError, "ownership mismatch"):
            load_authorities(runtime, store, monsters, viewer_id=1)

        runtime, store, monsters = setup_fixture()
        store.characters[2]["effective_level"] = 31
        with self.assertRaisesRegex(ValueError, "build level differs"):
            load_authorities(runtime, store, monsters, viewer_id=1)

    def test_all_ordinary_npcs_need_matching_complete_descriptors(self):
        runtime, store, monsters = setup_fixture()
        monsters.pop(3)
        with self.assertRaisesRegex(
            ValueError, "Missing complete native monster descriptor"
        ):
            load_authorities(runtime, store, monsters, viewer_id=1)

        runtime, store, monsters = setup_fixture()
        monsters[3]["id"] = 30
        with self.assertRaisesRegex(
            ValueError, "Missing complete native monster descriptor"
        ):
            load_authorities(runtime, store, monsters, viewer_id=1)

    def test_summons_are_registration_authority_not_sql_characters(self):
        runtime, store, monsters = setup_fixture()
        loaded = load_authorities(runtime, store, monsters, viewer_id=1)
        self.assertEqual([identity for _, identity, _ in store.character_calls], [1, 2])
        self.assertNotIn(4, loaded["characters"])
        self.assertNotIn(4, loaded["monsters"])
        self.assertIn(4, loaded["registrations"])

    def test_viewer_must_be_an_ordinary_participant(self):
        runtime, store, monsters = setup_fixture()
        with self.assertRaisesRegex(
            ValueError, "Viewer is not an ordinary participant"
        ):
            load_authorities(runtime, store, monsters, viewer_id=3)


if __name__ == "__main__":
    unittest.main()
