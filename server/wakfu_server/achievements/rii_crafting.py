"""Complete Rii's crafting tutorial from a committed native occupation.

The item, recipe and station are native client data. Connecting their successful
completion to the quest is a local reconstruction, not a captured server effect.
"""
from . import mission_dependencies, mission_progress, storage


def settle(db, store, character, occupation):
    """Settle the one qualified craft inside its inventory transaction."""
    if (character.get("map_id"), character.get("instance_id")) != (1385, 0):
        return []
    if (
        occupation.get("state") != "completed"
        or occupation.get("account_id") != character["account_id"]
        or occupation.get("character_id") != character["id"]
        or occupation.get("map_id") != 1385
        or occupation.get("instance_id") != 0
        or occupation.get("table_uid") != 34659
        or occupation.get("definition_id") != 194
        or occupation.get("recipe_id") != 9445
    ):
        return []
    products = occupation.get("products")
    if not isinstance(products, list) or not any(
        row.get("reference") == 31159
        and type(row.get("quantity")) is int
        and row["quantity"] > 0
        for row in products
        if isinstance(row, dict)
    ):
        return []
    before = storage.load_locked(db, character["id"])
    if 5156 not in before["running"] or 10602 in before["objectives"]:
        return []
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=ANY(%s)",
        ([5156, 5160],),
    ).fetchall()
    definitions = {row["definition_id"]: row["data"]["native"] for row in rows}
    if set(definitions) != {5156, 5160}:
        raise ValueError("Missing Rii crafting mission definitions")
    native = definitions[5156]
    if native.get("d") != 5156 or {row["d"] for row in native.get("cjJ", ())} != {
        10602
    }:
        raise ValueError("Unexpected Rii crafting objective")
    now_ms = int(store.now().timestamp() * 1000)
    planned = mission_progress.advance_objective(
        before, native, 10602, character=character, store=store, now_ms=now_ms
    )
    if not planned[2]:
        return []
    if not storage.record_event(
        db,
        character["id"],
        f"rii-craft:{occupation['token']}",
        {
            "kind": "reconstructed_rii_craft",
            "recipe_id": 9445,
            "station_id": 34659,
            "item_id": 31159,
        },
    ):
        raise ValueError("Rii crafting receipt exists without mission progress")
    return mission_dependencies.settle(
        db,
        store,
        character,
        before,
        planned,
        definitions,
        ((5160, 10619, 5156),),
        now_ms=now_ms,
    )["packets"]
