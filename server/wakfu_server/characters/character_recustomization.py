"""Native item-backed dressing room; keep the existing character aggregate."""
import struct

from psycopg.types.json import Jsonb
from protocol_codec import APPEARANCE_FIELDS

# Original item descriptions plus native eFQ bits; none grants name bit 2.
RULES = {
    18292: (5556, 13, 245),
    19164: (7192, 29, 80),
    19165: (7191, 29, 150),
    19166: (7193, 29, 245),
}


def pending(db, character_id):
    row = db.execute(
        "SELECT source_uid,source_ref,action_id,mode,level_cap FROM "
        "character_recustomization_receipts WHERE character_id=%s "
        "AND completed_at IS NULL",
        (character_id,),
    ).fetchone()
    return dict(row) if row else None


def creation_section(character):
    """Native pt presence byte followed by pw's five-byte value."""
    entitlement = character.get("recustomization")
    mode = entitlement["mode"] if entitlement else 0
    if mode not in (0, 13, 29):
        raise ValueError("Invalid pending recustomization mode")
    return struct.pack(">BBBhB", 1, 0, bool(entitlement), mode, 0)


def transition_packets(character):
    entitlement = character.get("recustomization")
    if not entitlement or entitlement["mode"] not in (13, 29):
        raise ValueError("No pending dressing-room entitlement")
    name = character["name"].encode("utf-8")
    if len(name) > 127:
        raise ValueError("Recustomization name exceeds native signed byte")
    mode = entitlement["mode"]
    return [
        (12707, struct.pack(">h", mode)),
        (
            22797,
            struct.pack(">qB", character["id"], len(name))
            + name
            + struct.pack(">hB", mode, 0),
        ),
    ]


def request(store, account_id, generation, character_id, body):
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Recustomization requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid recustomization item action")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        # Only the selected main can leave the world for the dressing room.
        store.lock_character(db, account_id, generation, character_id)
        from wakfu_server.characters.heroes import _idle

        _idle(db, [character_id])
        from wakfu_server.simple_item_actions import _idle as item_idle

        item_idle(db, character_id, store.now())
        # Native requests carry no nonce. Deduplicate the pending visit only;
        # after completion a remaining stack unit funds a new historical row.
        prior = db.execute(
            "SELECT * FROM character_recustomization_receipts "
            "WHERE account_id=%s AND source_uid=%s AND completed_at IS NULL",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            if prior["character_id"] != character_id or prior["action_id"] != action_id:
                raise ValueError("Recustomization receipt does not match request")
            character = store.character(account_id, character_id, db)
            return dict(
                character=character,
                packets=[],
                applied=False,
                pending=character.get("recustomization"),
            )
        if pending(db, character_id):
            raise ValueError("Character already has a pending recustomization")
        item = db.execute(
            "SELECT reference,quantity FROM inventory_items "
            "WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, character_id),
        ).fetchone()
        rule = RULES.get(item["reference"]) if item else None
        if not rule or rule[0] != action_id or item["quantity"] < 1:
            raise ValueError("Unavailable or foreign recustomization item")
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        active = _rules().get(item["reference"])
        if (
            not active
            or active.get("use_action_class") != "bIb"
            or active.get("use_action_id") != action_id
        ):
            raise ValueError("Recustomization action differs from native catalog")
        character = store.character(account_id, character_id, db)
        if not 1 <= character["level"] <= rule[2]:
            raise ValueError("Character exceeds recustomization level cap")
        from wakfu_server.wire import proto_fields

        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError("Unequip the recustomization item before use")
        db.execute(
            "INSERT INTO character_recustomization_receipts "
            "(account_id,source_uid,character_id,source_ref,action_id,mode,level_cap) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (account_id, source_uid, character_id, item["reference"], *rule),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        character = store.character(account_id, character_id, db)
        return dict(
            character=character,
            applied=True,
            pending=character["recustomization"],
            packets=[(12470, struct.pack(">qh", source_uid, -1))],
        )


def complete(store, account_id, generation, request):
    character_id = request["character_id"]
    if type(character_id) is not int or character_id <= 0 or request["creation_flag"]:
        raise ValueError("Invalid existing-character dressing-room identity")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character_id, selected=False)
        lease = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s", (account_id,)
        ).fetchone()
        if lease["character_id"] is not None:
            raise ValueError("Leave the world before completing recustomization")
        from wakfu_server.characters.heroes import _idle

        _idle(db, [character_id])
        from wakfu_server.simple_item_actions import _idle as item_idle

        item_idle(db, character_id, store.now())
        character = store.character(account_id, character_id, db)
        entitlement = character.get("recustomization")
        if not entitlement:
            raise ValueError("No pending recustomization entitlement")
        if not 1 <= character["level"] <= entitlement["level_cap"]:
            raise ValueError("Character exceeds recustomization level cap")
        breed = request["breed_id"]
        from wakfu_server.breed_resources import playable_breeds

        if type(breed) is not int or breed not in playable_breeds():
            raise ValueError("Invalid recustomization breed")
        if request["character_name"] != character["name"]:
            raise ValueError("This item does not authorize renaming")
        if entitlement["mode"] == 13 and breed != character["breed"]:
            raise ValueError("This item does not authorize class changes")
        appearance = request["appearance"]
        old = character["appearance"]
        if not isinstance(appearance, dict) or any(
            key not in APPEARANCE_FIELDS
            or type(value) is not int
            or not -(1 << 31) <= value < (1 << 31)
            or key not in APPEARANCE_FIELDS[:12]
            and value != old.get(key, 0)
            for key, value in appearance.items()
        ):
            raise ValueError("Invalid or unauthorized recustomization appearance")
        appearance = dict(old, **appearance)
        sex, face, cloth = (
            appearance.get(key, 0) for key in ("sex", "faceIndex", "clothIndex")
        )
        if sex not in (0, 1) or face not in range(32) or cloth not in range(32):
            raise ValueError("Invalid recustomization appearance")
        if breed != character["breed"]:
            from wakfu_server.builds import EMPTY_APTITUDES, effective_sheet_level
            from wakfu_server.spells import default_deck

            for index in character.get("builds", {}):
                deck = default_deck(
                    dict(
                        character,
                        breed=breed,
                        effective_level=effective_sheet_level(character, index),
                    )
                )
                db.execute(
                    "UPDATE character_builds SET deck=%s,aptitudes=%s "
                    "WHERE character_id=%s AND build_index=%s",
                    (deck, EMPTY_APTITUDES, character_id, index),
                )
            db.execute(
                "UPDATE character_build_selection SET revision=revision+1 WHERE character_id=%s",
                (character_id,),
            )
        db.execute(
            "UPDATE characters SET breed=%s,sex=%s,face=%s,hair=%s,appearance=%s "
            "WHERE id=%s AND account_id=%s",
            (
                breed,
                bool(sex),
                face,
                cloth,
                Jsonb(appearance),
                character_id,
                account_id,
            ),
        )
        db.execute(
            "UPDATE character_recustomization_receipts SET completed_at=now(),completion=%s "
            "WHERE account_id=%s AND source_uid=%s AND completed_at IS NULL",
            (Jsonb(request), account_id, entitlement["source_uid"]),
        )
        character = store.character(account_id, character_id, db)
        from wakfu_server.consumable_characteristics import reconcile_health

        character = reconcile_health(db, character)
        character["recustomized"] = True
        return character
