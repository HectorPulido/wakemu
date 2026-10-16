"""Ready-scene exploration facts from owned durable character positions."""
import uuid
from . import external


def observe(store, account_id, generation, character_id):
    """Reserve a true map/instance entry once, independent of transition producer.

    A reconnect in the same persisted scene retains its visit identity. Changes
    of map or instance create a new durable visit. Caller invokes only after the
    selected character's scene is ready, never with client-selected coordinates.
    """
    if not external.enabled():
        return False
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id, selected=True)
        character = db.execute(
            "SELECT map_id,instance_id,x,y FROM characters WHERE id=%s AND account_id=%s "
            "AND deleted_at IS NULL",
            (character_id, account_id),
        ).fetchone()
        if character is None:
            raise ValueError("Exploration character is not owned by account")
        prior = db.execute(
            "SELECT * FROM objectives_world_visits WHERE character_id=%s FOR UPDATE",
            (character_id,),
        ).fetchone()
        scene = (character["map_id"], character["instance_id"])
        from wakfu_server.territory_cells import region_at

        try:
            region_id = region_at(scene[0], character["x"], character["y"])
        except (ValueError, KeyError):
            region_id = None
        map_changed = prior is None or scene != (prior["map_id"], prior["instance_id"])
        region_changed = map_changed or region_id != prior["region_id"]
        if not map_changed and not region_changed:
            return False
        visit_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO objectives_world_visits(character_id,map_id,instance_id,region_id,visit_id) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
            "map_id=EXCLUDED.map_id,instance_id=EXCLUDED.instance_id,region_id=EXCLUDED.region_id,"
            "visit_id=EXCLUDED.visit_id,updated_at=CURRENT_TIMESTAMP",
            (character_id, *scene, region_id, visit_id),
        )
        if map_changed:
            external.enqueue_fact(
                db,
                account_id,
                character_id,
                "visit:" + visit_id,
                {
                    "kind": "map_entered",
                    "map_id": scene[0],
                    "instance_id": scene[1],
                    "visit_id": visit_id,
                },
            )
        if region_changed and region_id is not None:
            external.enqueue_fact(
                db,
                account_id,
                character_id,
                "region:" + visit_id,
                {
                    "kind": "region_entered",
                    "map_id": scene[0],
                    "instance_id": scene[1],
                    "region_id": region_id,
                    "visit_id": visit_id,
                },
            )
    return True
