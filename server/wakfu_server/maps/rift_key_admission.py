"""Recovered native activator costs; encounter balancing remains local policy.

Table 31 descriptors 1457, 1458 and 1477 charge the acting non-hero once.
Neither other mains nor owned heroes pay an additional inferred entrance fee.
"""


def contract(catalog):
    if catalog.get("type") == "INFINITE_WAVE":
        return None
    if catalog.get("type") != "ULTIMATE_INFINITE_WAVE":
        raise ValueError("Unsupported native rift kind")
    price = catalog.get("native_start_contract")
    if (
        not isinstance(price, dict)
        or price.get("source") != "native_table_31"
        or price.get("criterion") != "not IsHero()"
        or price.get("consume") is not True
        or any(
            type(price.get(field)) is not int or price[field] <= 0
            for field in (
                "object_id",
                "descriptor_id",
                "reference",
                "quantity",
                "script_reference",
            )
        )
        or price["quantity"] != 1
        or type(price.get("action")) is not int
        or price["action"] != 1
    ):
        raise ValueError("Ultimate rift key authority is unavailable for this catalog")
    sources = [
        row
        for row in catalog.get("objects", ())
        if row.get("id") == price["object_id"]
        and row.get("map_id") == catalog["map_id"]
        and row.get("type") == "GenericActivableInteractiveElement"
    ]
    if len(sources) != 1:
        raise ValueError(
            "Native ultimate rift activator does not match its key contract"
        )
    return dict(price)


def lock_owner(db, run, character_id, fight_id):
    """Acquire the selected main before the run lock, like interactive admission."""
    # Session before character, matching Store.lock_character. The combat
    # participant must still name this selected main's actual lease generation.
    from wakfu_server.rift_encounter_roles import roles_for_catalog

    player_team = roles_for_catalog(run["catalog"], run["policy"]).player_team
    owner = db.execute(
        "SELECT s.account_id FROM sessions s JOIN characters c ON c.account_id=s.account_id "
        "JOIN combat_fight_participants p ON p.character_id=c.id "
        "AND p.account_id=c.account_id AND p.session_generation=s.generation "
        "WHERE c.id=%s AND s.character_id=c.id AND s.expires_at>CURRENT_TIMESTAMP "
        "AND c.deleted_at IS NULL AND p.fight_id=%s AND p.team=%s FOR UPDATE OF s",
        (character_id, fight_id, player_team),
    ).fetchone()
    if owner is None:
        raise ValueError("Ultimate rift start requires its current selected main")
    actor = db.execute(
        "SELECT map_id,instance_id FROM characters WHERE id=%s AND account_id=%s "
        "AND deleted_at IS NULL FOR UPDATE",
        (character_id, owner["account_id"]),
    ).fetchone()
    if actor is None or (actor["map_id"], actor["instance_id"]) != (
        run["catalog"]["map_id"],
        run["instance_id"],
    ):
        raise ValueError("Ultimate rift owner left the admitted instance")


def consume(db, run, character_id, fight_id):
    """Pay alongside entered -> running; caller already holds owner/run locks.

    A failed subsequent wave bind rolls payment back with the same transaction.
    Running same-fight retries return their existing receipt before this helper.
    """
    price = contract(run["catalog"])
    if price is None:
        return ()
    if run["policy"].get("ultimate_enabled", False) is not True:
        raise ValueError("Ultimate rift key authority is disabled by policy")
    from wakfu_server.maps.dungeon_entry_payment import consume as consume_items

    return consume_items(db, (character_id,), price["reference"], price["quantity"])


def publication(db, store, account_id, character_id):
    """Rebuild absolute bag custody after payment; safe to resend.

    Send only after the enclosing start/bind transaction commits. A reconnect
    uses the same current custody through the normal character bootstrap.
    """
    from wakfu_server.inventory_move import synchronization
    from wakfu_server.inventory_items import equipment_inventory

    character = store.character(account_id, character_id, db)
    return (
        synchronization(character),
        equipment_inventory(character),
    )
