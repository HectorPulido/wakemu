"""Validate original client-local compass actions without inventing guild effects."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _criterion

SOURCE_SHA256 = "fa22f0ec458c41cbab5d38d9717a0fe70787660f45b711f0dab0c2bec35b56ee"


@lru_cache(maxsize=1)
def descriptors():
    raw = Path(__file__).with_name("native_world_marker_items.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native world-marker descriptors")
    return json.loads(raw)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native world-marker header")
    action_id, uid = struct.unpack_from(">iq", body)
    if not any(row["action_id"] == action_id for row in descriptors()["items"]):
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native world-marker grammar")
    return "bHA"


def use(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    native_map_id=None,
    private_context=False
):
    """Authorize custody and native conditions; the client already set its compass.

    The live native instance is supplied by World, never a client field or stale
    SQL location. These actions have no actor animation or inventory mutation.
    Guild creation and identity changes remain separate policy-disabled routes.
    """
    if type(in_fight) is not bool or type(private_context) is not bool:
        raise ValueError("Invalid native world-marker context")
    if action_class(body) != "bHA":
        raise ValueError("Unsupported native world-marker action")
    action_id, uid = struct.unpack(">iq", body)
    plan = next(row for row in descriptors()["items"] if row["action_id"] == action_id)
    if type(native_map_id) is not int or native_map_id <= 0 or private_context:
        raise ValueError(
            "The native compass conditions require the current world instance"
        )
    if in_fight and plan["use_in_fight_criterion"] == "False":
        raise ValueError("The native item cannot be used during combat")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        source = db.execute(
            "SELECT i.* FROM inventory_items i JOIN inventory_containers c "
            "ON c.uid=i.container AND c.character_id=i.character_id "
            "WHERE i.uid=%s AND i.character_id=%s FOR UPDATE OF i",
            (uid, owner_id),
        ).fetchone()
        if (
            source is None
            or source["reference"] != plan["item_ref"]
            or source["quantity"] < 1
        ):
            raise ValueError(
                "The compass source does not match its owned native action"
            )
        rule = db.execute(
            "SELECT * FROM native_world_marker_item_actions WHERE item_ref=%s",
            (source["reference"],),
        ).fetchone()
        marker = plan["marker"]
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["source_sha256"] != SOURCE_SHA256
            or rule["consumes_source"] is not False
            or any(rule["marker_" + key] != value for key, value in marker.items())
        ):
            raise ValueError("The qualified compass destination is unavailable")
        from .haven_bag_furniture_knowledge import _rules

        published = _rules().get(source["reference"], {})
        if (
            published.get("use_action_class") != "bHA"
            or published.get("use_action_id") != action_id
        ):
            raise ValueError(
                "The compass action differs from the active native catalog"
            )
        actor = db.execute(
            "SELECT id,account_id,level FROM characters WHERE id=%s", (owner_id,)
        ).fetchone()
        if actor is None or actor["level"] < plan["minimum_level"]:
            raise ValueError("The native compass item requires its minimum level")
        for criterion in (plan["use_criterion"], plan["action_criterion"]):
            if not _criterion(store, db, account_id, actor, criterion, native_map_id):
                raise ValueError("The native compass conditions are not satisfied")
        return dict(
            applied=True,
            validated=True,
            native_class="bHA",
            packets=[],
            consumed=0,
            actor_id=owner_id,
            source_uid=uid,
            source_reference=source["reference"],
            marker=dict(marker),
        )
