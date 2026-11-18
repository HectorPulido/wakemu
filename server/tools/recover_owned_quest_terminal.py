"""Review or settle one genuinely won local quest fight lost at process restart.

Requires the exact reviewed snapshot digest. Default mode rolls every mutation
back. Does not create a fight, alter actors/HP or directly assign objectives.
"""

import argparse
import json
import os
from psycopg.conninfo import conninfo_to_dict
from wakfu_server.store import Store
from wakfu_server.achievements.owned_quest_terminal_recovery import recover


class RollbackReview(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fight", type=int, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = os.environ["WAKFU_DATABASE_URL"]
    if conninfo_to_dict(url).get("host") not in ("127.0.0.1", "localhost"):
        raise ValueError("This reviewed recovery tool is local-only")
    store = Store(url)
    try:
        with store.connection() as db:
            try:
                with db.transaction():
                    receipt = recover(
                        store,
                        db,
                        args.fight,
                        reviewed_aborted_sha256=args.checkpoint_sha256,
                    )
                    print(
                        json.dumps(dict(receipt, applied=args.apply), sort_keys=True),
                        flush=True,
                    )
                    if not args.apply:
                        raise RollbackReview()
            except RollbackReview:
                pass
    finally:
        store.close()


if __name__ == "__main__":
    main()
