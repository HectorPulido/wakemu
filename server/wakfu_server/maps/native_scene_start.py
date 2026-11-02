"""Paid native scene activation inside an existing owned dungeon transaction.

The original object/descriptor supplies the header, criterion and price. Scene
selection is explicit reconstructed server policy, pinned once per start; no
spell root or native runner is replaced. Completion/exit belongs to the run.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import secrets
import struct
from psycopg.types.json import Jsonb


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _policy_database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=1)
def _runtime_rules():
    # Published rows are immutable. New policy publication is activated by the
    # coordinated runtime reload, while prior identities remain available.
    from wakfu_server import native_scene_policy_authority

    with _policy_database().connection() as db:
        return native_scene_policy_authority.rules(db)


def _rules(db=None):
    from wakfu_server import native_scene_policy_authority

    return _runtime_rules() if db is None else native_scene_policy_authority.rules(db)


def install(db):
    """Validate migration-owned authority; never publish JSON/settings rules."""
    return _rules(db)


def _published_rule(db, identity):
    from wakfu_server import native_scene_policy_authority

    return native_scene_policy_authority.read_policy(db, identity)


def binding(topology, *, db=None):
    selected = topology.get("native_scene_start")
    if selected is None:
        return None
    rule = (
        _published_rule(db, selected.get("policy_id"))
        if db is not None
        else next(
            (p for p in _rules() if p["policy_id"] == selected.get("policy_id")), None
        )
    )
    if (
        rule is None
        or rule["map_id"] != topology["asset_map_id"]
        or selected.get("source_id") != rule["source_id"]
    ):
        raise ValueError("Unknown native scene start binding")
    return rule


def _receipt(db, instance_id, rule):
    row = db.execute(
        "SELECT * FROM native_scene_start_receipts WHERE instance_id=%s AND source_id=%s",
        (instance_id, rule["source_id"]),
    ).fetchone()
    if row is not None and (
        row["policy_sha256"] != digest(row["policy"])
        or row["policy"] != rule
        or row["map_id"] != rule["map_id"]
        or row["policy_id"] != rule["policy_id"]
    ):
        raise ValueError("Native scene start receipt differs from its pinned source")
    if row is not None:
        profile = row["profile"]
        _validate_profile(rule, profile)
    return row


def project_configuration(db, run, config):
    rule = binding(config["topology"], db=db)
    if rule is None:
        return config
    if (run["definition_id"], run["template_id"]) != (
        rule["definition_id"],
        rule["template_id"],
    ):
        raise ValueError("Native scene start belongs to another instance definition")
    if (
        rule["profile"].get("kind") == "configured_native_roster_v1"
        and digest(config["compiled_plan"]) != rule["profile"]["compiled_plan_sha256"]
    ):
        raise ValueError("Native scene configuration differs from its pinned roster")
    row = _receipt(db, run["instance_id"], rule)
    return dict(
        config,
        topology=dict(
            config["topology"],
            _native_scene_started=row is not None,
            _native_scene_profile=None if row is None else row["profile"],
        ),
    )


def can_spawn(topology):
    return binding(topology) is None or topology.get("_native_scene_started") is True


def scene_room(topology, room):
    from wakfu_server.dungeon_encounter_regions import encounter_room

    room = encounter_room(room)
    rule = binding(topology)
    if rule is None:
        return room
    if rule["profile"].get("kind") == "configured_native_roster_v1":
        # Formation and grade selection belong to the already pinned plan.
        # This explicit authoring does not emulate an unshipped server script.
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
            source_uri=rule.get(
                "scene_source_uri",
                "native:GenericActivable/33366/descriptor1485/script3363",
            ),
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
                    reference=row.get(
                        "reference", rule["environment"].get("area_reference")
                    ),
                    level=row.get("level", rule["environment"].get("level", 0)),
                    cell=list(row["cell"]),
                )
                for row in rule["environment"]["placements"]
            ],
            native_initial_glyph_policy=rule["policy_id"],
            native_initial_glyph_authority=rule["environment"]["coordinate_authority"],
            native_initial_glyph_source_url=rule["environment"].get(
                "source_uri", "native:map1159/gfx+state5294/area1282"
            ),
        )
        if rule["environment"].get("reserve_spawn_slots") is True:
            # Legacy absence preserves the original scene and formation.
            result["encounter_scene"]["native_initial_spawn_cells"] = [
                list(row["cell"]) for row in rule["environment"]["placements"]
            ]
        if "native_border_reference" in rule:
            result["encounter_scene"]["native_border_reference"] = rule[
                "native_border_reference"
            ]
    return result


def validate_movement(topology, request):
    rule = binding(topology)
    if rule is None or topology.get("_native_scene_started") is True:
        return
    # The existing native edge validator still owns geometry and jump rules.
    blocked = {tuple(p["position"]) for p in rule["gates"]}
    current = tuple(request["start_position"][k] for k in ("x", "y", "z"))
    if current in blocked:
        raise ValueError("Native scene walking starts inside its locked gate")
    for step in request["steps"]:
        current = tuple(
            current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
        )
        if current in blocked:
            raise ValueError("Open the native scene entrance before crossing its gate")


def packets(topology):
    rule = binding(topology)
    if rule is None:
        return ()
    from wakfu_server.dungeon_object_states import state_payload

    opened = topology.get("_native_scene_started") is True
    result = []
    for gate in rule["gates"]:
        payload = state_payload(
            visible=not opened,
            usable=not opened and gate["id"] == rule["source_id"],
            state_id=0 if opened else 1,
        )
        result.append((12344, struct.pack(">qH", gate["id"], len(payload)) + payload))
    return tuple(result)


def _native_source(rule):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(
        rule["catalog_revision"],
        ("native-map-objects.json", f"combat-maps/{rule['map_id']}.json"),
    )
    for expected in rule.get("native_objects", rule["gates"]):
        actual = native_catalog.record(
            DATA_ROOT / "native-map-objects.json", "$", str(expected["id"])
        )
        if (
            actual is None
            or actual["map_id"] != rule["map_id"]
            or actual["type"] != expected["type"]
            or actual["payload_hex"] != expected["payload_hex"]
            or [int(actual[k]) for k in ("x", "y", "z")] != expected["position"]
        ):
            raise ValueError("Scene entrance differs from original native object")
    descriptor = rule["native_descriptor"]
    if len(descriptor["groups"]) != 1 or len(descriptor["groups"][0]["actions"]) != 1:
        raise ValueError("Native scene start requires one qualified action group")
    action = descriptor["groups"][0]["actions"][0]
    group = descriptor["groups"][0]
    if (
        descriptor["descriptor_id"] != rule["descriptor_id"]
        or action["wire_action"] != rule["wire_action"]
        or action["criterion"] != "not IsHero()"
        or group["cof"] is not True
        or type(group["cod"]) is not int
        or group["cod"] <= 0
        or type(group["coe"]) is not int
        or group["coe"] <= 0
        or not action["effects"]
        or action["effects"] != rule["native_effects"]
        or any(
            e["type"] != 1 or e["criterion"] != "not IsHero()" or e["parameters"]
            for e in action["effects"]
        )
    ):
        raise ValueError("Unsupported original native scene descriptor")
    return group["cod"], group["coe"]


def _state_choices(rule):
    """Read explicit source-bound alternatives; None means no installed state."""
    rows = rule["profile"].get("native_state_choices")
    if type(rows) is not list or not rows:
        raise ValueError("Native scene profile lacks state alternatives")
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"id", "levels"}:
            raise ValueError("Invalid native scene state alternative")
        identity, levels = row["id"], row["levels"]
        if (
            type(identity) is not int
            or identity <= 0
            or identity in seen
            or type(levels) is not list
            or not levels
            or any(
                value is not None
                and (type(value) is not int or not 1 <= value <= 32767)
                for value in levels
            )
            or len(set(levels)) != len(levels)
            or not any(value is not None for value in levels)
        ):
            raise ValueError("Invalid native scene state levels")
        seen.add(identity)
    return rows


def _selected_states(rows, choices):
    if (
        type(choices) is not list
        or len(choices) != len(rows)
        or any(
            type(choice) is not int or not 0 <= choice < len(row["levels"])
            for row, choice in zip(rows, choices)
        )
    ):
        raise ValueError("Native scene profile differs from its pinned selection")
    return [
        dict(id=row["id"], level=row["levels"][choice])
        for row, choice in zip(rows, choices)
        if row["levels"][choice] is not None
    ]


def _configured_roster_profile(rule):
    value = rule["profile"].get("compiled_plan_sha256")
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("Configured native scene lacks its immutable plan digest")
    return dict(schema="configured_native_roster_scene_v1", compiled_plan_sha256=value)


def _validate_profile(rule, profile):
    if type(profile) is not dict:
        raise ValueError("Invalid native scene profile receipt")
    if rule["profile"].get("kind") == "configured_native_roster_v1":
        if profile != _configured_roster_profile(rule):
            raise ValueError(
                "Native scene roster receipt differs from its pinned configuration"
            )
        return
    if "native_state_choices" in rule["profile"]:
        rows = _state_choices(rule)
        if profile.get(
            "schema"
        ) != "reconstructed_native_state_choices_v2" or profile.get(
            "native_states"
        ) != _selected_states(
            rows, profile.get("choices")
        ):
            raise ValueError("Native scene profile differs from its pinned selection")
        return
    identifiers = rule["profile"]["native_binary_state_ids"]
    choice = profile.get("choice")
    if (
        type(choice) is not int
        or not 0 <= choice < (1 << len(identifiers))
        or profile.get("schema") != "reconstructed_native_binary_scene_profile_v1"
        or profile.get("native_states")
        != [
            dict(id=i, level=1 + ((choice >> n) & 1)) for n, i in enumerate(identifiers)
        ]
    ):
        raise ValueError("Native scene profile differs from its pinned selection")


def _profile(rule):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    if rule["profile"].get("kind") == "configured_native_roster_v1":
        return _configured_roster_profile(rule)
    if "native_state_choices" in rule["profile"]:
        rows = _state_choices(rule)
        for row in rows:
            native = native_catalog.record(
                DATA_ROOT / "combat-state-definitions.json", "states", str(row["id"])
            )
            if native is None or any(
                level is not None and level > native.get("maximum_level", 0)
                for level in row["levels"]
            ):
                raise ValueError("Native scene state choice exceeds original levels")
        choices = [secrets.randbelow(len(row["levels"])) for row in rows]
        return dict(
            schema="reconstructed_native_state_choices_v2",
            choices=choices,
            native_states=_selected_states(rows, choices),
        )
    definitions = rule["profile"]["native_binary_state_ids"]
    if not definitions or len(set(definitions)) != len(definitions):
        raise ValueError("Native scene profile has duplicate or absent state choices")
    for identity in definitions:
        native = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "states", str(identity)
        )
        if native is None or native.get("maximum_level", 0) < 2:
            raise ValueError("Native scene profile state lacks its original two levels")
    choice = secrets.randbelow(1 << len(definitions))
    return dict(
        schema="reconstructed_native_binary_scene_profile_v1",
        choice=choice,
        native_states=[
            dict(id=identity, level=1 + ((choice >> index) & 1))
            for index, identity in enumerate(definitions)
        ],
    )


def start(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    groups,
    geometry,
    blocked,
    is_hero,
):
    if (
        type(body) is not bytes
        or len(body) != 12
        or type(blocked) is not bool
        or type(is_hero) is not bool
    ):
        raise ValueError("Malformed native scene start request")
    source_id, action, parameter = struct.unpack(">qHH", body)
    if blocked or is_hero:
        raise ValueError("This native scene action requires a free main participant")
    from wakfu_server import dungeon_runtime, dungeon_difficulty, dungeon_entry_payment
    from wakfu_server.achievements.service import _owner
    from wakfu_server.environment_interactions import _guard

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _owner(db, current)
        _guard(db, current["id"])
        db.execute(
            "SELECT instance_id FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (current["instance_id"],),
        )
        run, config = dungeon_runtime.configuration_for_instance(
            db, current["instance_id"]
        )
        rule = binding(config["topology"])
        if rule is None or (source_id, action, parameter) != (
            rule["source_id"],
            rule["wire_action"],
            0,
        ):
            raise ValueError("Unqualified native scene start action")
        rule = _published_rule(db, rule["policy_id"])
        if (
            run["status"] != "active"
            or current["map_id"] != rule["map_id"]
            or [current[k] for k in ("x", "y", "z")] not in rule["approaches"]
        ):
            raise ValueError("Native scene start is outside its owned approach")
        member = db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s AND session_generation=%s AND status='active'",
            (run["instance_id"], current["id"], generation),
        ).fetchone()
        if member is None:
            raise ValueError("Native scene start requires active membership")
        progress = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (run["instance_id"],),
        ).fetchone()
        if progress is None or progress["status"] != "active":
            raise ValueError("The native scene attempt has already ended")
        members = db.execute(
            "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active'",
            (run["instance_id"],),
        ).fetchall()
        from wakfu_server import companions

        # Heroes are already members. Active dungeon membership prevents
        # normal companion roster mutation while this receipt is checked.
        controlled = len(members) + companions.controlled_count(
            db, [row["character_id"] for row in members]
        )
        if not 1 <= controlled <= rule["maximum_members"]:
            raise ValueError(
                "Native scene participant count exceeds its original format"
            )
        selection = dungeon_difficulty.selection(db, run["instance_id"])
        if (
            selection["competitive"] is not True
            or selection["competitive_max_level"] != rule["competitive_ceiling"]
        ):
            raise ValueError("Native scene requires its competitive level profile")
        item, quantity = _native_source(rule)
        existing = _receipt(db, run["instance_id"], rule)
        payment = []
        if existing is None:
            payment = [
                dict(p)
                for p in dungeon_entry_payment.consume(
                    db, (current["id"],), item, quantity
                )
            ]
            profile = _profile(rule)
            db.execute(
                "INSERT INTO native_scene_start_receipts(instance_id,source_id,map_id,policy_id,policy_sha256,policy,account_id,character_id,session_generation,payment,profile) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    run["instance_id"],
                    source_id,
                    rule["map_id"],
                    rule["policy_id"],
                    digest(rule),
                    Jsonb(rule),
                    account_id,
                    current["id"],
                    generation,
                    Jsonb(payment),
                    Jsonb(profile),
                ),
            )
        else:
            profile = existing["profile"]
        # Receipt and the existing native roster creation share this transaction.
        group = dungeon_runtime.ensure_current_room(
            db, groups, run["instance_id"], geometry
        )
        _, projected = dungeon_runtime.configuration_for_instance(
            db, run["instance_id"]
        )
        return dict(
            replay=existing is not None,
            profile=profile,
            payment=payment,
            group=group,
            character=store.character(account_id, current["id"], db),
            packets=packets(projected["topology"]),
        )


@lru_cache(maxsize=1)
def _source_identities():
    return frozenset((p["map_id"], p["source_id"]) for p in _rules())


def handles(store, character, body):
    if len(body) != 12 or character.get("instance_id", 0) <= 0:
        return False
    identity = struct.unpack_from(">q", body)[0]
    return (character["map_id"], identity) in _source_identities()
