"""Authentic Kelba arrivals activate only the eligible native intro."""

import json
import struct
from pathlib import Path

from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import mission_transport
from wakfu_server.achievements import mission_character_events, mission_toolkit, storage


class KelbaMapEnterActivationPostgresTests(PostgresCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture = (
            Path(__file__).parent / "fixtures" / "native_kelba_exclusive_intros.json"
        )
        cls.native = json.loads(fixture.read_text(encoding="utf-8"))["definitions"]
        cls.revision = "a" * 64

    def _publish_fixture(self):
        profile = {
            "version": 1,
            "id": "kelba-map-enter-intro-test",
            "evidence": ["Exact native definitions and reviewed Kelba arrival scope."],
            "bindings": [],
            "links": [],
            "activations": [
                {
                    "id": "modern-intro-on-kelba-arrival",
                    "quest_id": 2534,
                    "event": {"kind": "map_enter", "reference": 943},
                    "maps": [943],
                    "instances": [0],
                },
                *[
                    {
                        "id": f"ready-intro-{quest_id}",
                        "quest_id": quest_id,
                        "event": {"kind": "character_ready", "reference": 0},
                        "minimum_level": 65,
                        "admission_evidence": "Reviewed level65 intro threshold.",
                        "maps": [943],
                        "instances": [0],
                    }
                    for quest_id in (2533, 2534)
                ],
            ],
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count)"
                " VALUES(%s,%s,%s,%s)",
                (
                    self.revision,
                    Jsonb({"fixture": "native_kelba_exclusive_intros"}),
                    b"fixture",
                    2,
                ),
            )
            for native in self.native:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data)"
                    " VALUES(%s,%s,%s)",
                    (self.revision, native["d"], Jsonb({"native": native})),
                )
            mission_toolkit.install(db, profile, activate=True)

    def _character(self, name, level):
        username = "kelba_" + name.lower().replace(" ", "_")
        account = self.store.register(username, "isolated-password")["id"]
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s AND account_id=%s",
                (level, character["id"], account),
            )
        return account, generation, self.store.character(account, character["id"])

    def _travel(self, account, generation, source, map_id):
        destination = {
            "map_id": map_id,
            "instance_id": 0,
            "x": -100 if map_id == 943 else 0,
            "y": 0,
            "z": -47 if map_id == 943 else 0,
        }
        return mission_transport.transition(
            self.store,
            account,
            generation,
            source,
            {"destination": destination},
            native_zaap=False,
        )

    def test_native_arrival_level_gate_replay_and_existing_legacy_intro(self):
        self._publish_fixture()

        # A real level65 map transition emits map_enter 943 and starts only
        # the modern native branch, including the normal incremental HUD rows.
        account, generation, source = self._character("Kelba Senior", 65)
        arrived, packets = self._travel(account, generation, source, 943)
        self.assertEqual((arrived["map_id"], arrived["instance_id"]), (943, 0))
        self.assertIn((13205, struct.pack(">qi", arrived["id"], 2534)), packets)
        self.assertTrue({13312, 13371} <= {opcode for opcode, _ in packets})
        with self.store.connection() as db:
            state = storage.load_locked(db, arrived["id"])
            self.assertIn(2534, state["running"])
            self.assertNotIn(2533, state["running"])

            # A fresh authentic event token cannot activate or pay the same
            # already-running native quest a second time.
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            self.store.lock_character(db, account, generation, arrived["id"])
            current = self.store.character(account, arrived["id"], db)
            self.assertEqual(
                mission_toolkit.settle(
                    db, self.store, current, "arrival-replay", "map_enter", 943
                ),
                [],
            )

        # The native cjI GetRealLevel gate independently rejects a level64
        # arrival, even though the profile's event scope matches exactly.
        account64, generation64, source64 = self._character("Kelba Junior", 64)
        _, packets64 = self._travel(account64, generation64, source64, 943)
        self.assertNotIn(13205, [opcode for opcode, _ in packets64])
        with self.store.connection() as db:
            state64 = storage.load_locked(db, source64["id"])
            self.assertNotIn(2533, state64["running"])
            self.assertNotIn(2534, state64["running"])

        # If the original legacy intro is already active, the modern arrival
        # must preserve it and honor native !IsAchievementActive(2533).
        account_old, generation_old, source_old = self._character("Legacy Kelba", 65)
        legacy_location = dict(source_old, map_id=943, x=-100, y=0, z=-47)
        self.store.transition_map(
            account_old,
            generation_old,
            source_old["id"],
            source_old,
            {
                key: legacy_location[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            },
        )
        selected = self.store.character(account_old, source_old["id"])
        self.assertIn(
            (13205, struct.pack(">qi", selected["id"], 2533)),
            mission_character_events.ready(
                self.store, account_old, generation_old, selected
            ),
        )
        back, _ = self._travel(account_old, generation_old, selected, 527)
        arrived_old, packets_old = self._travel(account_old, generation_old, back, 943)
        self.assertNotIn(13205, [opcode for opcode, _ in packets_old])
        with self.store.connection() as db:
            old_state = storage.load_locked(db, arrived_old["id"])
            self.assertIn(2533, old_state["running"])
            self.assertNotIn(2534, old_state["running"])
