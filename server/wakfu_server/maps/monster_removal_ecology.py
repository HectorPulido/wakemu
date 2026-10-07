"""Settle a confirmed world-group outcome and ecology in one transaction.

The caller determines victory from the resolved fight. This module neither
executes combat actions nor decides winners, damage, spells or turn order.
"""
from collections import Counter
from psycopg.pq import TransactionStatus

from .ecology_population import snapshot
from .ecology_policy import decision
from .ecology_feedback import describe, information
from .personal_ecology import apply
from .planting_cells import surface
from .monsters import reference


def finish(store, groups, lease, *, character_id, defeated, locate=surface, db=None):
    if type(character_id) is not int or not 0 < character_id < 2**63:
        raise ValueError("Invalid ecological outcome owner")
    if type(defeated) is not bool:
        raise ValueError("Group outcome must be explicit")
    key, generation, fight_id, revision = lease
    if db is None:
        with groups.lock, store.connection() as connection, connection.transaction():
            return finish(
                store,
                groups,
                lease,
                character_id=character_id,
                defeated=defeated,
                locate=locate,
                db=connection,
            )
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Ecological settlement requires an active transaction")
    actor = db.execute(
        "SELECT id FROM characters WHERE id=%s FOR UPDATE", (character_id,)
    ).fetchone()
    if actor is None:
        raise ValueError("Ecological outcome owner is missing")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("monster-population:" + ":".join(map(str, key[:2])),),
    )
    row = db.execute(
        "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s "
        "AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if (
        row is None
        or row["status"] != "fighting"
        or (row["generation"], row["fight_id"], row["revision"])
        != (generation, fight_id, revision)
    ):
        return {"applied": False, "packets": [], "receipts": []}
    evaluations = []
    unresolved = False
    if defeated:
        population = snapshot(db, *key[:2], kinds=("monster",), locate=locate)
        removals = Counter()
        if population["complete"]:
            for member in row["members"]:
                region = locate(key[0], *(member[k] for k in ("x", "y", "z")))[
                    "region_id"
                ]
                removals[region, reference(member["ref"])["family_id"]] += 1
            for (region, family), amount in sorted(removals.items()):
                before = population["regions"][region]["monster"][family]
                evaluation = decision(
                    db,
                    map_id=key[0],
                    region_id=region,
                    kind="monster",
                    family_id=family,
                    action="remove",
                    before=before,
                    amount=amount,
                )
                evaluation["evidence"].update(
                    group_id=key[2], fight_id=fight_id, group_revision=revision
                )
                evaluations.append((region, family, evaluation))
        else:
            unresolved = True
    # The same lease guard protects both the tombstone and its receipts.
    if not groups.finish(lease, defeated=defeated, db=db):
        raise ValueError("Group outcome changed during ecological settlement")
    packets, receipts = [], []
    for region, family, evaluation in evaluations:
        result = apply(
            db,
            character_id,
            operation=f"monster-removal:{key[0]}:{key[1]}:{key[2]}:{revision}:{region}:{family}",
            **evaluation,
        )
        receipts.append(result["receipt"])
        if not result["duplicate"]:
            packets.extend((result["packet"], information(describe(result["receipt"]))))
    if unresolved:
        packets.append(
            information(
                "Ecosistema: grupo retirado. No se pudo determinar su población regional; "
                "no se aplica un cambio de afinidad Wakfu/Stasis sin esos datos."
            )
        )
    return {"applied": True, "packets": packets, "receipts": receipts}
