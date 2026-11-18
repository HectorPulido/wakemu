"""Source-qualified admission for disabled/reviewed native order trials.

Only the original twelve-byte object interaction selects a mode. This adapter
has no client score, recipe, form, spawn, spell or victory input. Its frozen
proof can be committed by the eventual native encounter owner; importing it
neither registers a route nor enables an incomplete arcade.
"""
from functools import lru_cache
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import struct

SOURCE_SHA256 = "546afc532186962d18478d49b2a483b224c59afda7d04ed52474b8ad71717c32"
_SCHEMA = "native-order-trial-admission-v1"
_PROFILE = (
    Path(__file__).parents[1]
    / "achievements/order_trial_profiles/astrub_pizzlarva_admission.json"
)


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Admission:
    profile_id: str
    profile_sha256: str
    owner_id: int
    account_id: int
    generation: object
    instance_id: int
    source_id: int
    source_map_id: int
    source_sha256: str
    descriptor_sha256: str
    effect_reference: int
    mode: str
    hard_mode: bool | None


@lru_cache(maxsize=1)
def _cached_document():
    raw = _PROFILE.read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Native order admission source has not been reviewed")
    return validate(json.loads(raw))


def document():
    """Return caller-owned capability data; the sealed default stays immutable."""
    from copy import deepcopy

    return deepcopy(_cached_document())


def validate(value):
    if (
        type(value) is not dict
        or set(value) != {"schema", "id", "enabled", "context", "sources", "evidence"}
        or value["schema"] != _SCHEMA
        or type(value["id"]) is not str
        or not value["id"]
        or type(value["enabled"]) is not bool
        or not isinstance(value["evidence"], str)
        or not value["evidence"]
        or set(value["sources"]) != {"entrance", "normal", "hard"}
        or type(value["context"]) is not dict
        or set(value["context"])
        != {"map_id", "arrival", "direction", "ownership_policy", "evidence"}
        or type(value["context"]["map_id"]) is not int
        or value["context"]["map_id"] <= 0
        or value["context"]["ownership_policy"]
        != "reviewed-solo-native-order-context-v1"
        or type(value["context"]["direction"]) is not int
        or not 0 <= value["context"]["direction"] < 8
        or not value["context"]["evidence"]
        or not isinstance(value["context"]["arrival"], list)
        or len(value["context"]["arrival"]) != 3
        or any(type(n) is not int for n in value["context"]["arrival"])
    ):
        raise ValueError(
            "Order trial requires an explicit reviewed admission capability"
        )
    identities = set()
    for kind, source in value["sources"].items():
        required = {
            "object_id",
            "map_id",
            "position",
            "wire_action",
            "wire_parameter",
            "descriptor",
            "original_payload_sha256",
            "descriptor_sha256",
            "approaches",
        }
        if (
            set(source) != required
            or source["object_id"] in identities
            or source["wire_action"] != 0
            or source["wire_parameter"] != 0
        ):
            raise ValueError("Ambiguous native order admission source")
        identities.add(source["object_id"])
        if (
            not isinstance(source["approaches"], list)
            or not source["approaches"]
            or any(
                not isinstance(p, list)
                or len(p) != 3
                or any(type(n) is not int for n in p)
                for p in source["approaches"]
            )
            or digest(source["descriptor"]) != source["descriptor_sha256"]
        ):
            raise ValueError("Native order admission lost its source/approach proof")
        groups = source["descriptor"]["groups"]
        actions = [
            (g, a, e)
            for g in groups
            for a in g["actions"]
            for e in a["effects"]
            if a["wire_action"] == source["wire_action"]
        ]
        if len(actions) != 1:
            raise ValueError("Native order source has no unique immediate action")
        group, action, effect = actions[0]
        if (
            group["cod"]
            or group["coe"]
            or group["cnd"]
            or group["cog"]
            or action["raw_cob"] != 1.0
            or effect["effect_type"] != (3 if kind == "entrance" else 1)
        ):
            raise ValueError("Unsupported native order source cost, timer or program")
        if kind == "entrance":
            from wakfu_server.exploration_artifact_actions import _teleport

            target, direction, delay = _teleport(effect)
            context = value["context"]
            if (
                delay
                or target["map_id"] != context["map_id"]
                or [target[a] for a in ("x", "y", "z")] != context["arrival"]
                or direction != context["direction"]
            ):
                raise ValueError(
                    "Order entry differs from its original coordinate program"
                )
        elif source["map_id"] != value["context"]["map_id"]:
            raise ValueError("Order mode belongs to another native context")
    return value


def plan(value, character, body, *, native_source):
    """Pure declaration/request planner; this does not authorize or mutate play."""
    validate(value)
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Order admission requires its original object interaction")
    identity, wire_action, parameter = struct.unpack(">qHH", body)
    selected = next(
        (
            (kind, s)
            for kind, s in value["sources"].items()
            if s["object_id"] == identity
        ),
        None,
    )
    if selected is None:
        raise ValueError("Unknown native order admission source")
    kind, source = selected
    if (
        wire_action != source["wire_action"]
        or parameter != source["wire_parameter"]
        or character["map_id"] != source["map_id"]
        or [character[a] for a in ("x", "y", "z")] not in source["approaches"]
        or (character.get("instance_id", 0) == 0) != (kind == "entrance")
        or native_source is None
        or native_source["id"] != source["object_id"]
        or native_source["map_id"] != source["map_id"]
        or native_source["type"] != "GenericActivableInteractiveElement"
        or [native_source[a] for a in ("x", "y", "z")] != source["position"]
        or sha256(bytes.fromhex(native_source["payload_hex"])).hexdigest()
        != source["original_payload_sha256"]
    ):
        raise ValueError("Order admission source, mode or actual position changed")
    payload = bytes.fromhex(native_source["payload_hex"])
    length = struct.unpack_from(">i", payload, 33)[0]
    if (
        not 0 < length <= 64
        or 37 + length > len(payload)
        or payload[37 : 37 + length].decode("ascii")
        != str(source["descriptor"]["descriptor_id"])
    ):
        raise ValueError("Order source no longer binds its original descriptor")
    from wakfu_server.native_interaction_approaches import _DIRECTIONS, _RELATIVE

    orientation = payload[30]
    mask = struct.unpack_from(">H", payload, 31)[0]
    if orientation >= 8 or mask > 511:
        raise ValueError("Native order source lost its original QV approach")
    offsets = {(0, 0)} if mask & 256 else set()
    offsets.update(
        _DIRECTIONS[(orientation + relative) % 8]
        for bit, relative in _RELATIVE
        if mask & bit
    )
    if any(
        (point[0] - native_source["x"], point[1] - native_source["y"]) not in offsets
        or abs(point[2] - native_source["z"]) > 4
        for point in source["approaches"]
    ):
        raise ValueError("Order admission approach differs from its native QV mask")
    group, action, effect = next(
        (g, a, e)
        for g in source["descriptor"]["groups"]
        for a in g["actions"]
        for e in a["effects"]
        if a["wire_action"] == wire_action
    )
    return Admission(
        value["id"],
        digest(value),
        character["id"],
        character["account_id"],
        None,
        character.get("instance_id", 0),
        identity,
        source["map_id"],
        digest(native_source),
        source["descriptor_sha256"],
        effect["action_reference"],
        kind,
        None if kind == "entrance" else kind == "hard",
    )


def qualify(
    db, store, account_id, generation, character, body, *, loaded, blocked, value=None
):
    """Qualify within the caller's transaction; no disabled capability can run."""
    from dataclasses import replace
    from wakfu_server import world_static, dungeon_runtime, dungeon_criteria
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    value = document() if value is None else validate(value)
    if value["enabled"] is not True or loaded is not True or blocked is not False:
        raise ValueError("Native order trial admission is not enabled and ready")
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    store.lock_character(db, account_id, generation, character["id"], selected=True)
    current = store.character(account_id, character["id"], db)
    if (
        current is None
        or current["account_id"] != account_id
        or any(
            current[k] != character[k] for k in ("map_id", "instance_id", "x", "y", "z")
        )
    ):
        raise ValueError("Native order source lost its selected owner or position")
    _idle(db, current["id"], store.now())
    source_id = (
        struct.unpack_from(">q", body)[0]
        if type(body) is bytes and len(body) == 12
        else None
    )
    actual = next(
        (s for s in world_static.objects(current["map_id"]) if s["id"] == source_id),
        None,
    )
    proof = plan(value, current, body, native_source=actual)
    if proof.mode != "entrance":
        row = db.execute(
            "SELECT i.start_map_id,i.entry_map_id,i.entry_object_id,i.entry_destination_id "
            "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
            "WHERE i.instance_id=%s AND m.character_id=%s AND m.status='active' FOR UPDATE OF i,m",
            (current["instance_id"], current["id"]),
        ).fetchone()
        members = db.execute(
            "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active' ORDER BY character_id FOR UPDATE",
            (current["instance_id"],),
        ).fetchall()
        entrance = value["sources"]["entrance"]
        entry_effect = next(
            e
            for g in entrance["descriptor"]["groups"]
            for a in g["actions"]
            for e in a["effects"]
        )
        if (
            row is None
            or members != [dict(character_id=current["id"])]
            or (
                row["start_map_id"],
                row["entry_map_id"],
                row["entry_object_id"],
                row["entry_destination_id"],
            )
            != (
                value["context"]["map_id"],
                entrance["map_id"],
                entrance["object_id"],
                entry_effect["action_reference"],
            )
        ):
            raise ValueError(
                "Order mode lacks its actual owned native entry membership"
            )
        _, configuration = dungeon_runtime.configuration_for_instance(
            db, current["instance_id"]
        )
        route = configuration["route"]
        metadata = route.get("native_generic_entry", {})
        pinned_source = metadata.get("source", {})
        if (
            (
                route["entry_map_id"],
                route["entry_object_id"],
                route["destination_id"],
                route["start_map_id"],
            )
            != (
                entrance["map_id"],
                entrance["object_id"],
                entry_effect["action_reference"],
                value["context"]["map_id"],
            )
            or route.get("registration_policy") != "native_generic_choice"
            or metadata.get("effect_reference") != entry_effect["action_reference"]
            or metadata.get("wire_action") != entrance["wire_action"]
            or metadata.get("approaches") != entrance["approaches"]
            or digest(metadata.get("program")) != entrance["descriptor_sha256"]
            or pinned_source.get("id") != entrance["object_id"]
            or pinned_source.get("map_id") != entrance["map_id"]
            or sha256(bytes.fromhex(pinned_source.get("payload_hex", ""))).hexdigest()
            != entrance["original_payload_sha256"]
        ):
            raise ValueError(
                "Order mode differs from its immutable entry configuration"
            )
    state = storage.load_locked(db, current["id"])
    authority = queries_from_state(state)
    source = next(
        s for s in value["sources"].values() if s["object_id"] == proof.source_id
    )
    for group in source["descriptor"]["groups"]:
        for action in group["actions"]:
            if action["wire_action"] == 0:
                if not all(
                    dungeon_criteria.evaluate(
                        store, expression, character=current, queries=authority
                    )
                    for expression in (
                        action["criterion"],
                        *(e["criterion"] for e in action["effects"]),
                    )
                ):
                    raise ValueError("Native order source criteria are not met")
    return replace(proof, generation=generation)


def start_trial(proof, *, encounter_id, orders, existing=None):
    """Bind an original mode to a real server encounter; replay cannot reroll it."""
    from wakfu_server.achievements import native_order_trials

    if (
        not isinstance(proof, Admission)
        or proof.generation is None
        or proof.mode not in ("normal", "hard")
        or type(proof.hard_mode) is not bool
    ):
        raise ValueError("A native mode source must qualify before order trial start")
    if existing is not None:
        if (
            not isinstance(existing, native_order_trials.OrderTrial)
            or existing.owner_id != proof.owner_id
            or existing.encounter_id != encounter_id
            or existing.hard_mode != proof.hard_mode
        ):
            raise ValueError(
                "An order trial cannot change its bound owner, encounter or mode"
            )
        return existing
    return native_order_trials.start(
        owner_id=proof.owner_id,
        encounter_id=encounter_id,
        hard_mode=proof.hard_mode,
        orders=orders,
    )
