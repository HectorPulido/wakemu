"""Frozen pre-normalization133 scene projection; compatibility fixture only."""


def scene_room(topology, room):
    from wakfu_server.dungeon_encounter_regions import encounter_room

    room = encounter_room(room)
    rule = binding(topology)
    if rule is None:
        return room
    cells = rule["combat_cells"]
    if (
        not set(map(tuple, cells)) <= set(map(tuple, room["cells"]))
        or rule["combat_anchor"] not in cells
    ):
        raise ValueError("Native scene combat region leaves its pinned room")
    result = dict(room, cells=cells, anchor=rule["combat_anchor"])
    if topology.get("_native_scene_started") is True:
        profile = topology.get("_native_scene_profile")
        if type(profile) is not dict:
            raise ValueError("Started native scene lacks its frozen profile")
        states = profile["native_states"]
        result["encounter_scene"] = dict(
            schema_version=1,
            policy_id=rule["policy_id"],
            authority="authorized_wakemu_native_content_reconstruction",
            source_uri="native:GenericActivable/33366/descriptor1485/script3363",
            full_room_scope=True,
            state_programs=[
                dict(
                    target_references=list(rule["profile"]["target_references"]),
                    state_id=state["id"],
                    level=state["level"],
                    protected=False,
                    source_sha256=rule["profile"]["native_state_source_digests"][
                        str(state["id"])
                    ],
                )
                for state in states
            ],
            native_initial_glyphs=[
                dict(
                    reference=rule["environment"]["area_reference"],
                    level=rule["environment"]["level"],
                    cell=list(row["cell"]),
                )
                for row in rule["environment"]["placements"]
            ],
            native_initial_glyph_policy=rule["policy_id"],
            native_initial_glyph_authority=rule["environment"]["coordinate_authority"],
            native_initial_glyph_source_url="native:map1159/gfx+state5294/area1282",
        )
    return result
