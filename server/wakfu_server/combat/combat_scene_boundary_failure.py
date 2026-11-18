"""Opt-in encounter loss after an authentic native battleground contact.

Native border callbacks still execute unchanged. This reviewed server rule adds
the challenge outcome that is absent from the client prototype; it does not
manufacture damage, death, withdrawal or quest completion.
"""

from copy import deepcopy

SCHEMA = "owned-boundary-failure-v1"
SOURCE = "wakemu.reviewed_native_boundary_loss.v1"
CONTACT_EVENTS = frozenset((10000, 10001, 10008))


def declaration(descriptor):
    value = descriptor.get("native_boundary_failure")
    if value is None:
        return None
    if (
        type(value) is not dict
        or set(value)
        != {"schema", "border_reference", "losing_role", "outcome", "evidence"}
        or value["schema"] != SCHEMA
        or type(value["border_reference"]) is not int
        or value["border_reference"] <= 0
        or descriptor.get("native_border_reference") != value["border_reference"]
        or descriptor.get("full_room_scope") is not True
        or value["losing_role"] != "original_controlled"
        or value["outcome"] != "opposing_team_wins"
        or type(value["evidence"]) is not str
        or not value["evidence"].strip()
    ):
        raise ValueError("Encounter boundary failure lacks its explicit source policy")
    return value


def prepare_contact(fight, row, target, event_id):
    """Capture contact before the original border may move the player away."""
    record = getattr(fight, "native_encounter_scene", None)
    if (
        record is None
        or record.get("descriptor", {}).get("native_boundary_failure") is None
        or row.get("native_area_contract") != "faP"
        or event_id not in CONTACT_EVENTS
        or fight.phase != "active"
    ):
        return None
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles
    from .combat_battleground_border import verify_battleground_border
    from .combat_effect_area_geometry import contains_area_cell

    policy = declaration(frozen_scene(fight))
    roles = assigned_roles(fight)
    if (
        row.get("reference") != policy["border_reference"]
        or fight.native_effect_areas.get(row.get("uid")) is not row
        or target is None
        or fight.actors.get(target.id) is not target
        or target.controlled is not True
        or target.team != roles.player_team
        or target.owner_id is None
        or getattr(target, "native_summon_source", None) is not None
        or getattr(target, "is_summon", False)
        or not fight._in_play(target)
        or not contains_area_cell(row, target.position)
    ):
        return None
    verify_battleground_border(fight, row)
    if getattr(fight, "native_encounter_objective_policy", None) is not None:
        raise ValueError(
            "Encounter boundary failure conflicts with its result director"
        )
    return dict(
        source=SOURCE,
        schema=SCHEMA,
        fight_id=fight.id,
        scene_sha256=record["sha256"],
        scope=deepcopy(record["scope"]),
        actor_id=target.id,
        owner_id=target.owner_id,
        losing_team=roles.player_team,
        winning_team=roles.npc_team,
        border_reference=policy["border_reference"],
        area_uid=row["uid"],
        event_id=event_id,
        contact_cell=list(target.position),
    )


def settle_contact(fight, contact):
    """Use normal terminal publication after the genuine native callback."""
    if contact is None:
        return False
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles

    descriptor = frozen_scene(fight)
    policy = declaration(descriptor)
    if policy is None or type(contact) is not dict:
        raise ValueError("Encounter boundary result lost its explicit source policy")
    actor = fight.actors.get(contact["actor_id"])
    roles = assigned_roles(fight)
    if (
        contact.get("source") != SOURCE
        or contact.get("schema") != SCHEMA
        or contact.get("fight_id") != fight.id
        or contact.get("scene_sha256") != fight.native_encounter_scene["sha256"]
        or contact.get("scope") != fight.native_encounter_scene["scope"]
        or contact.get("border_reference") != policy["border_reference"]
        or contact.get("losing_team") != roles.player_team
        or contact.get("winning_team") != roles.npc_team
        or actor is None
        or actor.owner_id != contact["owner_id"]
        or actor.controlled is not True
        or actor.team != roles.player_team
    ):
        raise ValueError("Encounter boundary result lost its authentic contact")
    previous = getattr(fight, "native_boundary_failure_receipt", None)
    if previous is not None:
        if previous != contact:
            raise ValueError("Encounter already settled a different boundary failure")
        return False
    # The native callback can itself end a fight. Preserve that original result.
    if fight.phase != "active":
        return False
    fight.native_boundary_failure_receipt = deepcopy(contact)
    fight.phase = "finished"
    fight.winner = roles.npc_team
    fight._event(
        "finished",
        winner=fight.winner,
        reason="owned_scene_boundary_failure",
        actor_id=actor.id,
        border_reference=policy["border_reference"],
    )
    return True
