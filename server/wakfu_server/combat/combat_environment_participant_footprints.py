"""Exact pre-snapshot actor footprints for declared environmental placement."""
SCHEMA = "wakemu-initial-environment-participants-v1"


def participant_footprints(character, members, *, catalog=None):
    if catalog is None:
        from .combat_actor_snapshot import native_actor_catalog

        catalog = native_actor_catalog()
    actors = [
        dict(
            id=character["id"],
            reference=None,
            position=[character[k] for k in ("x", "y", "z")],
            physical_radius=catalog["default_actor_radius"],
            source="native-actor-characteristics.default_actor_radius",
        )
    ]
    for member in members:
        profile = catalog["npc_profiles"].get(str(member["ref"]))
        if not isinstance(profile, dict):
            raise ValueError("Missing exact initial environment NPC profile")
        actors.append(
            dict(
                id=member["id"],
                reference=member["ref"],
                position=[member[k] for k in ("x", "y", "z")],
                physical_radius=profile["physical_radius"],
                source="native-actor-characteristics.npc_profiles.physical_radius",
            )
        )
    return dict(schema=SCHEMA, map_id=character["map_id"], actors=actors)


def verified_participant_cells(fight, arena, *, catalog=None):
    """Validate frozen IDs, roles, positions and native radii before QI snapshots."""
    record = arena.get("native_environment_participant_footprints")
    if record is None:
        return None
    from .combat_encounter_roles import assigned_roles
    from .combat_obstacle_condition import footprint

    if catalog is None:
        from .combat_actor_snapshot import native_actor_catalog

        catalog = native_actor_catalog()
    roles = assigned_roles(fight)
    if (
        not isinstance(record, dict)
        or set(record) != {"schema", "map_id", "actors"}
        or record["schema"] != SCHEMA
        or record["map_id"] != arena["map_id"]
        or roles.map_id != arena["map_id"]
        or not isinstance(record["actors"], list)
    ):
        raise ValueError("Missing frozen environment participant scope")
    seen, references, occupied = set(), [], set()
    for row in record["actors"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "reference", "position", "physical_radius", "source"}
            or type(row["id"]) is not int
            or row["id"] in seen
            or not isinstance(row["position"], (list, tuple))
            or len(row["position"]) != 3
            or any(type(value) is not int for value in row["position"])
        ):
            raise ValueError("Invalid frozen environment participant identity")
        actor = fight.actors.get(row["id"])
        if actor is None or tuple(row["position"]) != tuple(actor.position):
            raise ValueError("Environment participant position changed")
        reference = row["reference"]
        if reference is None:
            radius = catalog["default_actor_radius"]
            source = "native-actor-characteristics.default_actor_radius"
            team = roles.player_team
            if actor.controlled is not True:
                raise ValueError("Environment player is not a controlled participant")
        else:
            if type(reference) is not int:
                raise ValueError("Invalid initial environment native breed")
            profile = catalog["npc_profiles"].get(str(reference))
            if not isinstance(profile, dict):
                raise ValueError("Missing initial environment native breed profile")
            radius = profile["physical_radius"]
            source = "native-actor-characteristics.npc_profiles.physical_radius"
            team = roles.npc_team
            from .combat_encounter_scene_helpers import helper_initial_team

            helper_team = helper_initial_team(fight, actor.id)
            if helper_team is not None:
                team = helper_team
            references.append(reference)
            if actor.controlled is not False:
                raise ValueError("Environment NPC is a controlled participant")
        if (
            actor.team != team
            or row["source"] != source
            or type(row["physical_radius"]) is not int
            or row["physical_radius"] != radius
            or actor.physical_radius is not None
            and actor.physical_radius != radius
        ):
            raise ValueError("Environment participant native footprint changed")
        occupied.update(footprint(actor.position, radius))
        seen.add(actor.id)
    if (
        seen != set(fight.actors)
        or tuple(sorted(references)) != roles.monster_references
    ):
        raise ValueError("Environment participants differ from the admitted roster")
    return occupied
