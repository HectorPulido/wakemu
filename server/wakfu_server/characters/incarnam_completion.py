"""Settle the final Incarnam objective after the observed Rii scene callback."""
from wakfu_server.achievements import mission_dependencies, mission_progress, storage


def complete_after_rii_intro(store, account_id, generation, character):
    """Return mission packets; reject stale or unrelated scene contexts."""
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if (current["map_id"], current["instance_id"]) != (1385, 0):
            raise ValueError("Incarnam completion requires the Rii introduction")
        before = storage.load_locked(db, current["id"])
        if 5139 not in before["running"] or 10568 in before["objectives"]:
            return []
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=%s",
            (5139,),
        ).fetchone()
        if row is None:
            raise ValueError("Missing native Incarnam mission definition")
        definition = row["data"]["native"]
        if definition.get("d") != 5139:
            raise ValueError("Invalid native Incarnam mission definition")
        now_ms = int(store.now().timestamp() * 1000)
        planned = mission_progress.advance_objective(
            before,
            definition,
            10568,
            character=current,
            store=store,
            now_ms=now_ms,
        )
        if not storage.record_event(
            db,
            current["id"],
            "incarnam-rii-intro:10568",
            {"kind": "scenario_callback", "event_id": 22360, "objective_id": 10568},
        ):
            raise ValueError("Incarnam completion receipt exists without progress")
        result = mission_dependencies.settle(
            db, store, current, before, planned, {}, (), now_ms=now_ms
        )
        return result["packets"]
