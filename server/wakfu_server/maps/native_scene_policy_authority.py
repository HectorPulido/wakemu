"""Project sealed, normalized paid-scene authority into existing receipt shapes.

Original native descriptors remain immutable evidence. Operational fields,
choices, positions, costs and admission are normalized migration-owned rows.
No file or settings fallback can publish new gameplay rules.
"""
import hashlib
import json


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _ordered(rows):
    if [row["ordinal"] for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Native scene authority has a noncontiguous ordered child")
    return rows


def _points(rows):
    return [[row[k] for k in ("x", "y", "z")] for row in _ordered(rows)]


def _present(source, target, pairs):
    for column, key in pairs:
        if source[column] is not None:
            target[key] = source[column]


def read_policy(db, identity, *, lock=True):
    """Read one explicit published identity; never choose a latest map/source."""
    if type(lock) is not bool:
        raise ValueError("Native scene authority lock mode must be boolean")
    suffix = " FOR SHARE" if lock else ""
    row = db.execute(
        "SELECT * FROM native_scene_policies WHERE policy_id=%s AND published" + suffix,
        (identity,),
    ).fetchone()
    if row is None:
        raise ValueError("Native scene policy is absent from normalized publication")
    value = {
        key: row[key]
        for key in (
            "policy_id",
            "authority",
            "map_id",
            "definition_id",
            "template_id",
            "source_id",
            "wire_action",
            "descriptor_id",
            "catalog_revision",
            "maximum_members",
            "native_descriptor",
            "native_effects",
        )
    }
    _present(
        row,
        value,
        (
            ("competitive_ceiling", "competitive_ceiling"),
            ("scene_source_uri", "scene_source_uri"),
            ("native_border_reference", "native_border_reference"),
            ("combat_area_provenance", "combat_area_provenance"),
        ),
    )
    objects = db.execute(
        "SELECT * FROM native_scene_policy_objects WHERE policy_id=%s ORDER BY object_role,ordinal",
        (identity,),
    ).fetchall()
    for role, key in (("gate", "gates"), ("evidence", "native_objects")):
        selected = _ordered([obj for obj in objects if obj["object_role"] == role])
        if selected or role == "gate":
            value[key] = [
                dict(
                    id=obj["object_id"],
                    type=obj["native_type"],
                    position=[obj[k] for k in ("x", "y", "z")],
                    payload_hex=obj["payload_hex"],
                )
                for obj in selected
            ]
    value["approaches"] = _points(
        db.execute(
            "SELECT * FROM native_scene_policy_approaches WHERE policy_id=%s ORDER BY ordinal",
            (identity,),
        ).fetchall()
    )
    if not value["approaches"] or not any(
        obj["object_id"] == row["source_id"] for obj in objects
    ):
        raise ValueError("Published native scene has no authenticated source approach")
    cells = _points(
        db.execute(
            "SELECT * FROM native_scene_policy_combat_cells WHERE policy_id=%s ORDER BY ordinal",
            (identity,),
        ).fetchall()
    )
    if cells:
        value["combat_cells"] = cells
    if row["combat_anchor_x"] is not None:
        value["combat_anchor"] = [row["combat_anchor_" + k] for k in ("x", "y", "z")]
        if value["combat_anchor"] not in cells:
            raise ValueError("Published scene anchor leaves its original combat cells")
    states = _ordered(
        db.execute(
            "SELECT * FROM native_scene_profile_states WHERE policy_id=%s ORDER BY ordinal",
            (identity,),
        ).fetchall()
    )
    levels = db.execute(
        "SELECT * FROM native_scene_profile_state_levels WHERE policy_id=%s ORDER BY state_ordinal,ordinal",
        (identity,),
    ).fetchall()
    targets = _ordered(
        db.execute(
            "SELECT * FROM native_scene_profile_targets WHERE policy_id=%s ORDER BY ordinal",
            (identity,),
        ).fetchall()
    )
    profile = {}
    mode = row["profile_mode"]
    if mode == "configured_roster":
        if states or levels or targets:
            raise ValueError(
                "Configured native roster must not inherit a scene state producer"
            )
        profile = dict(
            kind="configured_native_roster_v1",
            compiled_plan_sha256=row["compiled_plan_sha256"],
        )
    elif mode in ("binary", "choices"):
        if not states or not targets:
            raise ValueError("Native scene state producer is incomplete")
        choices = []
        for state in states:
            alternatives = [
                level["level"]
                for level in _ordered(
                    [
                        level
                        for level in levels
                        if level["state_ordinal"] == state["ordinal"]
                    ]
                )
            ]
            if not alternatives or not any(level is not None for level in alternatives):
                raise ValueError("Native scene state has no installed alternative")
            if mode == "binary" and alternatives != [1, 2]:
                raise ValueError("Legacy binary state levels changed")
            choices.append(dict(id=state["state_id"], levels=alternatives))
        if mode == "binary":
            profile["native_binary_state_ids"] = [state["state_id"] for state in states]
        else:
            profile["native_state_choices"] = choices
        profile["native_state_source_digests"] = {
            str(state["state_id"]): state["source_sha256"] for state in states
        }
        profile["target_references"] = [target["reference_id"] for target in targets]
    else:
        raise ValueError("Unknown normalized native scene profile mode")
    _present(row, profile, (("profile_provenance", "provenance"),))
    value["profile"] = profile
    placements = _ordered(
        db.execute(
            "SELECT * FROM native_scene_environment_placements WHERE policy_id=%s ORDER BY ordinal",
            (identity,),
        ).fetchall()
    )
    if row["environment_enabled"]:
        if not placements:
            raise ValueError("Published native scene environment has no placements")
        environment = dict(
            coordinate_authority=row["environment_coordinate_authority"], placements=[]
        )
        _present(
            row,
            environment,
            (
                ("environment_area_reference", "area_reference"),
                ("environment_level", "level"),
                ("environment_map_graphics_sha256", "map_graphics_sha256"),
                ("environment_provenance", "provenance"),
                ("environment_source_uri", "source_uri"),
                ("environment_reserve_spawn_slots", "reserve_spawn_slots"),
            ),
        )
        for placement in placements:
            item = dict(cell=[placement[k] for k in ("x", "y", "z")])
            _present(
                placement,
                item,
                (
                    ("area_reference", "reference"),
                    ("level", "level"),
                    ("original_graphic", "original_graphic"),
                ),
            )
            if item.get("reference", environment.get("area_reference")) is None:
                raise ValueError(
                    "Native scene placement has no original area reference"
                )
            environment["placements"].append(item)
        value["environment"] = environment
    elif placements:
        raise ValueError("Disabled native scene environment contains placements")
    _validate_native_evidence(row, value)
    if digest(value) != row["policy_sha256"]:
        raise ValueError(
            "Normalized scene authority differs from its sealed receipt digest"
        )
    return value


def _validate_native_evidence(row, value):
    """Typed price/action authority must agree with its original descriptor."""
    descriptor = value["native_descriptor"]
    groups = descriptor.get("groups", ())
    if len(groups) != 1 or len(groups[0].get("actions", ())) != 1:
        raise ValueError("Native paid scene has an ambiguous action descriptor")
    group = groups[0]
    action = group["actions"][0]
    effects = value["native_effects"]
    if (
        descriptor.get("descriptor_id") != row["descriptor_id"]
        or group.get("id") != row["native_group_id"]
        or action.get("id") != row["native_action_id"]
        or action.get("wire_action") != row["wire_action"]
        or group.get("cod") != row["price_item_id"]
        or group.get("coe") != row["price_quantity"]
        or group.get("cof") is not True
        or action.get("criterion") != row["native_criterion"]
        or row["native_criterion"] != "not IsHero()"
        or action.get("effects") != effects
        or len(effects) != 1
        or effects[0].get("reference") != row["native_script_reference"]
        or effects[0].get("type") != 1
        or effects[0].get("parameters") != []
        or effects[0].get("criterion") != row["native_criterion"]
    ):
        raise ValueError(
            "Normalized native scene action or price contradicts original evidence"
        )


def rules(db, *, lock=True):
    rows = db.execute(
        "SELECT policy_id FROM native_scene_policies WHERE published ORDER BY policy_id"
    ).fetchall()
    return [read_policy(db, row["policy_id"], lock=lock) for row in rows]


def admission_policy(
    db, route_key, *, policy_id=None, configuration_version=None, lock=True
):
    """Resolve the scene pinned by this exact configuration, not the newest rule."""
    if policy_id is None:
        if type(configuration_version) is not int or configuration_version <= 0:
            raise ValueError(
                "Native admission requires its pinned configuration version"
            )
        config = db.execute(
            "SELECT configuration FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
            (route_key, configuration_version),
        ).fetchone()
        if config is None:
            return None
        selected = config["configuration"].get("topology", {}).get("native_scene_start")
        if selected is None:
            return None
        policy_id = selected["policy_id"]
    if type(lock) is not bool:
        raise ValueError("Native admission authority lock mode must be boolean")
    suffix = " FOR SHARE OF a,p" if lock else ""
    row = db.execute(
        "SELECT a.*,p.map_id,p.definition_id,p.template_id,p.source_id,p.descriptor_id,p.maximum_members,p.competitive_ceiling FROM native_scene_admission_policies a JOIN native_scene_policies p USING(policy_id) WHERE a.policy_id=%s AND a.route_key=%s AND p.published"
        + suffix,
        (policy_id, route_key),
    ).fetchone()
    if row is None:
        raise ValueError("Pinned paid scene lacks its normalized outer admission")
    value = dict(
        policy_id=row["admission_policy_id"],
        authority=row["authority"],
        route=dict(
            template_id=row["template_id"],
            definition_id=row["definition_id"],
            entry_map_id=row["entry_map_id"],
            entry_object_id=row["entry_object_id"],
            destination_id=row["destination_id"],
            start_map_id=row["map_id"],
        ),
        maximum_members=row["maximum_members"],
        competitive_ceiling=row["competitive_ceiling"],
        provenance=row["provenance"],
        native_paid_start=dict(
            map_id=row["map_id"],
            object_id=row["source_id"],
            descriptor_id=row["descriptor_id"],
        ),
        minimum_configuration_version=row["minimum_configuration_version"],
    )
    if digest(value) != row["admission_sha256"]:
        raise ValueError("Normalized admission differs from its sealed source digest")
    return value
