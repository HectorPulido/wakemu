"""Explicit development-only grant and equip of one native finisher."""
import argparse
import json
import os
from pathlib import Path
from psycopg.types.json import Jsonb
from wakfu_server.store import Store
from wakfu_server.characters.cosmetics import OwnedCosmetics
from wakfu_server.characters.cosmetic_store import load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-id", type=int, required=True)
    parser.add_argument("--finisher", type=int, required=True)
    parser.add_argument("--grant-for-test", action="store_true")
    args = parser.parse_args()
    catalog = json.loads(
        (
            Path(__file__).resolve().parents[1] / "protocol/native-finisher-items.json"
        ).read_text()
    )
    entry = next(
        (row for row in catalog["items"] if row["reference"] == args.finisher), None
    )
    if entry is None:
        raise ValueError("Unknown native finisher reference")
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with store.connection() as db:
            character = db.execute(
                "SELECT id,account_id FROM characters WHERE id=%s AND deleted_at IS NULL",
                (args.character_id,),
            ).fetchone()
            if character is None:
                raise ValueError("Missing test character")
            db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                (character["account_id"],),
            )
            owner = db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
                (args.character_id, character["account_id"]),
            ).fetchone()
            if owner is None:
                raise ValueError("Test character ownership changed")
            owned = load(db, character["account_id"])
            if owned is None:
                raise ValueError("Apply the owned-account-cosmetics migration first")
            if (5, args.finisher) not in {(row[0], row[1]) for row in owned.items}:
                if not args.grant_for_test:
                    raise ValueError(
                        "Finisher is not owned; explicit --grant-for-test required"
                    )
                owned = OwnedCosmetics(
                    owned.account_id,
                    owned.items + ((5, args.finisher, 0, 0),),
                    owned.selections,
                    owned.inactive_characters,
                )
            owned = owned.equip_finishers(character, (args.finisher,))
            db.execute(
                "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s) ON CONFLICT(account_id) DO UPDATE SET record=EXCLUDED.record,revision=account_cosmetics.revision+1",
                (owned.account_id, Jsonb(owned.to_record())),
            )
        print(
            json.dumps(
                {
                    "character_id": args.character_id,
                    "finisher": args.finisher,
                    "death_script_id": entry["death_script_id"],
                    "test_grant_authorized": args.grant_for_test,
                }
            )
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
