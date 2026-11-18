"""Finite native achievement awards from authenticated final dungeon outcomes.

These are native aqb=true achievements, not visible mission-toolkit quests.
Original earning criteria and rewards remain unchanged. The ordinary
achievement engine and durable outbox settle the qualified objective once.
"""
from functools import lru_cache
import json
from pathlib import Path

SOURCE = (
    Path(__file__).with_name("dungeon_achievement_profiles")
    / "whisper-hushquarters693.json"
)


@lru_cache(maxsize=1)
def source():
    document = json.loads(SOURCE.read_text())
    if (
        set(document)
        != {
            "schema",
            "id",
            "native_metadata_revision",
            "definition",
            "objective_id",
            "proof",
            "provenance",
        }
        or document["schema"] != "native-dungeon-achievement-v1"
        or not document["provenance"]
    ):
        raise ValueError("Invalid native dungeon achievement binding")
    definition = document["definition"]
    if (
        definition.get("native_class") != "aJM"
        or definition.get("aqb") is not True
        or len(definition.get("cjJ", ())) != 1
        or definition["cjJ"][0]["d"] != document["objective_id"]
        or definition["cjJ"][0].get("ckf")
    ):
        raise ValueError("Native dungeon achievement differs from its finite objective")
    return document


def settle(db, store, character, event):
    from . import engine, rewards, storage, wire, service, mission_toolkit
    from . import native_effective_eligibility
    from wakfu_server import dungeon_criteria, dungeon_achievement_authority
    from wakfu_server import simultaneous_party_pads

    document = source()
    proof = document["proof"]
    if event.get("completed_dungeon_id") != proof["dungeon_definition_id"] or not set(
        proof["boss_references"]
    ) <= set(event.get("original_breeds", ())):
        return []
    # Publication of the complete physical party-pad block enables its real
    # dungeon-achievement dependency too; installing code alone activates none.
    pad_profile = simultaneous_party_pads.source()
    if not simultaneous_party_pads._enabled(db, pad_profile):
        return []
    definition = document["definition"]
    raw = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
        (document["native_metadata_revision"], definition["d"]),
    ).fetchone()
    if raw is None or raw["data"]["native"] != definition:
        raise ValueError("Dungeon achievement differs from imported native definition")
    outcome = simultaneous_party_pads.king_outcome(
        db, proof, character.get("instance_id", 0)
    )
    if outcome is None or outcome["fight_id"] != event["fight_id"]:
        return []
    packets = mission_toolkit.settle(
        db,
        store,
        character,
        token=f"owned-dungeon-boss:{event['fight_id']}",
        kind="owned_dungeon_boss_completed",
        reference=proof["dungeon_definition_id"],
    )
    before = storage.load_locked(db, character["id"])
    if definition["d"] in before["completed"]:
        return packets
    now_ms = int(store.clock() * 1000)
    queries = dungeon_achievement_authority.queries_from_state(before, now_ms=now_ms)
    objective = definition["cjJ"][0]
    if not all(
        dungeon_criteria.evaluate(
            store, criterion, character=character, queries=queries
        )
        for criterion in (
            # aHe controls native journal visibility, not earned completion.
            native_effective_eligibility.criterion(definition),
            objective["ckc"],
            objective["cke"],
        )
    ):
        return packets
    token = f"native-dungeon-achievement:{definition['d']}:{event['fight_id']}"
    if not storage.record_event(
        db,
        character["id"],
        token,
        dict(
            achievement_id=definition["d"],
            objective_id=document["objective_id"],
            dungeon_id=proof["dungeon_definition_id"],
            fight_id=event["fight_id"],
        ),
    ):
        return packets
    rule = dict(
        definition_id=definition["d"],
        prerequisites=[],
        objectives=[
            dict(
                objective_id=document["objective_id"],
                dungeon_id=proof["dungeon_definition_id"],
            )
        ],
        rewards=definition["cjK"],
    )
    after, intents, objectives, completed = engine.advance(
        before,
        event,
        {"definitions": {definition["d"]: rule}, "breed_variables": {}},
        now_ms=now_ms,
    )
    for identity, reward in intents:
        rewards.validate(reward)
        storage.claim_reward(db, character["id"], identity, "once", reward["d"], reward)
    storage.store(db, character["id"], after)
    return [
        *packets,
        *wire.changes(character["id"], before, after, objectives, completed, now_ms),
        *service.drain_rewards(db, store, character),
    ]
