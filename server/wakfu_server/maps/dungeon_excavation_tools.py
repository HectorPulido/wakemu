"""Source-bound entry shovel custody in the native paid-entry transaction."""
from wakfu_server import dungeon_excavation, native_catalog


def grant_entry(store, db, session, config, rule):
    if (
        store is None
        or rule.get("enabled") is not True
        or native_catalog.release() != rule["qualified_native_release"]
    ):
        raise ValueError("Excavation entry tool source is not enabled")
    binding = rule["entry_binding"]
    for field in ("entry_map_id", "entry_object_id", "entry_destination_id"):
        if session[field] != binding[field]:
            raise ValueError("Tool grant requires its original authorized entrance")
    from wakfu_server import generic_transports

    source = generic_transports.source(
        binding["entry_map_id"], binding["entry_object_id"]
    )
    targets = (
        []
        if source is None
        else [
            d
            for d in source["destinations"]
            if d["destination_id"] == binding["entry_destination_id"]
        ]
    )
    if (
        len(targets) != 1
        or targets[0]["item_reference"] != binding["entry_item_reference"]
        or targets[0]["cyW"] != binding["entry_item_quantity"]
        or session["start_map_id"] != rule["ground_authority"]["map_id"]
        or binding.get("native_scenario_event") != 17113
        or not binding.get("source_sha256")
    ):
        raise ValueError("Native shovel arrival scenario or entry payment changed")
    if not session["reused"] and not session.get("entry_item_payment"):
        raise ValueError("Fresh tool grant requires native paid-entry settlement")
    # The caller is the successful dungeon initializer in exactly the same DB
    # transaction as native payment, membership, transition outbox and location.
    from wakfu_server import inventory_items
    from wakfu_server.combat_drop_delivery import _container_can_hold
    from wakfu_server.haven_bag_furniture_knowledge import _rules

    native = _rules().get(rule["item_reference"], {})
    if (
        native.get("use_action_id") != rule["action_id"]
        or native.get("use_action_class") != "bIg"
    ):
        raise ValueError("Original arrival shovel item is not published")
    digest = dungeon_excavation.digest(rule)
    for identity in sorted(session["members"]):
        member = db.execute(
            "SELECT c.account_id,m.session_generation FROM dungeon_instance_members m JOIN characters c ON c.id=m.character_id WHERE m.instance_id=%s AND m.character_id=%s AND m.status='active' FOR UPDATE OF m",
            (session["instance_id"], identity),
        ).fetchone()
        if member is None:
            raise ValueError("Tool recipient is not an active frozen member")
        previous = db.execute(
            "SELECT * FROM dungeon_excavation_tools WHERE instance_id=%s AND character_id=%s FOR UPDATE",
            (session["instance_id"], identity),
        ).fetchone()
        if previous is not None and previous["active"]:
            if previous["rule_sha256"] != digest:
                raise ValueError("Entry tool receipt source changed")
            current = db.execute(
                "SELECT uid FROM inventory_items WHERE uid=%s AND character_id=%s AND reference=%s AND quantity>0 FOR UPDATE",
                (previous["tool_uid"], identity, rule["item_reference"]),
            ).fetchone()
            if current is not None:
                continue
        item = db.execute(
            "SELECT i.uid FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container AND c.character_id=i.character_id WHERE i.character_id=%s AND i.reference=%s AND i.quantity>0 AND i.instance_custody_id IS NULL AND c.kind IN (0,1,2,3) ORDER BY i.uid LIMIT 1 FOR UPDATE OF i",
            (identity, rule["item_reference"]),
        ).fetchone()
        granted = item is None
        if granted:
            bags = db.execute(
                "SELECT * FROM inventory_containers WHERE character_id=%s AND kind IN (0,1,2,3) ORDER BY kind,uid FOR UPDATE",
                (identity,),
            ).fetchall()
            destination = None
            for bag in bags:
                if not _container_can_hold(bag, identity):
                    continue
                occupied = {
                    r["slot"]
                    for r in db.execute(
                        "SELECT slot FROM inventory_items WHERE container=%s",
                        (bag["uid"],),
                    ).fetchall()
                }
                slot = next(
                    (s for s in range(bag["capacity"]) if s not in occupied), None
                )
                if slot is not None:
                    destination = (bag["uid"], slot)
                    break
            if destination is None:
                raise ValueError(
                    "Inventory needs one free slot for the native arrival shovel"
                )
            item = inventory_items.grant(
                store,
                member["account_id"],
                member["session_generation"],
                identity,
                reference=rule["item_reference"],
                quantity=1,
                container=destination[0],
                slot=destination[1],
                allowed_references={rule["item_reference"]},
                db=db,
            )
        db.execute(
            "INSERT INTO dungeon_excavation_tools(instance_id,character_id,tool_uid,tool_reference,granted_by_instance,rule_sha256,active) VALUES(%s,%s,%s,%s,%s,%s,true) ON CONFLICT(instance_id,character_id) DO UPDATE SET tool_uid=excluded.tool_uid,tool_reference=excluded.tool_reference,granted_by_instance=excluded.granted_by_instance,rule_sha256=excluded.rule_sha256,active=true",
            (
                session["instance_id"],
                identity,
                item["uid"],
                rule["item_reference"],
                granted,
                digest,
            ),
        )
        if granted:
            db.execute(
                "UPDATE inventory_items SET instance_custody_id=%s WHERE uid=%s AND character_id=%s",
                (session["instance_id"], item["uid"], identity),
            )
