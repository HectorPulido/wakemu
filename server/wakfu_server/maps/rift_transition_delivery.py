"""Single-world-worker wakeups for already committed rift map transitions.

Characters retain the durable destination. Login recovers it after a process
restart; this queue only prompts existing sockets to hydrate that destination.
"""
import threading
from contextlib import ExitStack

_LOCK = threading.RLock()
_PENDING = {}


def pending(account_id, generation, character_id):
    with _LOCK:
        return _PENDING.get((account_id, generation, character_id))


def acknowledge(account_id, generation, character_id, destination):
    with _LOCK:
        key = (account_id, generation, character_id)
        if _PENDING.get(key) == destination:
            del _PENDING[key]


def queue(members, destination):
    with _LOCK:
        for member in members:
            if member.get("hero_main_id") is not None or (
                member.get("selected_character_id") is not None
                and member["selected_character_id"] != member["id"]
            ):
                continue
            _PENDING[(member["account_id"], member["generation"], member["id"])] = dict(
                destination
            )


def enter(
    store, positions, account_id, generation, character_id, map_id, body, **options
):
    """Flush/fence each party position before the durable movement transaction."""
    from wakfu_server import rift_entry_adapter

    with store.connection() as db:
        members = db.execute(
            "SELECT c.id,c.account_id FROM characters c WHERE c.id=%s OR c.id IN("
            "SELECT m.character_id FROM player_party_members m WHERE m.party_id=("
            "SELECT party_id FROM player_party_members WHERE character_id=%s)) ORDER BY c.id",
            (character_id, character_id),
        ).fetchall()
    accounts = sorted({r["account_id"] for r in members})
    with ExitStack() as barriers:
        for account in accounts:
            barriers.enter_context(positions.account_barrier(account))
        for account in accounts:
            positions.flush(account_id=account)
        result = rift_entry_adapter.enter(
            store,
            account_id,
            generation,
            character_id,
            map_id,
            body,
            allowed_accounts=set(accounts),
            **options
        )
        if result is None:
            return None
        for row in result["members"]:
            positions.release(row["account_id"], row["generation"], row["id"])
        queue(result["members"], result["destination"])
        return result
