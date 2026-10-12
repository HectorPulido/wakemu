"""SQL-only descriptor authority; no runtime JSON fallback or import-time DB."""
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server import intergame_codec as codec


def seeded_schema():
    sql = (
        Path(__file__).resolve().parents[1]
        / "migrations/155_intergame_protocol_descriptors.sql"
    ).read_text()
    return json.loads(sql.split("$intergame$")[1])


class IntergameDatabaseSchemaTests(unittest.TestCase):
    def setUp(self):
        codec._schema.cache_clear()

    def tearDown(self):
        codec._schema.cache_clear()

    def database(self, value):
        database = MagicMock()
        database.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            value
        )
        return database

    def test_exact_seed_and_native_wire_round_trip_use_database(self):
        database = self.database({"value": seeded_schema()})
        with patch("wakfu_server.native_catalog._database", return_value=database):
            self.assertEqual(len(codec.IDS), 41)
            self.assertEqual(codec.IDS["channel.CreateChannelMessageCmd"], 1835442294)
            self.assertEqual(codec.NAMES[-1150791598], "user.FriendList")
            payload = codec.response(7, name="user.FriendList", value={"values": []})
            result = codec.decode("transport.Frame", payload)["response"]
            self.assertEqual(result["correlation_id"], 7)
            self.assertEqual(result["payload"]["id"], -1150791598)
            self.assertEqual(
                codec.decode("user.FriendList", result["payload"]["data"]), {}
            )
            self.assertEqual(database.connection.call_count, 1)

    def test_missing_database_authority_rejects_without_file_fallback(self):
        with patch(
            "wakfu_server.native_catalog._database", return_value=self.database(None)
        ):
            with self.assertRaisesRegex(ValueError, "Missing PostgreSQL"):
                len(codec.IDS)

    def test_duplicate_native_identifier_rejected(self):
        document = seeded_schema()
        document["identifiers"].append(dict(document["identifiers"][0]))
        with patch(
            "wakfu_server.native_catalog._database",
            return_value=self.database({"value": document}),
        ):
            with self.assertRaisesRegex(
                ValueError, "Invalid native intergame identifier"
            ):
                len(codec.IDS)
