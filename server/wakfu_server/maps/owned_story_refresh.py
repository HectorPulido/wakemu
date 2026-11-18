"""Restore the native map context between relocated original story stages.

Only committed owned stage receipts can request a refresh. The existing World
travel publisher owns the complete bootstrap and acknowledges successful server
writes; this module never changes coordinates, membership or mission progress.
"""

from wakfu_server import owned_story_controller as controller
from wakfu_server.achievements import storage


def _proof(selected, character, step):
    return dict(
        profile_sha256=controller._digest(selected),
        instance_id=character["instance_id"],
        step=step,
    )


def _ack_key(key):
    return "owned-story-context-refreshed:" + key


def pending(db, store, character, *, due_only=False):
    selected, completed = controller._scope(db, store, character, check_position=False)
    for step in selected["steps"]:
        if step["id"] not in completed:
            continue
        key = controller._key(selected, character["instance_id"], step["id"])
        receipt = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], key),
        ).fetchone()
        if receipt is None or receipt["payload"].get("refresh_context") is not True:
            continue
        if due_only:
            from wakfu_server.owned_story_mechanics import sources

            delay = (
                sources(selected).get("context_refresh_delays", {}).get(step["id"], 0)
            )
            if type(delay) is not int or not 0 <= delay <= 60000:
                raise ValueError("Malformed native story context refresh delay")
            if not receipt["payload"].get(
                "presentation_delivered",
                not receipt["payload"].get("presentation_suppressed", False),
            ):
                delay = 0
            if delay:
                started = receipt["payload"].get("created_ms")
                if type(started) is not int or started < 0:
                    raise ValueError(
                        "Story context refresh lost its authentic scene clock"
                    )
                if int(store.now().timestamp() * 1000) < started + delay:
                    return None
        acknowledged = db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], _ack_key(key)),
        ).fetchone()
        if acknowledged is None:
            return _proof(selected, character, step["id"])
    return None


def notify_pending(store, character, generation):
    from wakfu_server import rift_transition_delivery

    with store.connection() as db:
        enabled = db.execute(
            "SELECT 1 FROM dungeon_instances i JOIN dungeon_runtime_configurations c "
            "ON c.route_key=i.context_route_key AND c.policy_version=i.context_policy_version "
            "WHERE i.instance_id=%s AND jsonb_path_exists(c.configuration, "
            "'$.topology.owned_story_controller.steps[*].effects[*] ? (@.kind == \"context_refresh\")')",
            (character.get("instance_id"),),
        ).fetchone()
        if enabled is None:
            return False
        # The owned scene and selected lease are independently rechecked by
        # the existing World publisher before any packets are emitted.
        proof = pending(db, store, character, due_only=True)
        if proof is None:
            return False
        selected = db.execute(
            "SELECT 1 FROM sessions WHERE account_id=%s AND character_id=%s "
            "AND generation=%s AND expires_at>%s",
            (character["account_id"], character["id"], generation, store.now()),
        ).fetchone()
        if selected is None:
            raise ValueError("Owned context refresh lost its selected lease")
    rift_transition_delivery.queue_owned_position_refresh(
        character["account_id"],
        generation,
        character["id"],
        character,
        context_receipt=proof,
    )
    return True


def acknowledge(store, character, proof):
    if not isinstance(proof, dict) or set(proof) != {
        "profile_sha256",
        "instance_id",
        "step",
    }:
        raise ValueError("Malformed owned context refresh receipt")
    with store.connection() as db:
        selected, completed = controller._scope(
            db, store, character, check_position=False
        )
        if (
            proof != _proof(selected, character, proof["step"])
            or proof["step"] not in completed
        ):
            raise ValueError("Owned context refresh escaped its actual stage")
        key = controller._key(selected, character["instance_id"], proof["step"])
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], key),
        ).fetchone()
        if row is None or row["payload"].get("refresh_context") is not True:
            raise ValueError("Owned context refresh has no committed stage request")
        storage.record_event(
            db,
            character["id"],
            _ack_key(key),
            dict(
                proof, schema="owned-story-context-refreshed-v1", owner=character["id"]
            ),
        )
