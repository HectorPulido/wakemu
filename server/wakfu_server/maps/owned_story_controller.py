"""Declarative, owner-scoped room mechanics backed by durable native producers.

This module never interprets a client callback as a victory. The caller owns
its action barrier and SQL transaction, and must apply every returned mechanic
through its normal native adapter before the receipt commits. Profiles remain
inactive until their encounters, door collision and presentation adapters exist.
"""

from copy import deepcopy
from hashlib import sha256
import json
import re
import struct

from wakfu_server.achievements import storage

SCHEMA = "owned-story-controller-v1"
KINDS = frozenset(
    (
        "interactive",
        "dynamic_pickup",
        "zone_trigger",
        "room_admission",
        "room_available",
        "room_victory",
        "room_defeat",
        "emote_performed",
        "native_travel",
        "scenario_complete",
        "world_ready",
        "npc_spoken",
        "npc_target",
        "npc_targets_completed",
        "trial_success",
    )
)
EFFECTS = frozenset(
    (
        "scenario_event",
        "element_state",
        "native_loot",
        "native_transfer",
        "quest_objective",
        "scene_position",
        "stage_position",
        "native_state",
        "context_refresh",
        "native_item_gate",
        "reviewed_item_grant",
    )
)


def _positive(value):
    return type(value) is int and value > 0


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def policy(configuration):
    selected = configuration.get("topology", {}).get("owned_story_controller")
    if selected is None:
        return None
    if (
        type(selected) is not dict
        or selected.get("schema") != SCHEMA
        or not isinstance(selected.get("id"), str)
        or not selected["id"]
        or not _positive(selected.get("map_id"))
        or type(selected.get("maximum_members")) is not int
        or selected["maximum_members"] != 1
        or not selected.get("provenance")
    ):
        raise ValueError("Invalid reviewed owned story policy")
    from wakfu_server import owned_story_entry_variants

    owned_story_entry_variants.alternatives(selected.get("admission"))
    if selected.get("interaction_approach_policy") not in (None, "pinned_native_qv"):
        raise ValueError("Unsupported owned native interaction approach policy")
    if selected.get("npc_public_visit") is not None:
        from wakfu_server import owned_story_npc_entry

        owned_story_npc_entry.public_visit_destination(selected["npc_public_visit"])
    steps = selected.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Owned story has no reviewed room steps")
    seen = set()
    for step in steps:
        if (
            type(step) is not dict
            or set(step)
            != {"id", "kind", "reference", "requires", "effects", "evidence"}
            or not isinstance(step["id"], str)
            or not step["id"]
            or step["id"] in seen
            or step["kind"] not in KINDS
            or not _positive(step["reference"])
            or not step["evidence"]
            or not isinstance(step["requires"], list)
            or not set(step["requires"]) <= seen
            or len(set(step["requires"])) != len(step["requires"])
            or not isinstance(step["effects"], list)
        ):
            raise ValueError("Invalid or unordered owned story step")
        for effect in step["effects"]:
            if type(effect) is not dict or effect.get("kind") not in EFFECTS:
                raise ValueError("Unsupported owned story mechanic")
            if effect["kind"] == "scenario_event":
                valid = set(effect) in (
                    {"kind", "scenario", "event"},
                    {"kind", "scenario", "event", "arguments"},
                ) and all(_positive(effect[key]) for key in ("scenario", "event"))
                if "arguments" in effect:
                    valid = (
                        valid
                        and isinstance(effect["arguments"], list)
                        and all(
                            value
                            in ("owner", "source_object", "boss_actor", "boss_trigger")
                            or isinstance(value, str)
                            and re.fullmatch(
                                r"room_actor:[1-9][0-9]*:(?:0|[1-9][0-9]*)", value
                            )
                            is not None
                            or isinstance(value, str)
                            and re.fullmatch(r"story_npc:[1-9][0-9]*", value)
                            is not None
                            or isinstance(value, str)
                            and re.fullmatch(r"story_target:[1-9][0-9]*", value)
                            is not None
                            or isinstance(value, str)
                            and re.fullmatch(r"scene_actor:[a-z][a-z0-9-]*", value)
                            is not None
                            or type(value) is int
                            and value == 0
                            for value in effect["arguments"]
                        )
                    )
            elif effect["kind"] == "element_state":
                # The same declaration drives the native visual and collision;
                # a visual-only door opening is not a supported mechanic.
                valid = (
                    set(effect)
                    == {
                        "kind",
                        "object_id",
                        "state",
                        "visible",
                        "usable",
                        "blocks_movement",
                    }
                    and _positive(effect["object_id"])
                    and type(effect["state"]) is int
                    and 0 <= effect["state"] < 32768
                    and all(
                        type(effect[key]) is bool
                        for key in ("visible", "usable", "blocks_movement")
                    )
                    and (effect["visible"] or not effect["usable"])
                )
            elif effect["kind"] == "context_refresh":
                valid = set(effect) == {"kind"}
            elif effect["kind"] == "native_state":
                valid = (
                    set(effect) == {"kind", "state_id", "active"}
                    and _positive(effect["state_id"])
                    and effect["state_id"] <= 32767
                    and type(effect["active"]) is bool
                )
            elif effect["kind"] == "native_item_gate":
                valid = (
                    set(effect) == {"kind", "reference", "quantity", "consume"}
                    and all(
                        _positive(effect.get(key)) for key in ("reference", "quantity")
                    )
                    and type(effect.get("consume")) is bool
                )
            elif effect["kind"] == "reviewed_item_grant":
                valid = (
                    set(effect) == {"kind", "source_id"}
                    and isinstance(effect["source_id"], str)
                    and bool(effect["source_id"])
                )
            elif effect["kind"] == "native_loot":
                valid = set(effect) in (
                    {"kind", "table_id"},
                    {"kind", "table_id", "source_id", "effect_reference"},
                ) and all(_positive(effect.get(key)) for key in set(effect) - {"kind"})
            elif effect["kind"] == "native_transfer":
                valid = set(effect) == {
                    "kind",
                    "source_id",
                    "effect_reference",
                } and all(
                    _positive(effect[key]) for key in ("source_id", "effect_reference")
                )
            elif effect["kind"] == "scene_position":
                valid = (
                    set(effect) == {"kind", "scenario", "event", "position"}
                    and _positive(effect["scenario"])
                    and _positive(effect["event"])
                    and isinstance(effect["position"], list)
                    and len(effect["position"]) == 3
                    and all(type(value) is int for value in effect["position"])
                )
            elif effect["kind"] == "stage_position":
                valid = (
                    set(effect) == {"kind", "event", "position"}
                    and _positive(effect["event"])
                    and isinstance(effect["position"], list)
                    and len(effect["position"]) == 3
                    and all(type(value) is int for value in effect["position"])
                )
            else:
                valid = set(effect) == {"kind", "quest_id", "objective_id"} and all(
                    _positive(effect[key]) for key in ("quest_id", "objective_id")
                )
            if not valid:
                raise ValueError("Owned story mechanic lacks its native identity")
        seen.add(step["id"])
    recovery = selected.get("recoverable_native_loot", [])
    qualified = {
        step["reference"]
        for step in steps
        if step["kind"] == "interactive"
        and any(
            effect["kind"] == "native_loot"
            and effect.get("source_id") == step["reference"]
            for effect in step["effects"]
        )
    }
    if (
        not isinstance(recovery, list)
        or any(not _positive(source) for source in recovery)
        or len(set(recovery)) != len(recovery)
        or not set(recovery) <= qualified
    ):
        raise ValueError(
            "Recoverable story loot lacks source-qualified native pickup steps"
        )
    sources = selected.get("native_sources")
    if sources is not None:
        from pathlib import Path

        if (
            type(sources) is not dict
            or set(sources) != {"path", "sha256"}
            or not isinstance(sources["path"], str)
            or Path(sources["path"]).name != sources["path"]
            or not sources["path"].endswith(".json")
            or not isinstance(sources["sha256"], str)
            or len(sources["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in sources["sha256"])
        ):
            raise ValueError("Invalid pinned owned story native sources")
    from wakfu_server import owned_story_auto_start

    owned_story_auto_start.declaration(selected)
    if selected.get("generic_transfers") is not None:
        from wakfu_server import owned_story_generic_transfer

        owned_story_generic_transfer.declarations(selected)
    if selected.get("emote_triggers") is not None:
        from wakfu_server import owned_story_emotes

        owned_story_emotes.triggers(selected)
    initial = selected.get("initial_elements", [])
    if (
        not isinstance(initial, list)
        or any(
            type(effect) is not dict
            or effect.get("kind") != "element_state"
            or set(effect)
            != {"kind", "object_id", "state", "visible", "usable", "blocks_movement"}
            or not _positive(effect["object_id"])
            or type(effect["state"]) is not int
            or not 0 <= effect["state"] < 32768
            or any(
                type(effect[key]) is not bool
                for key in ("visible", "usable", "blocks_movement")
            )
            or effect["usable"]
            and not effect["visible"]
            for effect in initial
        )
        or len({effect["object_id"] for effect in initial}) != len(initial)
    ):
        raise ValueError("Invalid initial owned story element projection")
    transfers = selected.get("native_transfers", [])
    if (
        not isinstance(transfers, list)
        or any(
            type(row) is not dict
            or set(row) != {"source_id", "effect_reference", "requires"}
            or not _positive(row["source_id"])
            or not _positive(row["effect_reference"])
            or not isinstance(row["requires"], list)
            or not set(row["requires"]) <= seen
            for row in transfers
        )
        or len({row["source_id"] for row in transfers}) != len(transfers)
    ):
        raise ValueError("Invalid reviewed native story transfers")
    if selected.get("native_links") is not None:
        from wakfu_server import owned_story_native_links

        owned_story_native_links.declarations(selected)
    if selected.get("trap_cycle") is not None:
        from wakfu_server import owned_story_traps

        trap = owned_story_traps.policy(selected["trap_cycle"])
        if trap["map_id"] != selected["map_id"] or not set(trap["requires"]) <= seen:
            raise ValueError("Owned trap cycle differs from the declared story graph")
    if selected.get("optional_companion") is not None:
        from wakfu_server import owned_companion_rescue

        owned_companion_rescue.policy(selected)
    if selected.get("terminal_returns") is not None:
        from wakfu_server import owned_story_terminal_returns

        owned_story_terminal_returns.policy(selected)
    from wakfu_server import owned_story_defeat_qualification

    owned_story_defeat_qualification.policy(selected)
    from wakfu_server import owned_story_capture_qualification

    owned_story_capture_qualification.policy(selected)
    from wakfu_server import owned_story_victory_qualification

    owned_story_victory_qualification.policy(selected)
    return selected


def plan(selected, completed, *, kind, reference):
    """Plan one authentic fact; duplicates and unavailable steps have no effect."""
    if not isinstance(completed, (set, frozenset)):
        raise ValueError("Owned story progress must be a durable receipt set")
    declared = {row["id"] for row in selected["steps"]}
    if not completed <= declared:
        raise ValueError("Owned story receipt belongs to another profile")
    candidates = [
        row
        for row in selected["steps"]
        if row["kind"] == kind
        and row["reference"] == reference
        and row["id"] not in completed
        and set(row["requires"]) <= completed
    ]
    if len(candidates) > 1:
        raise ValueError("Ambiguous owned story producer")
    return None if not candidates else deepcopy(candidates[0])


def presentation_state(selected, completed):
    """Restore only durable element state, never replay a cinematic or a reward."""
    result = {
        effect["object_id"]: deepcopy(effect)
        for effect in selected.get("initial_elements", ())
    }
    for step in selected["steps"]:
        if step["id"] in completed:
            for effect in step["effects"]:
                if effect["kind"] == "element_state":
                    result[effect["object_id"]] = deepcopy(effect)
    return tuple(result.values())


def _key(selected, instance, suffix):
    return f'owned-story:{selected["id"]}:{instance}:{suffix}'


def _scope(db, store, character, *, check_position=True, lock=True):
    if not _positive(character.get("instance_id")):
        raise ValueError("Owned story requires a private instance")
    row = db.execute(
        "SELECT i.context_route_key,i.context_policy_version,i.start_map_id "
        "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
        "WHERE i.instance_id=%s AND m.character_id=%s AND m.status='active' "
        + ("FOR UPDATE OF i,m" if lock else ""),
        (character["instance_id"], character["id"]),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned story membership")
    members = db.execute(
        "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s "
        "AND status='active' ORDER BY character_id " + ("FOR UPDATE" if lock else ""),
        (character["instance_id"],),
    ).fetchall()
    if members != [dict(character_id=character["id"])]:
        raise ValueError("Owned story requires its one original owner")
    from wakfu_server import dungeon_runtime_config

    configuration = dungeon_runtime_config.pinned_configuration(
        db, row["context_route_key"], row["context_policy_version"]
    )
    selected = policy(configuration)
    if (
        selected is None
        or character["map_id"] != selected["map_id"]
        or selected["map_id"] != row["start_map_id"]
    ):
        raise ValueError("Owned story differs from its pinned native map")
    current = (
        store.character(character["account_id"], character["id"], db)
        if check_position
        else db.execute(
            "SELECT map_id,instance_id FROM characters WHERE id=%s AND account_id=%s",
            (character["id"], character["account_id"]),
        ).fetchone()
    )
    if current is None:
        raise ValueError("Owned story owner no longer exists")
    keys = (
        ("map_id", "instance_id", "x", "y", "z")
        if check_position
        else ("map_id", "instance_id")
    )
    if any(current[key] != character[key] for key in keys):
        raise ValueError("Owned story position changed during its action")
    prefix = _key(selected, character["instance_id"], "")
    rows = db.execute(
        "SELECT event_key,payload FROM character_achievement_events "
        "WHERE character_id=%s AND left(event_key,%s)=%s",
        (character["id"], len(prefix), prefix),
    ).fetchall()
    completed = set()
    profile_digest = _digest(selected)
    for receipt in rows:
        data = receipt["payload"]
        if (
            data.get("schema") != SCHEMA
            or data.get("profile_sha256") != profile_digest
            or data.get("owner") != character["id"]
            or data.get("instance_id") != character["instance_id"]
        ):
            raise ValueError("Owned story receipt conflicts with its frozen profile")
        completed.add(data["step"])
    return selected, completed


def _settle(
    db,
    store,
    character,
    selected,
    completed,
    *,
    kind,
    reference,
    evidence,
    apply_effects,
):
    step = plan(selected, completed, kind=kind, reference=reference)
    if step is None:
        return dict(applied=False, packets=[], step=None)
    if not callable(apply_effects):
        raise ValueError("Owned story needs its native mechanic adapters")
    # Apply before recording; the enclosing transaction rolls both back on any
    # reward, collision, position, or presentation-adapter failure.
    applied = apply_effects(db, store, character, step["effects"])
    skipped_scenes = set(getattr(applied, "skipped_scenes", ()))
    packets = list(applied)
    receipt = dict(
        schema=SCHEMA,
        profile_sha256=_digest(selected),
        owner=character["id"],
        instance_id=character["instance_id"],
        step=step["id"],
        evidence=evidence,
        presentation_suppressed=bool(
            getattr(applied, "suppressed_presentations", False)
        ),
        presentation_delivered=bool(getattr(applied, "presentation_delivered", False)),
        refresh_context=bool(getattr(applied, "refresh_context", False)),
        created_ms=int(store.now().timestamp() * 1000),
    )
    if not storage.record_event(
        db,
        character["id"],
        _key(selected, character["instance_id"], step["id"]),
        receipt,
    ):
        raise ValueError("Owned story step receipt raced its native mechanics")
    if skipped_scenes:
        from wakfu_server.owned_story_mechanics import sources

        native = sources(selected)
        completed = set(completed) | {step["id"]}
        for event in skipped_scenes:
            callback = native["scenes"][str(event)]["callback"]
            followup = plan(
                selected, completed, kind="scenario_complete", reference=callback
            )
            if followup is None or step["id"] not in followup["requires"]:
                raise ValueError(
                    "Skipped native scene lacks its mechanical continuation"
                )
            outcome = _settle(
                db,
                store,
                character,
                selected,
                completed,
                kind="scenario_complete",
                reference=callback,
                evidence=dict(skipped_presentation=event, source_step=step["id"]),
                apply_effects=apply_effects,
            )
            packets.extend(outcome["packets"])
            completed.add(followup["id"])
    return dict(applied=True, packets=packets, step=step["id"])


def initialize(db, session, resolved, *, store):
    """Qualify native admission inside the existing owned entry transaction."""
    from wakfu_server import dungeon_runtime_config, dungeon_instances, companions
    from wakfu_server.achievements import owned_quest_encounters

    key = dungeon_instances.canonical_context_key(resolved["route"])
    configuration = dungeon_runtime_config.pinned_configuration(
        db, key, session["context_policy_version"]
    )
    selected = policy(configuration)
    if selected is None:
        return
    members = list(session["members"])
    if len(members) != 1 or companions.controlled_count(db, members):
        raise ValueError("Owned story requires a single character without company")
    owner = members[0]
    row = db.execute(
        "SELECT id,account_id FROM characters WHERE id=%s", (owner,)
    ).fetchone()
    if row is None:
        raise ValueError("Owned story owner no longer exists")
    character = store.character(row["account_id"], owner, db)
    _scope(db, store, character)
    state = storage.load_locked(db, owner)
    from wakfu_server import owned_companion_rescue

    from wakfu_server import owned_story_entry_variants

    admission = selected["admission"]
    variant = owned_story_entry_variants.running_variant(admission, state)
    if variant is not None and variant["objective_id"] is not None:
        owned_quest_encounters._advance(
            db,
            store,
            character,
            dict(quest_id=variant["quest_id"]),
            variant["objective_id"],
            f'owned-story-entry:{session["instance_id"]}:{variant["quest_id"]}',
            dict(instance_id=session["instance_id"], route_key=key),
        )
    # Physical content admission is independent of whether its story is assigned.
    # Optional rescue remains a story offer and requires genuine main progress.
    state = storage.load_locked(db, owner)
    if owned_story_entry_variants.admitted(admission, state):
        owned_companion_rescue.admit(db, store, character, selected)
    session["owned_story_controller"] = dict(owner=owner, policy=selected["id"])


def interact(db, store, character, body, *, apply_effects, inspect_only=False):
    """Observe one authenticated native object action, never arbitrary IDs."""
    from wakfu_server import world_static

    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Malformed owned story interaction")
    object_id, action, parameter = struct.unpack(">qHH", body)
    if action != 0 or parameter != 0:
        raise ValueError("Unsupported owned story native action")
    selected, completed = _scope(db, store, character)
    native = next(
        (
            row
            for row in world_static.objects(character["map_id"])
            if row["id"] == object_id
        ),
        None,
    )
    nearby = (
        native is not None
        and native.get("type") in ("GenericActivableInteractiveElement", "Door")
        and abs(character["z"] - native["z"]) <= 1
        and abs(character["x"] - native["x"]) + abs(character["y"] - native["y"]) <= 1
    )
    if (
        native is not None
        and native.get("type") == "GenericActivableInteractiveElement"
        and selected.get("interaction_approach_policy") == "pinned_native_qv"
    ):
        from wakfu_server import owned_story_mechanics, owned_story_generic_entry

        declared = (
            owned_story_mechanics.sources(selected)
            .get("interaction_approaches", {})
            .get(str(object_id))
        )
        if declared is not None:
            nearby = tuple(
                character[k] for k in ("x", "y", "z")
            ) in owned_story_generic_entry.validate_approaches(native, declared)
    if not nearby:
        raise ValueError("Owned story object is outside its native interaction range")
    pending = plan(selected, completed, kind="interactive", reference=object_id)
    if inspect_only:
        return dict(selected=selected, completed=completed, native=native, step=pending)
    gate_step = pending or next(
        (
            step
            for step in selected["steps"]
            if step["kind"] == "interactive" and step["reference"] == object_id
        ),
        None,
    )
    if gate_step is not None:
        from wakfu_server import owned_story_item_gates

        failure = owned_story_item_gates.failure_packets(
            store, character, selected, gate_step["effects"]
        )
        if failure is not None:
            return dict(applied=False, packets=failure, step=None)
    return _settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="interactive",
        reference=object_id,
        evidence=dict(object_id=object_id, action=action, parameter=parameter),
        apply_effects=apply_effects,
    )


def on_zone_trigger(db, store, character, object_id, *, apply_effects):
    """Accept a native trigger only at its actual committed movement position."""
    from wakfu_server import world_static

    selected, completed = _scope(db, store, character)
    from wakfu_server import native_interactive_activation

    native = next(
        (
            row
            for row in world_static.objects(character["map_id"])
            if row["id"] == object_id and row["type"] == "ZoneTrigger"
        ),
        None,
    )
    allowed = (
        set()
        if native is None
        else set(map(tuple, native_interactive_activation.decode(native)))
    )
    if native is None or tuple(character[k] for k in ("x", "y", "z")) not in allowed:
        raise ValueError("Owned story trigger lacks its actual native arrival")
    return _settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="zone_trigger",
        reference=object_id,
        evidence=dict(
            object_id=object_id, position=[character[k] for k in ("x", "y", "z")]
        ),
        apply_effects=apply_effects,
    )


def on_scene_complete(db, store, character, body, *, pending_step, apply_effects):
    """A client may acknowledge only its explicitly offered current scene."""
    if not isinstance(body, bytes) or len(body) != 4:
        raise ValueError("Malformed owned story scene completion")
    event = struct.unpack(">i", body)[0]
    selected, completed = _scope(db, store, character)
    step = plan(selected, completed, kind="scenario_complete", reference=event)
    if step is None or pending_step != (character["instance_id"], step["id"]):
        raise ValueError("Owned story scene completion is not pending")
    offered = [
        row
        for row in selected["steps"]
        if row["id"] in step["requires"]
        and row["id"] in completed
        and any(effect["kind"] == "scenario_event" for effect in row["effects"])
    ]
    if not offered:
        raise ValueError("Owned story scene was never offered")
    return _settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="scenario_complete",
        reference=event,
        evidence=dict(callback=event, offered_steps=[row["id"] for row in offered]),
        apply_effects=apply_effects,
    )


def on_room_victory(db, store, character, fight, original_monsters, *, apply_effects):
    """Observe the actual durable encounter, never a cinematic's claimed win."""
    from wakfu_server import dungeon_runtime_config
    from wakfu_server.achievements import owned_quest_encounters

    if fight.phase != "finished" or type(fight.winner) is not int:
        raise ValueError("Owned story requires an actually finished battle")
    selected, completed = _scope(db, store, character)
    row = db.execute(
        "SELECT e.*,i.context_route_key,i.context_policy_version FROM dungeon_room_encounters e "
        "JOIN dungeon_instances i USING(instance_id) JOIN combat_fights f ON f.id=e.fight_id "
        "JOIN combat_fight_participants p ON p.fight_id=e.fight_id "
        "WHERE e.fight_id=%s AND e.instance_id=%s AND e.encounter_scope='main' "
        "AND e.status='victory' AND f.status='finished' AND p.character_id=%s "
        "AND p.account_id=%s AND p.team=e.player_team AND e.player_team=%s",
        (
            fight.id,
            character["instance_id"],
            character["id"],
            character["account_id"],
            fight.winner,
        ),
    ).fetchone()
    if row is not None and row["result"].get("qualified") is False:
        return dict(applied=False, packets=[], step=None)
    if row is None or row["result"].get("victory") is not True:
        raise ValueError("Owned story lacks its settled original encounter")
    configuration = dungeon_runtime_config.pinned_configuration(
        db, row["context_route_key"], row["context_policy_version"]
    )
    rooms = [
        room
        for room in configuration["compiled_plan"]["rooms"]
        if room["order"] == row["room_order"]
    ]
    if len(rooms) != 1:
        raise ValueError("Owned story room differs from its frozen formation")
    roster = dict(
        roster=[
            dict(reference=monster["ref_id"], count=monster["count"])
            for monster in rooms[0]["monsters"]
        ]
    )
    spawned = db.execute(
        "SELECT g.members,g.status,r.asset_map_id FROM dungeon_room_spawn_receipts r "
        "JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
        "WHERE r.instance_id=%s AND r.room_order=%s",
        (character["instance_id"], row["room_order"]),
    ).fetchone()
    identities = {(m["id"], m["ref"]) for m in original_monsters}
    actual_deaths = {
        event.get("actor_id") for event in fight.events if event.get("kind") == "death"
    }
    from wakfu_server.combat_scene_box_goals import qualified_result

    board_victory = qualified_result(fight, original_monsters)
    from wakfu_server.combat_scene_ball_goals import qualified_result as ball_result

    ball_victory = ball_result(fight, original_monsters)
    if (getattr(fight, "native_encounter_scene", None) or {}).get("descriptor", {}).get(
        "ball_goals"
    ) is not None and not ball_victory:
        raise ValueError("Owned ball victory lacks its native touchdown")
    board_victory = board_victory or ball_victory
    if (getattr(fight, "native_encounter_scene", None) or {}).get("descriptor", {}).get(
        "native_movement_escape"
    ) is not None:
        from wakfu_server.combat_scene_movement_escape import outcome_qualified

        if not outcome_qualified(fight):
            raise ValueError(
                "Owned escape victory lacks its committed native departure"
            )
        board_victory = True
    from wakfu_server.combat_test_commands import administrative_victory

    operator_victory = administrative_victory(
        fight,
        account_id=character["account_id"],
        character_id=character["id"],
    )
    if (
        spawned is None
        or spawned["status"] != "defeated"
        or spawned["asset_map_id"] != selected["map_id"]
        or identities != {(m["id"], m["ref"]) for m in spawned["members"]}
        or len(identities) != len(original_monsters)
        or (
            not board_victory
            and not operator_victory
            and not {m["id"] for m in original_monsters} <= actual_deaths
        )
        or (
            not board_victory
            and not owned_quest_encounters.qualified_roster(
                fight, original_monsters, roster
            )
        )
    ):
        raise ValueError(
            "Owned story victory has no original defeated native formation"
        )
    from wakfu_server import owned_story_capture_qualification

    if not owned_story_capture_qualification.qualified(
        selected, fight, character["id"], original_monsters, row["room_order"]
    ):
        return dict(applied=False, packets=[], step=None)
    from wakfu_server import owned_story_victory_qualification

    if not owned_story_victory_qualification.qualified(
        selected, fight, character["id"], original_monsters, row["room_order"]
    ):
        return dict(applied=False, packets=[], step=None)
    outcome = _settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="room_victory",
        reference=row["room_order"],
        evidence=dict(
            fight_id=fight.id,
            room_order=row["room_order"],
            original_actor_ids=sorted(m["id"] for m in original_monsters),
        ),
        apply_effects=apply_effects,
    )
    from wakfu_server import owned_story_dynamic_pickups, owned_story_mechanics

    if outcome["applied"] and owned_story_mechanics.sources(selected).get(
        "reviewed_dynamic_pickups"
    ):
        current = store.character(character["account_id"], character["id"], db)
        outcome["packets"].extend(
            owned_story_dynamic_pickups.packets(db, store, current)
        )
    return outcome


def element_packets(selected, completed):
    """Project persisted object mechanics with typed Door collision flags."""
    from wakfu_server import world_static
    from wakfu_server.dungeon_object_states import physical_door_payload

    objects = {row["id"]: row for row in world_static.objects(selected["map_id"])}
    packets = []
    for effect in presentation_state(selected, completed):
        native = objects.get(effect["object_id"])
        if native is None:
            raise ValueError("Owned story state references an absent native object")
        if native["type"] == "Door":
            if effect["state"] != int(effect["blocks_movement"]):
                raise ValueError("Owned story Door visual disagrees with collision")
            payload = physical_door_payload(opened=not effect["blocks_movement"])
            payload = (
                payload[:9]
                + bytes((effect["visible"], effect["usable"]))
                + payload[11:]
            )
        elif native["type"] == "GenericActivableInteractiveElement":
            payload = bytes.fromhex("01020000000602") + struct.pack(
                ">h6Bi",
                effect["state"],
                effect["visible"],
                effect["usable"],
                0,
                effect["blocks_movement"],
                effect["blocks_movement"],
                0,
                0,
            )
        else:
            raise ValueError("Unsupported native owned story state projection")
        packets.append(
            (12344, struct.pack(">qH", effect["object_id"], len(payload)) + payload)
        )
    return tuple(packets)


def collision_projection(selected, completed, *, columns=None):
    """Return exact native blocked/opened masks for the same persisted states.

    The normal movement registry must apply these overrides together with the
    wire projection; visual updates alone do not authorize crossing a gate.
    """
    from wakfu_server import world_static
    from wakfu_server.combat_sn_path import NativeSnColumns
    from wakfu_server.dungeon_native_door_collision import native_blocking_cells

    rows = {row["id"]: row for row in world_static.objects(selected["map_id"])}
    masks = {True: set(), False: set()}
    for effect in presentation_state(selected, completed):
        native = rows.get(effect["object_id"])
        if native is None or native["type"] not in (
            "Door",
            "GenericActivableInteractiveElement",
        ):
            raise ValueError("Owned story collision references another native object")
        if columns is None:
            columns = NativeSnColumns.from_published(selected["map_id"])
        masks[effect["blocks_movement"]].update(
            native_blocking_cells(
                selected["map_id"],
                [native[k] for k in ("x", "y", "z")],
                columns=columns,
                expected_source_sha256=columns.source_sha256,
            )
        )
    # A separate closed object always wins when native footprints overlap.
    return dict(
        blocked=frozenset(masks[True]), opened=frozenset(masks[False] - masks[True])
    )


def recognizes_instance(db, instance_id):
    """Cheap marker lookup; unrelated dungeon entry never loads story assets."""
    if not _positive(instance_id):
        return False
    row = db.execute(
        "SELECT (q.configuration->'topology'->'owned_story_controller' IS NOT NULL "
        "AND q.configuration->'topology'->'owned_story_controller' <> 'null'::jsonb) AS present "
        "FROM dungeon_instances i JOIN dungeon_runtime_configurations q "
        "ON q.route_key=i.context_route_key AND q.policy_version=i.context_policy_version "
        "WHERE i.instance_id=%s",
        (instance_id,),
    ).fetchone()
    return row is not None and row["present"] is True


def validate_movement(db, store, character, request, configuration):
    """Use normal directed native walking with the same durable gate states."""
    if configuration.get("topology", {}).get("owned_object_trials") is not None:
        from wakfu_server import owned_object_trials

        return owned_object_trials.validate_movement(
            db, store, character, request, configuration
        )
    selected = policy(configuration)
    if selected is None:
        return False
    _, completed = _scope(db, store, character, check_position=False, lock=False)
    if pending_callback_step(selected, completed) is not None:
        raise ValueError("The owned story cinematic is still pending")
    from wakfu_server.spatial_native import get_spatial
    from wakfu_server.spatial_topology import directed_path

    from wakfu_server import owned_story_mechanics, owned_story_traps

    if owned_story_mechanics.pending_reset(db, character) is not None:
        raise ValueError("The native story fall animation is still pending")
    collision = collision_projection(selected, completed)
    actual = store.character(character["account_id"], character["id"], db)
    traps = owned_story_traps.projection(
        db, store, actual, configuration, initialize=False
    )
    if traps["active"]:
        raised = {
            effect["object_id"]
            for effect in traps["state_effects"]
            if effect["state"] == 1
        }
        collision["blocked"] = collision["blocked"] | {
            tuple(tile["position"])
            for tile in selected["trap_cycle"]["tiles"]
            if tile["object_id"] in raised
        }
    directed_path(
        get_spatial(),
        configuration["topology"]["exploration_geometry"],
        request,
        collision["blocked"],
    )
    return True


def settle_combat(db, store, character, fight, original_monsters):
    """Common normal/recovery combat settlement hook for declared stories only."""
    if not recognizes_instance(db, character.get("instance_id")):
        return []
    from wakfu_server import owned_quest_pools

    if owned_quest_pools.bound_fight(db, fight.id, character["id"]) is not None:
        return []  # The independent pool cannot earn the main boss's receipt.
    selected, _ = _scope(db, store, character)
    from wakfu_server.owned_story_mechanics import executor

    outcome = on_room_victory(
        db, store, character, fight, original_monsters, apply_effects=executor(selected)
    )
    return outcome["packets"]


def pending_scene(db, store, character, selected, completed):
    """Find the one offered scene awaiting native acknowledgment or its deadline."""
    callback = pending_callback_step(selected, completed)
    if callback is None:
        return None
    from wakfu_server.owned_story_mechanics import sources

    native = sources(selected)
    candidates = []
    for step in selected["steps"]:
        if step["id"] not in callback["requires"] or step["id"] not in completed:
            continue
        for effect in step["effects"]:
            scene = (
                native["scenes"].get(str(effect.get("event")))
                if effect["kind"] == "scenario_event"
                else None
            )
            if scene is not None:
                candidates.append((step, effect, scene))
    if len(candidates) != 1:
        raise ValueError("Owned callback has no unique original offered scene")
    step, effect, scene = candidates[0]
    receipt = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], _key(selected, character["instance_id"], step["id"])),
    ).fetchone()
    started = None if receipt is None else receipt["payload"].get("created_ms")
    if type(started) is not int or started < 0:
        raise ValueError("Owned scene is missing its authoritative start time")
    return dict(
        step=callback["id"],
        event=effect["event"],
        callback=callback["reference"],
        due_ms=started + scene["duration_ms"],
        marker=(character["instance_id"], callback["id"]),
    )


def complete_due_scene(db, store, character):
    """Recover an offered native scene after its literal Lua timer, without replay."""
    selected, completed = _scope(db, store, character)
    pending = pending_scene(db, store, character, selected, completed)
    if pending is None or int(store.now().timestamp() * 1000) < pending["due_ms"]:
        return dict(applied=False, packets=[], step=None)
    from wakfu_server.owned_story_mechanics import executor

    return on_scene_complete(
        db,
        store,
        character,
        struct.pack(">i", pending["callback"]),
        pending_step=pending["marker"],
        apply_effects=executor(selected),
    )


def pending_callback_step(selected, completed):
    candidates = [
        row
        for row in selected["steps"]
        if row["kind"] == "scenario_complete"
        and row["id"] not in completed
        and set(row["requires"]) <= completed
    ]
    if len(candidates) > 1:
        raise ValueError("Owned story has ambiguous pending cinematic callbacks")
    return None if not candidates else candidates[0]


def on_world_ready(db, store, character):
    """Publish the optional original entry guide once after actual scene load."""
    selected, completed = _scope(db, store, character)
    from wakfu_server import dungeon_runtime_config
    from wakfu_server.owned_story_mechanics import executor

    admitted = db.execute(
        "SELECT context_route_key,context_policy_version,entry_map_id,entry_object_id,entry_destination_id "
        "FROM dungeon_instances WHERE instance_id=%s",
        (character["instance_id"],),
    ).fetchone()
    if admitted is None:
        raise ValueError("Owned story readiness lacks its actual admitted entrance")
    frozen = dungeon_runtime_config.pinned_configuration(
        db, admitted["context_route_key"], admitted["context_policy_version"]
    )["route"]
    if admitted["context_route_key"] != frozen["key"] or any(
        admitted[actual] != frozen[expected]
        for actual, expected in (
            ("entry_map_id", "entry_map_id"),
            ("entry_object_id", "entry_object_id"),
            ("entry_destination_id", "destination_id"),
        )
    ):
        raise ValueError("Owned story readiness lost its exact native entrance context")
    return _settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="world_ready",
        reference=character["map_id"],
        evidence=dict(
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            route_key=admitted["context_route_key"],
            policy_version=admitted["context_policy_version"],
            entry_map_id=admitted["entry_map_id"],
            source_id=admitted["entry_object_id"],
            destination_id=admitted["entry_destination_id"],
        ),
        apply_effects=executor(selected),
    )
