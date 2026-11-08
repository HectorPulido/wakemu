"""Opt-in bounded weak ownership evidence; never traverse or collect the heap."""
from collections import deque
import os
from threading import Lock
import time
from weakref import ref

ENABLED = os.environ.get("WAKFU_CLOSED_FIGHT_OBSERVATION") == "1"
_LIMIT = 16
_ROWS = deque(maxlen=_LIMIT)
_LOCK = Lock()


def record_removed(registry, shared):
    if not ENABLED:
        return
    try:
        # No callbacks or closure cells: these references cannot own the graph.
        row = (
            shared.fight.id,
            time.time(),
            ref(shared.fight),
            ref(shared.runtime),
            len(registry.fights),
            len(registry.by_actor),
            len(registry.by_character),
        )
        with _LOCK:
            _ROWS.append(row)
    except Exception:
        # Optional diagnostics must never turn successful removal into failure.
        return


def snapshot():
    if not ENABLED:
        return None
    with _LOCK:
        rows = tuple(_ROWS)
    return {
        "capacity": _LIMIT,
        "sampled_at": time.time(),
        "removed": [
            {
                "fight_id": row[0],
                "removed_at": row[1],
                "fight_alive": row[2]() is not None,
                "runtime_alive": row[3]() is not None,
                "registry_counts_at_removal": {
                    "fights": row[4],
                    "actors": row[5],
                    "characters": row[6],
                },
            }
            for row in rows
        ],
    }
