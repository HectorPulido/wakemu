"""Original bHE account companion activation and durable company membership.

Collection records use the native eSy/eSA layout. Combat projections remain
separate from human characters and use their original NPC breed stat curves.
"""
from bisect import bisect_right
from functools import lru_cache
import json
from pathlib import Path
import struct

SERIALIZATION_VERSION = 10093002
NATIVE_ADDITIONAL_MEMBER_CAP = 2


@lru_cache(maxsize=1)
def descriptors():
    rows = json.loads(
        Path(__file__).with_name("native_companion_items.json").read_text()
    )["items"]
    if len(rows) != 16 or len({r["action_id"] for r in rows}) != 16:
        raise ValueError("Invalid native companion action catalog")
    return {r["action_id"]: r for r in rows}


def action_class(body):
    """Recognize bHE without imposing its grammar on other 13220 families."""
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native item action header")
    action, uid = struct.unpack_from(">iq", body)
    if action not in descriptors():
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid companion activation request")
    return "bHE"


def level_for_xp(xp):
    """eSy.cmZ uses the original MP curve shared with player levels."""
    from wakfu_server.character_levels import XP_BY_LEVEL

    if type(xp) is not int or not 0 <= xp < 2**63:
        raise ValueError("Invalid companion experience")
    return bisect_right(tuple(XP_BY_LEVEL.values()), xp)


def record(row):
    """Encode a native eSA.w record with its original pT equipment custody."""
    name = row["name"].encode("utf-8")
    if not name or len(name) > 65535:
        raise ValueError("Invalid companion name")
    if (
        row["serialization_version"] != SERIALIZATION_VERSION
        or not 0 <= row["hp"] <= row["max_hp"]
        or row["max_hp"] <= 0
    ):
        raise ValueError("Invalid native companion health or version")
    from wakfu_server.companion_equipment import equipment_blob

    # eSy.Xi is the owning account, copied to eGj.pK by cZR. The active
    # character controller is a distinct sL/party membership identity.
    return (
        struct.pack(
            ">qhqqI",
            row["id"],
            row["breed_ref"],
            row["account_id"],
            row["xp"],
            len(name),
        )
        + name
        + struct.pack(
            ">Biii",
            int(row["unlocked"]),
            row["max_hp"],
            row["hp"],
            row["serialization_version"],
        )
        + equipment_blob(row.get("equipment_entries", ()))
    )


def collection(db, account_id):
    from wakfu_server.companion_equipment import hydrate_equipment

    rows = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM account_companions WHERE account_id=%s AND linked ORDER BY id",
            (account_id,),
        ).fetchall()
    ]
    return tuple(hydrate_equipment(db, rows))


def collection_packet(rows):
    """cEq22790/aZk signed-byte count, followed by eSA.fw records."""
    rows = tuple(rows)
    if len(rows) > 127:
        raise ValueError("Native companion collection exceeds signed-byte capacity")
    return 22790, bytes((len(rows),)) + b"".join(record(row) for row in rows)


def refresh_packet(rows, *, replace=True):
    """cua12576/aZl uses current-version eSA.fv and a replace boolean."""
    _, body = collection_packet(rows)
    return 12576, body + bytes((bool(replace),))


def _result(store, db, account_id, character_id, companion, *, applied):
    return dict(
        character=store.character(account_id, character_id, db),
        companion=dict(companion),
        native_class="bHE",
        applied=applied,
        consumed=int(applied),
        packets=[(13954, record(companion))]
        if applied
        else [refresh_packet(collection(db, account_id))],
    )


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Atomically consume one original activation item and learn its companion."""
    from wakfu_server.inventory_owner import lock_inventory_character, lock_item_owner
    from wakfu_server.simple_item_actions import _idle, _equipped
    from wakfu_server.haven_bag_furniture_knowledge import _rules
    from wakfu_server.combat_companions import native_stats
    from wakfu_server.monsters import reference

    if action_class(body) != "bHE" or type(in_fight) is not bool or in_fight:
        raise ValueError("Companion activation is unavailable during combat")
    action, uid = struct.unpack(">iq", body)
    descriptor = descriptors()[action]
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM companion_activation_receipts WHERE account_id=%s "
            "AND source_uid=%s AND action_id=%s",
            (account_id, uid, action),
        ).fetchone()
        if prior is not None:
            owner = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            _idle(db, owner, store.now())
            learned = db.execute(
                "SELECT * FROM account_companions WHERE id=%s AND account_id=%s",
                (prior["companion_id"], account_id),
            ).fetchone()
            return _result(store, db, account_id, owner, learned, applied=False)
        owner = lock_item_owner(store, db, account_id, generation, character_id, (uid,))
        _idle(db, owner, store.now())
        source = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, owner),
        ).fetchone()
        rule = _rules().get(source["reference"], {})
        if (
            source["reference"] != descriptor["item_ref"]
            or source["quantity"] < 1
            or rule.get("use_action_class") != "bHE"
            or rule.get("use_action_id") != action
            or rule.get("use_has_criteria") is not False
            or descriptor["criteria"]
        ):
            raise ValueError(
                "The item does not match its original companion activation"
            )
        character = store.character(account_id, owner, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the activation item first")
        if db.execute(
            "SELECT 1 FROM account_companions WHERE account_id=%s AND breed_ref=%s AND linked",
            (account_id, descriptor["breed_ref"]),
        ).fetchone():
            raise ValueError("This account already owns that companion")
        info = db.execute(
            "SELECT xp FROM inventory_item_companions WHERE uid=%s", (uid,)
        ).fetchone()
        xp = info["xp"] if info is not None else 0
        if info is not None and source["quantity"] != 1:
            raise ValueError("Unlinked companion XP requires one physical item")
        level = min(
            level_for_xp(xp),
            loaded_level_cap(db, store, account_id, owner, owner_character=character),
        )
        stats = native_stats(descriptor["breed_ref"], level)
        learned = db.execute(
            "INSERT INTO account_companions(account_id,breed_ref,owner_character_id,name,hp,max_hp,xp) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(account_id,breed_ref) DO UPDATE SET "
            "owner_character_id=EXCLUDED.owner_character_id,name=EXCLUDED.name,hp=EXCLUDED.hp,"
            "max_hp=EXCLUDED.max_hp,xp=EXCLUDED.xp,linked=true,unlocked=true,"
            "link_revision=account_companions.link_revision+1 RETURNING *",
            (
                account_id,
                descriptor["breed_ref"],
                owner,
                reference(descriptor["breed_ref"])["name"],
                stats["max_hp"],
                stats["max_hp"],
                xp,
            ),
        ).fetchone()
        if source["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s", (uid,)
            )
        db.execute(
            "INSERT INTO companion_activation_receipts(account_id,source_uid,action_id,character_id,companion_id) "
            "VALUES(%s,%s,%s,%s,%s)",
            (account_id, uid, action, owner, learned["id"]),
        )
        result = _result(store, db, account_id, owner, learned, applied=True)
        result["packets"].insert(0, (12470, struct.pack(">qh", uid, -1)))
        return result


def roster(db, account_id, owner_character_id):
    """Selected companion rows, never human-character or hero rows."""
    from wakfu_server.companion_equipment import hydrate_equipment

    rows = [
        dict(row)
        for row in db.execute(
            "SELECT c.*,s.slot,s.owner_character_id FROM account_companion_slots s "
            "JOIN account_companions c ON c.id=s.companion_id AND c.account_id=s.account_id "
            "WHERE s.account_id=%s AND s.owner_character_id=%s AND c.linked ORDER BY s.slot",
            (account_id, owner_character_id),
        ).fetchall()
    ]
    return tuple(hydrate_equipment(db, rows))


def loaded_level_cap(
    db, store, account_id, owner_character_id, *, owner_character=None
):
    """Native fkK.td: maximum effective level in the loaded human company.

    Learned but inactive characters and other accounts never raise this cap.
    The controller may itself be an active hero during inventory actions.
    """
    from wakfu_server import heroes
    from wakfu_server.builds import effective_sheet_level

    anchor = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s", (account_id,)
    ).fetchone()
    main_id = anchor["leader_id"] if anchor is not None else owner_character_id
    company = heroes.load_roster(db, store, account_id, main_id)
    humans = (company["leader"],) + tuple(company["heroes"])
    if owner_character_id not in {human["id"] for human in humans}:
        raise ValueError("Companion controller is not a loaded account character")
    if any(human["account_id"] != account_id for human in humans):
        raise ValueError("Loaded companion company crosses account ownership")
    return max(
        effective_sheet_level(human, human.get("active_build_index", 0))
        for human in humans
    )


def combat_sources(
    db, account_id, owner_character_id, *, owner_character=None, store=None
):
    """Return real native companion projections owned by this company anchor."""
    from wakfu_server.combat_companions import companion_projection

    rows = roster(db, account_id, owner_character_id)
    if not rows:
        return ()
    if store is None:
        raise ValueError("Companion projection requires the account company store")
    owner = owner_character or store.character(account_id, owner_character_id, db)
    if owner is None:
        raise ValueError("Companion controller is unavailable")
    level = loaded_level_cap(
        db, store, account_id, owner_character_id, owner_character=owner
    )
    return tuple(
        companion_projection(
            dict(row, level=min(level_for_xp(row["xp"]), level)), dict(owner)
        )
        for row in rows
    )


def controlled_count(db, owner_ids):
    """Additional sidekick seats for native six-member company capacity checks."""
    if not owner_ids:
        return 0
    return db.execute(
        "SELECT count(*) AS n FROM account_companion_slots WHERE owner_character_id=ANY(%s)",
        (list(owner_ids),),
    ).fetchone()["n"]


def _fence(store, db, account_id, generation, character_id):
    from wakfu_server import heroes

    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    store.lock_character(db, account_id, generation, character_id)
    db.execute(
        "SELECT account_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
        (account_id,),
    )
    owned = heroes.load_roster(db, store, account_id, character_id)
    heroes._idle(db, [character_id] + [hero["id"] for hero in owned["heroes"]])
    return owned


def add_to_party(store, account_id, generation, character_id, body):
    """cnX12555 carries the account-owned companion identity as one i64."""
    from wakfu_server import heroes

    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Invalid native companion party request")
    identity = struct.unpack(">q", body)[0]
    if identity <= 0:
        raise ValueError("Invalid companion identity")
    with store.connection() as db:
        owned = _fence(store, db, account_id, generation, character_id)
        if owned["leader"]["hp"] <= 0:
            raise ValueError("Dead characters cannot add a companion")
        companion = db.execute(
            "SELECT * FROM account_companions WHERE id=%s AND account_id=%s FOR UPDATE",
            (identity, account_id),
        ).fetchone()
        if companion is None or not companion["unlocked"] or not companion["linked"]:
            raise ValueError("Companion is unavailable or belongs to another account")
        current = roster(db, account_id, character_id)
        if any(row["id"] == identity for row in current):
            return dict(leader=owned["leader"], companions=current, applied=False)
        if db.execute(
            "SELECT 1 FROM account_companion_slots WHERE companion_id=%s", (identity,)
        ).fetchone():
            raise ValueError("Companion already belongs to another selected company")
        if len(current) + len(owned["heroes"]) >= NATIVE_ADDITIONAL_MEMBER_CAP:
            raise ValueError("Native company slots are full")
        party = heroes._ensure_party(db, character_id)
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE", (party["id"],)
        )
        owners = db.execute(
            "SELECT c.* FROM player_party_members m JOIN characters c ON c.id=m.character_id "
            "WHERE m.party_id=%s",
            (party["id"],),
        ).fetchall()
        humans = heroes.augment_party(db, store, owners)
        if len(humans) + controlled_count(db, [row["id"] for row in owners]) >= 6:
            raise ValueError(
                "Native party including companions already has six members"
            )
        slot = next(
            slot for slot in range(2) if slot not in {row["slot"] for row in current}
        )
        db.execute(
            "INSERT INTO account_companion_slots(account_id,slot,owner_character_id,companion_id) "
            "VALUES(%s,%s,%s,%s)",
            (account_id, slot, character_id, identity),
        )
        db.execute(
            "UPDATE account_companions SET owner_character_id=%s WHERE id=%s",
            (character_id, identity),
        )
        db.execute(
            "UPDATE player_parties SET revision=revision+1 WHERE id=%s", (party["id"],)
        )
        return dict(
            leader=owned["leader"],
            companions=roster(db, account_id, character_id),
            applied=True,
        )


def remove_from_party(store, account_id, generation, character_id, companion_id):
    """Remove only this selected company's sidekick under its main lease."""
    if type(companion_id) is not int or companion_id <= 0:
        raise ValueError("Invalid companion removal identity")
    with store.connection() as db:
        owned = _fence(store, db, account_id, generation, character_id)
        removed = db.execute(
            "DELETE FROM account_companion_slots WHERE account_id=%s "
            "AND owner_character_id=%s AND companion_id=%s RETURNING companion_id",
            (account_id, character_id, companion_id),
        ).fetchone()
        return dict(
            leader=owned["leader"],
            companions=roster(db, account_id, character_id),
            applied=removed is not None,
        )


def select_main(db, account_id, main_character_id):
    """Reanchor saved account sidekicks after the caller fences main selection."""
    if (
        db.execute(
            "SELECT 1 FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
            (main_character_id, account_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Companion company main is unavailable")
    previous = db.execute(
        "SELECT owner_character_id FROM account_companion_slots "
        "WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchall()
    if all(row["owner_character_id"] == main_character_id for row in previous):
        return
    from wakfu_server.heroes import _idle

    _idle(
        db,
        sorted({main_character_id, *(row["owner_character_id"] for row in previous)}),
    )
    db.execute(
        "UPDATE account_companion_slots SET owner_character_id=%s WHERE account_id=%s",
        (main_character_id, account_id),
    )
    db.execute(
        "UPDATE account_companions SET owner_character_id=%s WHERE account_id=%s AND id IN "
        "(SELECT companion_id FROM account_companion_slots WHERE account_id=%s)",
        (main_character_id, account_id, account_id),
    )


def party_member(row, *, account_id, effective_level, in_fight=False):
    """Original ffZ party identity is the negative collection ID, never actor ID."""
    if row["account_id"] != account_id:
        raise ValueError("Companion party association differs from owner")
    return dict(
        id=-row["id"],
        association_id=account_id,
        name=row["name"],
        breed=row["breed_ref"],
        portrait_variant=0,
        native_identity_flag=False,
        level=level_for_xp(row["xp"]),
        effective_level=effective_level,
        in_fight=in_fight,
        dead=row["hp"] == 0,
        hp=row["hp"],
        max_hp=row["max_hp"],
        companion_record=dict(row),
    )


def added_result(result=1):
    """cnX and cnY share cwC12587; native eEQ.NO_ERROR is byte1."""
    if type(result) is not int or not 1 <= result <= 15:
        raise ValueError("Invalid native companion party result")
    return 12587, bytes((result,))


def enroll(
    db, fight_id, companion_id, account_id, owner_character_id, generation, team
):
    """Freeze the selected real companion under its controlling player's lease."""
    if type(team) is not int or team not in (0, 1):
        raise ValueError("Invalid companion fight team")
    if (
        db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.fight_id=%s AND p.account_id=%s AND p.character_id=%s "
            "AND p.session_generation=%s AND p.team=%s AND f.status IN ('placement','active')",
            (fight_id, account_id, owner_character_id, generation, team),
        ).fetchone()
        is None
    ):
        raise ValueError("Companion controller lacks matching active fight membership")
    if (
        db.execute(
            "SELECT 1 FROM combat_fight_companions c JOIN combat_fights f ON f.id=c.fight_id "
            "WHERE c.companion_id=%s AND c.fight_id<>%s AND c.health_settled_at IS NULL "
            "AND f.status IN ('placement','active') LIMIT 1",
            (companion_id, fight_id),
        ).fetchone()
        is not None
    ):
        raise ValueError("Companion already has active combat membership")
    selected = db.execute(
        "SELECT 1 FROM account_companion_slots WHERE account_id=%s "
        "AND owner_character_id=%s AND companion_id=%s FOR UPDATE",
        (account_id, owner_character_id, companion_id),
    ).fetchone()
    if selected is None:
        raise ValueError("Companion does not belong to this selected company")
    db.execute(
        "INSERT INTO combat_fight_companions(fight_id,companion_id,account_id,owner_character_id,"
        "session_generation,team) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(fight_id,companion_id) DO NOTHING",
        (fight_id, companion_id, account_id, owner_character_id, generation, team),
    )
    row = db.execute(
        "SELECT * FROM combat_fight_companions WHERE fight_id=%s AND companion_id=%s",
        (fight_id, companion_id),
    ).fetchone()
    if any(
        row[key] != value
        for key, value in (
            ("account_id", account_id),
            ("owner_character_id", owner_character_id),
            ("session_generation", generation),
            ("team", team),
        )
    ):
        raise ValueError("Companion fight membership differs from frozen owner")
    return dict(row)


def settle_health(db, store, fight_id, companion_id, hp, max_hp, *, hp_projection=None):
    """Restore native sidekick HP once after combat, including a defeated actor.

    Original content.156.148 and tutorial.compagnonEndFight explicitly specify
    full automatic recovery; companion wounds never require player bread.
    """
    if (
        type(hp) is not int
        or type(max_hp) is not int
        or not 0 <= hp <= max_hp
        or max_hp <= 0
    ):
        raise ValueError("Invalid terminal companion health")
    membership = db.execute(
        "SELECT * FROM combat_fight_companions WHERE fight_id=%s "
        "AND companion_id=%s FOR UPDATE",
        (fight_id, companion_id),
    ).fetchone()
    if membership is None:
        raise ValueError("Missing frozen companion fight membership")
    if membership["health_settled_at"] is not None:
        return False
    if hp_projection is None:
        current = db.execute(
            "SELECT equipment_hp_projection FROM account_companions WHERE id=%s FOR UPDATE",
            (companion_id,),
        ).fetchone()
        hp_projection = current["equipment_hp_projection"]
    if hp_projection is not None:
        from wakfu_server.equipment_hp_lifecycle import NativeHPActor, OwnedEwoHPReplay

        replay = OwnedEwoHPReplay.restore(hp_projection)
        if replay.actor.max_hp != max_hp:
            raise ValueError("Companion recovery differs from native HP projection")
        raw = replay.actor.plain()
        raw["raw_current"] = raw["raw_maximum"]
        hp_projection = OwnedEwoHPReplay(
            NativeHPActor(**raw), replay.plain_receipts()
        ).checkpoint()
    from psycopg.types.json import Jsonb

    db.execute(
        "UPDATE account_companions SET hp=%s,max_hp=%s,equipment_hp_projection=%s WHERE id=%s AND account_id=%s",
        (
            max_hp,
            max_hp,
            Jsonb(hp_projection) if hp_projection is not None else None,
            companion_id,
            membership["account_id"],
        ),
    )
    db.execute(
        "UPDATE combat_fight_companions SET health_settled_at=%s WHERE fight_id=%s AND companion_id=%s",
        (store.now(), fight_id, companion_id),
    )
    return True


def advance_experience(db, *, account_id, companion_id, amount):
    """Advance a qualified reward recipient using the common native XP storage.

    The caller owns its durable eligibility and once-only settlement receipt.
    This primitive neither selects recipients nor creates player XP.
    """
    if (
        any(
            type(value) is not int or value <= 0 for value in (account_id, companion_id)
        )
        or type(amount) is not int
        or not 0 <= amount < 2**63
    ):
        raise ValueError("Invalid companion experience progression")
    row = db.execute(
        "UPDATE account_companions SET xp=LEAST(9223372036854775807::numeric,xp::numeric+%s)::bigint "
        "WHERE id=%s AND account_id=%s RETURNING xp",
        (amount, companion_id, account_id),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned companion experience recipient")
    return row["xp"]


def award_experience(db, store, fight_id, companion_id, amount):
    """Apply a server-resolved companion XP award once, without player rewards."""
    if type(amount) is not int or not 0 <= amount < 2**63:
        raise ValueError("Invalid companion experience award")
    membership = db.execute(
        "SELECT * FROM combat_fight_companions WHERE fight_id=%s "
        "AND companion_id=%s FOR UPDATE",
        (fight_id, companion_id),
    ).fetchone()
    if membership is None:
        raise ValueError("Missing frozen companion fight membership")
    if membership["experience_settled_at"] is not None:
        return False
    advance_experience(
        db,
        account_id=membership["account_id"],
        companion_id=companion_id,
        amount=amount,
    )
    db.execute(
        "UPDATE combat_fight_companions SET experience_settled_at=%s,experience_award=%s "
        "WHERE fight_id=%s AND companion_id=%s",
        (store.now(), amount, fight_id, companion_id),
    )
    return True


def owner_experience_award(amount):
    """Native sidekick tutorial specifies 150% of actual owner end-fight XP.

    Integer remainder is rounded down as the server's explicit reward policy;
    the original client text establishes the factor, not the rounding method.
    """
    if type(amount) is not int or not 0 <= amount < 2**63:
        raise ValueError("Invalid owner companion experience basis")
    return min((amount * 3) // 2, 2**63 - 1)


def settle_rewards(db, store, fight):
    """Settle sidekick XP and full native HP after the owners' reward callback.

    No independent player XP, kamas, quest credit, or drop recipient is created.
    This consumes the same fight's actual owner XP receipts exactly once.
    """
    from wakfu_server.combat_companions import native_stats, registered_companion_ids
    from wakfu_server.builds import effective_sheet_level

    if fight.phase != "finished" or fight.winner not in (0, 1):
        raise ValueError("Companion rewards require a finished fight")
    identities = registered_companion_ids(fight)
    if not identities:
        return ()
    rows = db.execute(
        "SELECT * FROM combat_fight_companions WHERE fight_id=%s "
        "ORDER BY companion_id FOR UPDATE",
        (fight.id,),
    ).fetchall()
    if {row["companion_id"] for row in rows} != set(identities):
        raise ValueError("Frozen companion settlement differs from runtime actors")
    results = []
    for membership in rows:
        if (
            membership["experience_settled_at"] is not None
            and membership["health_settled_at"] is not None
        ):
            continue
        identity = membership["companion_id"]
        actor = fight.actors[identity]
        owner = fight.actors.get(membership["owner_character_id"])
        if (
            owner is None
            or owner.team != membership["team"]
            or owner.owner_id != membership["account_id"]
        ):
            raise ValueError(
                "Companion settlement controller differs from frozen owner"
            )
        withdrawn = (
            db.execute(
                "SELECT 1 FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                (fight.id, membership["owner_character_id"]),
            ).fetchone()
            is not None
        )
        reward = db.execute(
            "SELECT xp FROM fight_rewards WHERE fight_id=%s AND character_id=%s AND account_id=%s",
            (fight.id, membership["owner_character_id"], membership["account_id"]),
        ).fetchone()
        if reward is None and owner.team == fight.winner and not withdrawn:
            raise ValueError("Winning companion controller has no committed XP receipt")
        owner_xp = reward["xp"] if reward is not None else 0
        applied = award_experience(
            db, store, fight.id, identity, owner_experience_award(owner_xp)
        )
        if applied:
            db.execute(
                "UPDATE combat_fight_companions SET owner_experience_award=%s "
                "WHERE fight_id=%s AND companion_id=%s",
                (owner_xp, fight.id, identity),
            )
        companion = db.execute(
            "SELECT * FROM account_companions WHERE id=%s AND account_id=%s FOR UPDATE",
            (identity, membership["account_id"]),
        ).fetchone()
        character = store.character(
            membership["account_id"], membership["owner_character_id"], db
        )
        level = min(
            level_for_xp(companion["xp"]),
            loaded_level_cap(
                db,
                store,
                membership["account_id"],
                membership["owner_character_id"],
                owner_character=character,
            ),
        )
        from wakfu_server.companion_equipment import hydrate_equipment

        companion = hydrate_equipment(db, [dict(companion)])[0]
        projected = native_stats(
            companion["breed_ref"],
            level,
            equipment_entries=companion["equipment_entries"],
            owner=character,
            record=companion,
        )
        maximum = projected["max_hp"]
        # content.156.148 restores all sidekick HP after the fight. Level/gear
        # growth uses the original native stat pipeline at the resulting level.
        settle_health(
            db,
            store,
            fight.id,
            identity,
            min(actor.hp, maximum),
            maximum,
            hp_projection=projected.get("equipment_hp_projection"),
        )
        results.append(
            dict(
                companion_id=identity,
                account_id=membership["account_id"],
                owner_character_id=membership["owner_character_id"],
                applied=applied,
                owner_xp=owner_xp,
                xp=owner_experience_award(owner_xp),
                level=level,
            )
        )
    return tuple(results)


def settle_owner_exit(db, store, fight, account_id):
    """Freeze recovery and zero XP before a withdrawing owner's sidekicks retire.

    A later settlement of the remaining fight cannot overwrite a companion
    already admitted to another fight after the owner's authorized exit.
    """
    from wakfu_server.combat_companions import native_stats
    from wakfu_server.builds import effective_sheet_level

    if not getattr(fight, "native_companion_sources", {}):
        return ()
    results = []
    for row in db.execute(
        "SELECT * FROM combat_fight_companions WHERE fight_id=%s AND account_id=%s "
        "ORDER BY companion_id FOR UPDATE",
        (fight.id, account_id),
    ).fetchall():
        if (
            row["experience_settled_at"] is not None
            and row["health_settled_at"] is not None
        ):
            continue
        companion = db.execute(
            "SELECT * FROM account_companions WHERE id=%s FOR UPDATE",
            (row["companion_id"],),
        ).fetchone()
        owner = store.character(account_id, row["owner_character_id"], db)
        level = min(
            level_for_xp(companion["xp"]),
            loaded_level_cap(
                db, store, account_id, row["owner_character_id"], owner_character=owner
            ),
        )
        from wakfu_server.companion_equipment import hydrate_equipment

        companion = hydrate_equipment(db, [dict(companion)])[0]
        projected = native_stats(
            companion["breed_ref"],
            level,
            equipment_entries=companion["equipment_entries"],
            owner=owner,
            record=companion,
        )
        maximum = projected["max_hp"]
        award_experience(db, store, fight.id, row["companion_id"], 0)
        settled = settle_health(
            db,
            store,
            fight.id,
            row["companion_id"],
            0,
            maximum,
            hp_projection=projected.get("equipment_hp_projection"),
        )
        results.append(dict(companion_id=row["companion_id"], applied=settled))
    return tuple(results)
