"""Reviewed physical visits offered beside actual owned-story entrances.

Native client teleport menus can omit quest-gated destinations completely. These
separate, explicitly labelled native actors offer the same installed route. They
never assign a quest or replace an entrance price or its source authority.
"""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json
import struct

from wakfu_server import dungeon_instances, dungeon_transport, generic_transports
from wakfu_server import owned_physical_entry, owned_story_controller

_BASE = -4400000000000000
_SPAN = 1 << 32
SOURCE_SHA256 = "f843d8a1560ee707b212a72c2ccb7db95e49c7ddb1c685b4c1efe52991920e78"
SOURCE_FILES = (
    ("astrub-cemetery-nest.json", SOURCE_SHA256),
    (
        "bovis-lair-1002.json",
        "0047e1f18d8dcd79ac70fd66a194cb19f99030b3b867c0a00126aebbdaa1d4d5",
    ),
    (
        "archaeology-2698.json",
        "8150f2e6eceae762edb87055066cdcb0c12b16ff9d4b6893598e4b9f4a35457d",
    ),
    (
        "kelba-lair-951.json",
        "4ce6aa1726f8a3da59196bfed48ac8a4dd40f730d74a4e14e95608398863d555",
    ),
)


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def policy():
    """Finite, reviewed capabilities; no visible-quest or route-name inference."""
    from wakfu_server import npc_dialogue

    document = None
    for filename, expected in SOURCE_FILES:
        raw = (
            Path(__file__)
            .with_name("owned_physical_offer_profiles")
            .joinpath(filename)
            .read_bytes()
        )
        if sha256(raw).hexdigest() != expected:
            raise ValueError("Physical entrance offer source has not been reviewed")
        current = json.loads(raw)
        if (
            set(current) != {"schema", "version", "appearance", "offers"}
            or current["schema"] != "owned-physical-offers-v1"
            or current["version"] != 1
        ):
            raise ValueError("Unsupported physical entrance capability")
        if document is None:
            document = current
        else:
            if current["appearance"] != document["appearance"]:
                raise ValueError(
                    "Physical entrance sources disagree on native presentation"
                )
            document["offers"].extend(current["offers"])
    appearance = document["appearance"]
    if set(appearance) != {
        "reference_id",
        "action_id",
        "speaker_sha256",
        "action_sha256",
    }:
        raise ValueError("Physical entrance has malformed native presentation")
    native = npc_dialogue.catalog()
    speaker = next(
        (r for r in native["speakers"] if r["ref"] == appearance["reference_id"]), None
    )
    action = next(
        (
            r
            for r in (speaker or {}).get("actions", ())
            if r["id"] == appearance["action_id"]
        ),
        None,
    )
    if (
        speaker is None
        or action is None
        or action["type"] != 4
        or action["criteria"]
        or _digest(speaker) != appearance["speaker_sha256"]
        or _digest(action) != appearance["action_sha256"]
    ):
        raise ValueError(
            "Physical entrance model/action differs from its original native source"
        )
    identities, sources = set(), set()
    for offer in document["offers"]:
        if (
            set(offer)
            != {
                "route_key",
                "policy_version",
                "configuration_sha256",
                "source_map_id",
                "source_id",
                "destination_id",
                "native_source_sha256",
                "label",
                "evidence",
            }
            or any(
                type(offer[k]) is not int or offer[k] <= 0
                for k in (
                    "policy_version",
                    "source_map_id",
                    "source_id",
                    "destination_id",
                )
            )
            or not offer["route_key"]
            or not offer["label"]
            or not offer["evidence"]
        ):
            raise ValueError("Malformed physical entrance capability")
        source = (offer["source_map_id"], offer["source_id"])
        if offer["route_key"] in identities or source in sources:
            raise ValueError("Physical entrance offers overlap at one native source")
        identities.add(offer["route_key"])
        sources.add(source)
    return document


def _declaration(configuration, source):
    route = configuration["route"]
    for offer in policy()["offers"]:
        if offer["route_key"] == route["key"] and (
            offer["policy_version"] == configuration["version"]
            and offer["configuration_sha256"] == _digest(configuration)
            and offer["native_source_sha256"] == _digest(source)
            and (offer["source_map_id"], offer["source_id"], offer["destination_id"])
            == (
                route["entry_map_id"],
                route["entry_object_id"],
                route["destination_id"],
            )
        ):
            return offer
    return None


def actor_id(route_key, configuration_sha256, source_sha256):
    # A newly published immutable policy invalidates an old rendered offer UID.
    identity = route_key + ":" + configuration_sha256 + ":" + source_sha256
    return _BASE + int(sha256(identity.encode()).hexdigest()[:8], 16)


def recognizes(opcode, body):
    if opcode != 13222 or not isinstance(body, bytes) or len(body) != 16:
        return False
    identity, _ = struct.unpack(">qq", body)
    return _BASE <= identity < _BASE + _SPAN


def _owned_policy(configuration):
    from wakfu_server.achievements import owned_quest_encounters
    from wakfu_server import owned_object_trials

    topology = configuration.get("topology", {})
    validators = (
        ("owned_story_controller", owned_story_controller.policy),
        ("owned_quest_encounter", owned_quest_encounters.policy),
        ("owned_object_trials", owned_object_trials.policy),
    )
    selected = [
        validate for name, validate in validators if topology.get(name) is not None
    ]
    if len(selected) != 1 or selected[0](configuration) is None:
        raise ValueError("Physical entrance lacks one typed owned policy")


def _row(configuration):
    route = configuration["route"]
    _owned_policy(configuration)
    source = generic_transports.source(route["entry_map_id"], route["entry_object_id"])
    if source is None:
        raise ValueError("Physical entrance lost its original native source")
    declaration = _declaration(configuration, source)
    if declaration is None:
        raise ValueError("Physical entrance lacks its reviewed capability")
    appearance = policy()["appearance"]
    positions = source.get("approach_positions")
    if not isinstance(positions, list) or not positions:
        raise ValueError("Physical entrance has no published native approach")
    anchor = positions[0]
    if any(type(anchor.get(axis)) is not int for axis in ("x", "y", "z")):
        raise ValueError("Physical entrance has malformed native approach")
    destination = next(
        (
            d
            for d in source["destinations"]
            if d["destination_id"] == route["destination_id"]
        ),
        None,
    )
    if destination is None or destination["criterion"] != route["criterion"]:
        raise ValueError("Physical entrance differs from its native destination")
    if not any(
        name in route["criterion"] for name in owned_physical_entry._MISSION_NAMES
    ):
        raise ValueError("Physical offer does not waive a mission menu gate")
    proof = dict(
        route_key=route["key"],
        policy_version=configuration["version"],
        configuration_sha256=_digest(configuration),
        source_id=source["id"],
        destination_id=route["destination_id"],
        source_sha256=_digest(source),
    )
    row = dict(
        actor_id=actor_id(
            route["key"], proof["configuration_sha256"], proof["source_sha256"]
        ),
        reference_id=appearance["reference_id"],
        map_id=route["entry_map_id"],
        instance_id=0,
        x=int(source["x"]),
        y=int(source["y"]),
        z=int(source["z"]),
        direction=3,
        action_ids=[appearance["action_id"]],
        action_type=4,
        action_criterion="",
        interaction_range=1,
        interaction_anchor=dict(anchor),
        provenance="Reviewed source-bound physical entrance offer; native model/action, not an original actor placement.",
        _physical_offer=proof,
        _physical_offer_label=declaration["label"],
    )
    if destination.get("cyW", 0) > 0 or destination.get("cyX", 0) > 0:
        row["_physical_offer_label"] += " (entry cost applies)"
    row["_physical_offer_sha256"] = _digest(row)
    return row


def placement(row):
    """Attest only this publisher's independent native actor presentation."""
    if type(row) is not dict or "_physical_offer" not in row:
        return False
    candidate = dict(row)
    digest = candidate.pop("_physical_offer_sha256", None)
    proof = candidate.get("_physical_offer")
    if (
        not isinstance(proof, dict)
        or set(proof)
        != {
            "route_key",
            "policy_version",
            "configuration_sha256",
            "source_id",
            "destination_id",
            "source_sha256",
        }
        or digest != _digest(candidate)
        or not {
            "map_id",
            "actor_id",
            "reference_id",
            "action_ids",
            "instance_id",
            "action_criterion",
            "x",
            "y",
            "z",
            "interaction_anchor",
            "_physical_offer_label",
        }
        <= row.keys()
    ):
        return False
    source = generic_transports.source(row["map_id"], proof["source_id"])
    destination = next(
        (
            d
            for d in (source or {}).get("destinations", ())
            if d["destination_id"] == proof["destination_id"]
        ),
        {},
    )
    suffix = (
        " (entry cost applies)"
        if destination.get("cyW", 0) > 0 or destination.get("cyX", 0) > 0
        else ""
    )
    declared = any(
        offer["route_key"] == proof["route_key"]
        and row["_physical_offer_label"] == offer["label"] + suffix
        and offer["policy_version"] == proof["policy_version"]
        and offer["configuration_sha256"] == proof["configuration_sha256"]
        and offer["native_source_sha256"] == proof["source_sha256"]
        and (offer["source_map_id"], offer["source_id"], offer["destination_id"])
        == (row["map_id"], proof["source_id"], proof["destination_id"])
        for offer in policy()["offers"]
    )
    return bool(
        declared
        and source is not None
        and _digest(source) == proof["source_sha256"]
        and tuple(row[axis] for axis in ("x", "y", "z"))
        == tuple(int(source[axis]) for axis in ("x", "y", "z"))
        and row["interaction_anchor"] in source.get("approach_positions", ())
        and row["actor_id"]
        == actor_id(
            proof["route_key"], proof["configuration_sha256"], proof["source_sha256"]
        )
        and row["reference_id"] == policy()["appearance"]["reference_id"]
        and row["action_ids"] == [policy()["appearance"]["action_id"]]
        and row["instance_id"] == 0
        and row["action_criterion"] == ""
    )


def rows(db, store, character):
    if character.get("instance_id", 0) != 0:
        return ()
    declarations = {
        r["route_key"]: r
        for r in policy()["offers"]
        if r["source_map_id"] == character["map_id"]
    }
    if not declarations:
        return ()
    installed = db.execute(
        "SELECT q.configuration FROM dungeon_runtime_active_configurations a "
        "JOIN dungeon_runtime_configurations q ON q.route_key=a.route_key "
        "AND q.policy_version=a.policy_version WHERE "
        "(q.configuration->'route'->>'entry_map_id')::bigint=%s "
        "AND (q.configuration->'topology'->'owned_story_controller' IS NOT NULL "
        "OR q.configuration->'topology'->'owned_quest_encounter' IS NOT NULL "
        "OR q.configuration->'topology'->'owned_object_trials' IS NOT NULL) "
        "ORDER BY a.route_key",
        (character["map_id"],),
    ).fetchall()
    result, seen = [], set()
    for record in installed:
        config = record["configuration"]
        if config["route"]["key"] not in declarations:
            continue
        # NPC-choice and generic-action journeys already have distinct visible
        # producers; they are not native teleport menus and must not be aliased.
        if config["route"].get("registration_policy") in (
            "native_npc_choice",
            "native_generic_choice",
        ):
            continue
        source = generic_transports.source(
            config["route"]["entry_map_id"], config["route"]["entry_object_id"]
        )
        if source is None:
            continue
        positions = source.get("approach_positions")
        if (
            not isinstance(positions, list)
            or not positions
            or any(
                not isinstance(point, dict)
                or any(type(point.get(axis)) is not int for axis in ("x", "y", "z"))
                for point in positions
            )
        ):
            # An optional attendant cannot invent an approach for an ordinary
            # zero-mask source, nor make the map bootstrap fail for its absence.
            continue
        try:
            route = dungeon_instances.route(config["route"]["key"])
        except ValueError:
            # An optional offer cannot expose a newly installed route before
            # this World has loaded its normal transport registration.
            continue
        if route is None or not owned_physical_entry.qualifies(store, route, db=db):
            continue
        if _declaration(config, source) is None:
            continue
        row = _row(config)
        if row["actor_id"] in seen:
            raise ValueError("Physical entrance actor identity collision")
        seen.add(row["actor_id"])
        result.append(row)
    return tuple(result)


def resolve(db, store, character, identity, action):
    """Requalify actual visible source identity and the original paid route."""
    row = next(
        (r for r in rows(db, store, character) if r["actor_id"] == identity), None
    )
    if row is None or action not in row["action_ids"] or not placement(row):
        raise ValueError("Physical entrance offer is no longer available")
    proof = row["_physical_offer"]
    resolved = dungeon_transport.resolve_route(
        row["map_id"], proof["source_id"], proof["destination_id"]
    )
    if resolved is None or resolved["route"].key != proof["route_key"]:
        raise ValueError("Physical entrance route changed")
    return row, resolved


def spawn_packets(db, store, character):
    from wakfu_server import npc_world

    return tuple(
        npc_world.spawn(row, enabled_actions=row["action_ids"])
        for row in rows(db, store, character)
    )
