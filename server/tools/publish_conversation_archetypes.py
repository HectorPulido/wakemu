"""Compile or publish reviewed NPC conversation archetypes, never player state.

Compile with a native ExportNativeQuestDefinitions JSON (optionally gzip) and
the existing conversation source. Publication requires the exact reviewed
source attestation and an additive predecessor; existing actors are preserved.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path

from psycopg.types.json import Jsonb

from wakfu_server.achievements import (
    conversation,
    conversation_authoring,
    conversation_story_authoring,
)
from wakfu_server import quest_npc
from wakfu_server.postgres import Database


def preserves(previous, current):
    """Permit additive definitions/edges/stages while pinning actor identity."""
    if type(previous) is not dict or type(current) is not dict:
        return False
    for key, old in previous.items():
        if key not in current:
            return False
        new = current[key]
        if key == "placements":
            for placement in old:
                matches = [
                    p
                    for p in new
                    if p["row"]["actor_id"] == placement["row"]["actor_id"]
                ]
                if len(matches) != 1 or not preserves(placement, matches[0]):
                    return False
        elif key == "row":
            if old != new:
                return False
        elif type(old) is dict:
            if not preserves(old, new):
                return False
        elif type(old) is list:
            if type(new) is not list or any(item not in new for item in old):
                return False
        elif old != new:
            return False
    return True


def publish(db, document):
    """Upgrade only an additive predecessor of the shipped reviewed source."""
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Conversation publication requires an active transaction")
    if conversation._digest(document) != quest_npc.source_contract_digest():
        raise ValueError("Conversation publication differs from reviewed source")
    previous = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (quest_npc.SETTING,)
    ).fetchone()
    if previous is not None and not preserves(previous["value"], document):
        raise ValueError("Conversation publication is not an additive predecessor")
    if previous is not None and previous["value"] != document:
        db.execute(
            "UPDATE settings SET value=%s WHERE name=%s",
            (Jsonb(document), quest_npc.SETTING),
        )
    quest_npc.install(db, document)
    return dict(
        definitions=len(document["definitions"]),
        bindings=len(document["bindings"]),
        deliveries=len(document.get("turnins", [])),
        sha256=conversation._digest(document),
    )


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "wakfu_server/maps/native_quest_conversation_contracts.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=source)
    parser.add_argument("--native-export", type=Path)
    parser.add_argument("--manifest", type=Path, action="append")
    parser.add_argument(
        "--native-dialogues",
        type=Path,
        default=root.parent / "database/protocol/npc-dialogues.json.gz",
        help="Read the packaged native NPC catalog once; compiling needs no database.",
    )
    parser.add_argument(
        "--native-site-context",
        type=Path,
        help="Reviewed native sources and floor proofs for explicitly reconstructed site NPCs.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.source.read_text())
    if args.manifest:
        if args.native_export is None:
            parser.error("--manifest requires --native-export")
        raw = args.native_export.read_bytes()
        native = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        definitions = {item["d"]: item for item in native["definitions"]}
        dialogue_raw = args.native_dialogues.read_bytes()
        dialogues = json.loads(
            gzip.decompress(dialogue_raw)
            if dialogue_raw[:2] == b"\x1f\x8b"
            else dialogue_raw
        )
        node_index = {row["id"]: row for row in dialogues["nodes"]}
        speakers = {row["ref"]: row for row in dialogues["speakers"]}
        site_context = (
            json.loads(args.native_site_context.read_text())
            if args.native_site_context
            else {}
        )
        site_sources = {row["id"]: row for row in site_context.get("sources", [])}
        site_floors = {
            int(identity): floor
            for identity, floor in site_context.get("floors", {}).items()
        }
        for manifest in args.manifest:
            declaration = json.loads(manifest.read_text())
            if declaration.get("schema") == "native-story-conversations-v1":
                document = conversation_story_authoring.extend(
                    document,
                    definitions,
                    node_index,
                    speakers,
                    declaration,
                    site_sources=site_sources,
                    site_floors=site_floors,
                )
            else:
                document = conversation_authoring.extend_delivery_chain(
                    document, definitions, node_index, declaration
                )
    raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    if args.output:
        args.output.write_bytes(raw)
    result = dict(
        applied=False,
        definitions=len(document["definitions"]),
        bindings=len(document["bindings"]),
        deliveries=len(document.get("turnins", [])),
        source_sha256=hashlib.sha256(raw).hexdigest(),
    )
    if args.apply:
        database = Database(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        try:
            with database.connection() as db:
                with db.transaction():
                    result.update(publish(db, document), applied=True)
        finally:
            database.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
