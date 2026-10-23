"""Original reusable bHw mission starters, limited to initial activation."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _equipped, _idle


SOURCE_SHA256 = "d8af41b03961255ea5cf6ad7617f99100f515aa85bf8ad6792c239bf84f0c620"


@lru_cache(maxsize=1)
def descriptors():
    raw = Path(__file__).with_name("native_achievement_item_actions.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting original item mission descriptors")
    return {row["action_id"]: row for row in json.loads(raw)["actions"]}


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native mission action header")
    action_id, uid = struct.unpack_from(">iq", body)
    plan = descriptors().get(action_id)
    if plan is None:
        return None
    if uid <= 0:
        raise ValueError("Invalid native mission source identity")
    if plan["positional_suffix"]:
        if not (
            (len(body) == 13 and body[12] == 0) or (len(body) == 23 and body[12] == 1)
        ):
            raise ValueError("Invalid native mission position suffix")
    elif len(body) != 12:
        raise ValueError("Invalid native mission action grammar")
    return "bHw"


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Fence the real item owner, then atomically retain only mission activation."""
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Start this mission outside combat")
    if action_class(body) != "bHw":
        raise ValueError("Unsupported native item mission action")
    action_id, uid = struct.unpack_from(">iq", body)
    plan = descriptors()[action_id]
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, owner_id),
        ).fetchone()
        if (
            item is None
            or item["reference"] != plan["item_ref"]
            or item["quantity"] < 1
        ):
            raise ValueError("The native mission source does not match its action")
        container = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s",
            (item["container"], owner_id),
        ).fetchone()
        from wakfu_server.combat_drop_delivery import _container_can_hold

        if (
            container is None
            or not _container_can_hold(container, owner_id)
            or not 0 <= item["slot"] < container["capacity"]
        ):
            raise ValueError("The mission starter must be in an owned ordinary bag")
        rule = db.execute(
            "SELECT * FROM native_achievement_item_actions WHERE item_ref=%s",
            (plan["item_ref"],),
        ).fetchone()
        if (
            rule is None
            or rule["source_sha256"] != SOURCE_SHA256
            or rule["descriptor"] != plan
            or any(
                rule[key] != plan[key]
                for key in (
                    "action_id",
                    "definition_id",
                    "minimum_real_level",
                    "positional_suffix",
                    "consumes_source",
                )
            )
        ):
            raise ValueError("The qualified item mission authority has changed")
        from .haven_bag_furniture_knowledge import _rules

        original = _rules().get(plan["item_ref"], {})
        if (
            original.get("use_action_class") != "bHw"
            or original.get("use_action_id") != action_id
            or original.get("use_has_criteria") is not plan["native_use_has_criteria"]
        ):
            raise ValueError(
                "The mission starter differs from the active native catalog"
            )
        character = store.character(account_id, owner_id, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the mission starter before using it")
        # This suffix belongs to the native request grammar; bHw has no
        # position-dependent effect and never moves or teleports the actor.
        from wakfu_server.achievements.item_activation import activate

        result = activate(db, store, character, plan, source_uid=uid)
        result.update(
            character=store.character(account_id, owner_id, db),
            actor_id=owner_id,
            native_class="bHw",
            validated=True,
            consumed=0,
            source_uid=uid,
            source_reference=plan["item_ref"],
            scope="initial_activation_only",
        )
        return result
