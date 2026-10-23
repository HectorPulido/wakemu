"""Five original neutrality scrolls over authoritative current nation identity.

National balances use durable components and explicit SQL reset rules.
Physical references24844/24268 are icons, not the national merit wallet.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _equipped, _idle

SOURCE_SHA256 = "6de10a893e07743ae3b8168ff9f50988a768e26a4bcc4c7c7c5b5d71c86a1a63"


@lru_cache(maxsize=1)
def descriptors():
    payload = Path(__file__).with_name("native_neutrality_items.json").read_bytes()
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native neutrality descriptors")
    return json.loads(payload)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native neutrality action header")
    action_id, uid = struct.unpack_from(">iq", body)
    if not any(row["action_id"] == action_id for row in descriptors()["items"]):
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native neutrality action grammar")
    return "bIn"


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Remove current membership and consume one scroll in one transaction.

    Return the same minimal publication signal as native enrollment: World
    refreshes own nation/company, remote identity and chat membership while
    preserving live scene coordinates and party. The UI event is own-account.
    """
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Use this neutrality scroll outside combat")
    if action_class(body) != "bIn":
        raise ValueError("Unsupported native neutrality scroll")
    action_id, uid = struct.unpack(">iq", body)
    plan = next(row for row in descriptors()["items"] if row["action_id"] == action_id)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        if owner_id != character_id:
            raise ValueError(
                "Select the character carrying this scroll before using it"
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
            raise ValueError("The source does not match this native neutrality action")
        row = db.execute(
            "SELECT * FROM native_neutrality_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if (
            row is None
            or row["action_id"] != action_id
            or row["scenario_id"] != plan["scenario_id"]
            or row["event_id"] != plan["event_id"]
            or row["consumes_source"] is not True
            or row["source_sha256"] != SOURCE_SHA256
        ):
            raise ValueError("The qualified neutrality authority has changed")
        from .haven_bag_furniture_knowledge import _rules
        from wakfu_server.characters.nation_state import nation_id

        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_class") != "bIn"
            or published.get("use_action_id") != action_id
        ):
            raise ValueError(
                "The neutrality action differs from the active native catalog"
            )
        character = store.character(account_id, owner_id, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the neutrality scroll before using it")
        previous = nation_id(character)
        if previous == 0:
            raise ValueError("This character is already neutral")
        from .national_earnings import neutralize

        neutralize(db, owner_id, item["reference"])
        # Absence is the existing canonical neutral state. Enrollment stores
        # only non-neutral identities; no government privileges are invented.
        db.execute(
            "DELETE FROM character_chat_nations WHERE character_id=%s", (owner_id,)
        )
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, owner_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (uid, owner_id),
            )
        character = store.character(account_id, owner_id, db)
        if nation_id(character) != 0:
            raise ValueError("The neutrality transition did not persist")
        return dict(
            character=character,
            native_class="bIn",
            consumed=1,
            applied=True,
            source_uid=uid,
            source_reference=item["reference"],
            nation_changed=True,
            previous_nation_id=previous,
            nation_id=0,
            packets=[
                (12470, struct.pack(">qh", uid, -1)),
                (
                    13411,
                    struct.pack(">BiiB", 0, plan["event_id"], plan["scenario_id"], 0),
                ),
            ],
        )
