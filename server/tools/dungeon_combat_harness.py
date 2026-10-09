"""Real shared multi-monster TLS combat driver for disposable dungeon candidates.

The driver uses native group attack/join/ready/movement/unarmed-action/turn-ACK/
return packets. Database access is read-only and limited to fight checkpoints and
terminal receipts; it never modifies victory, rewards, or room progression.
"""
from collections import deque
import struct
import time

from tools.three_peer_harness import decode_turn
from wakfu_server.combat_los import static_visible


def checkpoint(store, fight_id):
    """Read the persisted shared fight snapshot without issuing writes."""
    with store.connection() as db:
        row = db.execute(
            "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight_id,)
        ).fetchone()
    if row is None or not isinstance(row["snapshot"], dict):
        raise AssertionError(f"fight {fight_id} has no readable native checkpoint")
    return row["snapshot"]


def _cell(actor):
    value = actor.get("position")
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise AssertionError("checkpoint actor has no native position")
    cell = tuple(value)
    if any(type(part) is not int for part in cell):
        raise AssertionError("checkpoint actor position is malformed")
    return cell


def current_actor(snapshot):
    order, turn_index = snapshot.get("order"), snapshot.get("turn_index")
    if (
        not isinstance(order, list)
        or type(turn_index) is not int
        or not order
        or not 0 <= turn_index < len(order)
    ):
        raise AssertionError("checkpoint has no valid current turn actor")
    return order[turn_index]


def decode_turn_boundary(body, fight_id):
    """Decode native 12502 identity fields for diagnostics and peer checks."""
    if not isinstance(body, bytes) or len(body) != 28:
        raise AssertionError("truncated native 12502 turn-boundary packet")
    packet_fight_id, action_id, sentinel = struct.unpack_from(">iii", body)
    actor_id, marker_a, marker_b = struct.unpack_from(">qii", body, 12)
    if packet_fight_id != fight_id or sentinel != -1:
        raise AssertionError("12502 turn boundary has wrong fight prefix")
    if action_id <= 0 or (marker_a, marker_b) != (-1, 0):
        raise AssertionError("12502 turn boundary has invalid native fields")
    return {"fight_id": packet_fight_id, "action_id": action_id, "actor_id": actor_id}


def acknowledged_turn_for_boundary(snapshot, boundary):
    """Resolve 13510 from a persisted barrier or its verified pre-turn snapshot.

    AI-owned server turns are committed by the shared runtime and broadcast to
    clients, while the last durable checkpoint can still describe that same
    actor before the turn-end transition. In that case the native boundary
    proves the transition and the checkpoint's unchanged global turn is the
    exact 13510 value. Requiring the next action ID and matching current actor
    excludes already-consumed or unrelated queued boundaries.
    """
    runtime = snapshot.get("runtime") if isinstance(snapshot, dict) else None
    if not isinstance(runtime, dict):
        raise AssertionError("turn boundary checkpoint has no runtime state")
    pending = runtime.get("awaiting_ack")
    if pending is not None:
        if type(pending) is not int or pending <= 0:
            raise AssertionError("checkpoint has invalid ACK sequence")
        native_id = runtime.get("native_action_id")
        if type(native_id) is not int or native_id < boundary["action_id"]:
            raise AssertionError("persisted ACK predates its native 12502 boundary")
        return pending

    if snapshot.get("phase") != "active":
        raise AssertionError("unpersisted turn boundary is not in an active fight")
    if current_actor(snapshot) != boundary["actor_id"]:
        raise AssertionError(
            "12502 actor does not match the checkpoint's current actor"
        )
    turn_id = snapshot.get("turn_id")
    native_id = runtime.get("native_action_id")
    if type(turn_id) is not int or turn_id <= 0:
        raise AssertionError("pre-boundary checkpoint has no global turn identifier")
    if type(native_id) is not int or native_id < 0:
        raise AssertionError("pre-boundary checkpoint has no native action identifier")
    if boundary["action_id"] <= native_id:
        raise AssertionError(
            "12502 is stale relative to the checkpoint native action ID"
        )
    return turn_id


def checkpoint_turn_ready(snapshot, expected_actor_id):
    """A 13482 turn is actionable only after its checkpoint releases the ACK."""
    if not isinstance(snapshot, dict) or snapshot.get("phase") != "active":
        return False
    runtime = snapshot.get("runtime")
    if isinstance(runtime, dict) and runtime.get("awaiting_ack") is not None:
        return False
    try:
        return current_actor(snapshot) == expected_actor_id
    except AssertionError:
        # Order/turn_index can be transiently incomplete while a shared turn
        # transition is being checkpointed. The wire 13482 remains the
        # expected actor; wait until durable state catches up instead of
        # weakening the current-actor invariant.
        return False


def ordinary_action_checkpoint_ready(snapshot, previous_action_id):
    """Wait for the native unarmed action's logical commit, not a turn change."""
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("phase") == "finished":
        return True
    runtime = snapshot.get("runtime")
    return (
        isinstance(runtime, dict)
        and type(runtime.get("action_id")) is int
        and runtime["action_id"] > previous_action_id
    )


def living_enemies(snapshot, actor_id):
    actors = snapshot.get("actors")
    if not isinstance(actors, dict) or str(actor_id) not in actors:
        raise AssertionError("current turn actor is absent from checkpoint roster")
    actor = actors[str(actor_id)]
    team = actor.get("team")
    if type(team) is not int:
        raise AssertionError("checkpoint actor has no authoritative team")
    enemies = []
    for raw_id, candidate in actors.items():
        if (
            candidate.get("team") != team
            and type(candidate.get("hp")) is int
            and candidate["hp"] > 0
        ):
            enemies.append((int(raw_id), candidate))
    return sorted(enemies)


def legal_melee_plan(snapshot, actor_id, map_id, *, graph=None):
    """Pick a living enemy and legal native route, bounded by current MP.

    Returns ``None`` if no enemy is reachable by native cardinal movement.
    The route may stop short when the legal path is longer than current MP; the
    target remains valid for a later turn.
    """
    actors = snapshot["actors"]
    actor = actors[str(actor_id)]
    if type(actor.get("hp")) is not int or actor["hp"] <= 0:
        raise AssertionError("cannot plan movement for a defeated actor")
    mp = actor.get("mp")
    if type(mp) is not int or mp < 0:
        raise AssertionError("current actor has no native MP value")
    origin = _cell(actor)
    occupied = {
        _cell(row)
        for identity, row in actors.items()
        if int(identity) != actor_id and type(row.get("hp")) is int and row["hp"] > 0
    }
    choices = []
    for enemy_id, enemy in living_enemies(snapshot, actor_id):
        target = _cell(enemy)
        if graph is None:
            # Reuse the established TLS smoke map/path implementation without
            # importing its psycopg-dependent script during offline unit tests.
            from tools.candidate_shared_combat_push_smoke import (
                _path_to_melee_range,
            )

            route = _path_to_melee_range(
                map_id, origin, target, occupied, maximum_steps=mp
            )
        else:
            route = _path_on_graph(graph, origin, target, occupied, mp)
        if route is None:
            continue
        endpoint = route[-1] if route else origin
        adjacent = (
            abs(endpoint[0] - target[0]) + abs(endpoint[1] - target[1]) == 1
            and endpoint[2] == target[2]
        )
        if adjacent:
            try:
                visible = static_visible(map_id, endpoint, target)
            except ValueError:
                visible = False
            adjacent = visible
        distance = abs(endpoint[0] - target[0]) + abs(endpoint[1] - target[1])
        choices.append(
            (not adjacent, len(route), distance, enemy_id, target, route, adjacent)
        )
    if not choices:
        return None
    _, _, _, enemy_id, target, route, adjacent = min(choices)
    return dict(target_id=enemy_id, target=target, route=route, adjacent=adjacent)


def _path_on_graph(graph, start, target, occupied, maximum_steps):
    def adjacent(cell):
        return (
            cell[2] == target[2]
            and abs(cell[0] - target[0]) + abs(cell[1] - target[1]) == 1
        )

    if adjacent(start):
        return []
    queue, previous = deque([start]), {start: None}
    goal = None
    while queue:
        cell = queue.popleft()
        for candidate in graph.get(cell, ()):
            if candidate in previous or candidate in occupied:
                continue
            previous[candidate] = cell
            if adjacent(candidate):
                goal = candidate
                queue.clear()
                break
            queue.append(candidate)
    if goal is None:
        return None
    route, cursor = [], goal
    while previous[cursor] is not None:
        route.append(cursor)
        cursor = previous[cursor]
    route.reverse()
    return route[:maximum_steps]


def check_native_rejection(peer):
    """Inspect notices without consuming combat boundaries or result packets."""
    with peer.events.mutex:
        packets = list(peer.events.queue)
    packets.extend(peer.pending)
    for opcode, body in packets:
        if opcode == 674:
            raise AssertionError(
                f"native dungeon action rejected: {_command_text(body)}"
            )


def _wait_checkpoint(store, fight_id, predicate, *, timeout, description, peer=None):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        if peer is not None:
            check_native_rejection(peer)
        last = checkpoint(store, fight_id)
        if predicate(last):
            return last
        time.sleep(0.05)
    if isinstance(last, dict):
        order, turn_index = last.get("order"), last.get("turn_index")
        actor_at_index = (
            order[turn_index]
            if isinstance(order, list)
            and type(turn_index) is int
            and 0 <= turn_index < len(order)
            else None
        )
        runtime = last.get("runtime")
        summary = dict(
            phase=last.get("phase"),
            order_length=len(order) if isinstance(order, list) else None,
            turn_index=turn_index,
            actor_at_index=actor_at_index,
            turn_id=last.get("turn_id"),
            sequence=last.get("sequence"),
            awaiting_ack=runtime.get("awaiting_ack")
            if isinstance(runtime, dict)
            else None,
            runtime_action_id=runtime.get("action_id")
            if isinstance(runtime, dict)
            else None,
            runtime_native_action_id=(
                runtime.get("native_action_id") if isinstance(runtime, dict) else None
            ),
            actor_count=len(last.get("actors", {}))
            if isinstance(last.get("actors"), dict)
            else None,
        )
    else:
        summary = type(last).__name__
    raise AssertionError(
        f"timed out waiting for {description}; checkpoint_summary={summary!r}"
    )


def _wait_pair(peers, opcode, *, timeout):
    bodies = [peer.wait(opcode, timeout=timeout)[0] for peer in peers]
    if bodies[0] != bodies[1]:
        raise AssertionError(f"shared owners received different opcode {opcode} bodies")
    return bodies[0]


def validate_post_ack_transitions(transitions):
    """Shared turns match; terminal reports are private per-owner payloads."""
    if len(transitions) != 2 or transitions[0][0] != transitions[1][0]:
        raise AssertionError("owners received different post-ACK transitions")
    opcode = transitions[0][0]
    if opcode == 12755:
        if not transitions[0][1] or not transitions[1][1]:
            raise AssertionError("an owner received an empty native fight report")
    elif opcode == 13482 and transitions[0][1] != transitions[1][1]:
        raise AssertionError("owners received inconsistent active turn packets")
    elif opcode not in (12755, 13482):
        raise AssertionError(f"unexpected post-ACK opcode {opcode}")
    return opcode


def _command_text(body):
    if not body:
        return ""
    name_length = body[0]
    text_offset = 1 + name_length + 11
    if len(body) < text_offset + 2:
        return ""
    text_length = struct.unpack_from(">H", body, text_offset)[0]
    start = text_offset + 2
    if len(body) != start + text_length:
        return ""
    return body[start:].decode("utf-8", errors="replace")


def placement_event(event):
    """Return 13652 or raise promptly with the server's native 674 rejection."""
    opcode, body = event
    if opcode == 13652:
        return body
    if opcode == 674:
        reason = _command_text(body)
        raise AssertionError(
            "native dungeon group attack rejected" + (f": {reason}" if reason else "")
        )
    raise AssertionError(f"unexpected response while starting dungeon fight: {opcode}")


def _peer_map(peers, character_ids):
    if isinstance(peers, dict):
        result = {int(key): value for key, value in peers.items()}
    else:
        if len(peers) != len(character_ids):
            raise ValueError("peer sequence must match the supplied character IDs")
        result = dict(zip(character_ids, peers))
    if set(result) != set(character_ids) or len(result) != 2:
        raise ValueError("dungeon combat requires one peer for each of two owners")
    return result


def _attack_turn(store, peers_by_id, fight_id, map_id, turn_body, *, timeout):
    allowed = set(peers_by_id)
    snapshot = checkpoint(store, fight_id)
    allowed_actor_ids = {int(identity) for identity in snapshot["actors"]}
    action_id, actor_id = decode_turn(turn_body, fight_id, allowed_actor_ids)
    if not checkpoint_turn_ready(snapshot, actor_id):
        return dict(
            moved=False, attacked=False, target_id=None, hp_before=None, hp_after=None
        )
    actor = snapshot["actors"][str(actor_id)]
    if actor.get("controlled") is not True or actor_id not in allowed:
        return dict(
            moved=False, attacked=False, target_id=None, hp_before=None, hp_after=None
        )
    peer = peers_by_id[actor_id]
    # One owner-controlled action is resolved from the current checkpoint; no
    # NPC state is synthesized and no server-side actor is moved by this tool.
    plan = legal_melee_plan(snapshot, actor_id, map_id)
    if plan is None:
        return dict(
            moved=False, attacked=False, target_id=None, hp_before=None, hp_after=None
        )
    result = dict(
        moved=False,
        attacked=False,
        target_id=plan["target_id"],
        hp_before=None,
        hp_after=None,
    )
    if plan["route"]:
        before = _cell(actor)
        peer.send(
            12161,
            struct.pack(">q", actor_id)
            + b"".join(struct.pack(">iih", *cell) for cell in plan["route"]),
        )
        moved = _wait_checkpoint(
            store,
            fight_id,
            lambda state: _cell(state["actors"][str(actor_id)]) != before,
            timeout=timeout,
            description="native movement checkpoint",
            peer=peer,
        )
        snapshot = moved
        result["moved"] = True
        if not checkpoint_turn_ready(snapshot, actor_id):
            return result
        actor = snapshot["actors"][str(actor_id)]
        position = _cell(actor)
        target_actor = snapshot["actors"].get(str(plan["target_id"]))
        if target_actor is None or target_actor.get("hp", 0) <= 0:
            return result
        target_cell = _cell(target_actor)
        plan["adjacent"] = (
            abs(position[0] - target_cell[0]) + abs(position[1] - target_cell[1]) == 1
            and position[2] == target_cell[2]
            and static_visible(map_id, position, target_cell)
        )
        plan["target"] = target_cell
    if plan["adjacent"] and actor.get("ap", 0) >= 3:
        before = snapshot
        target_actor = before["actors"].get(str(plan["target_id"]))
        if (
            target_actor is None
            or type(target_actor.get("hp")) is not int
            or target_actor["hp"] <= 0
        ):
            return result
        result["hp_before"] = target_actor["hp"]
        peer.send(12889, struct.pack(">qqbiih", actor_id, -1, 15, *plan["target"]))
        after = _wait_checkpoint(
            store,
            fight_id,
            lambda state: ordinary_action_checkpoint_ready(
                state, before.get("runtime", {}).get("action_id", 0)
            ),
            timeout=timeout,
            description="ordinary unarmed action checkpoint",
            peer=peer,
        )
        updated_target = after["actors"].get(str(plan["target_id"]))
        result["hp_after"] = 0 if updated_target is None else updated_target.get("hp")
        result["attacked"] = True
    return result


def attack_owned_turn(
    store, peers_by_id, fight_id, map_id, current, actor_id, *, timeout
):
    """Spend available native AP, rechecking ownership after every action."""
    outcomes = []
    while True:
        state = checkpoint(store, fight_id)
        if not checkpoint_turn_ready(state, actor_id):
            break
        actor = state["actors"].get(str(actor_id), {})
        if actor.get("ap", 0) < 3 or actor.get("controlled") is not True:
            break
        outcome = _attack_turn(
            store, peers_by_id, fight_id, map_id, current, timeout=timeout
        )
        outcomes.append(outcome)
        if not outcome["attacked"]:
            break
    return outcomes


def drive_active_fight(
    store,
    peers,
    character_ids,
    fight_id,
    map_id,
    *,
    initial_turn=None,
    timeout=45,
    max_turns=500,
):
    """Play a started shared fight to native result and return each owner.

    Returns after both ordinary 12755 result packets and native 12925/13974
    returns. Durable victory/group status is read only and must say finished /
    defeated before the returned record claims success.
    """
    peers_by_id = _peer_map(peers, character_ids)
    peer_list = [peers_by_id[identity] for identity in character_ids]
    initial = (
        _wait_pair(peer_list, 13482, timeout=timeout)
        if initial_turn is None
        else initial_turn
    )
    fight_snapshot = checkpoint(store, fight_id)
    allowed = set(int(value) for value in fight_snapshot["actors"])
    last_action, actor_id = decode_turn(initial, fight_id, allowed)
    turns = actions = 0
    movement_count = 0
    hp_observations = []
    current = initial
    while turns < max_turns:
        snapshot = checkpoint(store, fight_id)
        if snapshot.get("phase") == "finished":
            break
        actor_id = decode_turn(current, fight_id, allowed)[1]
        if (
            not checkpoint_turn_ready(snapshot, actor_id)
            and snapshot.get("runtime", {}).get("awaiting_ack") is None
        ):
            snapshot = _wait_checkpoint(
                store,
                fight_id,
                lambda state: state.get("phase") == "finished"
                or state.get("runtime", {}).get("awaiting_ack") is not None
                or checkpoint_turn_ready(state, actor_id),
                timeout=timeout,
                description="durable active actor matching native 13482",
            )
            if snapshot.get("phase") == "finished":
                break
        if actor_id in peers_by_id and checkpoint_turn_ready(snapshot, actor_id):
            for outcome in attack_owned_turn(
                store, peers_by_id, fight_id, map_id, current, actor_id, timeout=timeout
            ):
                actions += int(outcome["attacked"])
                movement_count += int(outcome["moved"])
                if outcome["attacked"]:
                    hp_observations.append(
                        dict(
                            target_id=outcome["target_id"],
                            hp_before=outcome["hp_before"],
                            hp_after=outcome["hp_after"],
                        )
                    )
            snapshot = checkpoint(store, fight_id)
            if snapshot.get("phase") == "finished":
                break
            actor = snapshot["actors"][str(actor_id)]
            peer = peers_by_id[actor_id]
            if checkpoint_turn_ready(snapshot, actor_id):
                peer.send(12403, struct.pack(">qh", actor_id, actor["turn_count"]))
        # A turn boundary is acknowledged by both live participants. The value
        # comes from the read-only checkpoint, not a guessed local counter.
        first_event = peer_list[0].wait_any({12502, 12755}, timeout=timeout)[0]
        if first_event[0] == 12755:
            reports = [first_event[1], peer_list[1].wait(12755, timeout=timeout)[0]]
            return _return_and_verify(
                store,
                peer_list,
                fight_id,
                reports,
                turns,
                actions,
                movement_count,
                hp_observations,
            )
        second_boundary = peer_list[1].wait(12502, timeout=timeout)[0]
        boundary = decode_turn_boundary(first_event[1], fight_id)
        second_boundary_info = decode_turn_boundary(second_boundary, fight_id)
        if first_event[1] != second_boundary:
            raise AssertionError(
                "shared owners received different native 12502 boundaries: "
                f"first={boundary!r}, second={second_boundary_info!r}"
            )
        pending = _wait_checkpoint(
            store,
            fight_id,
            lambda state: (
                state.get("runtime", {}).get("awaiting_ack") is not None
                or (
                    state.get("phase") == "active"
                    and state.get("runtime", {}).get("awaiting_ack") is None
                    and isinstance(
                        state.get("runtime", {}).get("native_action_id"), int
                    )
                    and boundary["action_id"] > state["runtime"]["native_action_id"]
                    and state.get("turn_id") is not None
                    and type(state.get("turn_id")) is int
                    and isinstance(state.get("order"), list)
                    and type(state.get("turn_index")) is int
                    and 0 <= state["turn_index"] < len(state["order"])
                    and state["order"][state["turn_index"]] == boundary["actor_id"]
                )
            ),
            timeout=timeout,
            description=(
                "native shared turn ACK checkpoint after 12502 "
                f"action={boundary['action_id']} actor={boundary['actor_id']}"
            ),
        )
        ack_turn = acknowledged_turn_for_boundary(pending, boundary)
        for peer in peer_list:
            peer.send(13510, struct.pack(">i", ack_turn))
        transitions = [
            peer.wait_any({13482, 12755}, timeout=timeout)[0] for peer in peer_list
        ]
        transition_opcode = validate_post_ack_transitions(transitions)
        if transition_opcode == 12755:
            return _return_and_verify(
                store,
                peer_list,
                fight_id,
                [transitions[0][1], transitions[1][1]],
                turns,
                actions,
                movement_count,
                hp_observations,
            )
        current = transitions[0][1]
        last_action, _ = decode_turn(
            current, fight_id, allowed, after_action_id=last_action
        )
        turns += 1
    else:
        raise AssertionError(
            f"shared dungeon fight exceeded {max_turns} turn boundaries"
        )
    reports = [peer.wait(12755, timeout=timeout)[0] for peer in peer_list]
    return _return_and_verify(
        store,
        peer_list,
        fight_id,
        reports,
        turns,
        actions,
        movement_count,
        hp_observations,
    )


def _return_and_verify(
    store, peers, fight_id, reports, turns, actions, movement_count, hp_observations
):
    if len(reports) != 2 or not all(reports):
        raise AssertionError("both owners must receive the native fight report")
    return_bootstraps = []
    for peer in peers:
        peer.send(12925, struct.pack(">iB", fight_id, 0))
    for peer in peers:
        body, _ = peer.wait(13974, timeout=40)
        return_bootstraps.append(body)
    with store.connection() as db:
        fight = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
        ).fetchone()
    if fight is None or fight["status"] != "finished":
        raise AssertionError("native combat did not durably finish as a victory")
    return dict(
        fight_id=fight_id,
        turns=turns,
        owner_actions=actions,
        owner_movements=movement_count,
        target_hp_observations=hp_observations,
        victory_reports=reports,
        return_bootstraps=return_bootstraps,
        returned=True,
        durable_status=fight["status"],
    )


def fight_room(
    store, peers, character_ids, map_id, instance_id, group_record, *, timeout=90
):
    """Start one real group fight from map state, win it, and make native returns.

    ``group_record`` is the read-only ``combat_groups`` row (members/status),
    with negative monster IDs and native x/y/z fields.
    """
    if (
        group_record.get("map_id", map_id) != map_id
        or group_record.get("instance_id", instance_id) != instance_id
    ):
        raise ValueError("combat group belongs to another native dungeon map/instance")
    peers_by_id = _peer_map(peers, character_ids)
    peer_list = [peers_by_id[identity] for identity in character_ids]
    members = group_record.get("members")
    if (
        group_record.get("status") != "available"
        or not isinstance(members, list)
        or not members
    ):
        raise ValueError("fight_room requires an available native combat group")
    starter = members[0]
    position = starter.get("position")
    if isinstance(position, (list, tuple)) and len(position) == 3:
        starter = dict(starter, x=position[0], y=position[1], z=position[2])
    if type(starter.get("id")) is not int or starter["id"] >= 0:
        raise ValueError("group member is not a native monster identity")
    for key in ("x", "y", "z"):
        if type(starter.get(key)) is not int:
            raise ValueError("group member has no native starting position")
    peer_list[0].send(
        13130,
        struct.pack(
            ">qiihB", starter["id"], starter["x"], starter["y"], starter["z"], 1
        ),
    )
    placement_body = placement_event(
        peer_list[0].wait_any({13652, 674}, timeout=timeout)[0]
    )
    fight_id, positions = _placement(placement_body)
    expected_ids = {int(member["id"]) for member in members}
    if expected_ids - set(positions):
        raise AssertionError("native fight placement omitted a room group actor")
    peer_list[1].send(13241, struct.pack(">qB", character_ids[0], 0))
    (join_opcode, join_body), join_packets = peer_list[1].wait_any(
        {12847, 674}, timeout=timeout
    )
    if join_opcode == 674:
        raise AssertionError(
            f"native dungeon fight join rejected: {_command_text(join_body)}"
        )
    joined_placement = next(
        (body for opcode, body in join_packets if opcode == 13652), None
    )
    if joined_placement is None:
        joined_placement, _ = peer_list[1].wait(13652, timeout=timeout)
    joined_id, joined = _placement(joined_placement)
    if (
        joined_id != fight_id
        or expected_ids - set(joined)
        or set(character_ids) - set(joined)
    ):
        raise AssertionError(
            "second native owner did not join the full shared room fight"
        )
    peer_list[0].wait(13091, timeout=timeout)
    for peer in peer_list:
        peer.send(12523, b"\x01")
    starts = _wait_pair(peer_list, 13482, timeout=timeout)
    result = drive_active_fight(
        store,
        peer_list,
        character_ids,
        fight_id,
        map_id,
        initial_turn=starts,
        timeout=timeout,
    )
    with store.connection() as db:
        group = db.execute(
            "SELECT status,fight_id FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            (map_id, instance_id, group_record["group_id"]),
        ).fetchone()
    if group is None or group["status"] != "defeated" or group["fight_id"] is not None:
        raise AssertionError(
            "native room group was not durably defeated by ordinary combat"
        )
    result.update(
        room_group_id=group_record["group_id"], native_roster_count=len(expected_ids)
    )
    return result


def _placement(body):
    if len(body) < 7:
        raise AssertionError("truncated native 13652 placement")
    fight_id, count = struct.unpack_from(">ih", body)
    if count < 2 or len(body) != 7 + count * 18:
        raise AssertionError("malformed native 13652 placement")
    actors, offset = {}, 6
    for _ in range(count):
        actor, x, y, z = struct.unpack_from(">qiih", body, offset)
        actors[actor] = (x, y, z)
        offset += 18
    return fight_id, actors
