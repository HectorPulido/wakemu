"""Activate a seeded world group and its personal ecology in one transaction.

Caller owns the group registry lock, SQL transaction and post-commit delivery.
No fight or spell execution occurs here.
"""
from psycopg.pq import TransactionStatus
from .planting_cells import surface
from .ecology_population import snapshot
from .ecology_policy import decision
from .personal_ecology import apply, packet
from .monsters import reference
from .ecology_feedback import describe


def activate(db, groups, resource_uid):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Monster birth requires an active transaction")
    if type(resource_uid) is not int or not 0 < resource_uid < 2**63:
        raise ValueError("Invalid monster birth resource")
    owner = db.execute(
        "SELECT character_id FROM planting_receipts WHERE resource_uid=%s AND success",
        (resource_uid,),
    ).fetchone()
    character_id = None if owner is None else owner["character_id"]
    actor = None
    if character_id is not None:
        actor = db.execute(
            "SELECT * FROM characters WHERE id=%s FOR UPDATE", (character_id,)
        ).fetchone()
        if actor is None:
            raise ValueError("Monster birth planter is missing")
    event = db.execute(
        "SELECT * FROM planting_growth_outbox WHERE resource_uid=%s FOR UPDATE",
        (resource_uid,),
    ).fetchone()
    if event is None or event["group_payload"] is None:
        raise ValueError("Monster birth event is missing")
    group = event["group_payload"]
    key = tuple(group["key"])
    resource = event["resource"]
    if key[:2] != (resource["map_id"], resource["instance_id"]):
        raise ValueError("Monster birth location disagrees")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("monster-population:" + ":".join(map(str, key[:2])),),
    )
    existing = db.execute(
        "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        key,
    ).fetchone()
    operation = f"monster-birth:{resource_uid}"
    if existing is not None:
        if not {m["id"] for m in group["members"]}.issubset(
            {m["id"] for m in existing["members"]}
        ):
            raise ValueError("Monster birth identity disagrees")
        receipt = (
            None
            if character_id is None
            else db.execute(
                "SELECT * FROM personal_ecology_receipts WHERE character_id=%s AND operation=%s",
                (character_id, operation),
            ).fetchone()
        )
        # Never award retroactively for groups activated by older code.
        return dict(
            character_id=character_id,
            reason="already_activated",
            duplicate=True,
            members=existing["members"],
            status=existing["status"],
            packets=[]
            if receipt is None
            else [packet(character_id, actor["ecology_value"])],
        )
    evaluation = None
    reason = (
        "unattributed_birth" if character_id is None else "native_region_unavailable"
    )
    if character_id is not None:
        population = snapshot(db, *key[:2], kinds=("monster",), locate=surface)
        try:
            regions = [
                surface(key[0], member["x"], member["y"], member["z"])["region_id"]
                for member in group["members"]
            ]
        except ValueError:
            regions = []
        families = [
            reference(member["ref"])["family_id"] for member in group["members"]
        ]
        if (
            population["complete"]
            and regions
            and all(r == regions[0] and r > 0 for r in regions)
            and len(set(families)) == 1
        ):
            before = (
                population["regions"]
                .get(regions[0], {})
                .get("monster", {})
                .get(families[0], 0)
            )
            evaluation = decision(
                db,
                map_id=key[0],
                region_id=regions[0],
                kind="monster",
                family_id=families[0],
                action="plant",
                before=before,
                amount=len(group["members"]),
            )
            evaluation["evidence"].update(resource_uid=resource_uid, group_id=key[2])
        elif not population["complete"]:
            reason = "incomplete_native_population"
    groups.register_transaction(db, *key, group["members"])
    applied = (
        None
        if evaluation is None
        else apply(db, character_id, operation=operation, **evaluation)
    )
    return dict(
        character_id=character_id,
        duplicate=False,
        members=group["members"],
        status="available",
        reason=reason if applied is None else "applied",
        packets=[] if applied is None else [applied["packet"]],
        information=None if applied is None else describe(applied["receipt"]),
    )
