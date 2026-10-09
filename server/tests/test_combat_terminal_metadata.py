import unittest
from types import SimpleNamespace

from wakfu_server.combat.combat_terminal_metadata import (
    owner_characters_for_finish,
    registered_summon_metadata,
)


class FakeStore:
    def __init__(self, rows):
        self.rows = rows
        self.reads = []

    def character(self, account_id, character_id):
        self.reads.append((account_id, character_id))
        row = self.rows.get((account_id, character_id))
        if row is None:
            raise ValueError("missing owner character")
        return dict(row)


class TerminalMetadataTests(unittest.TestCase):
    def test_adds_only_retained_withdrawn_owner_for_result_metadata(self):
        active = {7: {"id": 7, "account_id": 3, "name": "Active"}}
        fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(
                    id=7, owner_id=3, controlled=True, pve_withdrawn=False
                ),
                8: SimpleNamespace(
                    id=8, owner_id=4, controlled=True, pve_withdrawn=True
                ),
                -20: SimpleNamespace(
                    id=-20, owner_id=None, controlled=False, pve_withdrawn=False
                ),
            }
        )
        shared = SimpleNamespace(
            participants={
                3: SimpleNamespace(account_id=3, character_id=7),
                4: SimpleNamespace(account_id=4, character_id=8),
            }
        )
        store = FakeStore({(4, 8): {"id": 8, "account_id": 4, "name": "Withdrawn"}})

        result = owner_characters_for_finish(store, shared, fight, active)

        self.assertEqual(set(result), {7, 8})
        self.assertEqual(result[8]["name"], "Withdrawn")
        self.assertEqual(store.reads, [(4, 8)])
        self.assertEqual(set(active), {7})  # Active authority input stays intact.

    def test_withdrawn_controlled_summon_is_reported_as_registered_native_monster(self):
        summon = SimpleNamespace(
            id=901,
            owner_id=3,
            controlled=True,
            pve_withdrawn=True,
            native_summon_source={
                "ref": 3251,
                "level": 6,
                "caster_id": 7,
                "controller_id": 7,
            },
        )
        controller = SimpleNamespace(id=7, owner_id=3, controlled=True)
        registration = {
            "actor_id": 901,
            "caster_id": 7,
            "controller_id": 7,
            "authority": {
                "breed_id": 3251,
                "is_summon": True,
                "native_real_level": 6,
                "native_controller_id": 7,
            },
        }
        fight = SimpleNamespace(
            actors={7: controller, 901: summon},
            native_summon_registrations={901: registration},
        )
        shared = SimpleNamespace(participants={})
        store = FakeStore({})

        owners = owner_characters_for_finish(
            store, shared, fight, {7: {"id": 7, "account_id": 3, "name": "Owner"}}
        )
        metadata = registered_summon_metadata(fight)

        self.assertEqual(set(owners), {7})
        self.assertEqual(metadata, {901: {"kind": "monster", "ref": 3251}})
        self.assertEqual(store.reads, [])

    def test_unregistered_controlled_actor_still_requires_owner_metadata(self):
        actor = SimpleNamespace(id=901, owner_id=3, controlled=True, pve_withdrawn=True)
        fight = SimpleNamespace(actors={901: actor}, native_summon_registrations={})
        shared = SimpleNamespace(participants={})

        with self.assertRaisesRegex(ValueError, "retained owner participant"):
            owner_characters_for_finish(FakeStore({}), shared, fight, {})

    def test_self_controlled_registered_summon_is_not_a_character_lookup(self):
        summon = SimpleNamespace(
            id=901,
            owner_id=None,
            controlled=False,
            pve_withdrawn=True,
            native_summon_source={
                "ref": 3251,
                "level": 6,
                "caster_id": 7,
                "controller_id": 901,
            },
        )
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, owner_id=3, controlled=True), 901: summon},
            native_summon_registrations={
                901: {
                    "actor_id": 901,
                    "caster_id": 7,
                    "controller_id": 901,
                    "authority": {
                        "breed_id": 3251,
                        "is_summon": True,
                        "native_real_level": 6,
                        "native_controller_id": 901,
                    },
                }
            },
        )
        store = FakeStore({})
        self.assertEqual(
            registered_summon_metadata(fight), {901: {"kind": "monster", "ref": 3251}}
        )
        self.assertEqual(store.reads, [])

    def test_player_sources_never_loads_controlled_summon_uid_as_character(self):
        from unittest.mock import patch
        from wakfu_server.combat.combat_session_adapter import CombatSessionAdapter

        summon = SimpleNamespace(
            id=901,
            owner_id=3,
            controlled=True,
            pve_withdrawn=True,
            native_summon_source={
                "ref": 3251,
                "level": 6,
                "caster_id": 7,
                "controller_id": 7,
            },
        )
        controller = SimpleNamespace(id=7, owner_id=3, controlled=True)
        fight = SimpleNamespace(
            actors={7: controller, 901: summon},
            native_summon_registrations={
                901: {
                    "actor_id": 901,
                    "caster_id": 7,
                    "controller_id": 7,
                    "authority": {
                        "breed_id": 3251,
                        "is_summon": True,
                        "native_real_level": 6,
                        "native_controller_id": 7,
                    },
                }
            },
        )
        store = FakeStore(
            {
                (3, 7): {
                    "id": 7,
                    "account_id": 3,
                    "deleted_at": None,
                    "active_build_index": 0,
                    "builds": {},
                }
            }
        )

        with patch("wakfu_server.spells.default_deck", return_value=b"deck"):
            characters, decks = CombatSessionAdapter(store).player_sources(fight)

        self.assertEqual(set(characters), {7})
        self.assertEqual(decks, {7: b"deck"})
        self.assertEqual(store.reads, [(3, 7)])

    def test_unmatched_or_nonwithdrawn_missing_owner_fails_closed(self):
        actor = SimpleNamespace(id=8, owner_id=4, controlled=True, pve_withdrawn=True)
        shared = SimpleNamespace(
            participants={4: SimpleNamespace(account_id=4, character_id=99)}
        )
        with self.assertRaisesRegex(ValueError, "retained owner participant"):
            owner_characters_for_finish(
                FakeStore({}), shared, SimpleNamespace(actors={8: actor}), {}
            )

    def test_deleted_historical_character_cannot_enter_result_metadata(self):
        actor = SimpleNamespace(id=8, owner_id=4, controlled=True, pve_withdrawn=True)
        shared = SimpleNamespace(
            participants={4: SimpleNamespace(account_id=4, character_id=8)}
        )
        store = FakeStore({(4, 8): {"id": 8, "account_id": 4, "deleted_at": "deleted"}})
        with self.assertRaisesRegex(ValueError, "identity changed"):
            owner_characters_for_finish(
                store, shared, SimpleNamespace(actors={8: actor}), {}
            )

        actor.pve_withdrawn = False
        shared.participants[4].character_id = 8
        with self.assertRaisesRegex(ValueError, "no current owner source"):
            owner_characters_for_finish(
                FakeStore({}), shared, SimpleNamespace(actors={8: actor}), {}
            )


if __name__ == "__main__":
    unittest.main()
