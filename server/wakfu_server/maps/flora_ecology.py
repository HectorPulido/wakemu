"""Personal ecology participates in the caller's successful flora transaction."""
from .planting_cells import surface
from .ecology_population import snapshot
from .ecology_policy import decision
from .personal_ecology import apply
from .planting import RESOURCES
from .ecology_feedback import describe, information
from .resource_domains import is_mineral, is_fish


def change(db, character_id, resource, *, operation, action):
    if action not in ("plant", "remove", "harvest"):
        raise ValueError("Invalid flora ecology action")
    if is_fish(resource["resource_reference"]):
        return {"packets": [], "reason": "fish_not_ecological"}
    if is_mineral(resource["resource_reference"]):
        return {"packets": [], "reason": "mineral_not_ecological"}
    if resource["map_id"] == 9 or (
        resource["map_id"] == 1440 and resource["instance_id"] > 0
    ):
        # Private gardens never modify exterior ecology or personal affinity.
        return {"packets": [], "reason": "private_haven_bag_garden"}
    definition = RESOURCES[resource["resource_reference"]]
    if definition["monster_resource"]:
        message = (
            "Ecosistema: semilla de monstruo plantada. Todavía no cuenta como "
            "población viva; la afinidad se evalúa cuando nace el monstruo."
            if action == "plant"
            else "Ecosistema: esta semilla no es un monstruo vivo; "
            "esta acción no modifica tu afinidad Wakfu/Stasis."
        )
        return {
            "packets": [information(message)],
            "reason": "monster_seed_not_living_population",
        }
    map_id, instance_id = resource["map_id"], resource["instance_id"]
    # Independent flora lock avoids inverting monster group/row locks.
    # Both planting and removal take it before their population mutation.
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"flora-population:{map_id}:{instance_id}",),
    )
    try:
        region_id = surface(map_id, resource["x"], resource["y"], resource["z"])[
            "region_id"
        ]
    except ValueError:
        return {
            "packets": [
                information(
                    "Ecosistema: región del recurso no disponible; "
                    "no se aplica un cambio de afinidad sin esos datos."
                )
            ],
            "reason": "native_region_unavailable",
        }
    if type(region_id) is int and region_id == -1:
        return {"packets": [], "reason": "native_unassigned_terrain"}
    population = snapshot(
        db,
        map_id,
        instance_id,
        kinds=("plant",),
        locate=surface,
        exclude_unassigned=True,
    )
    if not population["complete"] or not region_id:
        return {
            "packets": [
                information(
                    "Ecosistema: población regional incompleta; "
                    "no se aplica un cambio de afinidad sin esos datos."
                )
            ],
            "reason": "incomplete_native_population",
        }
    family = definition["family_id"]
    counts = population["regions"].get(region_id, {}).get("plant", {})
    result = decision(
        db,
        map_id=map_id,
        region_id=region_id,
        kind="plant",
        family_id=family,
        action=action,
        before=counts.get(family, 0),
    )
    result["evidence"]["resource_uid"] = resource["resource_uid"]
    result["evidence"]["resource_reference"] = resource["resource_reference"]
    applied = apply(db, character_id, operation=operation, **result)
    packets = [applied["packet"]]
    if not applied["duplicate"]:
        packets.append(information(describe(applied["receipt"])))
    return {"packets": packets, "receipt": applied["receipt"], "reason": "applied"}
