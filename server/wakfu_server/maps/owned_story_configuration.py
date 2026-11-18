"""Compile reviewed multi-room stories without changing native travel or combat.

The controller owns physical mechanics; room cells bound ordinary encounters,
while the complete original exploration geometry governs walking between them.
Native exit alternatives stay literal and require the separate story executor.
"""

from wakfu_server import dungeon_runtime_config as configurations
from wakfu_server import owned_story_controller, owned_story_encounters

SCHEMA = "owned-story-instance-v1"


def validate_sequential_arenas(controller, topology_rooms):
    # Reusing an arena is safe only when every earlier overlapping formation
    # has a genuine victory prerequisite, never just an animation or arrival.
    by_step = {step["id"]: step for step in controller["steps"]}

    def prerequisites(identities):
        result = set(identities)
        pending = list(identities)
        while pending:
            for dependency in by_step[pending.pop()]["requires"]:
                if dependency not in result:
                    result.add(dependency)
                    pending.append(dependency)
        return result

    for index, room in enumerate(topology_rooms):
        required = prerequisites(room["requires"])
        for previous in topology_rooms[:index]:
            if set(map(tuple, room["cells"])) & set(map(tuple, previous["cells"])):
                if not any(
                    by_step[identity]["kind"] == "room_victory"
                    and by_step[identity]["reference"] == previous["order"]
                    for identity in required
                ):
                    raise ValueError(
                        "Sequential arena reuse lacks its earlier actual victory"
                    )


def compile_story(
    manifest,
    *,
    controller,
    encounters,
    geometry,
    exploration,
    sources,
    monster,
    trial_sidecar=None,
):
    if (
        manifest.get("schema") != SCHEMA
        or not manifest.get("provenance")
        or manifest.get("map_id") != geometry.map_id
        or controller.get("map_id") != geometry.map_id
    ):
        raise ValueError(
            "Story configuration requires explicit matching native sources"
        )
    from wakfu_server import owned_object_trials, owned_noncombat_context

    object_trials = manifest.get("content_policy") == owned_object_trials.SCHEMA
    narrative = manifest.get("content_policy") == owned_noncombat_context.NARRATIVE
    noncombat = object_trials or narrative
    if object_trials:
        owned_object_trials.policy(dict(topology=dict(owned_object_trials=controller)))
    else:
        if manifest.get("content_policy") is not None and not narrative:
            raise ValueError("Unknown owned story content policy")
        owned_story_controller.policy(
            dict(topology=dict(owned_story_controller=controller))
        )
    if noncombat and (encounters is not None or monster is not None):
        raise ValueError("Noncombat owned content cannot invent encounter rosters")
    if narrative and any(
        step["kind"] in ("room_admission", "room_available", "room_victory")
        for step in controller["steps"]
    ):
        raise ValueError("Narrative owned content cannot declare combat producers")
    if (
        exploration.get("map_id") != geometry.map_id
        or exploration.get("profile")
        != dict(height=6, movement_type=0, jump_capacity=4, native_class="Sm")
        or not exploration.get("client_sha256")
        or not exploration.get("topology_sha256")
    ):
        raise ValueError(
            "Story exploration requires original native player walking geometry"
        )
    entry = manifest["entry"]
    npc_entry = entry.get("kind") == "native_npc_choice"
    generic_entry = entry.get("kind") == "native_generic_choice"
    if npc_entry:
        from wakfu_server.owned_story_npc_entry import validate_entry

        validate_entry(entry, map_id=geometry.map_id, cells=exploration["cells"])
        if manifest["native_entry_payment"] != {"reference": 0, "quantity": 0}:
            raise ValueError("NPC owned entrance cannot invent a native payment")
        entry_map, entry_source, entry_destination = (
            entry["map_id"],
            entry["reference_id"],
            entry["choice_id"],
        )
        entry_criterion, native_template = manifest["native_entry_criterion"], None
    elif generic_entry:
        from wakfu_server.owned_story_generic_entry import validate_entry

        source, group, action, effect, target, _ = validate_entry(
            entry, cells=exploration["cells"]
        )
        if (
            target["map_id"] != geometry.map_id
            or effect["criterion"] != manifest["native_entry_criterion"]
            or manifest["native_entry_payment"]
            != {"reference": group["cod"], "quantity": group["coe"]}
        ):
            raise ValueError(
                "Generic story entrance differs from its native destination/payment"
            )
        entry_map, entry_source, entry_destination = (
            source["map_id"],
            source["id"],
            effect["action_reference"],
        )
        entry_criterion, native_template = effect["criterion"], None
    else:
        source = sources[(entry["map_id"], entry["object_id"])]
        choices = [
            row
            for row in source["destinations"]
            if row["destination_id"] == entry["destination_id"]
        ]
        if len(choices) != 1:
            raise ValueError("Story entrance must name one exact native destination")
        native = choices[0]
        payment = manifest["native_entry_payment"]
        if (
            native["map_id"] != geometry.map_id
            or native["criterion"] != manifest["native_entry_criterion"]
            or native["cyZ"] >= 0
            or native["cyX"] != 0
            or native["item_reference"] != payment["reference"]
            or native["cyW"] != payment["quantity"]
            or native["native_altitude_walkable"] is not True
            or [native[k] for k in ("x", "y", "z")] not in exploration["cells"]
        ):
            raise ValueError(
                "Story entrance differs from its literal native gate/payment/arrival"
            )
        entry_map, entry_source, entry_destination = (
            source["map_id"],
            source["id"],
            native["destination_id"],
        )
        entry_criterion, native_template = native["criterion"], native["cyZ"]
    if noncombat:
        rooms, topology_rooms = [], []
    else:
        rooms, topology_rooms = owned_story_encounters.compile_rooms(
            encounters, geometry=geometry, exploration=exploration, monster=monster
        )
        steps = {row["id"] for row in controller["steps"]}
        terminals = [
            (row["kind"], row["reference"])
            for row in controller["steps"]
            if row["kind"] in ("room_victory", "room_defeat")
        ]
        if {order for _kind, order in terminals} != {
            room["order"] for room in rooms
        } or any(not set(room["requires"]) <= steps for room in topology_rooms):
            raise ValueError(
                "Story formations and controller victory/gate producers differ"
            )
        validate_sequential_arenas(controller, topology_rooms)
    exits = []
    for selection in manifest["exit_sources"]:
        if type(selection) is int:
            identity, selected_destination = selection, None
        elif isinstance(selection, dict) and set(selection) == {
            "source_id",
            "destination_id",
        }:
            identity, selected_destination = (
                selection["source_id"],
                selection["destination_id"],
            )
            if any(
                type(value) is not int or value <= 0
                for value in (identity, selected_destination)
            ):
                raise ValueError("Invalid selected native story exit")
        else:
            raise ValueError("Invalid selected native story exit")
        current = sources[(geometry.map_id, identity)]
        targets = [
            row
            for row in current["destinations"]
            if selected_destination is None
            or row["destination_id"] == selected_destination
        ]
        if not targets:
            raise ValueError("Selected native story exit is absent")
        for target in targets:
            if (
                target["map_id"] == geometry.map_id
                or target["cyZ"] >= 0
                or target["cyX"] != 0
                or target["cyW"] != 0
                or target["native_altitude_walkable"] is not True
            ):
                raise ValueError(
                    "Story exit requires a literal free native foreign endpoint"
                )
            from wakfu_server.owned_story_exits import criterion_allowed

            # Validate supported native grammar without treating offline
            # compilation as fulfillment of the character's live predicate.
            linked = any(
                row["source_id"] == identity
                and row["destination_id"] == target["destination_id"]
                for row in controller.get("native_links", [])
            )
            if not linked:
                criterion_allowed(target["criterion"], set())
            exits.append(
                dict(
                    source_id=identity,
                    destination_id=target["destination_id"],
                    source_position=[current[k] for k in ("x", "y", "z")],
                    source_sha256=configurations.canonical_hash(current),
                    criterion=target["criterion"],
                    destination={k: target[k] for k in ("map_id", "x", "y", "z")},
                )
            )
    from wakfu_server import owned_story_generic_return

    generic_returns = owned_story_generic_return.validate(controller)
    if (
        not exits
        and not generic_returns
        and controller.get("terminal_returns", {}).get("schema")
        != "owned-story-step-return-v1"
    ) or len({(row["source_id"], row["destination_id"]) for row in exits}) != len(
        exits
    ):
        raise ValueError("Story exits must be explicit and unambiguous")
    runtime_id = 1_000_000 + geometry.map_id
    route = dict(
        key=(
            f'quest-npc-{geometry.map_id}-{entry_source}-{entry["action_id"]}-{entry["node_id"]}-{entry_destination}'
            if npc_entry
            else f"quest-generic-{geometry.map_id}-{entry_source}-{entry_destination}"
            if generic_entry
            else f"quest-map-{geometry.map_id}-{entry_source}-{entry_destination}"
        ),
        definition_id=runtime_id,
        template_id=runtime_id,
        entry_map_id=entry_map,
        entry_object_id=entry_source,
        destination_id=entry_destination,
        start_map_id=geometry.map_id,
        criterion=entry_criterion,
        registration_policy=(
            "native_npc_choice"
            if npc_entry
            else "native_generic_choice"
            if generic_entry
            else "local_legacy_map_registry"
        ),
        native_definition_id=None,
        native_template_id=native_template,
        native_localization_key=f"content.77.{geometry.map_id}",
    )
    if npc_entry:
        route["native_npc_entry"] = entry
    if generic_entry:
        route["native_generic_entry"] = entry
    document = dict(manifest=manifest, controller=controller, encounters=encounters)
    plan = dict(
        slug=manifest["id"],
        source_url="installed-native-quest-map-and-scenario",
        source_sha256=configurations.canonical_hash(document),
        document_sha256=configurations.canonical_hash(
            dict(document=document, rooms=rooms)
        ),
        definition_id=runtime_id,
        template_id=runtime_id,
        asset_map_id=geometry.map_id,
        roster_ready=True,
        diagnostics=[],
        rooms=rooms,
        official=False,
        policy_mode=SCHEMA,
    )
    topology = dict(
        asset_map_id=geometry.map_id,
        policy=(
            owned_object_trials.SCHEMA
            if object_trials
            else owned_noncombat_context.NARRATIVE
            if narrative
            else owned_story_controller.SCHEMA
        ),
        official_room_order_verified=False,
        progression_authority=manifest["provenance"],
        rooms=topology_rooms,
        doors=[],
        physical_doors=[],
        physical_exit_objects=[],
        exploration_geometry=exploration,
        native_story_exits=exits,
    )
    topology[
        "owned_object_trials" if object_trials else "owned_story_controller"
    ] = controller
    if trial_sidecar is not None:
        if noncombat or manifest.get("object_trials") != trial_sidecar.get("id"):
            raise ValueError(
                "Hybrid story trials require their explicit sidecar identity"
            )
        owned_object_trials.policy(
            dict(topology=dict(owned_object_trials=trial_sidecar))
        )
        validate_object_trial_geometry(trial_sidecar, exploration)
        if trial_sidecar["map_id"] != manifest["map_id"]:
            raise ValueError("Hybrid trial sidecar belongs to another native map")
        story_steps = {step["id"] for step in controller["steps"]}
        for trial in trial_sidecar["trials"]:
            if not set(trial.get("requires_story_steps", ())) <= story_steps:
                raise ValueError("Hybrid trial requires an absent story receipt")
            for edge, effects in trial["effects"].items():
                for effect in effects:
                    if effect.get("kind") == "story_event" and (
                        edge != "success"
                        or not any(
                            step["kind"] == "trial_success"
                            and step["reference"] == effect.get("reference")
                            for step in controller["steps"]
                        )
                    ):
                        raise ValueError(
                            "Hybrid story join lacks its actual trial success"
                        )
        topology["owned_object_trials"] = trial_sidecar
    if manifest.get("owned_quest_pools"):
        from copy import deepcopy

        if object_trials or not isinstance(manifest["owned_quest_pools"], list):
            raise ValueError("Native quest farming requires a typed combat story")
        topology["owned_quest_pools"] = deepcopy(manifest["owned_quest_pools"])
    if manifest.get("owned_transfers"):
        from wakfu_server import owned_quest_transfers

        if (
            not object_trials
            and controller.get("schema") != "owned-story-controller-v1"
        ):
            raise ValueError(
                "Owned transfers require typed trials or a story controller"
            )
        declarations = manifest["owned_transfers"]
        if not isinstance(declarations, list):
            raise ValueError("Invalid native owned transfer declarations")
        topology["owned_quest_transfers"] = declarations
        for declaration in declarations:
            import struct

            request = struct.pack(
                ">qiBi", declaration["source_id"], declaration["destination_id"], 0, 2
            )
            owned_quest_transfers.selection(topology, request)
            source = sources.get((geometry.map_id, declaration["source_id"]))
            if source is None or not any(
                row["destination_id"] == declaration["destination_id"]
                and row["map_id"] != geometry.map_id
                for row in source["destinations"]
            ):
                raise ValueError(
                    "World trial transfer lacks its original native destination"
                )
    return configurations.prepare_configuration(
        plan,
        topology,
        route,
        version=manifest["version"],
        provenance=manifest["provenance"],
    )


def compile_object_trials(manifest, *, trials, geometry, exploration, sources):
    """Use literal private transport and walking geometry with zero encounters."""
    from wakfu_server import owned_object_trials

    if manifest.get("content_policy") != owned_object_trials.SCHEMA:
        raise ValueError("Object trial context requires explicit noncombat policy")
    validate_object_trial_geometry(trials, exploration)
    return compile_story(
        manifest,
        controller=trials,
        encounters=None,
        monster=None,
        geometry=geometry,
        exploration=exploration,
        sources=sources,
    )


def validate_object_trial_geometry(trials, exploration):
    """Attest declared native zones, action durations and ramp exceptions."""
    from hashlib import sha256
    from wakfu_server import owned_story_mechanics, native_interactive_activation

    native = owned_story_mechanics.sources(trials)
    objects = {row["id"]: row for row in native["objects"]}
    edges = {tuple(map(tuple, edge)) for edge in exploration["edges"]}
    walking = set(map(tuple, exploration["cells"]))
    for source in trials["sources"]:
        raw = objects.get(source["id"])
        if raw is None or any(
            tuple(point) not in walking for point in source["approaches"]
        ):
            raise ValueError("Object trial approaches leave native walking geometry")
        if (
            [raw[key] for key in ("x", "y", "z")] != source["position"]
            or raw["descriptor_id"] != source["descriptor_id"]
            or sha256(bytes.fromhex(raw["payload_hex"])).hexdigest()
            != source["payload_sha256"]
        ):
            raise ValueError("Object trial source differs from native payload")
        program = native["programs"][str(source["id"])]
        durations = {
            group["cog"]
            for group in program["groups"]
            if any(
                action["wire_action"] == source["action"] for action in group["actions"]
            )
        }
        if durations != {source["duration_ms"]}:
            raise ValueError("Object trial duration differs from native action group")
    for trial in trials["trials"]:
        if trial["kind"] in {
            "sliding_tiles",
            "resource_course",
            "light_course",
            "stealth_course",
            "safe_course",
        }:
            program = trial["program"]
            points = list(map(tuple, program["cells"]))
            if not set(points) <= walking:
                raise ValueError(
                    "World trial board leaves original native walking floor"
                )
            program_edges = (
                {(points[a], points[b]) for a, b in program["edges"]}
                if trial["kind"] == "sliding_tiles"
                else {tuple(map(tuple, edge)) for edge in program["edges"]}
            )
            if not program_edges <= edges:
                raise ValueError("World trial movement invents a native walking edge")
        for cells_key, ids_key in (
            ("hazard_cells", "hazard_zone_ids"),
            ("destination_cells", "destination_zone_ids"),
        ):
            if ids_key in trial:
                actual = set()
                for identity in trial[ids_key]:
                    actual.update(
                        map(
                            tuple,
                            native_interactive_activation.decode(objects[identity]),
                        )
                    )
                if actual != set(map(tuple, trial[cells_key])):
                    raise ValueError(
                        "Object trial cells differ from literal native zones"
                    )
        for region in trial.get("failure_regions", ()):
            actual = set(
                map(
                    tuple,
                    native_interactive_activation.decode(
                        objects[region["native_zone_id"]]
                    ),
                )
            )
            if actual != set(map(tuple, region["cells"])):
                raise ValueError(
                    "Object trial feedback differs from literal native region"
                )
        if (
            not {tuple(map(tuple, edge)) for edge in trial.get("safe_edges", ())}
            <= edges
        ):
            raise ValueError("Object trial ramp exception is not a native walking edge")
