"""Read current generation-bound Redis movement without changing its ownership."""
import json
import os

from wakfu_server.storage.position_redis import _identity, _position
from wakfu_server.admin_map_catalog import load as load_map_names


def present(store, rows):
    rows = [dict(row) for row in rows]
    if not rows:
        return rows
    ids = [row.get("id", row.get("character_id")) for row in rows]
    with store.connection() as db:
        active = {
            row["id"]: row
            for row in db.execute(
                "SELECT c.id,c.account_id,c.map_id,c.instance_id,c.x,c.y,c.z,c.direction,s.generation "
                "FROM characters c JOIN sessions s ON s.character_id=c.id "
                "WHERE c.id=ANY(%s) AND s.expires_at>now()",
                (ids,),
            )
        }
        labels = {
            row["map_id"]: row["name"]
            for row in db.execute(
                "SELECT map_id,name FROM admin_map_metadata WHERE name<>''"
            )
        }
        native_names = load_map_names(db)
    records = {}
    address = os.environ.get("WAKFU_REDIS_URL")
    if address and active:
        import redis

        client = redis.Redis.from_url(
            address, socket_connect_timeout=0.3, socket_timeout=0.3
        )
        try:
            with client.pipeline(transaction=False) as pipeline:
                for character in active.values():
                    key = (
                        character["account_id"],
                        character["generation"],
                        character["id"],
                    )
                    pipeline.hget("wakfu:positions:v2", _identity(key))
                values = pipeline.execute()
            records = dict(zip(active, values))
        except redis.RedisError:
            pass
        finally:
            client.close()
    for row in rows:
        character_id = row.get("id", row.get("character_id"))
        row["position_source"] = "PostgreSQL"
        character = active.get(character_id)
        if character and records.get(character_id):
            try:
                record = json.loads(records[character_id])
                owner = [character["account_id"], character["generation"], character_id]
                baseline = _position(record["baseline"])
                current = _position(record["current"])
                if (
                    record["version"] == 2
                    and record["owner"] == owner
                    and all(baseline[k] == character[k] for k in baseline)
                    and all(
                        current[k] == baseline[k] for k in ("map_id", "instance_id")
                    )
                ):
                    row.update(current)
                    row["position_source"] = "Redis movement journal"
            except (ValueError, KeyError, TypeError):
                pass
        row["map_name"] = (
            labels.get(row["map_id"])
            or native_names.get(str(row["map_id"]))
            or f"Map #{row['map_id']}"
        )
    return rows
