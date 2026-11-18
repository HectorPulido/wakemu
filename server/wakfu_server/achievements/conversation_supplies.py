"""Explicit reviewed supplies on a genuinely accepted native NPC choice.

These declarations reconstruct missing server grants; they are not native
reward-field claims. Existing item writers retain inventory domains, binding,
capacity and wire semantics. The caller owns the account/session/character
locks, offered-choice validation and transaction rollback.
"""

from uuid import uuid4

POLICY = "reviewed-missing-server-supply-v1"
FIELD = "reviewed_item_grants"


def validate(document, native):
    from wakfu_server.native_quest_complex_loot import dialogue_consumer_source, digest

    rows = document.get(FIELD, [])
    if not isinstance(rows, list):
        raise ValueError("Invalid reviewed NPC supply declarations")
    seen = set()
    placements = document.get("placements", [])
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "id",
            "policy",
            "reference_id",
            "action_id",
            "map_id",
            "node_id",
            "choice_id",
            "quest_id",
            "item_reference",
            "quantity",
            "required_completed",
            "blocked_objectives",
            "native_source_sha256",
            "evidence",
        }:
            raise ValueError("Malformed reviewed NPC supply declaration")
        if (
            row["policy"] != POLICY
            or not isinstance(row["id"], str)
            or not row["id"]
            or row["id"] in seen
            or not row["evidence"]
            or any(
                type(row[k]) is not int or row[k] <= 0
                for k in (
                    "reference_id",
                    "action_id",
                    "map_id",
                    "node_id",
                    "choice_id",
                    "quest_id",
                    "item_reference",
                    "quantity",
                )
            )
            or row["quantity"] > 32767
        ):
            raise ValueError("Invalid reviewed NPC supply identity")
        seen.add(row["id"])
        for field in ("required_completed", "blocked_objectives"):
            values = row[field]
            if (
                not isinstance(values, list)
                or len(set(values)) != len(values)
                or any(type(value) is not int or value <= 0 for value in values)
            ):
                raise ValueError("Invalid reviewed NPC supply progress guard")
        source = dialogue_consumer_source(row, native)
        if digest(source) != row["native_source_sha256"]:
            raise ValueError("Reviewed NPC supply lost its exact native source")
        matching = [
            p
            for p in placements
            if p["row"]["reference_id"] == row["reference_id"]
            and row["action_id"] in p["row"]["action_ids"]
            and p["row"]["map_id"] == row["map_id"]
            and p["row"]["instance_id"] == 0
            and any(
                edge[:2] == [row["node_id"], row["choice_id"]]
                or tuple(edge[:2]) == (row["node_id"], row["choice_id"])
                for edge in p["graph"]
            )
        ]
        if len(matching) != 1 or row["quest_id"] not in {
            q["d"] for q in document["definitions"]
        }:
            raise ValueError(
                "Reviewed NPC supply lacks its published native choice/quest"
            )
    return rows


def quantity(character, reference):
    """Count the freshly reloaded owner's actual carried and quest inventories."""
    total = 0
    for field, owner_field, owner in (
        ("inventory_items", "character_id", character["id"]),
        ("quest_items", "character_id", character["id"]),
        ("account_quest_items", "account_id", character["account_id"]),
    ):
        for item in character.get(field, ()):
            if item.get(owner_field) == owner and item.get("reference") == reference:
                value = item.get("quantity")
                if type(value) is not int or value < 0:
                    raise ValueError("Invalid owned NPC supply quantity")
                total += value
    return total


def eligible(row, character, state):
    return (
        character["map_id"] == row["map_id"]
        and character.get("instance_id", 0) == 0
        and row["quest_id"] in state["running"]
        and row["quest_id"] not in state["completed"]
        and set(row["required_completed"]) <= set(state["completed"])
        and not set(row["blocked_objectives"]) & set(state["objectives"])
        and quantity(character, row["item_reference"]) == 0
    )


def settle(db, store, character, document, actor, *, node_id, choice_id):
    """Call only AFTER this exact source's real session choice was accepted."""
    from . import rewards, storage

    rows = [
        row
        for row in document.get(FIELD, ())
        if (row["reference_id"], row["map_id"], row["node_id"], row["choice_id"])
        == (actor["reference_id"], actor["map_id"], node_id, choice_id)
        and row["action_id"] in actor["action_ids"]
    ]
    if not rows:
        return []
    current = store.character(character["account_id"], character["id"], db)
    state = storage.load_locked(db, current["id"])
    packets = []
    for row in rows:
        if not eligible(row, current, state):
            continue
        packets.extend(
            rewards._item(db, store, current, row["item_reference"], row["quantity"])
        )
        # Missing-only recovery is intentional after a legitimate native cost
        # consumes a supply. Each accepted new choice gets its own receipt;
        # the owner lock and reloaded holdings make duplicates inert.
        fact = dict(
            policy=POLICY,
            contract=row["id"],
            actor_id=actor["actor_id"],
            node_id=node_id,
            choice_id=choice_id,
            item_reference=row["item_reference"],
            quantity=row["quantity"],
            native_source_sha256=row["native_source_sha256"],
        )
        if not storage.record_event(
            db, current["id"], "npc-supply:" + row["id"] + ":" + uuid4().hex, fact
        ):
            raise ValueError("Reviewed NPC supply receipt conflicts")
        current = store.character(character["account_id"], character["id"], db)
    return packets
