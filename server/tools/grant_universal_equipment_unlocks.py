"""Apply the configured universal equipment entitlements to existing characters.

No item, level, XP or reward is granted. New characters and later selections use
this same idempotent application helper. The database must be selected explicitly.
"""
import argparse
import json
import os


def apply(store):
    from wakfu_server.universal_equipment_unlocks import grant, policy

    with store.connection() as db:
        selected = policy(db)
        identities = [
            row["id"]
            for row in db.execute(
                "SELECT id FROM characters WHERE deleted_at IS NULL ORDER BY id"
            )
        ]
    changed = 0
    # Each owner is committed separately so unrelated players are never held
    # behind one transaction locking the entire character population.
    for identity in identities:
        with store.connection() as db, db.transaction():
            changed += bool(grant(db, identity, int(store.now().timestamp() * 1000)))
    return dict(
        characters=len(identities),
        changed=changed,
        enabled=selected["enabled"],
        achievement=1509,
        company_rank=selected["minimum_company_rank"],
        rewards_granted=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from wakfu_server.store import Store
    from wakfu_server.universal_equipment_unlocks import policy

    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        if args.apply:
            result = apply(store)
        else:
            with store.connection() as db:
                result = dict(
                    policy=policy(db),
                    applied=False,
                    characters=db.execute(
                        "SELECT count(*) AS count FROM characters WHERE deleted_at IS NULL"
                    ).fetchone()["count"],
                )
        print(json.dumps(result, sort_keys=True))
    finally:
        store.close()


if __name__ == "__main__":
    main()
