"""Recorded original publication replay for private native combat fixtures.

This is an offline session namespace, not authentication or evidence that the
recorded original server encounter contained the selected monster species.
The original13974 body and its ProtoDungeon are preserved byte for byte.
"""
from contextlib import contextmanager
import base64
import hashlib
from io import BytesIO
import os
from pathlib import Path
import struct
from unittest.mock import patch

SOURCE_SHA256 = "061e3c7c2c4dca1d63e1986910b79467a26f0aa52eb86e43d3e1abb8ad8619ba"
BODY_SHA256 = "dc6565a23b469194b6bb0577bd71603d739fbd85f0e02a57a09cc6ff4ad6cbfe"
CONTEXT_SHA256 = "f00551fdbf96d789cb2792a000d0a6902a9a2d4a2d83cf5c82001a9a62227dd7"


@contextmanager
def original_bootstrap_publication():
    """Bind before native constructors through the actual publication adapter."""
    import psycopg
    from psycopg.rows import dict_row
    from wakfu_server.storage.bootstrap_capture import load
    from wakfu_server.combat_instance_publication import InstancePublicationTracker
    from wakfu_server.combat_instance_context import capture_publication
    from wakfu_server.maps.proto_dungeon import decode
    from wakfu_server import combat_actor_snapshot as snapshots

    with psycopg.connect(
        os.environ["WAKFU_DATABASE_URL"],
        password=Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip(),
        row_factory=dict_row,
        connect_timeout=10,
    ) as db:
        assert (
            db.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"]
            == "on"
        )
        records = load(db, expected_source_sha256=SOURCE_SHA256)
    record = records[64]
    assert record["direction"] == "in" and record["opcode"] == 13974
    body = base64.b64decode(record["body_base64"], validate=True)
    assert hashlib.sha256(body).hexdigest() == BODY_SHA256
    context = capture_publication(13974, body, session_actor_id=1, instance_id=0)
    assert context.sha256 == CONTEXT_SHA256
    facts = {
        "authority": "original-recorded-bootstrap-replay",
        "capture_source_sha256": SOURCE_SHA256,
        "ordinal": 64,
        "body_sha256": BODY_SHA256,
        "context_sha256": CONTEXT_SHA256,
        "context": decode(context.payload),
        "bindings": [],
        "limits": "Recorded session context2 replay, not a source Excarnus encounter or difficulty5/8 qualification.",
    }
    original = snapshots.initialize_fight_snapshots

    def bound(fight, **kwargs):
        characters = kwargs["characters"]
        monsters = kwargs["monsters"]
        assert (
            len(characters) == 1
        ), "Recorded fixture requires one actual controlled participant"
        player_id = next(iter(characters))
        character = characters[player_id]
        assert (
            character["instance_id"] == 0
        ), "Original recordedcontext replay onlyqualifies instance0"
        npc_ids = tuple(monsters)
        assert set(npc_ids) | {player_id} == set(
            fight.actors
        ), "Recorded fixture roster mismatch"
        tracker = InstancePublicationTracker()
        scope = (
            character["account_id"],
            "private-recorded-bootstrap-replay",
            player_id,
            1,
            character["instance_id"],
        )
        # A real successful immutable write in the isolated fixture transport;
        # after_write receives the exact completed frame, never invented GN.
        frame = struct.pack(">IH", 6 + len(body), 13974) + body
        transport = BytesIO()
        assert transport.write(frame) == len(frame)
        tracker.after_write(transport.getvalue(), scope)
        assert tracker.bind_encounter(
            fight, scope, npc_ids=npc_ids, player_id=player_id
        )
        facts["bindings"].append(
            {
                "fight_id": fight.id,
                "npc_ids": list(npc_ids),
                "player_id": player_id,
                "instance_id": character["instance_id"],
                "published_context_sha256": tracker.published.sha256,
            }
        )
        fight.validation_recorded_instance_publication = dict(
            facts, bindings=[facts["bindings"][-1]]
        )
        return original(fight, **kwargs)

    with patch.object(snapshots, "initialize_fight_snapshots", bound):
        yield facts
