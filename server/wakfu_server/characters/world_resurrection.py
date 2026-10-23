"""Native world-death occupation and atomic BenKO company resurrection.

Recovered HP reuses Wakemu's explicit one-HP exploration policy. The original
client proves occupation/permission/interaction codecs, not a healing percent.
Combat defeat, result acknowledgment and their existing recovery remain intact.
"""
import struct


def occupation_packet(character_id, *, dead):
    """cyN12088: action u8, occupation i16, actor i64, byte-array length u32."""
    if type(character_id) is not int or character_id <= 0 or type(dead) is not bool:
        raise ValueError("Invalid world-death occupation")
    data = b"\x01" if dead else b""
    return (
        12088,
        struct.pack(">BhqI", 1 if dead else 2, 4, character_id, len(data)) + data,
    )


def _outside(db, character_id):
    # A finished result still owns its casualty until the normal return ACK.
    return (
        db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=%s AND (f.status IN ('placement','active') OR "
            "(f.status='finished' AND NOT EXISTS(SELECT 1 FROM fight_health_exits e "
            "WHERE e.fight_id=f.id AND e.character_id=p.character_id "
            "AND (e.reason<>'return' OR e.return_acknowledged_at IS NOT NULL)))) LIMIT 1",
            (character_id,),
        ).fetchone()
        is None
    )


def snapshot(store, character):
    """Replay a canonical dead exploration actor; never convert a combat KO."""
    if character.get("health_dead") is not True or character.get("hp") != 0:
        return []
    with store.connection() as db:
        row = db.execute(
            "SELECT hp,health_dead FROM characters WHERE id=%s AND account_id=%s "
            "AND deleted_at IS NULL",
            (character["id"], character["account_id"]),
        ).fetchone()
        if (
            row is None
            or row["hp"] != 0
            or row["health_dead"] is not True
            or not _outside(db, character["id"])
        ):
            return []
    return [occupation_packet(character["id"], dead=True)]


def resurrect(
    store,
    account_id,
    generation,
    selected_character_id,
    body,
    *,
    target_generation,
    live_locations
):
    """12239 request; caller holds per-account position barriers for live_locations.

    The caller snapshots World briefly under its lock, then releases that
    global lock before database work. Trusted live private-instance positions are not packet
    coordinates or buffered exterior SQL coordinates. Lease ownership is
    checked again inside this transaction before any mutation.
    """
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.characters.heroes import session_authorized
    from wakfu_server.simple_item_actions import _idle, _equipped
    from wakfu_server import health, health_policy

    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Invalid native BenKO target packet")
    target_id = struct.unpack(">q", body)[0]
    if (
        target_id <= 0
        or not isinstance(target_generation, str)
        or not target_generation
    ):
        raise ValueError("Invalid native BenKO target identity")
    locations = {}
    if not isinstance(live_locations, dict):
        raise ValueError("Missing live resurrection position fence")
    for identity, expected_generation in (
        (selected_character_id, generation),
        (target_id, target_generation),
    ):
        row = live_locations.get(identity)
        if (
            not isinstance(row, dict)
            or row.get("generation") != expected_generation
            or any(
                type(row.get(key)) is not int
                for key in ("map_id", "instance_id", "x", "y", "z")
            )
        ):
            raise ValueError("Changed live resurrection position fence")
        locations[identity] = dict(row)
    origin, destination = locations[selected_character_id], locations[target_id]
    # Original aBn.A uses only Manhattan x/y distance; z is not compared.
    if (origin["map_id"], origin["instance_id"]) != (
        destination["map_id"],
        destination["instance_id"],
    ) or abs(origin["x"] - destination["x"]) + abs(origin["y"] - destination["y"]) > 1:
        raise ValueError("Move next to the resurrection target")
    with store.connection() as db:
        target = db.execute(
            "SELECT account_id FROM characters WHERE id=%s AND deleted_at IS NULL",
            (target_id,),
        ).fetchone()
        if target is None:
            raise ValueError("Resurrection target is unavailable")
        target_account = target["account_id"]
        db.execute(
            "SELECT id FROM accounts WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (sorted({account_id, target_account}),),
        ).fetchall()
        lock_inventory_character(
            store, db, account_id, generation, selected_character_id
        )
        lease = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
            "AND expires_at>%s FOR UPDATE",
            (target_account, target_generation, store.now()),
        ).fetchone()
        if lease is None or not session_authorized(
            db,
            {
                "account_id": target_account,
                "id": target_id,
                "selected_character_id": lease["character_id"],
            },
        ):
            raise ValueError("Resurrection target left its loaded company")
        db.execute("SELECT id FROM characters WHERE id=%s FOR UPDATE", (target_id,))
        source = store.character(account_id, selected_character_id, db)
        before = store.character(target_account, target_id, db)
        for identity in {selected_character_id, target_id}:
            _idle(db, identity, store.now())
            if not _outside(db, identity):
                raise ValueError("Return from combat before using BenKO")
        if before["health_dead"] is not True or before["hp"] != 0:
            raise ValueError("Resurrection target is already alive")
        if source["health_dead"] and target_id != selected_character_id:
            raise ValueError("A dead character may only resurrect itself")
        company = [selected_character_id] + [
            row["character_id"]
            for row in db.execute(
                "SELECT h.character_id FROM account_hero_slots h "
                "JOIN account_hero_rosters r USING(account_id) "
                "WHERE h.account_id=%s AND r.leader_id=%s ORDER BY h.slot",
                (account_id, selected_character_id),
            ).fetchall()
        ]
        if len(company) > 3 or len(company) != len(set(company)):
            raise ValueError("Invalid resurrection donor company")
        db.execute(
            "SELECT id FROM characters WHERE id=ANY(%s) AND account_id=%s "
            "AND deleted_at IS NULL ORDER BY id FOR UPDATE",
            (company, account_id),
        ).fetchall()
        candidates = db.execute(
            "SELECT i.* FROM inventory_items i JOIN characters c ON c.id=i.character_id "
            "JOIN inventory_containers b ON b.uid=i.container AND b.character_id=i.character_id "
            "WHERE i.character_id=ANY(%s) AND c.account_id=%s AND c.deleted_at IS NULL "
            "AND c.level>=1 AND i.reference=9247 AND i.quantity>=1 "
            "AND b.kind BETWEEN 0 AND 3 AND i.slot>=0 AND i.slot<b.capacity "
            "ORDER BY CASE WHEN i.character_id=%s THEN 0 ELSE 1 END,i.uid FOR UPDATE OF i",
            (company, account_id, selected_character_id),
        ).fetchall()
        donors = {}
        item = None
        for candidate in candidates:
            owner = candidate["character_id"]
            if owner not in donors:
                donors[owner] = store.character(account_id, owner, db)
            if not _equipped(donors[owner], candidate["uid"]):
                item = candidate
                break
        if item is None:
            raise ValueError("Your active company has no BenKO")
        lock_inventory_character(
            store, db, account_id, generation, item["character_id"]
        )
        _idle(db, item["character_id"], store.now())
        if not _outside(db, item["character_id"]):
            raise ValueError("Return the BenKO donor from combat first")
        damage, dead = health_policy.recover_finished_return(
            before["max_hp"], before["hp_damage"], before["health_dead"]
        )
        hp = health_policy.apply_damage(db, before, damage, dead)
        coefficient = health.exploration_coefficient(before["max_hp"], hp)
        now = store.now()
        db.execute(
            "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
            "coefficient=excluded.coefficient,last_at=excluded.last_at",
            (target_id, hp, now, coefficient, now),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (item["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (item["uid"],),
            )
        return dict(
            target_account_id=target_account,
            target_generation=target_generation,
            previous_target=dict(
                before,
                **{
                    key: destination[key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                }
            ),
            target=dict(
                store.character(target_account, target_id, db),
                **{
                    key: destination[key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                }
            ),
            donor=store.character(account_id, item["character_id"], db),
            donor_packets=[(12470, struct.pack(">qh", item["uid"], -1))],
            target_packets=[(12436, health.packet(target_id, hp, coefficient))],
            world_packets=[occupation_packet(target_id, dead=False)],
        )
