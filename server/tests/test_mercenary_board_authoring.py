"""Reviewed native mercenary-board compilation and admission semantics."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import struct
import unittest
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server.achievements import mercenary_board_authoring
from wakfu_server import dungeon_criteria, mercenary_boards


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/native_mercenary_board_compiler.json"
PROFILE = ROOT / "wakfu_server/achievements/mercenary_board_profiles/astrub.json"
PACKAGED = ROOT / "wakfu_server/maps/native_mercenary_board_contracts.json"


def inputs():
    fixture = json.loads(FIXTURE.read_text())
    source = {
        "boards": [
            {
                "source": fixture["board_source"],
                "descriptor": fixture["descriptor"],
            },
            *fixture.get("additional_boards", []),
        ],
        "definitions": [fixture["definition"], *fixture["additional_definitions"]],
        "additional_floor_proofs": fixture.get("additional_floor_proofs", {}),
    }
    manifest = json.loads(PROFILE.read_text())
    floor = fixture["floor_proof"]
    return source, manifest, floor


def compile_candidate(*, source=None, manifest=None, floor=None):
    source, manifest, floor = inputs() if source is None else (source, manifest, floor)
    return mercenary_board_authoring.compile_contracts(
        [row["source"] for row in source["boards"]],
        [row["descriptor"] for row in source["boards"]],
        {row["d"]: row for row in source["definitions"]},
        manifest,
        floor_proofs={
            527: floor,
            **{int(k): v for k, v in source.get("additional_floor_proofs", {}).items()},
        },
    )


class MercenaryBoardAuthoringTests(unittest.TestCase):
    def test_compiler_is_deterministic_and_preserves_exact_native_board_and_whitelist(
        self,
    ):
        first = compile_candidate()
        second = compile_candidate()
        packaged = json.loads(PACKAGED.read_text())
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], packaged["schema"])
        self.assertEqual(first["boards"], packaged["boards"])
        self.assertEqual(len(first["boards"]), 3)
        board = first["boards"][0]
        self.assertEqual(board["source"]["id"], 23865)
        self.assertEqual(board["source"]["z"], 13.0)
        self.assertEqual(board["native_effect"]["effect_type"], 11)
        self.assertEqual(board["category"], 237)
        self.assertEqual(board["playable_quests"], [2135, 2140])
        self.assertEqual(board["interaction_anchor"], {"x": 18, "y": 45, "z": 0})
        fields = first["boards"][1]
        self.assertEqual((fields["source"]["id"], fields["category"]), (24162, 238))
        self.assertEqual(fields["playable_quests"], [2138, 2143, 2144, 2145, 2146])
        self.assertEqual(fields["interaction_anchor"], {"x": 16, "y": 45, "z": 0})
        self.assertEqual(
            [row["d"] for row in first["definitions"]],
            [2135, 2140, 2138, 2143, 2144, 2145, 2146, 2139, 2147, 2150, 2151],
        )
        for identity in (2145, 2146):
            native = next(row for row in first["definitions"] if row["d"] == identity)
            eligibility = (
                mercenary_board_authoring.native_effective_eligibility.criterion(native)
            )
            self.assertIn("GetLevel() >= 6", eligibility)
            self.assertIn("IsAchievementComplete(2143)", eligibility)
            self.assertIn("IsAchievementComplete(2144)", eligibility)
        rank3 = next(row for row in first["definitions"] if row["d"] == 2138)
        rank3_eligibility = (
            mercenary_board_authoring.native_effective_eligibility.criterion(rank3)
        )
        for parent in (2143, 2144, 2145, 2146):
            self.assertIn(f"IsAchievementComplete({parent})", rank3_eligibility)
        sewer = first["boards"][2]
        self.assertEqual((sewer["source"]["id"], sewer["category"]), (24110, 239))
        self.assertEqual(sewer["playable_quests"], [2139, 2147, 2150, 2151])
        self.assertEqual(sewer["interaction_anchor"], {"x": -20, "y": 14, "z": 0})
        self.assertNotIn(2149, [row["d"] for row in first["definitions"]])
        for identity in (2139, 2150, 2151):
            native = next(row for row in first["definitions"] if row["d"] == identity)
            eligibility = (
                mercenary_board_authoring.native_effective_eligibility.criterion(native)
            )
            self.assertIn("IsAchievementComplete(2147)", eligibility)
            self.assertIn("IsAchievementComplete(2149)", eligibility)
        definition = next(row for row in first["definitions"] if row["d"] == 2140)
        packaged_definition = next(
            row for row in packaged["definitions"] if row["d"] == 2140
        )
        self.assertEqual(definition["cjI"], "")
        self.assertIn(
            "GetLevel() >= 6",
            mercenary_board_authoring.native_effective_eligibility.criterion(
                definition
            ),
        )
        self.assertEqual(definition["d"], packaged_definition["d"])
        self.assertEqual(definition["cjG"], packaged_definition["cjG"])
        self.assertEqual(definition["cjP"], packaged_definition["cjP"])

    def test_compiler_rejects_auto_board_ambiguous_effect_wrong_category_and_timed_quest(
        self,
    ):
        source, manifest, floor = inputs()
        bad = deepcopy(source)
        bad["boards"][0]["source"]["auto"] = True
        with self.assertRaisesRegex(ValueError, "explicit native board action"):
            compile_candidate(source=bad, manifest=manifest, floor=floor)

        source, manifest, floor = inputs()
        bad = deepcopy(source)
        bad["boards"][0]["descriptor"]["groups"][0]["actions"][0]["effects"].append(
            deepcopy(
                bad["boards"][0]["descriptor"]["groups"][0]["actions"][0]["effects"][0]
            )
        )
        with self.assertRaisesRegex(ValueError, "Ambiguous native mercenary"):
            compile_candidate(source=bad, manifest=manifest, floor=floor)

        source, manifest, floor = inputs()
        bad = deepcopy(source)
        bad["definitions"] = [
            dict(row, cjG=999) if row["d"] == 2140 else row
            for row in bad["definitions"]
        ]
        with self.assertRaisesRegex(ValueError, "does not belong"):
            compile_candidate(source=bad, manifest=manifest, floor=floor)

        source, manifest, floor = inputs()
        bad = deepcopy(source)
        bad["definitions"] = [
            dict(row, getDuration=1) if row["d"] == 2140 else row
            for row in bad["definitions"]
        ]
        with self.assertRaisesRegex(ValueError, "does not belong"):
            compile_candidate(source=bad, manifest=manifest, floor=floor)

    def test_compiler_requires_connected_floor_proof_and_a_real_playable_allowlist(
        self,
    ):
        source, manifest, floor = inputs()
        with self.assertRaisesRegex(ValueError, "reviewed native floor geometry"):
            mercenary_board_authoring.compile_contracts(
                [row["source"] for row in source["boards"]],
                [row["descriptor"] for row in source["boards"]],
                {row["d"]: row for row in source["definitions"]},
                manifest,
            )
        disconnected = deepcopy(floor)
        disconnected["edges"] = []
        with self.assertRaisesRegex(ValueError, "connected native geometry"):
            compile_candidate(source=source, manifest=manifest, floor=disconnected)
        bad_manifest = deepcopy(manifest)
        bad_manifest["boards"][0]["playable_quests"] = [999999]
        with self.assertRaises((KeyError, ValueError)):
            compile_candidate(source=source, manifest=bad_manifest, floor=floor)

    def test_recognizer_and_native_selection_codec_fail_closed(self):
        mercenary_boards._object_ids.cache_clear()
        self.assertTrue(mercenary_boards.recognizes(struct.pack(">qHH", 23865, 0, 0)))
        self.assertFalse(mercenary_boards.recognizes(struct.pack(">qHH", 99999, 0, 0)))
        for body in (b"", bytearray(struct.pack(">qHH", 23865, 0, 0))):
            self.assertFalse(mercenary_boards.recognizes(body))

        now = datetime(2026, 11, 15, tzinfo=timezone.utc)
        clock = Mock()
        clock.now.return_value = now
        offer = mercenary_boards.BoardOffer(
            account_id=4,
            generation="owner-generation",
            character_id=8,
            map_id=527,
            instance_id=0,
            board_id=23865,
            source_sha256="a" * 64,
            offered=(2140,),
            expires_at_ms=int(now.timestamp() * 1000) + 1000,
        )
        cases = (
            (None, 4, "owner-generation", 8, struct.pack(">iqB", 2140, -1, 1)),
            (offer, 5, "owner-generation", 8, struct.pack(">iqB", 2140, -1, 1)),
            (offer, 4, "other-generation", 8, struct.pack(">iqB", 2140, -1, 1)),
            (offer, 4, "owner-generation", 9, struct.pack(">iqB", 2140, -1, 1)),
            (offer, 4, "owner-generation", 8, struct.pack(">iqB", 2140, 0, 1)),
            (offer, 4, "owner-generation", 8, struct.pack(">iqB", 2140, -1, 0)),
            (offer, 4, "owner-generation", 8, struct.pack(">iqB", 2141, -1, 1)),
            (offer, 4, "owner-generation", 8, b"short"),
        )
        for candidate, account, generation, character_id, body in cases:
            with self.subTest(body=body.hex(), account=account), self.assertRaises(
                ValueError
            ):
                mercenary_boards.select(
                    clock,
                    account,
                    generation,
                    {"id": character_id},
                    candidate,
                    body,
                )
        expired = mercenary_boards.BoardOffer(
            **{**offer.__dict__, "expires_at_ms": int(now.timestamp() * 1000) - 1}
        )
        with self.assertRaisesRegex(ValueError, "not offered"):
            mercenary_boards.select(
                clock,
                4,
                "owner-generation",
                {"id": 8},
                expired,
                struct.pack(">iqB", 2140, -1, 1),
            )

    def test_rank_and_effective_level_gate_is_independent_of_real_level(self):
        from wakfu_server.achievements.native_effective_eligibility import criterion

        source = json.loads(FIXTURE.read_text())["rank_definition"]
        self.assertFalse(
            mercenary_boards._eligible(
                None,
                {"id": 1, "level": 6, "effective_level": 6},
                {"running": [], "completed": [], "objectives": []},
                source,
            )
        )
        self.assertIn("IsAchievementComplete(2143)", criterion(source))
        self.assertFalse(
            mercenary_boards._eligible(
                None,
                {"id": 1, "level": 99, "effective_level": 5},
                {
                    "running": [],
                    "completed": [2143, 2144, 2145, 2146],
                    "objectives": [],
                },
                source,
            )
        )
        self.assertTrue(
            mercenary_boards._eligible(
                None,
                {"id": 1, "level": 1, "effective_level": 6},
                {
                    "running": [],
                    "completed": [2143, 2144, 2145, 2146],
                    "objectives": [],
                },
                source,
            )
        )

    def test_native_nation_and_instance_predicates_use_owned_map_facts(self):
        character = {"nation_id": 0, "map_id": 527, "instance_id": 987654}
        self.assertTrue(
            dungeon_criteria.evaluate(
                None,
                "GetNationId() == 0 && GetInstanceId() == 527",
                character=character,
                queries={},
                now_ms=0,
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                None,
                "GetNationId() == 30 || GetInstanceId() == 0",
                character=character,
                queries={},
                now_ms=0,
            )
        )
        for expression, incomplete in (
            ("GetNationId() == 0", {"map_id": 527}),
            ("GetInstanceId() == 527", {"nation_id": 0}),
            ("GetNationId() == 0", {"nation_id": True}),
        ):
            with self.subTest(
                expression=expression, incomplete=incomplete
            ), self.assertRaises(ValueError):
                dungeon_criteria.evaluate(
                    None, expression, character=incomplete, queries={}, now_ms=0
                )


class MercenaryBoardPostgresTests(PostgresCase):
    def test_real_board_offer_binds_owner_scene_and_accepts_once(self):
        from psycopg.types.json import Jsonb
        from wakfu_server.achievements import storage

        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8))
        account = self.store.register("board_" + suffix, secrets.token_urlsafe(24))[
            "id"
        ]
        character = self.store.create_character(account, "Board Qa " + suffix, breed=19)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        document = json.loads(PACKAGED.read_text())
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=18,y=45,z=0,level=6 WHERE id=%s",
                (character["id"],),
            )
            result = mercenary_boards.install(db, document)
        self.assertEqual(result, {"boards": 3, "definitions": 11})
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["completed"] = sorted(set(state["completed"]) | {5568})
            state["completion_dates"]["5568"] = 1_794_767_836_018
            storage.store(db, character["id"], state)
        current = self.store.character(account, character["id"])
        open_body = struct.pack(">qHH", 23865, 0, 0)
        offer = mercenary_boards.open_board(
            self.store, account, generation, current, open_body
        )
        self.assertEqual(offer.offered, (2135, 2140))

        # A valid offer cannot be replayed from another public map.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=888 WHERE id=%s", (character["id"],)
            )
        changed = self.store.character(account, character["id"])
        with self.assertRaisesRegex(ValueError, "another scene"):
            mercenary_boards.select(
                self.store,
                account,
                generation,
                changed,
                offer,
                struct.pack(">iqB", 2140, -1, 1),
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,x=18,y=45,z=0 WHERE id=%s",
                (character["id"],),
            )
        current = self.store.character(account, character["id"])
        packets = mercenary_boards.select(
            self.store,
            account,
            generation,
            current,
            offer,
            struct.pack(">iqB", 2140, -1, 1),
        )
        self.assertTrue(packets)
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            receipts = db.execute(
                "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key='native-mercenary-board-acceptance:2140'",
                (character["id"],),
            ).fetchone()["n"]
        self.assertIn(2140, state["running"])
        self.assertEqual(receipts, 1)
        with self.assertRaisesRegex(ValueError, "eligibility changed"):
            mercenary_boards.select(
                self.store,
                account,
                generation,
                current,
                offer,
                struct.pack(">iqB", 2140, -1, 1),
            )
        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertIn(2140, storage.load_locked(db, character["id"])["running"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key='native-mercenary-board-acceptance:2140'",
                    (character["id"],),
                ).fetchone()["n"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
