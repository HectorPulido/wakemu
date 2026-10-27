"""Explicit reconstructed initial NPC helpers, never native summon effects.

Ordinary reference records retain their exact native shape and books. The
manifest owns only initial scene roles and a separate current-controller link.
It does not insert actors into a world group or manufacture307/207/933 effects.
"""
from copy import deepcopy

from .combat_quest_scene_authority import canonical_digest

SCHEMA = "wakemu.initial-scene-npc-helpers.v1"
SPIRIT_POLICY = "wakemu-spirit-scenario2710-v1"
SECURITY_POLICY = "wakemu.security.initial-three-globs.v1"


def _scene(character, members):
    refs = tuple(member["ref"] for member in members)
    if refs == (3518,):
        return SECURITY_POLICY, (
            ("glob1", 3516, 150, "npc", "self"),
            ("glob2", 3516, 150, "npc", "self"),
            ("glob3", 3516, 150, "npc", "self"),
        )
    if refs == (5848,):
        from .combat_encounter_objective_spirit import _published_book

        if not _published_book():
            return None
        from wakfu_server.builds import effective_sheet_level

        if (
            effective_sheet_level(character, character.get("active_build_index", 0))
            < 96
        ):
            return None
        from wakfu_server.monsters import reference

        return SPIRIT_POLICY, tuple(
            (role, ref, reference(ref)["min_level"], "player", "principal")
            for role, ref in (("lieutenant", 5849), ("monk", 5850))
        )
    return None


def _cells(character, members, definitions):
    """Choose adapted native reachable cells; never claim original anchors."""
    from .combat_geometry import published_geometry, prepare_geometry, reachable
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_obstacle_condition import footprint

    geometry = prepare_geometry(published_geometry(character["map_id"]))
    catalog = native_actor_catalog()
    player = tuple(character[key] for key in ("x", "y", "z"))
    boss = tuple(members[0][key] for key in ("x", "y", "z"))
    if player not in geometry.cells or boss not in geometry.cells:
        raise ValueError("Scene helper participants lack actual native terrain")
    common = reachable(player, geometry.cells, geometry.outgoing) & reachable(
        boss, geometry.cells, geometry.outgoing
    )
    occupied = set(footprint(player, catalog["default_actor_radius"]))
    for member in members:
        occupied.update(
            footprint(
                tuple(member[key] for key in ("x", "y", "z")),
                catalog["npc_profiles"][str(member["ref"])]["physical_radius"],
            )
        )
    selected = []
    for _role, ref, _level, side, _controller in definitions:
        radius = catalog["npc_profiles"][str(ref)]["physical_radius"]
        origin = player if side == "player" else boss
        candidates = sorted(
            common,
            key=lambda cell: (
                abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]),
                abs(cell[2] - origin[2]),
                cell,
            ),
        )
        chosen = None
        for cell in candidates:
            covered = set(footprint(cell, radius))
            if covered & occupied or not all(
                (x, y, cell[2]) in common for x, y in covered
            ):
                continue
            chosen = cell
            occupied.update(covered)
            break
        if chosen is None:
            raise ValueError("Actual terrain cannot hold complete native scene helpers")
        selected.append(chosen)
    return selected


def prepare_scene_roster(store, character, members):
    """Return extended ordinary sources and a frozen explicit reconstruction.

    Caller retains original world-group membership independently. Only this
    returned combat roster gains initial scene actors. IDs use the existing
    durable ordinary-NPC identity allocator.
    """
    members = tuple(members)
    if tuple(member["ref"] for member in members) not in ((3518,), (5848,)):
        return members, None
    from .combat_encounter_roles import role_assignment, ORDINARY_POLICY

    if (
        role_assignment(character["map_id"], tuple(m["ref"] for m in members)).policy
        != ORDINARY_POLICY
    ):
        return members, None
    from .combat_supreme_scene_policies import policy_for_reference

    if any(
        (policy_for_reference(member["ref"]) or {}).get("map_id") == character["map_id"]
        for member in members
    ):
        return members, None
    scope = _scene(character, members)
    if scope is None:
        return members, None
    policy, definitions = scope
    cells = _cells(character, members, definitions)
    from wakfu_server import native_catalog
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block

    revision = native_catalog.release()
    with store.connection() as db:
        first = allocate_block(db, len(definitions))
    helpers, roles = [], []
    for index, (definition, cell) in enumerate(zip(definitions, cells)):
        role, ref, level, side, controller = definition
        member = owned_instance(
            ref,
            level,
            -(first + index),
            map_id=character["map_id"],
            instance_id=character.get("instance_id", 0),
            x=cell[0],
            y=cell[1],
            z=cell[2],
            team=0 if side == "player" else 1,
        )
        helpers.append(member)
        roles.append(
            dict(
                role=role,
                actor_id=member["id"],
                reference=ref,
                level=level,
                initial_position=list(cell),
                team_role=side,
                controller_role=controller,
                reward_eligible=side == "npc",
            )
        )
    if native_catalog.release() != revision:
        raise ValueError("Scene helper native source changed during preparation")
    source = dict(
        schema=SCHEMA,
        policy=policy,
        version=1,
        authority="explicit_source_backed_wakemu_reconstruction",
        original_spawn="unrecovered",
        anchors="adapted_actual_reachable_native_terrain",
        catalog_revision=revision,
        map_id=character["map_id"],
        instance_id=character.get("instance_id", 0),
        principal_id=character["id"],
        account_id=character["account_id"],
        originals=[
            dict(
                id=m["id"],
                reference=m["ref"],
                position=[m[key] for key in ("x", "y", "z")],
            )
            for m in members
        ],
        helpers=roles,
        source_facts=(
            [
                "native3518:HP30000",
                "native3516:level150/state3373",
                "native3380:global1012/148500=12500",
                "reviewed guide:three globs; initial assembly is explicit reconstruction",
            ]
            if policy == SECURITY_POLICY
            else [
                "native guide175:level96/player-controlled allies",
                "native5849:9149/9169",
                "native5850:9169",
            ]
        ),
    )
    return members + tuple(helpers), dict(
        source=source, source_digest=canonical_digest(source)
    )


def validated_manifest(manifest):
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"source", "source_digest"}
        or manifest["source_digest"] != canonical_digest(manifest["source"])
    ):
        raise ValueError("Initial scene helper manifest changed")
    source = manifest["source"]
    if (
        source.get("schema") != SCHEMA
        or source.get("version") != 1
        or source.get("policy") not in (SPIRIT_POLICY, SECURITY_POLICY)
        or source.get("authority") != "explicit_source_backed_wakemu_reconstruction"
    ):
        raise ValueError("Unknown initial scene helper authority")
    expected = (
        ((5849, "player", "principal"), (5850, "player", "principal"))
        if (source["policy"] == SPIRIT_POLICY)
        else ((3516, "npc", "self"),) * 3
    )
    actual = tuple(
        (row["reference"], row["team_role"], row["controller_role"])
        for row in source["helpers"]
    )
    expected_original = 5848 if source["policy"] == SPIRIT_POLICY else 3518
    if (
        actual != expected
        or len(source["originals"]) != 1
        or source["originals"][0]["reference"] != expected_original
        or any(
            type(row["actor_id"]) is not int or row["actor_id"] >= 0
            for row in source["helpers"]
        )
        or len({row["actor_id"] for row in source["helpers"]}) != len(actual)
    ):
        raise ValueError("Scene helper role roster differs from its typed declaration")
    return source


def adapt_helper_placement(character, members, arena):
    """Put friendly native helpers in real free player placement cells.

    Call before freezing the placement policy or deriving glyph footprints.
    Enemy helper layouts retain the normal adapted arena generator.
    """
    manifest = arena.get("native_encounter_scene_helpers")
    if manifest is None:
        return arena
    source = validated_manifest(manifest)
    order = [member["id"] for member in members]
    expected = {row["id"] for row in source["originals"]} | {
        row["actor_id"] for row in source["helpers"]
    }
    if len(order) != len(set(order)) or set(order) != expected:
        raise ValueError(
            "Scene helper seed order differs from its actual member roster"
        )
    arena["native_encounter_scene_helper_seed_order"] = order
    arena["native_encounter_scene_helper_seed_positions"] = [
        [member[key] for key in ("x", "y", "z")] for member in members
    ]
    friendly = {
        row["actor_id"] for row in source["helpers"] if row["team_role"] == "player"
    }
    if not friendly:
        return arena
    from .combat_encounter_scene_layout import scene_player_position
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_obstacle_condition import footprint

    catalog = native_actor_catalog()
    player = scene_player_position(character, arena)
    pairs = arena.get("participant_positions", [])
    if pairs and len(pairs) != len(members):
        raise ValueError("Scene helper layout lost its actual NPC roster")
    destinations = (
        [tuple(pair[1]) for pair in pairs]
        if pairs
        else [tuple(member[key] for key in ("x", "y", "z")) for member in members]
    )
    occupied = set(footprint(player, catalog["default_actor_radius"]))
    for member, cell in zip(members, destinations):
        if member["id"] not in friendly:
            occupied.update(
                footprint(
                    cell, catalog["npc_profiles"][str(member["ref"])]["physical_radius"]
                )
            )
    cells = {tuple(cell) for cell in arena["placement_cells"][0]}
    if not cells <= set(arena["validated_cells"]):
        raise ValueError("Friendly helper placement leaves actual native arena")
    for index, member in enumerate(members):
        if member["id"] not in friendly:
            continue
        radius = catalog["npc_profiles"][str(member["ref"])]["physical_radius"]
        choices = sorted(
            cells,
            key=lambda cell: (
                abs(cell[0] - player[0]) + abs(cell[1] - player[1]),
                cell,
            ),
        )
        for cell in choices:
            covered = set(footprint(cell, radius))
            if not covered & occupied and all(
                (x, y, cell[2]) in arena["validated_cells"] for x, y in covered
            ):
                destinations[index] = cell
                occupied.update(covered)
                break
        else:
            raise ValueError(
                "Player placement cannot hold complete native helper bodies"
            )
    arena["participant_positions"] = [
        [list(member[key] for key in ("x", "y", "z")), list(cell)]
        for member, cell in zip(members, destinations)
    ]
    return arena


def helper_member_team(arena, member):
    """Exact verified ordinary source team for this declared initial helper."""
    manifest = arena.get("native_encounter_scene_helpers")
    if manifest is None:
        return 1
    source = validated_manifest(manifest)
    row = next(
        (row for row in source["helpers"] if row["actor_id"] == member["id"]), None
    )
    if row is None:
        return 1
    if row["reference"] != member["ref"] or row["level"] != member["level"]:
        raise ValueError("Initial helper raw member differs from its declared source")
    return 0 if row["team_role"] == "player" else 1


def apply_helper_constructor_roles(
    character, members, actors, arena, *, fight_id, player_team, npc_team
):
    """Apply initial team before actual fdt/global/QI registration exists."""
    manifest = arena.get("native_encounter_scene_helpers")
    if manifest is None:
        return None
    source = validated_manifest(manifest)
    by_id = {member["id"]: member for member in members}
    expected = {row["id"] for row in source["originals"]} | {
        row["actor_id"] for row in source["helpers"]
    }
    if (
        set(by_id) != expected
        or set(actors) != expected
        or source["principal_id"] != character["id"]
        or source["account_id"] != character["account_id"]
        or source["map_id"] != character["map_id"]
        or source["map_id"] != arena["map_id"]
        or source["instance_id"] != character.get("instance_id", 0)
    ):
        raise ValueError("Scene helper manifest belongs to another actual placement")
    if any(by_id[row["id"]]["ref"] != row["reference"] for row in source["originals"]):
        raise ValueError("Scene helper original source breed changed")
    for row in source["helpers"]:
        member, actor = by_id[row["actor_id"]], actors[row["actor_id"]]
        if (
            member["ref"] != row["reference"]
            or member["level"] != row["level"]
            or actor.controlled
            or actor.owner_id is not None
            or getattr(actor, "native_summon_source", None) is not None
        ):
            raise ValueError("Scene helper is not its ordinary native NPC constructor")
        actor.team = player_team if row["team_role"] == "player" else npc_team
        actor.native_scene_helper_origin = dict(
            source="explicit_initial_scene_npc",
            fight_id=fight_id,
            manifest_digest=manifest["source_digest"],
            role=row["role"],
        )
    return deepcopy(manifest)


def helper_initial_team(fight, actor_id):
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return None
    source = validated_manifest(manifest)
    from .combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    for row in source["helpers"]:
        if row["actor_id"] == actor_id:
            actor = fight.actors.get(actor_id)
            origin = getattr(actor, "native_scene_helper_origin", None)
            if (
                not isinstance(origin, dict)
                or origin.get("fight_id") != fight.id
                or origin.get("manifest_digest") != manifest["source_digest"]
            ):
                raise ValueError("Initial scene helper lost its constructor source")
            return roles.player_team if row["team_role"] == "player" else roles.npc_team
    return None


def bind_scene_helper_controls(fight, *, source_policy, source_digest):
    """Separate authored current controller from immutable ordinary NPC birth.

    This server primitive does not claim a native207 effect or client book
    publication. The source-qualified client control codec is a separate adapter.
    """
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return ()
    source = validated_manifest(manifest)
    if source["policy"] != source_policy or source_digest != manifest["source_digest"]:
        raise ValueError("Scene controller belongs to another frozen helper source")
    from .combat_controller_registry import transfer_native_controller, _row
    from .combat_ai_control import set_native_ai_control
    from .combat_encounter_actor_contract import bind_actor_role

    records = []
    for row in source["helpers"]:
        actor = fight.actors[row["actor_id"]]
        if helper_initial_team(fight, actor.id) != actor.team:
            raise ValueError("Scene helper original team changed")
        receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor.id)
        if not isinstance(receipt, dict) or receipt.get("ref") != row["reference"]:
            raise ValueError(
                "Scene controller requires actual ordinary native initialization"
            )
        if row["controller_role"] == "self":
            continue
        principal = fight.actors.get(source["principal_id"])
        if (
            principal is None
            or not principal.controlled
            or principal.owner_id != source["account_id"]
        ):
            raise ValueError("Scene controller lost its actual owned player")
        if getattr(fight, "native_encounter_actor_contract", None) is not None:
            bind_actor_role(fight, row["role"], actor.id)
        original = deepcopy(_row(fight, actor.id))
        transfer_native_controller(fight, actor.id, principal.id)
        set_native_ai_control(actor, False)
        records.append(
            dict(
                actor_id=actor.id,
                controller_id=principal.id,
                original_controller=original["original_controller"],
                original_team=original["original_team"],
                role=row["role"],
                source_policy=source_policy,
                source_digest=source_digest,
                constructor="ordinary_npc",
                client_publication="native_12514_fdA_controller_snapshot",
            )
        )
    fight.native_scene_helper_controls = records
    return tuple(deepcopy(records))


def reward_eligible_members(fight, members):
    """Friendly initial scene NPCs never become kill/XP/drop source monsters."""
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return tuple(members)
    source = validated_manifest(manifest)
    excluded = {
        row["actor_id"] for row in source["helpers"] if not row["reward_eligible"]
    }
    return tuple(member for member in members if member["id"] not in excluded)


def scene_helper_controller_records(fight):
    """Actual fdy rows for the native12514 codec, qualified by helper birth."""
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    controls = getattr(fight, "native_scene_helper_controls", ())
    if manifest is None or not controls:
        return ()
    source = validated_manifest(manifest)
    allowed = {
        row["actor_id"]: row
        for row in source["helpers"]
        if row["controller_role"] == "principal"
    }
    from .combat_controller_registry import _row
    from .combat_global_pv_collections import _collections
    from .combat_scene_controller_snapshot import NativeControllerRecord

    statuses = _collections(fight)["fighter_status"]
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(fight)
    result, seen = [], set()
    for receipt in controls:
        identity = receipt["actor_id"]
        role = allowed.get(identity)
        actor = fight.actors.get(identity)
        if (
            role is None
            or actor is None
            or identity in seen
            or receipt.get("source_policy") != source["policy"]
            or receipt.get("source_digest") != manifest["source_digest"]
            or receipt.get("constructor") != "ordinary_npc"
            or actor.controlled
            or actor.owner_id is not None
            or getattr(actor, "native_summon_source", None) is not None
            or helper_initial_team(fight, identity) != actor.team
        ):
            raise ValueError("Controller publication lacks its actual scene NPC source")
        seen.add(identity)
        current = _row(fight, identity)
        if (
            current["original_controller"] != receipt["original_controller"]
            or current["original_team"] != receipt["original_team"]
        ):
            raise ValueError("Scene helper original controller changed")
        if identity in hidden:
            continue  # A fresh client has no retired helper bje to receive a row.
        result.append(
            NativeControllerRecord(
                actor_id=identity,
                status=statuses[str(identity)],
                current_team=current["current_team"],
                original_team=current["original_team"],
                is_summon=False,
                original_controller_id=current["original_controller"],
                is_team_leader=False,
                current_controller_id=current["current_controller"],
            )
        )
    if seen != set(allowed):
        raise ValueError("Controller publication lacks a required initial helper")
    return tuple(result)


def controlled_scene_helper(fight, actor, *, character_id, account_id):
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return False
    source = validated_manifest(manifest)
    role = next(
        (
            row
            for row in source["helpers"]
            if row["actor_id"] == actor.id and row["controller_role"] == "principal"
        ),
        None,
    )
    if role is None:
        return False
    if source["principal_id"] != character_id or source["account_id"] != account_id:
        raise ValueError("Ordinary scene NPC belongs to another player")
    records = scene_helper_controller_records(fight)
    if not any(row.actor_id == actor.id for row in records):
        raise ValueError("Ordinary scene NPC has no authored current-controller source")
    from .combat_effective_control import require_effective_owner

    require_effective_owner(fight, actor, account_id)
    birth = getattr(fight, "native_npc_initialization_receipts", {}).get(actor.id)
    if (
        not isinstance(birth, dict)
        or birth.get("initialized") is not True
        or birth.get("ref") != role["reference"]
        or birth.get("descriptor_level") != actor.effective_level
        or actor.effective_level != role["level"]
    ):
        raise ValueError(
            "Ordinary scene NPC action lost its original native book source"
        )
    return True


def resolve_scene_helper_action(fight, actor, *, character_id, account_id, uid):
    """Resolve ordinary bje.dos/bPD raw actions without summon ownership."""
    if not controlled_scene_helper(
        fight, actor, character_id=character_id, account_id=account_id
    ):
        return None
    from .combat_spell_grant_book import removed_raw_uids

    if type(uid) is not int or uid in removed_raw_uids(fight, actor.id):
        raise ValueError("Ordinary scene NPC action UID is absent or removed")
    manifest = validated_manifest(fight.native_scene_helper_manifest)
    role = next(row for row in manifest["helpers"] if row["actor_id"] == actor.id)
    from wakfu_server.monsters import native_abilities

    for ability in native_abilities(role["reference"], actor.effective_level):
        # Native bPD initialization gives each fresh bPO its definition UID.
        if ability["spell_id"] == uid:
            return uid, ability["spell_level"]
    raise ValueError("Spell UID absent from the ordinary scene NPC native book")


def helper_actor_ids_for_departing(fight, departing_actor_ids):
    """Only actual ordinary helpers whose current human controller departs."""
    removed = frozenset(departing_actor_ids)
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return ()
    source = validated_manifest(manifest)
    if source["policy"] != SPIRIT_POLICY:
        return ()
    from .combat_global_pv_collections import global_fighter_guards
    from .combat_controller_registry import current_native_controller
    from .combat_forced_retirement import retired_forced_fighter_ids

    already = retired_forced_fighter_ids(fight)
    # This also proves actual ordinary births and original fdy rows; it never
    # treats every protected friendly NPC as belonging to a leaving player.
    records = scene_helper_controller_records(fight)
    candidates = []
    for row in records:
        if (
            row.actor_id in already
            or current_native_controller(fight, row.actor_id) not in removed
        ):
            continue
        actor = fight.actors[row.actor_id]
        if (
            global_fighter_guards(fight, actor.id)
            != dict(baF=True, baG=False, baK=False)
            or actor.effect_minima is None
            or actor.effect_minima.get(1) != 1
        ):
            raise ValueError(
                "Departing scene helper lost its actual protected live role"
            )
        candidates.append(actor.id)
    return tuple(candidates)


def retire_departing_scene_helpers(
    fight, departing_actor_ids, runtime_factory, packets
):
    """Explicit reconstructed scene exit using the real native934 primitive.

    Original Spirit exit caller is unavailable. Native117993 is a verified
    zero-parameter934 SELF prototype, not asserted to be an original Spirit
    spell. The exact helper/controller departure is this server-authored source.
    Caller owns the detached withdrawal transaction; HP/minimum1 stay intact.
    """
    identities = helper_actor_ids_for_departing(fight, departing_actor_ids)
    if not identities:
        return ()
    if not callable(runtime_factory) or fight.phase != "active":
        raise ValueError("Living scene helper exit requires its owned native runtime")
    from collections.abc import Mapping
    from .combat_effect_dispatch import EffectInvocation
    from .combat_encounter_actor_contract_terminal import _preserved
    from .combat_forced_retirement import retired_forced_fighter_ids
    from .combat_global_pv_collections import global_fighter_guards
    from .combat_qi_fight import current_registry
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    dispatcher, outbox = runtime_factory(
        fight, {"native_retained_container": {"present": False}}
    )
    if dispatcher.native_retention.fight is not fight:
        raise ValueError("Scene helper exit changed its actual withdrawal preview")
    effect = dispatcher.effects.get("117993")
    if (
        not isinstance(effect, Mapping)
        or effect.get("effect_class") != 934
        or effect.get("parameter_count") != 0
        or effect.get("parameters") != []
        or effect.get("children")
        or effect.get("criteria") != ""
    ):
        raise ValueError("Missing unchanged native934 scene-exit prototype")
    before = {identity: _preserved(fight.actors[identity]) for identity in identities}
    prior_retired = retired_forced_fighter_ids(fight)
    deliveries = []
    with fight.effect_resolution():
        for identity in identities:
            actor = fight.actors[identity]
            dispatcher.execute(
                EffectInvocation(
                    117993,
                    actor.effective_level,
                    identity,
                    identity,
                    actor.position,
                    native_retained_container={"present": False},
                )
            )
            native = getattr(fight, "native_forced_retirements", {}).get(str(identity))
            if (
                not isinstance(native, dict)
                or native.get("source") != "native.eXl934.eGj_dnu.v1"
                or identity not in retired_forced_fighter_ids(fight)
                or _preserved(actor) != before[identity]
                or actor.native_obstacle_id != -1
                or global_fighter_guards(fight, identity)
                != dict(baF=False, baG=False, baK=True)
                or identity not in hidden_snapshot_actor_ids(fight)
            ):
                raise ValueError(
                    "Scene helper exit lacks genuine HP-preserving native retirement"
                )
            current_registry(fight)
            deliveries.append(
                dict(
                    actor_id=identity,
                    running_uid=native["uid"],
                    prototype_reference=117993,
                    family=934,
                    source="declared_scene_current_controller_departure",
                    source_digest=fight.native_scene_helper_manifest["source_digest"],
                )
            )
    if (
        retired_forced_fighter_ids(fight) - prior_retired != set(identities)
        or any(identity in fight.order for identity in identities)
        or not any(opcode == 13497 for opcode, _ in outbox)
    ):
        raise ValueError("Scene helper departure changed the wrong native population")
    fight.native_scene_helper_departures = (
        list(getattr(fight, "native_scene_helper_departures", ())) + deliveries
    )
    packets.extend(outbox)
    return identities


def helper_score_owner_receipt(fight, actor):
    """Attribute living ordinary helper damage through its actual Ready human.

    This is explicitly scene-NPC provenance, never registered-summon ownership.
    A native current-controller change remains authoritative over the original
    principal, while the complete Ready roster bounds eligible score owners.
    """
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return None
    source = validated_manifest(manifest)
    if source["policy"] != SPIRIT_POLICY:
        return None
    role = next(
        (
            row
            for row in source["helpers"]
            if row["actor_id"] == actor.id and row["controller_role"] == "principal"
        ),
        None,
    )
    if role is None:
        return None
    from .combat_encounter_objective_spirit import spirit_admission

    admission = spirit_admission(fight)
    if admission is None or admission.get("status") != "granted":
        return None
    ready = admission.get("ready_participants")
    if ready is None:
        return None
    records = scene_helper_controller_records(fight)
    if not any(row.actor_id == actor.id and row.status == "IN_PLAY" for row in records):
        return None
    from .combat_controller_registry import current_native_controller
    from .combat_effective_control import effective_input_owner

    controller_id = current_native_controller(fight, actor.id)
    controller = fight.actors.get(controller_id)
    if controller is None or not controller.controlled:
        return None
    account_id = effective_input_owner(fight, actor)
    if account_id is None or account_id != controller.owner_id:
        return None
    if (
        dict(actor_id=controller_id, account_id=account_id)
        not in ready["source"]["players"]
    ):
        return None
    birth = getattr(fight, "native_npc_initialization_receipts", {}).get(actor.id)
    if (
        not isinstance(birth, dict)
        or birth.get("initialized") is not True
        or birth.get("ref") != role["reference"]
        or birth.get("descriptor_level") != actor.effective_level
        or actor.effective_level != role["level"]
    ):
        raise ValueError("Scene damage helper lost its genuine native NPC birth")
    return dict(
        schema="wakemu.scene-helper-score-owner.v1",
        source="declared_initial_scene_npc.current_human_controller.v1",
        owner_actor_id=controller_id,
        current_controller_id=controller_id,
        account_id=account_id,
        native_birth_digest=canonical_digest(birth),
        actor_id=actor.id,
        reference=role["reference"],
        descriptor_level=actor.effective_level,
        source_policy=source["policy"],
        source_digest=manifest["source_digest"],
        fight_id=fight.id,
        map_id=source["map_id"],
        catalog_revision=source["catalog_revision"],
        ready_digest=ready["source_digest"],
    )
