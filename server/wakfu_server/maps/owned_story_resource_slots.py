"""Instantiate pinned native harvest resources for one existing story owner.

The profile supplies original resource/action/loot definitions and reviewed
legal floor placements. It grants no objective or product on arrival: normal
leased harvest occupations own duration, depletion, random draw and delivery.
"""
from copy import deepcopy
import secrets

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics
from wakfu_server import quest_resource_slots


def _template(selected):
    native = mechanics.sources(selected)
    value = native.get("resource_slots")
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or value.get("map_id") != selected["map_id"]
        or value.get("owned_story") is not None
    ):
        raise ValueError("Owned story resource template differs from its native source")
    for action in value.get("resource_actions", ()):
        loot = action.get("native_loot")
        if loot is None:
            continue
        proof = native.get("harvest_getter_proofs", {}).get(str(action["action_id"]))
        if (
            not isinstance(proof, dict)
            or quest_resource_slots.digest(proof) != loot["source_sha256"]
            or proof.get("resource_reference") != action["resource_reference"]
            or proof.get("stage") != action["stage"]
            or proof.get("action_id") != action["action_id"]
            or proof.get("native_class") != "aNn"
            or proof.get("native_loot_getter") != "csO"
            or proof.get("loot_table") != loot["table_id"]
            or value.get("loot_tables", {}).get(str(loot["table_id"]))
            != native.get("loot_tables", {}).get(str(loot["table_id"]))
        ):
            raise ValueError("Owned harvest lost its original native loot getter proof")
    return deepcopy(value)


def authorize(db, store, character, profile):
    """Recheck durable membership and immutable source before every occupation."""
    selected, _ = controller._scope(db, store, character)
    scope = profile.get("owned_story", {})
    if scope != dict(
        controller_id=selected["id"],
        owner_id=character["id"],
        instance_id=character["instance_id"],
        native_sources_sha256=selected["native_sources"]["sha256"],
    ):
        raise ValueError("Quest resource escaped its original private story owner")
    template = _template(selected)
    actual = deepcopy(profile)
    actual.pop("owned_story", None)
    if template is None or len(template["placements"]) != len(actual["placements"]):
        raise ValueError("Owned resources lost their finite native source")
    for source, row in zip(template["placements"], actual["placements"]):
        row["resource_uid"] = source["resource_uid"]
    if actual != template:
        raise ValueError("Owned resource policy changed after source publication")


def approachable(db, character, placement):
    """Keep the native harvest's ordinary adjacent-floor approach choices."""
    from wakfu_server import dungeon_runtime

    configuration = dungeon_runtime.configuration_for_instance(
        db, character["instance_id"]
    )[1]
    geometry = configuration["topology"]["exploration_geometry"]
    origin = [character[k] for k in ("x", "y", "z")]
    return [origin, placement["position"]] in geometry["edges"]


def ensure(db, store, character, selected, configuration):
    """Create stable resources once within the ordinary leased story transaction."""
    profile = _template(selected)
    if profile is None:
        return []
    from wakfu_server.achievements import storage, mission_toolkit

    progress = storage.load_locked(db, character["id"])
    if profile["quest_id"] not in progress["running"]:
        return []
    existing = db.execute(
        "SELECT policy FROM quest_resource_slots WHERE instance_id=%s AND profile_id=%s ORDER BY resource_uid",
        (character["instance_id"], profile["id"]),
    ).fetchall()
    if existing:
        if len(existing) != len(profile["placements"]):
            raise ValueError("Owned quest resource slots are missing or duplicated")
        authorize(db, store, character, existing[0]["policy"])
        return []
    # _scope takes the existing instance/member lock before this call. Another
    # session cannot allocate a second pool for the same immutable private run.
    profile["owned_story"] = dict(
        controller_id=selected["id"],
        owner_id=character["id"],
        instance_id=character["instance_id"],
        native_sources_sha256=selected["native_sources"]["sha256"],
    )
    for placement in profile["placements"]:
        placement["resource_uid"] = secrets.randbelow(2**63 - 1) + 1
    definitions = mission_toolkit.definitions(
        db,
        dict(bindings=[dict(quest_id=profile["quest_id"])], links=[], activations=[]),
    )
    quest_resource_slots.install(
        db,
        store,
        profile,
        definitions,
        configuration["topology"]["exploration_geometry"],
    )
    from wakfu_server.planting import resource_packet

    rows = db.execute(
        "SELECT p.* FROM planted_resources p JOIN quest_resource_slots q USING(resource_uid) "
        "WHERE q.instance_id=%s AND q.profile_id=%s ORDER BY p.resource_uid",
        (character["instance_id"], profile["id"]),
    ).fetchall()
    db.execute(
        "UPDATE planting_growth_outbox SET published=TRUE WHERE resource_uid=ANY(%s)",
        ([row["resource_uid"] for row in rows],),
    )
    return [resource_packet(row) for row in rows]
