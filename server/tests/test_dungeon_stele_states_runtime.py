"""Actual native-runtime qualification for boss-carried dungeon stele states."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from postgres_case import PostgresCase


class _EncounterDb:
    def __init__(self, fight_id, instance_id, snapshot, rooms, scaling_snapshot):
        self.fight_id = fight_id
        self.instance_id = instance_id
        self.snapshot = snapshot
        self.rooms = rooms
        self.scaling_snapshot = scaling_snapshot

    def execute(self, query, params=()):
        if "dungeon_encounter_difficulties" in query:
            return SimpleNamespace(fetchone=lambda: {"snapshot": self.scaling_snapshot})
        if "to_regclass" in query:
            return SimpleNamespace(
                fetchone=lambda: {"relation": "dungeon_stele_encounters"}
            )
        if "dungeon_stele_encounters" in query:
            return SimpleNamespace(fetchone=lambda: {"snapshot": self.snapshot})
        if "dungeon_room_runs" in query:
            return SimpleNamespace(fetchone=lambda: {"rooms": self.rooms})
        raise AssertionError(f"Unexpected encounter query: {query}")


class DungeonSteleNativeRuntimeTests(PostgresCase):
    def test_selected_native_states_install_through_complete_server_runtime(self):
        self._qualify_states((4020, 8167, 8318))

    def test_state_4020_first_round_reduces_enemy_max_mp(self):
        self._qualify_states((4020,))

    def test_all_distinct_selected_native_states_install_on_real_boss_runtime(self):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_state import Fight
        from wakfu_server.maps import dungeon_combat_scaling, dungeon_scaling_catalog
        from wakfu_server.maps import dungeon_stele_states
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests

        with self.store.connection() as db:
            supplement = dungeon_scaling_catalog.load(db)
            definitions = list(
                db.execute(
                    "SELECT stele_id,configuration FROM dungeon_stele_definitions"
                )
            )
        states = {
            (difficulty["state_id"], row["stele_id"])
            for row in definitions
            for difficulty in row["configuration"]["difficulties"]
        }
        self.assertEqual(len({state for state, _ in states}), 115)
        self.assertIsNotNone(supplement)
        rooms = json.loads(
            Path(
                "server/test-fixtures/dungeons/jalato-runtime-config-v1.json"
            ).read_text()
        )["compiled_plan"]["rooms"]
        with patch.object(Fight, "ready"):
            character, monster, fight = SpellTransactionTests().native_server_fixture(
                8, 60, native_qi=True, target_ref=44, target_level=20
            )
        monsters = {monster["id"]: monster}
        deck = encode_deck(())
        scaling_snapshot = dict(
            schema_version=1,
            instance_id=9900,
            selection_revision=1,
            stasis_level=1,
            competitive=True,
            competitive_max_level=20,
            hp_percent=100,
            damage_percent=100,
            reward_rate_bp=10000,
        )
        encounter_db = _EncounterDb(fight.id, 9900, None, rooms, scaling_snapshot)

        def scaling_factory(preview, identity):
            factory, _ = server_runtime(
                character,
                monsters,
                deck,
                action_id=30,
                critical=False,
                player_characters={7: character},
                deck_blobs={7: deck},
            )
            return factory(preview, {"native_retained_container": {"present": False}})[
                0
            ]

        with patch.object(dungeon_scaling_catalog, "current", return_value=supplement):
            scaled, scale_receipt = dungeon_combat_scaling.initialize(
                encounter_db,
                fight,
                monsters,
                catalog=supplement,
                runtime_factory=scaling_factory,
            )
            self.assertTrue(scale_receipt["initialized"])
            scaled.ready(3)
            factory, _ = server_runtime(
                character,
                monsters,
                deck,
                action_id=31,
                critical=False,
                player_characters={7: character},
                deck_blobs={7: deck},
            )
            baseline_qi = (
                deepcopy(scaled.native_qi_slots),
                deepcopy(scaled.native_qi_touched_cells),
                deepcopy(scaled.native_qi_byte_topology),
            )
            applied = 0
            for state_id, stele_id in sorted(states):
                with self.subTest(state_id=state_id):
                    encounter_db.snapshot = dict(
                        schema_version=1,
                        instance_id=9900,
                        fight_id=fight.id,
                        player_team=0,
                        selections=[dict(stele_id=stele_id, state_ids=[state_id])],
                    )
                    preview, receipt, _packets = dungeon_stele_states.initialize(
                        encounter_db,
                        deepcopy(scaled),
                        monsters,
                        runtime_factory=lambda _fight, _identity: factory,
                    )
                    self.assertEqual(receipt["state_ids"], [state_id])
                    self.assertEqual(receipt["actor_ids"], [-7])
                    self.assertIn(
                        state_id,
                        [
                            entry.reference
                            for entry in preview.actors[-7].state_ledger.entries
                        ],
                    )
                    self.assertEqual(
                        (
                            preview.native_qi_slots,
                            preview.native_qi_touched_cells,
                            preview.native_qi_byte_topology,
                        ),
                        baseline_qi,
                    )
                    applied += 1
            self.assertEqual(applied, 115)

    def _qualify_states(self, target_states):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.fight_checkpoint_store import snapshot as checkpoint
        from wakfu_server import dungeon_combat_scaling, dungeon_scaling_catalog
        from wakfu_server import dungeon_stele_states
        from wakfu_server.combat_state import Fight as FixtureFight
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests

        with self.store.connection() as db:
            supplement = dungeon_scaling_catalog.load(db)
            definitions = list(
                db.execute(
                    "SELECT stele_id,configuration FROM dungeon_stele_definitions"
                )
            )
        self.assertIsNotNone(supplement)
        definitions_by_state = {
            difficulty["state_id"]: (
                row["stele_id"],
                row["configuration"],
                difficulty["id"],
            )
            for row in definitions
            for difficulty in row["configuration"]["difficulties"]
        }
        rooms = json.loads(
            Path(
                "server/test-fixtures/dungeons/jalato-runtime-config-v1.json"
            ).read_text()
        )["compiled_plan"]["rooms"]
        deck = encode_deck(())

        for offset, state_id in enumerate(target_states):
            with self.subTest(state_id=state_id):
                # The fixture's constructor calls ready(); preserve the actual
                # actor/snapshot setup while keeping the unpublished placement.
                with patch.object(FixtureFight, "ready"):
                    (
                        character,
                        monster,
                        fight,
                    ) = SpellTransactionTests().native_server_fixture(
                        8, 60, native_qi=True, target_ref=44, target_level=20
                    )
                self.assertEqual(fight.phase, "placement")
                self.assertEqual(monster["ref"], 44)
                self.assertEqual(fight.actors[-7].hp, fight.actors[-7].max_hp)
                stele_id, _configuration, difficulty_id = definitions_by_state[state_id]
                snapshot = dict(
                    schema_version=1,
                    instance_id=9000 + offset,
                    fight_id=fight.id,
                    player_team=0,
                    difficulty_revision=1,
                    selections=[dict(stele_id=stele_id, state_ids=[state_id])],
                )
                scaling_snapshot = dict(
                    schema_version=1,
                    instance_id=9000 + offset,
                    selection_revision=1,
                    stasis_level=1,
                    competitive=True,
                    competitive_max_level=20,
                    hp_percent=100,
                    damage_percent=100,
                    reward_rate_bp=10000,
                )
                encounter_db = _EncounterDb(
                    fight.id, 9000 + offset, snapshot, rooms, scaling_snapshot
                )
                monsters = {monster["id"]: monster}

                def scaling_factory(preview, identity):
                    factory, _adapter = server_runtime(
                        character,
                        monsters,
                        deck,
                        action_id=1,
                        critical=False,
                        player_characters={character["id"]: character},
                        deck_blobs={character["id"]: deck},
                    )
                    return factory(
                        preview,
                        {"native_retained_container": {"present": False}},
                    )[0]

                with patch.object(
                    dungeon_scaling_catalog, "current", return_value=supplement
                ):
                    scaled, scaling_receipt = dungeon_combat_scaling.initialize(
                        encounter_db,
                        fight,
                        monsters,
                        catalog=supplement,
                        runtime_factory=scaling_factory,
                    )
                    self.assertTrue(scaling_receipt["initialized"])
                    scaled.ready(3)

                    def state_factory(preview, identity):
                        factory, _adapter = server_runtime(
                            character,
                            monsters,
                            deck,
                            action_id=2,
                            critical=False,
                            player_characters={character["id"]: character},
                            deck_blobs={character["id"]: deck},
                        )
                        return factory

                    (
                        initialized,
                        receipt,
                        _stele_packets,
                    ) = dungeon_stele_states.initialize(
                        encounter_db,
                        scaled,
                        monsters,
                        runtime_factory=state_factory,
                    )
                    original_qi = (
                        deepcopy(scaled.native_qi_slots),
                        deepcopy(scaled.native_qi_touched_cells),
                        deepcopy(scaled.native_qi_byte_topology),
                    )
                    (
                        replay,
                        replay_receipt,
                        replay_packets,
                    ) = dungeon_stele_states.initialize(
                        encounter_db,
                        initialized,
                        monsters,
                        runtime_factory=state_factory,
                    )

                self.assertEqual(receipt["state_ids"], [state_id])
                self.assertEqual(receipt["actor_ids"], [-7])
                self.assertEqual(replay_receipt, receipt)
                self.assertEqual(replay_packets, [])
                self.assertEqual(replay.native_dungeon_stele_receipt, receipt)
                self.assertEqual(
                    (
                        replay.native_qi_slots,
                        replay.native_qi_touched_cells,
                        replay.native_qi_byte_topology,
                    ),
                    original_qi,
                )
                states = [
                    entry.reference for entry in replay.actors[-7].state_ledger.entries
                ]
                self.assertIn(state_id, states)
                self.assertNotIn(
                    state_id,
                    [
                        entry.reference
                        for entry in replay.actors[7].state_ledger.entries
                    ],
                )
                serialized = checkpoint(replay)
                self.assertEqual(serialized["native_dungeon_stele_receipt"], receipt)
                self.assertIn(
                    state_id,
                    [
                        entry.reference
                        for entry in replay.actors[-7].state_ledger.entries
                    ],
                )
                if state_id == 4020:
                    from wakfu_server.combat_server_spell import (
                        prepare_server_initialization,
                    )

                    active = deepcopy(replay)
                    before_player_max_mp = active.actors[7].max_mp
                    before_boss_max_mp = active.actors[-7].max_mp
                    started, _packets = prepare_server_initialization(
                        character,
                        monsters,
                        active,
                        3,
                        deck,
                        action_id=3,
                        fight_start=True,
                    )
                    self.assertEqual(started.actors[7].max_mp, before_player_max_mp - 3)
                    self.assertEqual(started.actors[-7].max_mp, before_boss_max_mp)
