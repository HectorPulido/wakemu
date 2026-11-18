"""Publish spoken events only after a real, authenticated native NPC opening.

The reviewed source binds an exact actor, action, map and native objective.
The event reference is that objective's identity, never a client supplied ID.
The shared planner preserves its native prerequisites and ordinary progression.
"""

from uuid import uuid4

from . import conversation, mission_toolkit, storage
from .service import _owner
from wakfu_server.dungeon_achievement_authority import queries_from_state


def on_open(store, account_id, generation, character, row, action_id, session, digest):
    from wakfu_server import quest_npc

    if (
        getattr(session, "quest_publication_sha256", None) != digest
        or getattr(session, "quest_conversation_actor_id", None) != row["actor_id"]
        or session.speaker_id != row["actor_id"]
        or session.node_id is None
        or not session.authorize_speaker(session.speaker_id, session.node_id)
    ):
        raise ValueError(
            "NPC spoken source requires an authenticated open conversation"
        )
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        actual = store.character(account_id, character["id"], db)
        _owner(db, actual)
        published = quest_npc.publication(db)
        if published is None or conversation._digest(published[0]) != digest:
            raise ValueError("NPC spoken publication changed after opening")
        current, item = quest_npc._row(db, row["actor_id"], published)
        if (
            conversation.placement_signature(current)
            != conversation.placement_signature(row)
            or action_id not in current["action_ids"]
            or not quest_npc._nearby_placement(actual, current, item)
        ):
            raise ValueError("NPC spoken source is no longer in the owned scene")
        state = storage.load_locked(db, actual["id"])
        authority = queries_from_state(state)
        packets = []
        for binding in item.get("spoken_objectives", []):
            if (
                action_id not in binding["action_ids"]
                or binding["objective_id"] in state["objectives"]
            ):
                continue
            try:
                running = authority["IsAchievementRunning"](binding["quest_id"])
            except ValueError:
                # Missing native period authority cannot earn progress, but
                # must not make an unrelated ordinary greeting unusable.
                continue
            if not running:
                continue
            packets.extend(
                mission_toolkit.settle(
                    db,
                    store,
                    actual,
                    token="native-npc-spoken:" + uuid4().hex,
                    kind="npc_spoken",
                    reference=binding["objective_id"],
                )
            )
        return packets
