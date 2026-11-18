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
import re
import math

from psycopg.types.json import Jsonb


def _inventory_loot_leaf(db, effect):
    """Prove a single deterministic original leaf before permitting reacquisition."""
    row = db.execute(
        "SELECT payload,source_sha256 FROM native_random_item_tables WHERE reference=%s",
        (effect["loot_list_id"],),
    ).fetchone()
    if row is None or row["source_sha256"] != effect["loot_source_sha256"]:
        raise ValueError("Inventory-repeatable loot lacks its original table")
    table = row["payload"]
    entries = table.get("gBN")
    if (
        type(table.get("d")) is not int
        or table["d"] != effect["loot_list_id"]
        or type(table.get("czg")) is not int
        or table["czg"] != 1
        or not isinstance(entries, list)
        or len(entries) != 1
    ):
        raise ValueError("Inventory-repeatable loot requires one guaranteed leaf")
    leaf = entries[0]
    if (
        type(leaf.get("aAi")) is not int
        or leaf["aAi"] <= 0
        or leaf.get("cqA") is not False
        or type(leaf.get("cqy")) is not int
        or type(leaf.get("cqz")) is not int
        or not 1 <= leaf["cqy"] <= 32767
        or leaf.get("cqz") != leaf["cqy"]
        or (leaf.get("bfh"), leaf.get("czl"), leaf.get("csE")) != (1, 0, 1)
        or any(type(leaf.get(key)) is not int for key in ("bfh", "czl", "csE"))
        or leaf.get("gBO") != []
        or not isinstance(leaf.get("czk"), str)
        or leaf["czk"] != ""
        and not _positive_inventory_guard(leaf["czk"], leaf["aAi"])
        or type(leaf.get("cmY")) not in (int, float)
        or not math.isfinite(leaf["cmY"])
        or not (leaf["cmY"] == -1 or leaf["cmY"] > 0)
    ):
        raise ValueError("Inventory-repeatable loot is not a guaranteed native item")
    return leaf


def _inventory_loot_reference(db, effect):
    return _inventory_loot_leaf(db, effect)["aAi"]


def _inventory_loot_guard(db, effect):
    """The original quantity guard may be on the effect or its sole loot leaf."""
    leaf = _inventory_loot_leaf(db, effect)
    return _positive_inventory_guard(
        effect["criterion"], leaf["aAi"]
    ) or _positive_inventory_guard(leaf["czk"], leaf["aAi"])


def _positive_inventory_guard(criterion, reference):
    """Recognize an original positive conjunction, never an OR bypass."""
    terms = re.split(r"\s+and\s+|\s*&&\s*", criterion.strip())
    guard = re.compile(rf"GetItemQuantity\({reference}\)\s*(?:==|<=)\s*0")
    prerequisite = re.compile(
        r"(?:IsAchievementRunning|IsAchievementActive|IsAchievementComplete|IsAchievementObjectiveComplete)\([1-9][0-9]*\)"
    )
    level = re.compile(r"GetRealLevel\(\)\s*>=\s*[1-9][0-9]*")
    return any(guard.fullmatch(term.strip()) for term in terms) and all(
        guard.fullmatch(term.strip())
        or prerequisite.fullmatch(term.strip())
        or level.fullmatch(term.strip())
        for term in terms
    )


def external_quest_scripts(db, rule, *, map_id, object_id):
    """Resolve absent client callbacks owned by guarded quest interactions."""
    rows = db.execute(
        "SELECT native_effect_reference,native_criterion FROM quest_interactive_bindings "
        "WHERE map_id=%s AND object_id=%s AND action_id=%s AND parameter=0 "
        "AND script_id=0 AND native_effect_reference>0",
        (map_id, object_id, rule["wire_action"]),
    ).fetchall()
    effects = {effect["effect_reference"]: effect for effect in rule["effects"]}
    result = set()
    for row in rows:
        reference = row["native_effect_reference"]
        effect = effects.get(reference)
        if (
            effect is None
            or effect["effect_type"] != 1
            or effect["criterion"] != row["native_criterion"]
        ):
            raise ValueError("External quest callback differs from its native effect")
        result.add(reference)
    return result


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
            qualified = (
                kind == 12
                and effect["criterion"]
                == f"GetItemQuantity({effect['item_reference']}) <= 0"
            )
            if kind == 4:
                if sum(row["effect_type"] != 1 for row in rule["effects"]) != 1:
                    raise ValueError(
                        "Repeatable native loot requires one item-producing effect"
                    )
                qualified = _inventory_loot_guard(db, effect)
            if not qualified:
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
        queries = None

        def allowed(expression):
            nonlocal queries
            if queries is None and "IsAchievement" in expression:
                from wakfu_server.achievements import storage
                from wakfu_server.dungeon_achievement_authority import (
                    queries_from_state,
                )

                queries = queries_from_state(
                    storage.load_locked(db, actual["id"]), now_ms=now_ms
                )
            # Same eKE view as native dungeon access: bags + personal QUEST +
            # effective ACCOUNT_QUEST, including existing artifact projection.
            return evaluate(
                store, expression, character=actual, now_ms=now_ms, queries=queries
            )

        if not allowed(rule["action_criterion"]):
            raise ValueError("Native generic action criterion failed")
        server_scripts = external_quest_scripts(
            db, rule, map_id=actual["map_id"], object_id=object_id
        )
        visual = chest_scripts.packets(
            dict(
                rule,
                scripts=[
                    dict(effect, effect_criterion=effect["criterion"])
                    for effect in rule["effects"]
                    if effect["effect_type"] == 1
                    and effect["effect_reference"] not in server_scripts
                ],
            ),
            actual["id"],
            evaluate=allowed,
        )
        token, packets, grants, consumed = uuid.uuid4(), [], [], []
        paid = False
        digest = _digest(rule)
        from wakfu_server import dungeon_optional_votes

        ballot_scope = dungeon_optional_votes.reward_scope(
            db, actual, rule, generation=generation
        )
        for effect in rule["effects"]:
            if effect["effect_type"] == 1 or not allowed(effect["criterion"]):
                continue
            previous = None
            if ballot_scope is not None:
                previous = (
                    {"rule_digest": digest} if ballot_scope["granted_units"] else None
                )
            elif rule["lifecycle_mode"] == "ONCE_PER_CHARACTER_RECONSTRUCTED":
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
            if ballot_scope is not None:
                dungeon_optional_votes.claim_scope(db, ballot_scope, token, products)
            elif rule["lifecycle_mode"] == "ONCE_PER_CHARACTER_RECONSTRUCTED":
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
        if grants:
            from wakfu_server.achievements import mission_toolkit

            # The event reference is the exact physical source, rather than an
            # item ID that could also be produced by another unrelated object.
            # The attempt row above freezes the actual native products and is
            # committed atomically with their inventory/objective settlement.
            packets.extend(
                mission_toolkit.settle(
                    db,
                    store,
                    actual,
                    f"generic-item-acquired:{token}",
                    "generic_item_acquired",
                    object_id,
                    quantity=sum(grant["quantity"] for grant in grants),
                )
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
