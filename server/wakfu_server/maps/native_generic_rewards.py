"""Original free GenericActivable item effects with explicit lifecycle policy.

The native12870 action has no request nonce. Inventory guards are rechecked
under the owner lock on every action; only explicitly reconstructed once rules
use a permanent marker. A new action after consumption may reacquire an item.
"""
import hashlib
import json
import secrets
from types import SimpleNamespace
import struct
import uuid

from psycopg.types.json import Jsonb


def _rule(db, map_id, object_id):
    row = db.execute(
        "SELECT p.*,l.* FROM native_generic_reward_locations l "
        "JOIN native_generic_reward_programs p USING(policy_id) "
        "WHERE l.map_id=%s AND l.object_id=%s",
        (map_id, object_id),
    ).fetchone()
    if row is None:
        return None
    rule = dict(row)
    rule["approaches"] = [
        [r[k] for k in ("x", "y", "z")]
        for r in db.execute(
            "SELECT x,y,z FROM native_generic_reward_approaches WHERE map_id=%s AND object_id=%s ORDER BY x,y,z",
            (map_id, object_id),
        ).fetchall()
    ]
    rule["effects"] = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM native_generic_reward_effects WHERE policy_id=%s ORDER BY effect_order",
            (rule["policy_id"],),
        ).fetchall()
    ]
    if (
        rule["sealed"] is not True
        or not rule["authority"]
        or not rule["approaches"]
        or rule["lifecycle_mode"]
        not in ("NATIVE_INVENTORY_GUARD", "ONCE_PER_CHARACTER_RECONSTRUCTED")
        or rule["raw_cob"] != 1
        or rule["group_cnd"] != 0
        or any(
            type(rule[k]) is not int or rule[k] < 0 for k in ("group_cod", "group_coe")
        )
        or (rule["group_cod"] == 0) != (rule["group_coe"] == 0)
        or rule["group_coe"] > 32767
        or (rule["group_cod"] > 0 and rule["group_cof"] is not True)
        or rule["approach_policy"] != "wakemu.reconstructed-cardinal-native-walkable.v1"
        or not rule["effects"]
    ):
        raise ValueError("Unqualified native generic reward program")
    for effect in rule["effects"]:
        kind = effect["effect_type"]
        if (
            kind not in (1, 4, 12)
            or type(effect["effect_reference"]) is not int
            or effect["effect_reference"] <= 0
            or len(effect["source_sha256"]) != 64
        ):
            raise ValueError("Unsupported native generic effect")
        if kind == 12 and (
            effect["item_reference"] is None
            or effect["item_quantity"] is None
            or effect["parameters"]
            != [str(effect["item_reference"]), str(effect["item_quantity"])]
            or effect["item_reference"] <= 0
            or not 1 <= effect["item_quantity"] <= 32767
        ):
            raise ValueError("Native item reward differs from its original parameters")
        if kind == 4 and (
            effect["loot_list_id"] is None
            or effect["parameters"] != [str(effect["loot_list_id"])]
            or not effect["loot_source_sha256"]
        ):
            raise ValueError("Native loot reward differs from its original table")
        if kind != 1 and rule["lifecycle_mode"] == "NATIVE_INVENTORY_GUARD":
            if (
                kind != 12
                or effect["criterion"]
                != f"GetItemQuantity({effect['item_reference']}) <= 0"
            ):
                raise ValueError(
                    "Inventory-repeatable reward lacks its native quantity guard"
                )
    return rule


def definition(store, map_id, object_id):
    with store.connection() as db:
        return _rule(db, map_id, object_id)


def _source(rule):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(
        rule["catalog_revision"],
        (
            "native-map-objects.json",
            "native-interactive-states.json",
            f"combat-maps/{rule['map_id']}.json",
        ),
    )
    current_revision = native_catalog.release()
    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(rule["object_id"])
    )
    state = native_catalog.record(
        DATA_ROOT / "native-interactive-states.json", "objects", str(rule["object_id"])
    )
    with native_catalog._database().connection() as db:
        terrain = db.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (current_revision, f"combat-maps/{rule['map_id']}.json"),
        ).fetchone()
    if (
        current_revision != native_catalog.release()
        or original is None
        or original.get("type") != "GenericActivableInteractiveElement"
        or original.get("map_id") != rule["map_id"]
        or [original.get(k) for k in ("x", "y", "z")]
        != [rule[k] for k in ("x", "y", "z")]
        or original.get("payload_hex") != rule["payload_hex"]
        or terrain is None
        or terrain["sha256"] != rule["geometry_sha256"]
    ):
        raise ValueError("Generic reward differs from its original world source")
    if rule["state_payload_hex"] is None:
        if state is not None:
            raise ValueError("Unexpected native generic state")
    elif (
        state is None
        or state.get("map_id") != rule["map_id"]
        or state.get("type") != "GenericActivableInteractiveElement"
        or state.get("payload_hex") != rule["state_payload_hex"]
    ):
        raise ValueError("Generic reward differs from its original state")


def _digest(rule):
    return hashlib.sha256(
        json.dumps(
            rule, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _products(db, effect, *, allowed):
    if effect["effect_type"] == 12:
        return {effect["item_reference"]: effect["item_quantity"]}
    from wakfu_server.random_item_actions import draw_products

    def lookup(reference):
        row = db.execute(
            "SELECT payload,source_sha256 FROM native_random_item_tables WHERE reference=%s",
            (reference,),
        ).fetchone()
        if row is None or row["source_sha256"] != effect["loot_source_sha256"]:
            raise ValueError("Missing exact original generic loot table")
        return row["payload"]

    # Reuse the existing qualified table/quantity/weight resolver. No global
    # loot eligibility bypass, bag-opening item or guessed output is introduced.
    return draw_products(
        effect["loot_list_id"],
        lookup,
        SimpleNamespace(randbelow=secrets.randbelow),
        entry_allowed=allowed,
    )


def _payment(db, store, character, rule):
    """Reuse carried/QUEST/account-QUEST payment without projected substitutes."""
    if rule["group_cod"] == 0:
        return character, [], []
    from wakfu_server.dungeon_entry_payment import consume
    from wakfu_server.quest_inventory import changes
    from wakfu_server.characters.exploration_secrets import account_packet

    rows = consume(db, (character["id"],), rule["group_cod"], rule["group_coe"])
    after = store.character(character["account_id"], character["id"], db)
    packets = [
        (12470, struct.pack(">qh", row["uid"], -row["consumed"]))
        for row in rows
        if not row.get("quest_item") and not row.get("account_quest_item")
    ]
    if any(row.get("quest_item") for row in rows):
        packets.extend(changes(character, after))
    if any(row.get("account_quest_item") for row in rows):
        packets.append(account_packet(db, character["account_id"]))
    return after, packets, [dict(row) for row in rows]


def claim(
    store, account_id, generation, character, body, *, loaded=False, blocked=False
):
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.dungeon_criteria import evaluate
    from wakfu_server.achievements import chest_scripts, rewards, storage

    if type(body) is not bytes or len(body) != 12 or not loaded or blocked:
        raise ValueError("Generic reward requires its authenticated loaded action")
    object_id, action, parameter = struct.unpack(">qHH", body)
    if parameter != 0:
        raise ValueError("Unsupported native generic action parameter")
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        rule = _rule(db, character["map_id"], object_id)
        if rule is None or action != rule["wire_action"]:
            raise ValueError("Unknown native generic reward action")
        actual = store.character(account_id, character["id"], db)
        if (
            any(
                actual.get(k, 0) != character.get(k, 0)
                for k in ("map_id", "instance_id", "x", "y", "z")
            )
            or [actual[k] for k in ("x", "y", "z")] not in rule["approaches"]
        ):
            raise ValueError("Generic reward requires its owned current approach")
        _idle(db, actual["id"], store.now())
        if db.execute(
            "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
            (actual["id"],),
        ).fetchone():
            raise ValueError("Another native occupation is active")
        _source(rule)
        before = actual
        now_ms = int(store.now().timestamp() * 1000)

        def allowed(expression):
            # Same eKE view as native dungeon access: bags + personal QUEST +
            # effective ACCOUNT_QUEST, including existing artifact projection.
            return evaluate(store, expression, character=actual, now_ms=now_ms)

        if not allowed(rule["action_criterion"]):
            raise ValueError("Native generic action criterion failed")
        visual = chest_scripts.packets(
            dict(
                rule,
                scripts=[
                    dict(effect, effect_criterion=effect["criterion"])
                    for effect in rule["effects"]
                    if effect["effect_type"] == 1
                ],
            ),
            actual["id"],
            evaluate=allowed,
        )
        token, packets, grants, consumed = uuid.uuid4(), [], [], []
        paid = False
        digest = _digest(rule)
        for effect in rule["effects"]:
            if effect["effect_type"] == 1 or not allowed(effect["criterion"]):
                continue
            previous = None
            if rule["lifecycle_mode"] == "ONCE_PER_CHARACTER_RECONSTRUCTED":
                previous = db.execute(
                    "SELECT rule_digest FROM native_generic_reward_claims "
                    "WHERE character_id=%s AND policy_id=%s AND object_id=%s AND effect_reference=%s",
                    (
                        actual["id"],
                        rule["policy_id"],
                        object_id,
                        effect["effect_reference"],
                    ),
                ).fetchone()
            if previous is not None:
                if previous["rule_digest"] != digest:
                    raise ValueError("Generic reward rule changed after its once claim")
                continue
            if not paid:
                actual, payment_packets, consumed = _payment(db, store, actual, rule)
                packets.extend(payment_packets)
                paid = True
            products = _products(db, effect, allowed=allowed)
            for reference, quantity in sorted(products.items()):
                packets.extend(rewards._item(db, store, actual, reference, quantity))
                grants.append(
                    dict(
                        effect_reference=effect["effect_reference"],
                        reference=reference,
                        quantity=quantity,
                    )
                )
                actual = store.character(account_id, actual["id"], db)
            if rule["lifecycle_mode"] == "ONCE_PER_CHARACTER_RECONSTRUCTED":
                db.execute(
                    "INSERT INTO native_generic_reward_claims "
                    "(character_id,policy_id,object_id,effect_reference,rule_digest,attempt_uuid) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        actual["id"],
                        rule["policy_id"],
                        object_id,
                        effect["effect_reference"],
                        digest,
                        token,
                    ),
                )
        db.execute(
            "INSERT INTO native_generic_reward_attempts "
            "(token,account_id,character_id,generation,map_id,instance_id,object_id,policy_id,rule_digest,granted,consumed) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                token,
                account_id,
                actual["id"],
                generation,
                before["map_id"],
                before.get("instance_id", 0),
                object_id,
                rule["policy_id"],
                digest,
                Jsonb(grants),
                Jsonb(consumed),
            ),
        )
        key = None
        if packets:
            key = f"generic-reward:{token}"
            storage.enqueue_notifications(
                db,
                actual["id"],
                key,
                [
                    dict(opcode=opcode, payload_hex=payload.hex())
                    for opcode, payload in packets
                ],
            )
        return dict(
            character=actual,
            packets=packets,
            visual_packets=visual,
            notification_key=key,
            attempt=token,
            replay=not grants,
            granted=grants,
        )
