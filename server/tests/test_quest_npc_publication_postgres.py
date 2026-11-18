"""Publish the complete reviewed NPC candidate through its real SQL installer."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from psycopg import Rollback
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from tools.publish_conversation_archetypes import publish
from wakfu_server import quest_npc
from wakfu_server.achievements import conversation

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "wakfu_server/maps/native_quest_conversation_contracts.json"
)


class QuestNpcPublicationPostgresTests(PostgresCase):
    def test_full_candidate_publishes_qualified_roots_then_rolls_back_and_rejects_unrelated_edges(
        self,
    ):
        document = json.loads(SOURCE.read_text())
        actors = [p["row"]["actor_id"] for p in document["placements"]]
        qualified = [p for p in document["placements"] if p.get("native_opening_roots")]
        self.assertGreaterEqual(len(qualified), 4)
        quest_npc.source_contract_digest.cache_clear()
        self.addCleanup(quest_npc.source_contract_digest.cache_clear)
        with self.store.connection() as db:
            original = db.execute(
                "SELECT value FROM settings WHERE name=%s", (quest_npc.SETTING,)
            ).fetchone()
            before = db.execute(
                "SELECT count(*) AS n FROM world_dialogue_npcs WHERE actor_id=ANY(%s)",
                (actors,),
            ).fetchone()["n"]
            with db.transaction():
                summary = publish(db, document)
                self.assertEqual(summary["definitions"], len(document["definitions"]))
                self.assertEqual(summary["bindings"], len(document["bindings"]))
                published = quest_npc.publication(db)
                self.assertEqual(published[0], document)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM world_dialogue_npcs WHERE actor_id=ANY(%s)",
                        (actors,),
                    ).fetchone()["n"],
                    len(actors),
                )

                malformed = deepcopy(document)
                target = next(
                    p for p in malformed["placements"] if p.get("native_opening_roots")
                )
                foreign = next(
                    p
                    for p in malformed["placements"]
                    if p.get("native_opening_roots")
                    and p["row"]["actor_id"] != target["row"]["actor_id"]
                )
                target["graph"].append(deepcopy(foreign["graph"][0]))
                db.execute(
                    "UPDATE settings SET value=%s WHERE name=%s",
                    (Jsonb(malformed), quest_npc.SETTING),
                )
                # Deliberately bypass only the file-attestation guard in this
                # negative fixture, so the real graph validator must reject it.
                with patch.object(
                    quest_npc,
                    "source_contract_digest",
                    return_value=conversation._digest(malformed),
                ):
                    with self.assertRaisesRegex(ValueError, "disconnected edge"):
                        quest_npc.publication(db)
                raise Rollback()
            self.assertEqual(
                db.execute(
                    "SELECT value FROM settings WHERE name=%s", (quest_npc.SETTING,)
                ).fetchone(),
                original,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM world_dialogue_npcs WHERE actor_id=ANY(%s)",
                    (actors,),
                ).fetchone()["n"],
                before,
            )
