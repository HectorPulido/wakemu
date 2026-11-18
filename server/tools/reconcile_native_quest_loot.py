"""Review or recover never-rolled quest loot from a genuine local victory.

Default mode executes the normal native planner/allocation/delivery transaction
and rolls it back. An exact reviewed original empty award digest is mandatory.
No combat, progression, HP or ordinary random outcome is changed.
"""

import argparse
import json
import os

from tools.install_mission_bundle import local_connection
from wakfu_server.store import Store
from wakfu_server.native_quest_loot_reconciliation import reconcile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fight", type=int, required=True)
    parser.add_argument("--character", type=int, required=True)
    parser.add_argument("--reviewed-snapshot-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = os.environ["WAKFU_DATABASE_URL"]
    local_connection(url)
    store = Store(url)
    try:
        with store.connection() as db:
            with db.transaction(force_rollback=not args.apply):
                result = reconcile(
                    store,
                    db,
                    args.fight,
                    args.character,
                    reviewed_snapshot_sha256=args.reviewed_snapshot_sha256,
                )
                print(
                    json.dumps(dict(result, applied=args.apply), sort_keys=True),
                    flush=True,
                )
    finally:
        store.close()


if __name__ == "__main__":
    main()
