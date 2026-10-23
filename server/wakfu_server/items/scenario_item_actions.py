"""One native reusable diary-reading scenario; no generic scenario executor."""
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _equipped, _idle

ITEM_REFERENCE = 30723
ACTION_ID = 14933
SCENARIO_ID = 2704
EVENT_ID = 24072
SCRIPT_SHA256 = "ecb63a5f6b301229d8c7887f7c2339c5b3d7bc9791c97ec12286d86c1b849710"


def action_class(body):
    """Leave every other bIn scenario unsupported until separately qualified."""
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native scenario item header")
    action_id, uid = struct.unpack_from(">iq", body)
    if action_id != ACTION_ID:
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native reading scenario grammar")
    return "bIn"


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Authorize a read, returning original 13411 only to the owner connection."""
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Read this diary outside combat")
    if action_class(body) != "bIn":
        raise ValueError("Unsupported native item scenario")
    _, uid = struct.unpack(">iq", body)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        # Original bIn.aP checks the controlled actor's dqT().tD(sourceUID),
        # rather than bIa's company-wide fkH.ag(sourceUID) lookup.
        if owner_id != character_id:
            raise ValueError(
                "Select the character carrying this diary before reading it"
            )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, owner_id),
        ).fetchone()
        if item is None or item["reference"] != ITEM_REFERENCE or item["quantity"] < 1:
            raise ValueError(
                "The diary source does not match this native reading action"
            )
        rule = db.execute(
            "SELECT * FROM native_reading_scenario_item_actions WHERE item_ref=%s",
            (ITEM_REFERENCE,),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != ACTION_ID
            or rule["scenario_id"] != SCENARIO_ID
            or rule["event_id"] != EVENT_ID
            or rule["script_sha256"] != SCRIPT_SHA256
            or rule["consumes_source"] is not False
        ):
            raise ValueError("The qualified diary scenario authority has changed")
        from .haven_bag_furniture_knowledge import _rules

        published = _rules().get(ITEM_REFERENCE, {})
        if (
            published.get("use_action_class") != "bIn"
            or published.get("use_action_id") != ACTION_ID
        ):
            raise ValueError("The diary differs from the active native catalog")
        character = store.character(account_id, owner_id, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the diary before reading it")
        # Native cqa=false: neither the scenario's initialization nor its empty
        # follow-up callback destroys the source, grants items, or awards XP.
        packet = (13411, struct.pack(">BiiB", 0, EVENT_ID, SCENARIO_ID, 0))
        return dict(
            character=character,
            packets=[packet],
            native_class="bIn",
            applied=True,
            validated=True,
            consumed=0,
            source_uid=uid,
            source_reference=ITEM_REFERENCE,
            scenario_id=SCENARIO_ID,
            event_id=EVENT_ID,
            background_id=415,
        )
