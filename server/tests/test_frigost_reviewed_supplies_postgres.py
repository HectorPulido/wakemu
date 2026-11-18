"""Accepted native Frigost dialogue choices recover only missing supplies."""

import json
import struct
from pathlib import Path
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

from wakfu_server import quest_npc
from wakfu_server.achievements import conversation, mission_toolkit, storage
from wakfu_server.items import quest_inventory


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/frigost_native_missing_supply_dialogue.json"


class FrigostReviewedSuppliesPostgresTests(PostgresCase):
    def test_native_begin_choose_completion_and_missing_only_supply_recovery(self):
        document = json.loads(FIXTURE.read_text())
        definitions = {row["d"]: row for row in document["definitions"]}
        placements = {row["row"]["reference_id"]: row for row in document["placements"]}
        source_digest = conversation._digest(document)
        profile = json.loads(
            (
                ROOT
                / "wakfu_server/achievements/mission_profiles/frigost-initial-acquisitions.json"
            ).read_text()
        )
        native_revision = "f" * 64

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (quest_npc.SETTING, Jsonb(document)),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count)"
                "VALUES(%s,%s,%s,%s)",
                (
                    native_revision,
                    Jsonb({"fixture": "reviewed Frigost native supply"}),
                    b"frigost-native-supply-dialogue",
                    len(definitions),
                ),
            )
            for identity, definition in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data)"
                    "VALUES(%s,%s,%s)",
                    (native_revision, identity, Jsonb({"native": definition})),
                )
            mission_toolkit.install(db, profile, activate=True)

            for placement in document["placements"]:
                row = placement["row"]
                db.execute(
                    "INSERT INTO world_dialogue_npcs"
                    "(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,"
                    "action_ids,interaction_range,enabled,provenance)"
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        row["actor_id"],
                        row["reference_id"],
                        row["map_id"],
                        row["instance_id"],
                        row["x"],
                        row["y"],
                        row["z"],
                        row["direction"],
                        row["dialogue_root"],
                        Jsonb(row["action_ids"]),
                        row["interaction_range"],
                        row["enabled"],
                        row["provenance"],
                    ),
                )

        def character_at(actor_id):
            placement = placements[actor_id]
            row = placement["row"]
            anchor = placement.get("interaction_anchor", row)
            account = self.store.register(
                f"frigost-supply-{actor_id}", "isolated-supply-password"
            )["id"]
            character = self.store.create_character(
                account, "David Supply" if actor_id == 2394 else "Bill Supply"
            )
            generation = self.store.begin_session(account)
            character = self.store.select_character(
                account, generation, character["id"]
            )
            character_id = character["id"]
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=100,map_id=504,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (anchor["x"], anchor["y"], anchor["z"], character_id),
                )
                state = storage.load_locked(db, character_id)
                if actor_id == 2394:
                    # A genuine prior hunter assignment with objective2196 and
                    # its ten delivered furs authorizes David's native turn-in.
                    state["completed"] = [1224]
                    state["running"] = [1226]
                    state["objectives"] = [2196]
                    state["variables"]["268"] = 10
                    storage.store(db, character_id, state)
                    quest_inventory.grant(db, character_id, 16070, 10)
                else:
                    # The prior camp clue is complete; the final accepted
                    # native Bill acknowledgment completes1227 and starts1110.
                    state["completed"] = [1224, 1226]
                    state["running"] = [1227]
                    state["objectives"] = [2197]
                    state["variables"]["258"] = 10
                    storage.store(db, character_id, state)
            return account, generation, character_id

        def open_dialogue(account, generation, character_id, actor_id):
            placement = placements[actor_id]
            row = placement["row"]
            npc_actor_id = row["actor_id"]
            with patch.object(
                quest_npc, "source_contract_digest", return_value=source_digest
            ):
                with self.store.connection() as db:
                    published = quest_npc.publication(db)
                    persisted_row = db.execute(
                        "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s",
                        (row["actor_id"],),
                    ).fetchone()
                    self.assertTrue(
                        quest_npc.qualified_placement(
                            persisted_row, published=published
                        ),
                        dict(persisted_row),
                    )
                self.assertIsNotNone(published)

                def rows_provider():
                    return [dict(row, _quest_publication=published)]

                session, packets = quest_npc.begin(
                    self.store,
                    account,
                    generation,
                    self.store.character(account, character_id),
                    npc_actor_id,
                    row["action_ids"][0],
                    character_provider=lambda: self.store.character(
                        account, character_id
                    ),
                    rows_provider=rows_provider,
                )
            return session, packets

        def choose(account, generation, character_id, session, node, choice):
            with patch.object(
                quest_npc, "source_contract_digest", return_value=source_digest
            ):
                return quest_npc.choose(
                    self.store,
                    account,
                    generation,
                    self.store.character(account, character_id),
                    session,
                    struct.pack(">ii", node, choice),
                )

        def current_state(character_id):
            with self.store.connection() as db:
                return storage.load_locked(db, character_id)

        david_account, david_generation, david_id = character_at(2394)
        david, _opening = open_dialogue(david_account, david_generation, david_id, 2394)
        self.assertEqual(david.node_id, 2047)
        # Opening alone and an unoffered terminal choice do not supply the tool.
        with self.store.connection() as db:
            self.assertEqual(
                sum(
                    item["quantity"]
                    for item in quest_inventory.load(db, david_id)
                    if item["reference"] == 16073
                ),
                0,
            )
        with self.assertRaises(ValueError):
            choose(david_account, david_generation, david_id, david, 2047, 4742)
        choose(david_account, david_generation, david_id, david, 2047, 4740)
        self.assertEqual(david.node_id, 2052)
        state = current_state(david_id)
        self.assertIn(1226, state["completed"])
        self.assertIn(1227, state["running"])
        choose(david_account, david_generation, david_id, david, 2052, 4742)
        with self.store.connection() as db:
            amount = sum(
                item["quantity"]
                for item in quest_inventory.load(db, david_id)
                if item["reference"] == 16073
            )
        self.assertEqual(amount, 1)
        replay, _packets = open_dialogue(
            david_account, david_generation, david_id, 2394
        )
        self.assertEqual(replay.node_id, 2052)
        choose(david_account, david_generation, david_id, replay, 2052, 4742)
        with self.store.connection() as db:
            self.assertEqual(
                sum(
                    item["quantity"]
                    for item in quest_inventory.load(db, david_id)
                    if item["reference"] == 16073
                ),
                1,
            )

        bill_account, bill_generation, bill_id = character_at(2358)
        bill, _opening = open_dialogue(bill_account, bill_generation, bill_id, 2358)
        self.assertEqual(bill.node_id, 1985)
        choose(bill_account, bill_generation, bill_id, bill, 1985, 4735)
        choose(bill_account, bill_generation, bill_id, bill, 2074, 4814)
        choose(bill_account, bill_generation, bill_id, bill, 2049, 4736)
        state = current_state(bill_id)
        self.assertIn(1227, state["completed"])
        self.assertIn(1110, state["running"])
        with self.store.connection() as db:
            self.assertEqual(
                sum(
                    item["quantity"]
                    for item in quest_inventory.load(db, bill_id)
                    if item["reference"] == 16158
                ),
                1,
            )
        recovery, _packets = open_dialogue(bill_account, bill_generation, bill_id, 2358)
        choose(bill_account, bill_generation, bill_id, recovery, 1985, 4689)
        choose(bill_account, bill_generation, bill_id, recovery, 2027, 4690)
        with self.store.connection() as db:
            self.assertEqual(
                sum(
                    item["quantity"]
                    for item in quest_inventory.load(db, bill_id)
                    if item["reference"] == 16158
                ),
                1,
            )
