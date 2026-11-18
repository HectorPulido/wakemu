"""Compile reviewed one-room quest instances onto the existing dungeon runtime.

Species/count/arena declarations are explicit reconstruction policy. Map cells,
statistics, transport criteria and costs remain their installed native sources.
"""

from wakfu_server import dungeon_runtime_config as configurations

SCHEMA = "owned-quest-instance-v1"


def native_running_gate(criterion, quest_id):
    """Accept the exact original one-quest native admission predicate spellings."""
    return criterion in (
        f"IsAchievementRunning({quest_id})",
        f"IsAchievementActive({quest_id})",
    )


def reviewed_entry_gate(criterion, quest_id, declaration):
    """An explicitly reviewed empty native gate retains the owned quest fence.

    Ordinary profiles still require an exact native running predicate. Empty
    native criteria are preserved rather than rewritten into invented catalog
    data; initialize independently requires the declared quest to be running.
    """
    if "native_entry_criterion" in declaration:
        return declaration["native_entry_criterion"] == "" and criterion == ""
    return native_running_gate(criterion, quest_id)


def reviewed_reentry_quests(declaration):
    """Only explicit follow-up IDs can reopen a completed quest encounter."""
    if "reentry_quests" not in declaration:
        return ()
    values = declaration["reentry_quests"]
    if (
        not isinstance(values, list)
        or not values
        or any(type(value) is not int or value <= 0 for value in values)
        or len(set(values)) != len(values)
        or declaration.get("quest_id") in values
    ):
        raise ValueError("Quest reentry requires explicit distinct follow-up quests")
    return tuple(values)


def reviewed_pending_reentry(declaration):
    """A declared missed optional goal need not already be an active quest."""
    value = declaration.get("pending_reentry")
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"all_completed", "none_completed"}:
        raise ValueError("Invalid pending optional quest reentry declaration")
    for values in value.values():
        if (
            not isinstance(values, list)
            or not values
            or any(type(quest) is not int or quest <= 0 for quest in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError(
                "Pending optional reentry requires explicit quest identities"
            )
    if set(value["all_completed"]) & set(value["none_completed"]):
        raise ValueError("Pending optional reentry has contradictory quest guards")
    return value


def reviewed_owned_policy(configuration):
    """Qualify only declared controllers with strict solo admission contracts."""
    from wakfu_server.achievements.owned_quest_encounters import policy

    selected = policy(configuration)
    if selected is None:
        from wakfu_server import owned_noncombat_context

        selected = owned_noncombat_context.selected(configuration["topology"])
    if (
        selected is None
        and configuration["topology"].get("owned_story_controller") is not None
    ):
        from wakfu_server import owned_story_controller

        selected = owned_story_controller.policy(configuration)
        if selected is None:
            raise ValueError(
                "Owned story controller did not validate its solo admission policy"
            )
    if selected is not None and (
        type(selected.get("maximum_members")) is not int
        or selected["maximum_members"] != 1
    ):
        raise ValueError("Quest route requires an authenticated solo admission policy")
    return selected


def merge_runtime_routes(routes, configurations):
    """Add only explicitly activated quest routes; preserve every ordinary route."""
    from wakfu_server.dungeon_instances import _load_routes

    result = dict(routes)
    for configuration in configurations:
        if reviewed_owned_policy(configuration) is None:
            continue
        qualified = _load_routes([configuration["route"]])
        for key, selected in qualified.items():
            identity = (
                selected.entry_map_id,
                selected.entry_object_id,
                selected.destination_id,
            )
            if key in result and result[key] != selected:
                raise ValueError(
                    "Quest route conflicts with an installed route identity"
                )
            if any(
                (row.entry_map_id, row.entry_object_id, row.destination_id) == identity
                and row != selected
                for row in result.values()
            ):
                raise ValueError("Quest entrance already belongs to another route")
            result[key] = selected
    return result


def compile_profile(profile, *, geometry, exploration, sources, monster):
    if profile.get("schema") != SCHEMA or not profile.get("provenance"):
        raise ValueError("Quest instance requires explicit reconstruction provenance")
    for key in ("quest_id", "entry_objective", "victory_objective", "monster_count"):
        if type(profile.get(key)) is not int or profile[key] <= 0:
            raise ValueError("Quest instance has an invalid objective or roster")
    reviewed_reentry_quests(profile)
    reviewed_pending_reentry(profile)
    if (
        geometry.map_id != profile["map_id"]
        or monster["ref"] != profile["monster_reference"]
    ):
        raise ValueError("Quest instance native identity differs")
    if (
        exploration.get("map_id") != geometry.map_id
        or exploration.get("profile")
        != dict(height=6, movement_type=0, jump_capacity=4, native_class="Sm")
        or not exploration.get("client_sha256")
        or not exploration.get("topology_sha256")
    ):
        raise ValueError(
            "Quest walking topology requires the native player exploration profile"
        )
    from wakfu_server.combat_geometry import prepare_geometry

    walking = prepare_geometry(exploration)
    source = sources[(profile["entry_map_id"], profile["entry_object_id"])]
    destinations = [
        d
        for d in source["destinations"]
        if d["destination_id"] == profile["destination_id"]
    ]
    if len(destinations) != 1:
        raise ValueError("Quest instance requires one exact native entrance")
    destination = destinations[0]
    if destination["map_id"] != geometry.map_id or not reviewed_entry_gate(
        destination["criterion"], profile["quest_id"], profile
    ):
        raise ValueError("Quest instance must retain its native running-quest gate")
    from wakfu_server.combat_geometry import reachable

    seed = tuple(profile["arena_seed"])
    if seed not in geometry.cells:
        raise ValueError("Quest arena seed is outside native terrain")
    arena = reachable(seed, geometry.cells, geometry.outgoing) & reachable(
        seed, geometry.cells, geometry.incoming
    )
    if not arena <= walking.cells:
        raise ValueError("Quest combat region leaves native exploration terrain")
    room_cells = sorted(walking.cells)
    runtime_id = 1_000_000 + geometry.map_id
    route = dict(
        key=f'quest-map-{geometry.map_id}-{source["id"]}-{destination["destination_id"]}',
        definition_id=runtime_id,
        template_id=runtime_id,
        entry_map_id=source["map_id"],
        entry_object_id=source["id"],
        destination_id=destination["destination_id"],
        start_map_id=geometry.map_id,
        criterion=destination["criterion"],
        registration_policy="local_legacy_map_registry",
        native_definition_id=None,
        native_template_id=destination["cyZ"],
        native_localization_key=f"content.77.{geometry.map_id}",
    )
    roster = dict(
        name=monster["name"],
        ref_id=monster["ref"],
        count=profile["monster_count"],
        role="monster",
        native_min_level=monster["min_level"],
        native_max_level=monster["max_level"],
        guide_min_level=None,
        guide_max_level=None,
    )
    plan = dict(
        slug=profile["id"],
        source_url="installed-native-quest-and-map",
        source_sha256=configurations.canonical_hash(profile),
        document_sha256=configurations.canonical_hash(
            dict(profile=profile, roster=roster)
        ),
        definition_id=runtime_id,
        template_id=runtime_id,
        asset_map_id=geometry.map_id,
        roster_ready=True,
        diagnostics=[],
        rooms=[dict(order=1, monsters=[roster], diagnostics=[])],
        official=False,
        policy_mode=SCHEMA,
    )
    doors = []
    for identity in profile["internal_sources"]:
        native = sources[(geometry.map_id, identity)]
        if len(native["destinations"]) != 1:
            raise ValueError("Quest internal transport is ambiguous")
        target = native["destinations"][0]
        if (
            target["map_id"] != geometry.map_id
            or target["criterion"]
            or target["cyX"]
            or target["cyW"]
        ):
            raise ValueError(
                "Quest internal transport requires a free native same-map link"
            )
        point = [int(native[k]) for k in ("x", "y", "z")]
        doors.append(
            dict(
                source_id=identity,
                destination_id=target["destination_id"],
                source_room=1,
                destination_room=1,
                source_position=point,
                native_approach_cells=[point],
                destination_position=[target[k] for k in ("x", "y", "z")],
            )
        )
    exit_source = sources[(geometry.map_id, profile["exit_source"])]
    exterior = [
        d for d in exit_source["destinations"] if d["map_id"] == source["map_id"]
    ]
    if len(exterior) != 1:
        raise ValueError("Quest instance has no exact native exterior return")
    exit_target = exterior[0]
    point = [int(exit_source[k]) for k in ("x", "y", "z")]
    transfers = profile.get("owned_quest_transfers", [])
    if not isinstance(transfers, list):
        raise ValueError("Quest transfers require explicit native declarations")
    if transfers:
        import struct
        from wakfu_server.owned_quest_transfers import selection

        for declared in transfers:
            if not isinstance(declared, dict):
                raise ValueError("Quest transfer declaration is invalid")
            try:
                body = struct.pack(
                    ">qiBi", declared["source_id"], declared["destination_id"], 0, 2
                )
                selection(dict(owned_quest_transfers=transfers), body)
                origin = sources[(geometry.map_id, declared["source_id"])]
            except (KeyError, struct.error) as error:
                raise ValueError(
                    "Quest transfer lacks its actual native source"
                ) from error
            targets = [
                row
                for row in origin["destinations"]
                if row["destination_id"] == declared["destination_id"]
            ]
            if (
                len(targets) != 1
                or targets[0]["map_id"] == geometry.map_id
                or targets[0]["cyZ"] >= 0
                or targets[0]["cyX"] != 0
                or targets[0]["native_altitude_walkable"] is not True
                or targets[0]["cyW"] > 0
                and targets[0]["item_reference"] <= 0
            ):
                raise ValueError(
                    "Quest transfer differs from a supported literal native target"
                )
    topology = dict(
        asset_map_id=geometry.map_id,
        policy="native_mixed_victory_policy",
        official_room_order_verified=False,
        progression_authority=profile["provenance"],
        rooms=[
            dict(
                order=1,
                anchor=[destination[k] for k in ("x", "y", "z")],
                cells=[list(c) for c in room_cells],
                encounter_region=dict(
                    schema_version=1,
                    cells=[list(c) for c in sorted(arena)],
                    anchor=list(seed),
                    provenance=profile["provenance"],
                ),
            )
        ],
        doors=doors,
        physical_doors=[],
        physical_exit_objects=[
            dict(
                source_id=exit_source["id"],
                destination_id=exit_target["destination_id"],
                room_order=1,
                native_approach_cells=[point],
                source_position=point,
                destination={k: exit_target[k] for k in ("map_id", "x", "y", "z")},
            )
        ],
        exploration_geometry=exploration,
        **({"owned_quest_transfers": transfers} if transfers else {}),
        owned_quest_encounter=dict(
            schema=SCHEMA,
            quest_id=profile["quest_id"],
            entry_objective=profile["entry_objective"],
            victory_objective=profile["victory_objective"],
            maximum_members=1,
            roster=[dict(reference=monster["ref"], count=profile["monster_count"])],
            provenance=profile["provenance"],
            **(
                {"native_entry_criterion": profile["native_entry_criterion"]}
                if "native_entry_criterion" in profile
                else {}
            ),
            **(
                {"reentry_quests": list(reviewed_reentry_quests(profile))}
                if "reentry_quests" in profile
                else {}
            ),
            **(
                {"pending_reentry": reviewed_pending_reentry(profile)}
                if "pending_reentry" in profile
                else {}
            ),
        ),
    )
    return configurations.prepare_configuration(
        plan,
        topology,
        route,
        version=profile.get("version", 1),
        provenance=profile["provenance"],
    )
