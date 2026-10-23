"""Neutral feedback for extracting a living monster's renewable product."""
from .ecology_population import snapshot
from .ecology_policy import decision
from .ecology_feedback import describe, information
from .personal_ecology import apply
from .ecology_context import population_region
from .monsters import reference


def change(db, character_id, monster, *, operation, locate=population_region):
    map_id, instance_id = monster["map_id"], monster["instance_id"]
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"monster-population:{map_id}:{instance_id}",),
    )
    from .environmental_group_ecology import owned_monster_ids

    if monster["id"] in owned_monster_ids(db, map_id, instance_id):
        return []
    population = snapshot(
        db,
        map_id,
        instance_id,
        kinds=("monster",),
        locate=locate,
        exclude_unassigned=True,
    )
    try:
        region = locate(map_id, *(monster[key] for key in ("x", "y", "z")))["region_id"]
    except ValueError:
        region = 0
    if not population["complete"] or type(region) is not int or region <= 0:
        return [
            information(
                "Ecosistema: extraer este producto no elimina al monstruo "
                "ni cambia tu afinidad. Población regional no disponible."
            )
        ]
    family = reference(monster["ref"])["family_id"]
    before = population["regions"].get(region, {}).get("monster", {}).get(family, 0)
    evaluation = decision(
        db,
        map_id=map_id,
        region_id=region,
        kind="monster",
        family_id=family,
        action="harvest",
        before=before,
    )
    evaluation["evidence"]["monster_id"] = monster["id"]
    result = apply(db, character_id, operation=operation, **evaluation)
    return [] if result["duplicate"] else [information(describe(result["receipt"]))]
