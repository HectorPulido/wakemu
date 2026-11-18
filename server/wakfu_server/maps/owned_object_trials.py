"""Ordered objects, distinct discoveries and fragile carry in owned content.

The pure reducer has no quest or map special cases. The transaction adapter
qualifies the actual pinned instance, native object and owner before executing
trusted inventory/quest/presentation effects. Story assignment is not access.
"""

from copy import deepcopy
from hashlib import sha256
from functools import lru_cache
from pathlib import Path
import json
import re
import struct

from wakfu_server.achievements import storage

SCHEMA = "owned-object-trials-v1"
KINDS = {
    "ordered_objects",
    "distinct_discoveries",
    "fragile_carry",
    "sliding_tiles",
    "resource_course",
    "light_course",
    "stealth_course",
    "safe_course",
    "zone_checkpoint",
}


@lru_cache(maxsize=1)
def trial_maps():
    """Cheap routing only; a source manifest never authorizes an instance."""
    result = set()
    for path in (
        Path(__file__).with_name("owned_object_trial_profiles").glob("*.instance.json")
    ):
        value = json.loads(path.read_text())
        if value.get("content_policy") == SCHEMA and type(value.get("map_id")) is int:
            result.add(value["map_id"])
    for path in (
        Path(__file__).with_name("owned_story_profiles").glob("*.instance.json")
    ):
        value = json.loads(path.read_text())
        if (
            isinstance(value.get("object_trials"), str)
            and type(value.get("map_id")) is int
        ):
            result.add(value["map_id"])
    return frozenset(result)


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _point(value):
    return (
        isinstance(value, (tuple, list))
        and len(value) == 3
        and all(type(x) is int for x in value)
    )


def policy(configuration):
    selected = configuration.get("topology", {}).get("owned_object_trials")
    if selected is None:
        return None
    if (
        type(selected) is not dict
        or selected.get("schema") != SCHEMA
        or not isinstance(selected.get("id"), str)
        or not selected["id"]
        or type(selected.get("map_id")) is not int
        or selected["map_id"] <= 0
        or type(selected.get("maximum_members")) is not int
        or selected["maximum_members"] != 1
        or not isinstance(selected.get("sources"), list)
        or not isinstance(selected.get("trials"), list)
        or not selected["trials"]
    ):
        raise ValueError("Invalid owned object trial policy")
    sources = {}
    for row in selected["sources"]:
        if (
            type(row) is not dict
            or type(row.get("id")) is not int
            or row["id"] <= 0
            or row["id"] in sources
            or not _point(row.get("position"))
            or type(row.get("descriptor_id")) is not int
            or row["descriptor_id"] <= 0
            or type(row.get("action")) is not int
            or row["action"] < 0
            or type(row.get("duration_ms")) is not int
            or not 0 <= row["duration_ms"] <= 60000
            or type(row.get("payload_sha256")) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", row["payload_sha256"])
            or not isinstance(row.get("approaches"), list)
            or not row["approaches"]
            or any(not _point(point) for point in row["approaches"])
        ):
            raise ValueError(
                "Object trial requires its exact native source and approaches"
            )
        sources[row["id"]] = row
    seen = set()
    for trial in selected["trials"]:
        if (
            not isinstance(trial.get("id"), str)
            or not trial["id"]
            or trial["id"] in seen
            or trial.get("kind") not in KINDS
            or not isinstance(trial.get("requires"), list)
            or not set(trial["requires"]) <= seen
            or not isinstance(trial.get("effects"), dict)
            or set(trial["effects"]) != {"begin", "success", "failure"}
            or any(not isinstance(value, list) for value in trial["effects"].values())
            or not isinstance(trial.get("requires_story_steps", []), list)
            or any(
                type(value) is not str or not value
                for value in trial.get("requires_story_steps", [])
            )
        ):
            raise ValueError("Object trials need an ordered explicit effect graph")
        if trial["kind"] == "zone_checkpoint":
            if (
                not trial.get("destination_zone_ids")
                or not trial.get("destination_cells")
                or any(not _point(point) for point in trial["destination_cells"])
            ):
                raise ValueError("World checkpoint requires its original native zone")
        elif trial["kind"] in {
            "sliding_tiles",
            "resource_course",
            "light_course",
            "stealth_course",
            "safe_course",
        }:
            from wakfu_server import owned_object_trial_world_programs

            owned_object_trial_world_programs.validate(trial, sources)
        elif trial["kind"] == "fragile_carry":
            if (
                trial.get("pickup_source") not in sources
                or not isinstance(trial.get("destination_cells"), list)
                or not trial["destination_cells"]
                or not isinstance(trial.get("hazard_cells"), list)
                or any(
                    not _point(point)
                    for point in trial["destination_cells"] + trial["hazard_cells"]
                )
                or set(map(tuple, trial["destination_cells"]))
                & set(map(tuple, trial["hazard_cells"]))
                or trial.get("failure_policy") != "return_to_pickup"
            ):
                raise ValueError(
                    "Fragile carry needs reviewed pickup, destination and failure cells"
                )
            if "max_height_delta" in trial and (
                type(trial["max_height_delta"]) is not int
                or trial["max_height_delta"] < 0
                or not isinstance(trial.get("safe_edges"), list)
                or any(
                    not isinstance(edge, list)
                    or len(edge) != 2
                    or any(not _point(point) for point in edge)
                    for edge in trial["safe_edges"]
                )
            ):
                raise ValueError(
                    "Fragile carry needs explicit reviewed native ramp edges"
                )
        elif (
            not isinstance(trial.get("sources"), list)
            or not trial["sources"]
            or len(set(trial["sources"])) != len(trial["sources"])
            or not set(trial["sources"]) <= set(sources)
        ):
            raise ValueError("Discovery trial lacks its qualified object sequence")
        if (
            not isinstance(trial.get("failure_feedback", []), list)
            or not isinstance(trial.get("failure_regions", []), list)
            or any(
                not isinstance(region, dict)
                or not isinstance(region.get("cells"), list)
                or any(not _point(cell) for cell in region["cells"])
                or not isinstance(region.get("effects"), list)
                for region in trial.get("failure_regions", ())
            )
        ):
            raise ValueError("Object trial failure feedback lacks its reviewed regions")
        source_effects = trial.get("source_effects", {})
        allowed_sources = set(trial.get("sources", ())) | {trial.get("pickup_source")}
        if not isinstance(source_effects, dict) or any(
            key not in {str(identity) for identity in allowed_sources}
            or not isinstance(effects, dict)
            or set(effects) - {"accept", "failure"}
            or any(not isinstance(rows, list) for rows in effects.values())
            for key, effects in source_effects.items()
        ):
            raise ValueError("Object trial source effects lack qualified identities")
        seen.add(trial["id"])
    return selected


def initial_state(selected):
    return dict(schema=SCHEMA, profile_sha256=digest(selected), revision=0, trials={})


def _resolve(value, facts):
    """Resolve only declared server facts, never client-supplied effect values."""
    if isinstance(value, dict):
        if set(value) == {"fact"}:
            if value["fact"] not in facts:
                raise ValueError("Object trial effect requests an unknown server fact")
            return deepcopy(facts[value["fact"]])
        return {key: _resolve(item, facts) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, facts) for item in value]
    return deepcopy(value)


def reduce(selected, state, event, *, completed_story_steps=()):
    """Apply one already authenticated fact; failure never invents progress."""
    if state.get("schema") != SCHEMA or state.get("profile_sha256") != digest(selected):
        raise ValueError("Object trial state belongs to another pinned profile")
    if event.get("kind") not in {"interact", "movement", "tick", "stealth_attack"}:
        raise ValueError("Unknown object trial event")
    after = deepcopy(state)
    effects = []
    changed = False
    completed = {
        key for key, value in after["trials"].items() if value.get("complete") is True
    }
    for trial in selected["trials"]:
        if trial["id"] in completed or not set(trial["requires"]) <= completed:
            continue
        if not set(trial.get("requires_story_steps", ())) <= set(completed_story_steps):
            continue
        if event["kind"] == "tick" and trial["kind"] != "light_course":
            continue
        if event["kind"] == "stealth_attack" and trial["kind"] != "stealth_course":
            continue
        current = after["trials"].setdefault(trial["id"], {})
        success = failure = begin = accepted = False
        previous_index = current.get("index", 0)
        failure_cell = []
        failure_reason = ""
        if trial["kind"] == "zone_checkpoint":
            if event["kind"] != "movement":
                continue
            cells = event.get("cells", [])
            if not any(
                tuple(point) in set(map(tuple, trial["destination_cells"]))
                for point in cells[1:]
            ):
                continue
            success = changed = True
        elif trial["kind"] in {
            "sliding_tiles",
            "resource_course",
            "light_course",
            "stealth_course",
            "safe_course",
        }:
            from wakfu_server import owned_object_trial_world_programs

            result = owned_object_trial_world_programs.advance(trial, current, event)
            if not result["changed"]:
                continue
            after["trials"][trial["id"]] = current = result["state"]
            begin, success, failure, changed = (
                result["begin"],
                result["success"],
                result["failure"],
                True,
            )
            accepted = event["kind"] == "interact"
            effects.extend(result.get("effects", ()))
            effects.extend(owned_object_trial_world_programs.feedback(trial, current))
        elif trial["kind"] == "ordered_objects":
            if (
                event["kind"] != "interact"
                or event["source_id"] not in trial["sources"]
            ):
                continue
            index = current.get("index", 0)
            expected = trial["sources"][index]
            if event["source_id"] == expected:
                current["index"] = index + 1
                accepted = True
                success = current["index"] == len(trial["sources"])
            else:
                current["index"] = int(event["source_id"] == trial["sources"][0])
                failure = True
            changed = True
        elif trial["kind"] == "distinct_discoveries":
            if (
                event["kind"] != "interact"
                or event["source_id"] not in trial["sources"]
            ):
                continue
            discovered = set(current.get("discovered", ()))
            if event["source_id"] in discovered:
                continue
            discovered.add(event["source_id"])
            current["discovered"] = sorted(discovered)
            accepted = True
            success = len(discovered) == len(trial["sources"])
            changed = True
        elif event["kind"] == "interact":
            if event["source_id"] != trial["pickup_source"] or current.get("carrying"):
                continue
            current["carrying"] = True
            begin = changed = True
        elif current.get("carrying"):
            cells = event.get("cells")
            if (
                not isinstance(cells, list)
                or not cells
                or any(not _point(point) for point in cells)
            ):
                raise ValueError(
                    "Fragile carry needs the actual accepted movement cells"
                )
            hazards = set(map(tuple, trial["hazard_cells"]))
            safe_edges = {
                tuple(map(tuple, edge)) for edge in trial.get("safe_edges", ())
            }
            for index, cell in enumerate(cells):
                if tuple(cell) in hazards:
                    failure_cell, failure_reason = list(cell), "hazard"
                    break
                if index and "max_height_delta" in trial:
                    previous = cells[index - 1]
                    if (
                        abs(previous[2] - cell[2]) > trial["max_height_delta"]
                        and (tuple(previous), tuple(cell)) not in safe_edges
                    ):
                        failure_cell, failure_reason = list(cell), "height"
                        break
            if failure_cell:
                current["carrying"] = False
                current["failures"] = current.get("failures", 0) + 1
                failure = changed = True
            elif tuple(cells[-1]) in set(map(tuple, trial["destination_cells"])):
                current["carrying"] = False
                success = changed = True
        if success:
            current["complete"] = True
            completed.add(trial["id"])
        facts = dict(
            source_id=event.get("source_id", 0),
            previous_index=previous_index,
            index=current.get("index", 0),
            discovery_count=len(current.get("discovered", ())),
            failures=current.get("failures", 0),
            failure_cell=failure_cell,
            failure_reason=failure_reason,
        )
        source_effects = trial.get("source_effects", {}).get(
            str(event.get("source_id")), {}
        )
        for fired, name in ((accepted, "accept"), (failure, "failure")):
            if fired:
                effects.extend(_resolve(source_effects.get(name, []), facts))
        for fired, name in (
            (begin, "begin"),
            (failure, "failure"),
            (success, "success"),
        ):
            if fired:
                effects.extend(_resolve(trial["effects"][name], facts))
        if failure:
            feedback = trial.get("failure_feedback", [])
            if failure_reason == "height":
                for region in trial.get("failure_regions", ()):
                    if tuple(failure_cell) in set(map(tuple, region["cells"])):
                        feedback = region["effects"]
                        break
            effects.extend(_resolve(feedback, facts))
        # One fact never counts again as the next, newly unlocked puzzle action.
        break
    if changed:
        after["revision"] = state["revision"] + 1
    return dict(state=after, changed=changed, effects=effects)


def _scope(db, store, character, *, lock=True, check_position=True):
    from wakfu_server import dungeon_runtime_config

    row = db.execute(
        "SELECT i.context_route_key,i.context_policy_version,i.created_by_character_id "
        "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
        "WHERE i.instance_id=%s AND m.character_id=%s AND m.status='active' "
        + ("FOR UPDATE OF i,m" if lock else ""),
        (character["instance_id"], character["id"]),
    ).fetchone()
    if row is None or row["created_by_character_id"] != character["id"]:
        raise ValueError("Object trial requires its actual owned instance")
    members = db.execute(
        "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active' ORDER BY character_id "
        + ("FOR UPDATE" if lock else ""),
        (character["instance_id"],),
    ).fetchall()
    if members != [dict(character_id=character["id"])]:
        raise ValueError("Object trial requires its one owner")
    configuration = dungeon_runtime_config.pinned_configuration(
        db, row["context_route_key"], row["context_policy_version"]
    )
    selected = policy(configuration)
    current = store.character(character["account_id"], character["id"], db)
    if (
        selected is None
        or current["map_id"] != selected["map_id"]
        or any(
            current[key] != character[key]
            for key in (
                ("map_id", "instance_id", "x", "y", "z")
                if check_position
                else ("map_id", "instance_id")
            )
        )
    ):
        raise ValueError("Object trial differs from its owned native position")
    return selected, current


def _load_state(db, character, selected):
    prefix = f'owned-object-trial:{selected["id"]}:{character["instance_id"]}:'
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND left(event_key,%s)=%s "
        "ORDER BY (payload->'state'->>'revision')::bigint DESC,created_at DESC,event_key DESC LIMIT 1",
        (character["id"], len(prefix), prefix),
    ).fetchone()
    return initial_state(selected) if row is None else row["payload"]["state"]


def snapshot(db, store, character):
    """Read reconnect state without replaying items, rewards or presentation."""
    selected, current = _scope(db, store, character, lock=False, check_position=False)
    state = _load_state(db, current, selected)
    if state.get("profile_sha256") != digest(selected):
        raise ValueError("Object trial snapshot differs from its pinned profile")
    return dict(policy=selected, state=state)


def _settle(db, store, character, selected, event, token, apply_effects):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", token):
        raise ValueError("Object trial requires a server command identity")
    prefix = f'owned-object-trial:{selected["id"]}:{character["instance_id"]}:'
    duplicate = db.execute(
        "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], prefix + token),
    ).fetchone()
    if duplicate is not None:
        return dict(changed=False, packets=[])
    before = _load_state(db, character, selected)
    if any(trial["kind"] == "light_course" for trial in selected["trials"]):
        # Time and pose come from the committed owner transaction, never the
        # client packet or a caller's requested endpoint/time field.
        event = dict(
            event,
            now_ms=int(store.now().timestamp() * 1000),
            position=[character[key] for key in ("x", "y", "z")],
        )
    story_steps = ()
    if any(trial.get("requires_story_steps") for trial in selected["trials"]):
        from wakfu_server import owned_story_controller

        _, story_steps = owned_story_controller._scope(db, store, character)
    planned = reduce(selected, before, event, completed_story_steps=story_steps)
    if not planned["changed"]:
        return dict(changed=False, packets=[])
    if not callable(apply_effects):
        raise ValueError("Object trial needs its trusted native effect executor")
    applied = apply_effects(db, store, character, planned["effects"])
    presentation_due_ms = getattr(applied, "presentation_due_ms", 0)
    packets = list(applied)
    if not storage.record_event(
        db,
        character["id"],
        prefix + token,
        dict(
            schema=SCHEMA,
            owner=character["id"],
            instance_id=character["instance_id"],
            state=planned["state"],
            event=event,
            presentation_due_ms=presentation_due_ms,
        ),
    ):
        raise ValueError("Object trial event raced its mechanical effects")
    return dict(changed=True, packets=packets, presentation_due_ms=presentation_due_ms)


def presentation_pending(db, store, character, selected):
    prefix = f'owned-object-trial:{selected["id"]}:{character["instance_id"]}:'
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND left(event_key,%s)=%s "
        "ORDER BY (payload->'state'->>'revision')::bigint DESC,created_at DESC,event_key DESC LIMIT 1",
        (character["id"], len(prefix), prefix),
    ).fetchone()
    return (
        row is not None
        and row["payload"].get("presentation_due_ms", 0)
        > store.now().timestamp() * 1000
    )


def validate_movement(db, store, character, request, configuration):
    if policy(configuration) is None:
        return False
    selected, current = _scope(db, store, character, lock=False, check_position=False)
    if presentation_pending(db, store, current, selected):
        raise ValueError("The native object challenge presentation is still running")
    from wakfu_server.spatial_native import get_spatial
    from wakfu_server.spatial_topology import directed_path

    state = _load_state(db, current, selected)
    blocked = set()
    for trial in selected["trials"]:
        if trial["kind"] == "light_course":
            program = state["trials"].get(trial["id"], {}).get("program") or {}
            for gate in trial["program"]["gates"]:
                if not set(gate["switches"]) <= set(program.get("switches", ())):
                    blocked.update(map(tuple, gate.get("blocking_cells", ())))
    directed_path(
        get_spatial(),
        configuration["topology"]["exploration_geometry"],
        request,
        blocked,
    )
    return True


def due_tick(db, store, character, *, token, apply_effects):
    """Expire only due persisted timers; idle polling creates no receipts."""
    selected, current = _scope(db, store, character)
    state = _load_state(db, current, selected)
    now_ms = int(store.now().timestamp() * 1000)
    for trial in selected["trials"]:
        if trial["kind"] != "light_course":
            continue
        program = state["trials"].get(trial["id"], {}).get("program")
        if (
            program is not None
            and program["stage"] == "active"
            and program["deadline_ms"] <= now_ms
        ):
            return _settle(
                db, store, current, selected, dict(kind="tick"), token, apply_effects
            )
    return dict(changed=False, packets=[])


def _native_source(selected, current, source, action, parameter=0):
    from wakfu_server import world_static

    actual = next(
        (
            row
            for row in world_static.objects(selected["map_id"])
            if row["id"] == source["id"]
        ),
        None,
    )
    if (
        actual is None
        or actual.get(
            "descriptor_id", actual.get("native_parameters", source["descriptor_id"])
        )
        not in (source["descriptor_id"], str(source["descriptor_id"]))
        or [actual[key] for key in ("x", "y", "z")] != source["position"]
        or sha256(bytes.fromhex(actual["payload_hex"])).hexdigest()
        != source["payload_sha256"]
        or action != source["action"]
        or parameter != 0
        or tuple(current[key] for key in ("x", "y", "z"))
        not in set(map(tuple, source["approaches"]))
    ):
        raise ValueError("Object trial interaction lacks its exact native authority")
    # The installed world-object baseline stores the descriptor inside its
    # original serialized payload, without authoring-only descriptor_id keys.
    # The exact payload hash above authenticates that same descriptor; supplied
    # metadata, when present, must independently agree with the declaration.


def interact(db, store, character, body, *, token, generation, apply_effects):
    """Accept only an exact original object/action at an authored native floor."""
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Malformed object trial interaction")
    from wakfu_server.inventory_items import _lease

    _lease(store, db, character["account_id"], generation, character["id"])
    source_id, action, parameter = struct.unpack(">qHH", body)
    selected, current = _scope(db, store, character)
    if presentation_pending(db, store, current, selected):
        raise ValueError("The native object challenge presentation is still running")
    source = next((row for row in selected["sources"] if row["id"] == source_id), None)
    if source is None:
        return dict(changed=False, packets=[])
    _native_source(selected, current, source, action, parameter)
    if source["duration_ms"]:
        if not isinstance(token, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,80}", token
        ):
            raise ValueError("Object trial requires a server occupation identity")
        prefix = (
            f'owned-object-trial-pending:{selected["id"]}:{current["instance_id"]}:'
        )
        ticket = dict(
            schema=SCHEMA,
            owner=current["id"],
            instance_id=current["instance_id"],
            profile_sha256=digest(selected),
            source_id=source_id,
            generation=generation,
            position=[current[key] for key in ("x", "y", "z")],
            due_ms=int(store.now().timestamp() * 1000) + source["duration_ms"],
        )
        previous = db.execute(
            "SELECT event_key,payload FROM character_achievement_events e WHERE character_id=%s "
            "AND left(event_key,%s)=%s AND NOT EXISTS (SELECT 1 FROM character_achievement_events d "
            "WHERE d.character_id=e.character_id AND d.event_key='owned-object-trial-done:' || e.event_key) LIMIT 1",
            (current["id"], len(prefix), prefix),
        ).fetchone()
        if previous is not None:
            old = previous["payload"]
            if (
                old.get("generation") != generation
                or old.get("position") != ticket["position"]
            ):
                storage.record_event(
                    db,
                    current["id"],
                    "owned-object-trial-done:" + previous["event_key"],
                    dict(cancelled=True),
                )
            elif old.get("source_id") == source_id:
                return dict(
                    changed=False,
                    packets=[],
                    pending=dict(old, token=previous["event_key"][len(prefix) :]),
                )
            else:
                raise ValueError("Another owned object occupation is pending")
        if not storage.record_event(db, current["id"], prefix + token, ticket):
            raise ValueError("Object occupation identity was already used")
        return dict(changed=False, packets=[], pending=dict(ticket, token=token))
    return _settle(
        db,
        store,
        current,
        selected,
        dict(kind="interact", source_id=source_id),
        token,
        apply_effects,
    )


def complete_interaction(db, store, character, token, *, generation, apply_effects):
    """Finish one elapsed stationary source action, never an instant dig."""
    from wakfu_server.inventory_items import _lease

    _lease(store, db, character["account_id"], generation, character["id"])
    selected, current = _scope(db, store, character)
    key = (
        f'owned-object-trial-pending:{selected["id"]}:{current["instance_id"]}:{token}'
    )
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (current["id"], key),
    ).fetchone()
    if row is None:
        raise ValueError("Unknown owned object occupation")
    ticket = row["payload"]
    if (
        ticket.get("profile_sha256") != digest(selected)
        or ticket.get("owner") != current["id"]
        or ticket.get("instance_id") != current["instance_id"]
        or ticket.get("generation") != generation
        or store.now().timestamp() * 1000 < ticket["due_ms"]
    ):
        raise ValueError("Object occupation is not qualified or elapsed")
    done = "owned-object-trial-done:" + key
    if (
        db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (current["id"], done),
        ).fetchone()
        is not None
    ):
        return dict(changed=False, packets=[])
    if [current[axis] for axis in ("x", "y", "z")] != ticket["position"]:
        storage.record_event(db, current["id"], done, dict(cancelled=True))
        return dict(changed=False, packets=[], cancelled=True)
    source = next(
        row for row in selected["sources"] if row["id"] == ticket["source_id"]
    )
    _native_source(selected, current, source, source["action"])
    outcome = _settle(
        db,
        store,
        current,
        selected,
        dict(kind="interact", source_id=ticket["source_id"]),
        token,
        apply_effects,
    )
    if not storage.record_event(db, current["id"], done, dict(cancelled=False)):
        raise ValueError("Object occupation completion raced")
    return outcome


def cancel_pending(db, character, selected):
    """Cancel occupations on an accepted move, including away-and-back loops."""
    prefix = f'owned-object-trial-pending:{selected["id"]}:{character["instance_id"]}:'
    rows = db.execute(
        "SELECT event_key FROM character_achievement_events e WHERE character_id=%s "
        "AND left(event_key,%s)=%s AND NOT EXISTS (SELECT 1 FROM character_achievement_events d "
        "WHERE d.character_id=e.character_id AND d.event_key='owned-object-trial-done:' || e.event_key)",
        (character["id"], len(prefix), prefix),
    ).fetchall()
    for row in rows:
        storage.record_event(
            db,
            character["id"],
            "owned-object-trial-done:" + row["event_key"],
            dict(cancelled=True),
        )
    return bool(rows)


def on_landing(db, store, character, cells, *, token, apply_effects):
    """Observe the server's accepted path after its endpoint is durably flushed.

    Callers must retain their ordinary position barrier and movement lease; this
    is not a movement request endpoint and never trusts a client-supplied list.
    """
    selected, current = _scope(db, store, character)
    if (
        not isinstance(cells, list)
        or not cells
        or any(not _point(point) for point in cells)
        or tuple(cells[-1]) != tuple(current[key] for key in ("x", "y", "z"))
    ):
        raise ValueError("Object trial landing differs from the committed path")
    cancelled = False
    if any(tuple(left) != tuple(right) for left, right in zip(cells, cells[1:])):
        cancelled = cancel_pending(db, current, selected)
    outcome = _settle(
        db,
        store,
        current,
        selected,
        dict(kind="movement", cells=cells),
        token,
        apply_effects,
    )
    outcome["cancelled_occupation"] = cancelled
    return outcome
