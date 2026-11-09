"""Accept an explicitly enabled bot's friendly challenge under its live lease."""

import struct


def accept(runtime, adapter, target_session, challenger_id, flush_positions):
    from wakfu_server.friendly_duels import answer_challenge, flush_answer_positions
    from wakfu_server.friendly_duel_runtime import prepare_and_register
    from wakfu_server.combat_terrain import prepare_terrain

    with runtime.lock:
        lease = next(
            (
                entry
                for entry in runtime.active.values()
                if entry["character_id"] == target_session.character_id
            ),
            None,
        )
        if (
            lease is None
            or lease["account_id"] != target_session.account_id
            or lease["generation"] != target_session.generation
            or "duel" not in lease["capabilities"]
            or runtime._lease(lease["bot_id"]) is not lease
        ):
            raise ValueError("Bot is not enabled for friendly duels")
        body = struct.pack(">qBB", challenger_id, 1, 0)
        flush_answer_positions(runtime.store, target_session, body, flush_positions)

        def prepare(
            db, fight_id, invitation, challenger, target, *, prepared_terrain=None
        ):
            prepared = prepare_and_register(
                runtime.store,
                adapter,
                db,
                fight_id,
                invitation,
                challenger,
                target,
                auto_locked=bool(invitation["auto_lock"]),
                prepared_terrain=prepared_terrain,
                ai_bot_character_id=target_session.character_id,
            )
            rollback = prepared.pop("rollback")
            return prepared, rollback

        return answer_challenge(
            runtime.store,
            target_session,
            body,
            prepare_duel=prepare,
            prewarm_duel=prepare_terrain,
        )
