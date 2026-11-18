"""Bounded native QA combat driver for the Fields mercenary continuation.

This is an ordinary client-action policy, not server AI or quest authority. It
uses the selected validated deck, original checkpoint identities and live native
geometry. Rejected casts do not advance quest state or bypass server legality.
"""
from collections import deque
import struct
import time


def actor_reference(snapshot, actor):
    """Identify native originals from their frozen checkpoint source receipts."""
    key = str(actor["id"])
    original = snapshot.get("_qa_admitted_original_refs", {}).get(key)
    if type(original) is int:
        return original
    row = snapshot.get("native_ordinary_npc_turn_roots", {}).get(key, {})
    if type(row.get("reference")) is int:
        return row["reference"]
    row = snapshot.get("native_npc_initialization_receipts", {}).get(key, {})
    return row.get("ref")


def footprint_cells(snapshot, actor):
    """Return actual floor cells covered by the actor's inclusive QI square."""
    x, y, z = actor["position"]
    radius = actor.get("physical_radius", 0)
    if type(radius) is not int or radius < 0:
        raise ValueError("Invalid checkpoint actor footprint")
    floor = {tuple(cell) for edge in snapshot["edges"] for cell in edge}
    floor.update(tuple(cell) for cell in snapshot.get("walkable", ()))
    floor.add((x, y, z))
    result = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            choices = [p for p in floor if p[:2] == (x + dx, y + dy)]
            if choices:
                result.append(min(choices, key=lambda p: abs(p[2] - z)))
    return tuple(result)


def ordered_enemies(snapshot, hero, *, priority_breed=None):
    living = [
        a
        for a in snapshot["actors"].values()
        if a["hp"] > 0 and a["team"] != hero["team"]
    ]
    summons = {int(key) for key in snapshot.get("native_summon_registrations", {})}
    originals = snapshot.get("_qa_admitted_original_refs", {})
    here = hero["position"]
    return sorted(
        living,
        key=lambda a: (
            0
            if priority_breed is not None
            and actor_reference(snapshot, a) == priority_breed
            else 1,
            int(
                a["id"] in summons
                or bool(a.get("native_summon_source"))
                or bool(originals)
                and str(a["id"]) not in originals
            ),
            min(
                abs(p[0] - here[0]) + abs(p[1] - here[1])
                for p in footprint_cells(snapshot, a)
            ),
            a["hp"],
            a["id"],
        ),
    )


def _spell_shapes(probe, spell_ids):
    from wakfu_server.combat_native_spell_casting import catalog

    casting = catalog()
    result = {}
    level = probe.character["level"]
    for spell in spell_ids:
        row = casting[str(spell)]
        index = min(level, len(row["levels"])) - 1
        # Use the guaranteed native baseline for movement planning. The selected
        # QA deck lacks the optional5581 branch which extends these ranges;
        # treating every conditional branch as active causes range oscillation.
        # Actual casts still pass through the server's current state selection.
        values = [(row["levels"][index][:2], row)]
        result[spell] = tuple(
            (r[0], r[1], flags["linear"], flags["diagonal"]) for r, flags in values
        )
    return result


def _in_shape(here, target, shapes):
    dx, dy = abs(here[0] - target[0]), abs(here[1] - target[1])
    for minimum, maximum, linear, diagonal in shapes:
        if not minimum <= dx + dy <= maximum:
            continue
        if (
            not linear
            and not diagonal
            or linear
            and (dx == 0 or dy == 0)
            or diagonal
            and dx == dy
        ):
            return True
    return False


def path_to_cast(snapshot, hero, enemy, shapes, *, rejected_positions=()):
    """Find a reachable native firing cell without walking through footprints."""
    here = tuple(hero["position"])
    targets = footprint_cells(snapshot, enemy)
    occupied_xy = {
        p[:2]
        for a in snapshot["actors"].values()
        if a["hp"] > 0 and a["id"] != hero["id"]
        for p in footprint_cells(snapshot, a)
    }
    graph = {}
    for left, right in snapshot["edges"]:
        graph.setdefault(tuple(left), []).append(tuple(right))
    previous, pending, goal = {here: None}, deque([here]), None
    while pending:
        cell = pending.popleft()
        if (
            cell != here
            and cell not in rejected_positions
            and any(
                _in_shape(cell, target, flags)
                for flags in shapes.values()
                for target in targets
            )
        ):
            goal = cell
            break
        for nxt in graph.get(cell, ()):
            if nxt not in previous and nxt[:2] not in occupied_xy:
                previous[nxt] = cell
                pending.append(nxt)
    if goal is None:
        return None
    path = []
    while goal != here:
        path.append(goal)
        goal = previous[goal]
    return list(reversed(path))


def play_existing(
    probe,
    fight_id,
    wire_start,
    *,
    resume_existing=False,
    timeout=600,
    priority_breed=None
):
    from tools.line2_rank23_native_tls_probe import (
        Rank23NativeRun,
        _owned_class_spell_ids,
    )

    # The public QA checkpoint projection omits some native identity metadata.
    # Read the actual admitted group's frozen original roster once; this local
    # planner map is never persisted into the checkpoint or sent as authority.
    with probe.store.connection() as db:
        groups = db.execute(
            "SELECT members FROM combat_groups WHERE fight_id=%s", (fight_id,)
        ).fetchall()
    if len(groups) != 1:
        raise AssertionError(("Fight lacks one original admitted group", fight_id))
    original_refs = {
        str(member["id"]): member["ref"] for member in groups[0]["members"]
    }
    if not original_refs or any(
        type(ref) is not int or ref <= 0 for ref in original_refs.values()
    ):
        raise AssertionError(
            ("Admitted group lacks native species identities", fight_id)
        )
    # Prepare before Ready so local catalog reads never consume an active turn.
    spell_ids = _owned_class_spell_ids(probe)
    if not spell_ids:
        raise AssertionError("Selected character has no validated active spells")
    shapes = _spell_shapes(probe, spell_ids)
    runner = Rank23NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    runner.wire_cursor = 0 if resume_existing else wire_start
    runner.native_global_turn, runner.native_turn_actor = 0, None
    runner.native_timeline_phase, runner.native_timeline_members = None, frozenset()
    runner.last_begin_identity = runner.last_acked_turn = None
    probe.peer.send(
        13332, struct.pack(">i", fight_id)
    ) if resume_existing else probe.peer.send(12523, b"\x01")
    deadline = time.monotonic() + timeout
    paid, rejected = [], set()
    current_turn, blocked_positions, turn_rejections = None, set(), []
    capped_spells = set()
    movement_blocked = False
    while time.monotonic() < deadline:
        snap = runner.ready_for_input()
        if snap["phase"] == "finished":
            break
        snap = dict(snap, _qa_admitted_original_refs=original_refs)
        hero = snap["actors"][str(probe.character["id"])]
        if current_turn != snap["turn_id"]:
            current_turn, rejected, blocked_positions = snap["turn_id"], set(), set()
            capped_spells.clear()
            movement_blocked = False
        if hero["ap"] < 2:
            runner.end_turn()
            continue
        enemies = ordered_enemies(snap, hero, priority_breed=priority_breed)
        if not enemies:
            raise AssertionError(("Active fight without living enemy", fight_id))
        here = tuple(hero["position"])
        # Maintain genuine boss focus instead of farming an infinite summon stream.
        enemy = enemies[0]
        if movement_blocked:
            # A real tackle/cost rejection makes walking unavailable for this
            # turn. Attack a currently reachable blocker instead; the server
            # still decides LOS, ownership and every paid cost of that cast.
            castable = [
                candidate
                for candidate in enemies
                if any(
                    spell not in capped_spells
                    and (current_turn, here, candidate["id"], spell, target)
                    not in rejected
                    and _in_shape(here, target, shapes[spell])
                    for spell in spell_ids
                    for target in footprint_cells(snap, candidate)
                )
            ]
            if not castable:
                runner.end_turn()
                continue
            enemy = min(
                castable,
                key=lambda candidate: (
                    min(
                        abs(target[0] - here[0]) + abs(target[1] - here[1])
                        for target in footprint_cells(snap, candidate)
                    ),
                    candidate["hp"],
                ),
            )
        targets = sorted(
            footprint_cells(snap, enemy),
            key=lambda p: abs(p[0] - here[0]) + abs(p[1] - here[1]),
        )
        accepted = False
        for spell in spell_ids:
            if spell in capped_spells:
                continue
            for target in targets:
                key = (current_turn, here, enemy["id"], spell, target)
                if key in rejected or not _in_shape(here, target, shapes[spell]):
                    continue
                try:
                    runner.cast(spell, target, class_spell=True)
                except AssertionError as error:
                    text = str(error)
                    if (
                        "Action rejected" not in text
                        and "maximum casts per turn" not in text
                    ):
                        raise
                    rejected.add(key)
                    turn_rejections.append(
                        dict(
                            turn=current_turn,
                            spell=spell,
                            target=list(target),
                            reason=text,
                        )
                    )
                    # A cap for one spell never forbids the remaining owned spells.
                    if "maximum casts per turn" in text:
                        capped_spells.add(spell)
                        for other_target in targets:
                            rejected.add(
                                (current_turn, here, enemy["id"], spell, other_target)
                            )
                        break
                    continue
                paid.append(
                    dict(
                        spell=spell,
                        target_id=enemy["id"],
                        target=list(target),
                        turn=current_turn,
                    )
                )
                accepted = True
                break
            if accepted:
                break
        if accepted:
            continue
        if len(capped_spells) == len(spell_ids):
            runner.end_turn()
            continue
        if movement_blocked:
            # All available casts on this target were rejected. The next
            # iteration can select another reachable target without moving.
            continue
        blocked_positions.add(here)
        path = path_to_cast(
            snap, hero, enemy, shapes, rejected_positions=blocked_positions
        )
        if hero["mp"] <= 0 or not path:
            runner.end_turn()
            continue
        try:
            runner.action(
                12161,
                struct.pack(">q", hero["id"])
                + b"".join(struct.pack(">iih", *cell) for cell in path[: hero["mp"]]),
                label="native Fields firing-position movement",
            )
        except AssertionError as error:
            if "Empty path or insufficient AP/MP for combat movement" not in str(error):
                raise
            movement_blocked = True
            probe.receipt.setdefault("native_movement_rejections", []).append(
                dict(
                    fight_id=fight_id,
                    turn=current_turn,
                    position=list(here),
                    requested_path=[list(cell) for cell in path[: hero["mp"]]],
                    reason=str(error),
                )
            )
            probe.save()
    snapshot = runner.checkpoint()
    hero = snapshot["actors"][str(probe.character["id"])]
    probe.receipt.setdefault("fights", []).append(
        dict(
            fight_id=fight_id,
            native_paid_spells=paid,
            native_cast_rejections=turn_rejections,
            priority_breed=priority_breed,
            original_native_members=original_refs,
            phase=snapshot["phase"],
            winner=snapshot.get("winner"),
        )
    )
    probe.save()
    if snapshot["phase"] != "finished" or snapshot["winner"] != hero["team"]:
        raise AssertionError(
            ("Actual Fields fight not won", fight_id, snapshot["phase"], hero["hp"])
        )
    mark = probe.peer.mark()
    probe.peer.send(12925, struct.pack(">iB", fight_id, 1))
    probe.peer.matching(
        13046,
        mark,
        lambda body: len(body) == 15
        and struct.unpack_from(">q", body)[0] == hero["id"]
        and body[10] == 17
        and struct.unpack_from(">i", body, 11)[0] == -1,
        timeout=30,
    )
    return dict(
        fight_id=fight_id,
        casts=len(paid),
        native_paid_spells=[p["spell"] for p in paid],
    )
