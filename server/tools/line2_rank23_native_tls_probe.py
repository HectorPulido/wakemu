"""Natural TLS acceptance for Sewers rank-two contracts and Pizz'larva 2139.

This is a bounded continuation runner for an existing local QA character. It
never creates a character, edits quest state, changes combat statistics, grants
items, or forces a win. Before connecting, it requires durable board acceptance
and producer receipts for both native rank-one prerequisites, including a real
native-order-trial settlement for 2149. Run only after 2149 is genuinely earned.

Usage (from repository root):
  PYTHONPATH=server:server/tools python3 server/tools/line2_rank23_native_tls_probe.py \
    --account-id ACCOUNT --character-id CHARACTER --preflight
  PYTHONPATH=server:server/tools python3 server/tools/line2_rank23_native_tls_probe.py \
    --account-id ACCOUNT --character-id CHARACTER --run

The character must be a level-6+ Huppermage at public map 546. The runner
walks to native sources, accepts through the real board, uses native spell and
movement packets for combat, enters dungeon 65 through object 24026, and
records only allowlisted gameplay packet summaries under private QA storage.
"""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import struct
import time

from tools.candidate_friendly_duel_socket_smoke import placement
from tools.install_mission_bundle import local_connection
from tools.quest_instance_combat_probe import fight_owned_room
from tools.regional_quest_tls_probe import NativeRun, RegionalProbe
from tools.rii_departure_probe import ObservedPeer, login
from wakfu_server import dungeon_instances, dungeon_runtime_config
from wakfu_server.store import Store


BOARD_ID = 24110
BOARD_APPROACH = (-20, 14, 0)
RANK_ONE = (2147, 2149)
RANK_TWO = (2150, 2151)
FINAL_QUEST = 2139
QUESTS = (*RANK_ONE, *RANK_TWO, FINAL_QUEST)
OBJECTIVES = {
    2150: 4682,
    2151: (4265, 4266, 4267, 4268, 4269, 4270),
    2139: 4231,
}
SOURCES_2151 = (
    (24138, 4265, (60, -32, 0), "gather"),
    (24139, 4266, (60, -31, 0), "encounter"),
    (24140, 4267, (40, 64, 0), "gather"),
    (24141, 4268, (37, 64, 0), "encounter"),
    (24142, 4269, (-47, 44, 0), "gather"),
    (24143, 4270, (-47, 43, 0), "encounter"),
)
SOURCE_2150 = (24126, 4682, (-29, -51, 0), "encounter")
ROUTE_KEY = "native_dungeon_65"
ENTRY_OBJECT = 24026
ENTRY_DESTINATION = 2053
PRIVATE_RECEIPT_ROOT = Path(".local-state/wakemu/qa")
# Verified native baseline ranges for the Huppermage spells used by QA308's
# actual selected build. Cast legality is still decided by the live server.
_HUPPER_BASE_RANGES = {5562: 4, 5564: 5, 5567: 3}


class Rank23NativeRun(NativeRun):
    """Track the native wire timeline, including recovery after reconnect."""

    def ready_for_input(self):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            with self.peer.observation_lock:
                messages = self.peer.records[self.wire_cursor :]
                self.wire_cursor = len(self.peer.records)
            for opcode, body in messages:
                if len(body) < 4 or struct.unpack_from(">i", body)[0] != self.fight_id:
                    continue
                if opcode in (12847, 12053):
                    from wakfu_server import combat_core_reconstruction

                    timeline = combat_core_reconstruction.decode_core_packet(
                        opcode, body
                    )["timeline"]
                    self.native_global_turn = timeline["turn"]
                    self.native_turn_actor = timeline["current"]
                    self.native_timeline_phase = timeline["phase"]
                    self.native_timeline_members = frozenset(timeline["available"])
                    self.last_begin_identity = None
                    self.last_acked_turn = None
                elif opcode == 13482 and len(body) >= 20:
                    identity = (
                        struct.unpack_from(">i", body, 4)[0],
                        struct.unpack_from(">q", body, 12)[0],
                    )
                    if identity != getattr(self, "last_begin_identity", None):
                        if not (
                            getattr(self, "native_timeline_phase", None) == 1
                            and self.native_turn_actor == identity[1]
                        ):
                            self.native_global_turn += 1
                        self.native_turn_actor = identity[1]
                        self.native_timeline_phase = 1
                        self.last_begin_identity = identity
                elif opcode == 12502 and len(body) >= 20:
                    actor_id = struct.unpack_from(">q", body, 12)[0]
                    if (
                        (
                            actor_id == getattr(self, "native_turn_actor", None)
                            or getattr(self, "native_turn_actor", None) is None
                            and actor_id in self.native_timeline_members
                        )
                        and self.native_global_turn > 0
                        and self.last_acked_turn != self.native_global_turn
                    ):
                        self.peer.send(
                            13510, struct.pack(">i", self.native_global_turn)
                        )
                        self.last_acked_turn = self.native_global_turn
                        self.native_turn_actor = None
                        self.native_timeline_phase = 2
            snapshot = self.checkpoint()
            if snapshot:
                if snapshot.get("phase") == "finished":
                    return snapshot
                order = snapshot.get("order", ())
                turn_index = snapshot.get("turn_index", 0)
                if (
                    snapshot.get("phase") == "active"
                    and type(turn_index) is int
                    and 0 <= turn_index < len(order)
                    and order[turn_index] == self.char["id"]
                    and getattr(self, "native_turn_actor", None) == self.char["id"]
                    and getattr(self, "native_timeline_phase", None) == 1
                ):
                    return snapshot
            time.sleep(0.05)
        raise AssertionError(
            ("No native input turn after source-fight recovery", self.fight_id)
        )


def _progress(store, character_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT state FROM character_achievement_progress WHERE character_id=%s",
            (character_id,),
        ).fetchone()
    if row is None or not isinstance(row["state"], dict):
        raise ValueError("The QA character has no persisted achievement progress")
    return row["state"]


def _active_native_dungeon_instance(store, account_id, character_id, character):
    """Return an exact active dungeon-65 membership for this selected character."""
    if character.get("instance_id", 0) <= 0:
        return None
    dungeon_instances.load_runtime_routes(store)
    route = dungeon_instances.route(ROUTE_KEY)
    with store.connection() as db:
        configuration = dungeon_runtime_config.active_configuration(db, ROUTE_KEY)
        row = db.execute(
            "SELECT i.instance_id,i.party_id,i.status AS instance_status,i.start_map_id,"
            "i.entry_object_id,i.entry_destination_id,m.status AS membership_status "
            "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
            "JOIN characters c ON c.id=m.character_id "
            "WHERE i.instance_id=%s AND m.character_id=%s AND c.account_id=%s",
            (character["instance_id"], character_id, account_id),
        ).fetchone()
    if (
        configuration is None
        or row is None
        or row["instance_status"] != "active"
        or row["membership_status"] != "active"
        or row["start_map_id"] != character.get("map_id")
        or row["start_map_id"] != configuration["route"]["start_map_id"]
        or row["entry_object_id"] != route.entry_object_id
        or row["entry_destination_id"] != route.destination_id
        or route.entry_object_id != ENTRY_OBJECT
        or route.destination_id != ENTRY_DESTINATION
    ):
        return None
    return row


def _event_rows(store, character_id, pattern):
    with store.connection() as db:
        return db.execute(
            "SELECT event_key,payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key LIKE %s ORDER BY event_key",
            (character_id, pattern),
        ).fetchall()


def _preflight(store, account_id, character_id, *, resume=False):
    character = store.character(account_id, character_id)
    if character is None:
        raise ValueError("The supplied QA character does not exist")
    if character.get("breed") != 19:
        raise ValueError(
            "This native paid-cast driver requires a Huppermage (breed 19)"
        )
    if character.get("level", 0) < 6 or character.get("effective_level", 0) < 6:
        raise ValueError(
            "Both native real-level and effective-level gates require level 6"
        )
    public_exterior = (
        character.get("map_id") == 546 and character.get("instance_id") == 0
    )
    active_dungeon = None
    if not public_exterior:
        if resume:
            active_dungeon = _active_native_dungeon_instance(
                store, account_id, character_id, character
            )
        if active_dungeon is None:
            raise ValueError(
                "Resume requires public map 546 or this character's verified active dungeon-65 membership"
            )

    state = _progress(store, character_id)
    completed = set(state.get("completed", ()))
    running = set(state.get("running", ()))
    missing = set(RANK_ONE) - completed
    if missing:
        raise ValueError(
            "Refusing to run: rank-one prerequisites are not naturally complete: "
            + ", ".join(map(str, sorted(missing)))
        )
    if 4261 not in set(state.get("objectives", ())):
        raise ValueError("2149 completion lacks its durable native objective 4261")
    dates = state.get("completion_dates", {})
    if any(str(quest_id) not in dates for quest_id in RANK_ONE):
        raise ValueError("Rank-one completion timestamps are incomplete")

    board_receipts = {
        quest_id: _event_rows(
            store, character_id, f"native-mercenary-board-acceptance:{quest_id}"
        )
        for quest_id in RANK_ONE
    }
    if any(not board_receipts[qid] for qid in RANK_ONE):
        raise ValueError("Rank-one board acceptance receipts are missing")
    repair_receipts = _event_rows(store, character_id, "quest-interactive:2147:%")
    if len(repair_receipts) < 4:
        raise ValueError("2147 lacks all four actual interactive-source receipts")
    from tools.native_order_trial_receipts import settled_trial_fights

    trial_fights = settled_trial_fights(store, character_id)
    if not trial_fights:
        raise ValueError(
            "2149 lacks a durable native hard-order-trial settlement receipt"
        )

    downstream = set(RANK_TWO) | {FINAL_QUEST}
    downstream_objectives = {
        identity
        for quest_id in downstream
        for identity in (
            (OBJECTIVES[quest_id],)
            if isinstance(OBJECTIVES[quest_id], int)
            else OBJECTIVES[quest_id]
        )
    }
    present_objectives = downstream_objectives.intersection(state.get("objectives", ()))
    if not resume and (
        running.intersection(downstream) or completed.intersection(downstream)
    ):
        raise ValueError(
            "This runner expects fresh downstream contracts; use --resume for an "
            "already accepted attempt"
        )
    if not resume and present_objectives:
        raise ValueError(
            "This runner requires fresh downstream objectives; use --resume to "
            f"continue the existing attempt: {sorted(present_objectives)}"
        )

    downstream_board_receipts = {}
    for quest_id in sorted(downstream):
        rows = _event_rows(
            store, character_id, f"native-mercenary-board-acceptance:{quest_id}"
        )
        accepted = quest_id in running or quest_id in completed
        if resume and accepted:
            if len(rows) != 1:
                raise ValueError(
                    f"Resume requires exactly one durable board receipt for accepted quest {quest_id}"
                )
            payload = rows[0]["payload"]
            digest = payload.get("source_sha256") if isinstance(payload, dict) else None
            if (
                not isinstance(payload, dict)
                or payload.get("kind") != "native_mercenary_board_acceptance_v1"
                or payload.get("board_id") != BOARD_ID
                or payload.get("quest_id") != quest_id
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError(
                    f"Resume found an invalid native board acceptance receipt for quest {quest_id}"
                )
        if resume and rows and not accepted:
            raise ValueError(
                f"Resume found a board receipt without active/completed state for quest {quest_id}"
            )
        downstream_board_receipts[str(quest_id)] = len(rows)
    if resume:
        unowned_objectives = []
        for quest_id in downstream:
            quest_objectives = (
                (OBJECTIVES[quest_id],)
                if isinstance(OBJECTIVES[quest_id], int)
                else OBJECTIVES[quest_id]
            )
            if (
                present_objectives.intersection(quest_objectives)
                and quest_id not in running | completed
            ):
                unowned_objectives.extend(
                    present_objectives.intersection(quest_objectives)
                )
        if unowned_objectives:
            raise ValueError(
                "Resume found downstream objectives without an accepted quest: "
                f"{sorted(set(unowned_objectives))}"
            )
    return {
        "character": character,
        "state": state,
        "active_dungeon": active_dungeon,
        "prerequisites": {
            "completed": sorted(completed.intersection(RANK_ONE)),
            "board_acceptance_receipts": {
                str(k): len(v) for k, v in board_receipts.items()
            },
            "2147_interaction_receipts": len(repair_receipts),
            "2149_native_order_trial_receipts": len(trial_fights),
            "2149_native_order_trial_fights": trial_fights,
            "resume": resume,
            "downstream_running": sorted(running.intersection(downstream)),
            "downstream_completed": sorted(completed.intersection(downstream)),
            "downstream_objectives": sorted(present_objectives),
            "downstream_board_acceptance_receipts": downstream_board_receipts,
        },
    }


def _wait_until(predicate, *, timeout, label, interval=0.1):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = predicate()
        if latest:
            return latest
        time.sleep(interval)
    raise AssertionError(("Timed out waiting for " + label, latest))


def _state_when(probe, predicate):
    state = probe.progress()
    return state if predicate(state) else None


def _character_when(probe, predicate):
    character = probe.current()
    return character if predicate(character) else None


def _walk_probe(probe, goal):
    probe.walk(tuple(goal))
    current = probe.current()
    if tuple(current[k] for k in ("x", "y", "z")) != tuple(goal):
        raise AssertionError(("Native walk did not settle", goal, current))


def _assert_wire(trace, *, objective=False, completion=False, reward=False):
    opcodes = [row["opcode"] for row in trace]
    required = []
    if objective:
        required.append(13832)
    if completion:
        required.append(13422)
    missing = [opcode for opcode in required if opcode not in opcodes]
    if missing:
        raise AssertionError(
            ("Expected immediate native gameplay packets", missing, opcodes)
        )
    if reward:
        reward_delivery_opcodes = {12471, 13879}
        if not reward_delivery_opcodes.intersection(opcodes):
            raise AssertionError(
                (
                    "Expected an immediate native reward delivery packet",
                    sorted(reward_delivery_opcodes),
                    opcodes,
                )
            )
        if not any(
            row.get("item_update", {}).get("reference_id") == 12686
            or any(
                item.get("reference_id") == 12686
                for item in row.get("fields", {}).get("quest_item_updates", ())
            )
            for row in trace
            if row["opcode"] in reward_delivery_opcodes
        ):
            raise AssertionError(
                "The immediate reward trace omitted native bread 12686"
            )


def _await_wire(
    probe, start, *, objective=False, completion=False, reward=False, timeout=15
):
    """Wait for required live frames after durable state changes, without sleeping blindly."""
    if objective:
        probe.peer.matching(13832, start, timeout=timeout)
    if completion:
        probe.peer.matching(13422, start, timeout=timeout)
    if reward:
        opcode, _body = probe.peer.matching_any((12471, 13879), start, timeout=timeout)
        if opcode not in (12471, 13879):
            raise AssertionError(("Unexpected native reward opcode", opcode))


def _accept_board_quest(probe, quest_id):
    state = probe.progress()
    if quest_id in state["completed"]:
        return state
    if quest_id in state["running"]:
        return state
    _walk_probe(probe, BOARD_APPROACH)
    mark = probe.peer.mark()
    probe.peer.send(12870, struct.pack(">qHH", BOARD_ID, 0, 0))
    probe.peer.send(12864, struct.pack(">iqB", quest_id, -1, 1))
    state = _wait_until(
        lambda: _state_when(
            probe,
            lambda current: quest_id in current["running"]
            or quest_id in current["completed"],
        ),
        timeout=12,
        label=f"native board acceptance {quest_id}",
    )
    if quest_id not in state["running"]:
        raise AssertionError(
            ("Quest was not naturally accepted from the board", quest_id, state)
        )
    probe.receipt["trace"].extend(probe.peer.gameplay_trace(mark))
    probe.receipt["journey"].append(
        {"boundary": "native board accepted quest", "quest_id": quest_id}
    )
    probe.save()
    return state


def _source_click(probe, source_id, objective_id, approach, mode, *, timeout=45):
    if objective_id in probe.progress()["objectives"]:
        return
    mark = probe.peer.mark()
    active_fight = (
        _active_source_fight(probe, source_id) if mode == "encounter" else None
    )
    if active_fight is None:
        _walk_probe(probe, approach)
        mark = probe.peer.mark()
        probe.peer.send(12870, struct.pack(">qHH", source_id, 0, 0))
    if mode == "gather":
        state = _wait_until(
            lambda: _state_when(
                probe, lambda current: objective_id in current["objectives"]
            ),
            timeout=timeout,
            label=f"native gather source {source_id} objective {objective_id}",
        )
        _await_wire(probe, mark, objective=True, timeout=timeout)
        trace = probe.peer.gameplay_trace(mark)
        _assert_wire(trace, objective=True)
        probe.receipt["trace"].extend(trace)
        probe.receipt["journey"].append(
            {
                "source": source_id,
                "objective": objective_id,
                "result": "gathered",
                "position": list(approach),
                "running": state["running"],
                "completed": state["completed"],
            }
        )
        probe.save()
        return
    if mode != "encounter":
        raise ValueError(("Unknown source action mode", mode))

    if active_fight is None:
        start_packet = probe.peer.matching(13652, mark, timeout=timeout)
        fight_id, _ = placement(start_packet)
    else:
        fight_id = active_fight
    _play_already_started_fight(
        probe, fight_id, mark, resume_existing=active_fight is not None
    )
    state = _wait_until(
        lambda: _state_when(
            probe, lambda current: objective_id in current["objectives"]
        ),
        timeout=15,
        label=f"native source victory objective {objective_id}",
    )
    _await_wire(probe, mark, objective=True, timeout=timeout)
    trace = probe.peer.gameplay_trace(mark)
    _assert_wire(trace, objective=True)
    from wakfu_server.achievements import source_quest_encounters

    binding = next(
        row
        for row in source_quest_encounters._all_bindings()
        if row["source"]["id"] == source_id
    )
    spawned = _event_rows(
        probe.store,
        probe.character["id"],
        source_quest_encounters._spawn_key(binding),
    )
    if len(spawned) != 1:
        raise AssertionError(
            (
                "Source encounter lacks its single authenticated spawn receipt",
                source_id,
                spawned,
            )
        )
    probe.receipt["trace"].extend(trace)
    probe.receipt["journey"].append(
        {
            "source": source_id,
            "objective": objective_id,
            "result": "native_fight_won",
            "fight_id": fight_id,
            "position": list(approach),
            "spawn_receipt": spawned[0],
            "running": state["running"],
            "completed": state["completed"],
        }
    )
    probe.save()


def _active_source_fight(probe, source_id):
    """Find only a live fight bound by the server's durable source receipt."""
    from wakfu_server.achievements import source_quest_encounters

    bindings = [
        row
        for row in source_quest_encounters._all_bindings()
        if row["source"]["id"] == source_id
    ]
    if len(bindings) != 1:
        raise ValueError(("Native source binding is not unique", source_id))
    binding = bindings[0]
    expected_digest = source_quest_encounters._source_digest(binding)
    with probe.store.connection() as db:
        candidates = db.execute(
            "SELECT f.id,f.status,c.snapshot FROM combat_fight_participants p "
            "JOIN combat_fights f ON f.id=p.fight_id "
            "LEFT JOIN fight_checkpoints c ON c.fight_id=f.id "
            "WHERE p.character_id=%s AND p.account_id=%s AND f.status='active' "
            "ORDER BY f.id DESC",
            (probe.character["id"], probe.account["id"]),
        ).fetchall()
        verified = []
        for candidate in candidates:
            event = db.execute(
                "SELECT payload FROM character_achievement_events "
                "WHERE character_id=%s AND event_key=%s",
                (
                    probe.character["id"],
                    f"quest-source-fight:{candidate['id']}",
                ),
            ).fetchone()
            payload = None if event is None else event["payload"]
            snapshot = candidate["snapshot"]
            if (
                isinstance(payload, dict)
                and payload.get("schema") == source_quest_encounters.SCHEMA
                and payload.get("owner") == probe.character["id"]
                and payload.get("binding") == binding["id"]
                and payload.get("source_sha256") == expected_digest
                and payload.get("fight_id") == candidate["id"]
                and isinstance(payload.get("members"), list)
                and isinstance(snapshot, dict)
                and snapshot.get("phase") == "active"
            ):
                verified.append(candidate["id"])
    if len(verified) > 1:
        raise ValueError(
            ("Multiple active source fights for one owner", source_id, verified)
        )
    return verified[0] if verified else None


def _owned_class_spell_ids(probe):
    """Return only the selected character build's actually owned active spells."""
    from wakfu_server.spells import validate_deck

    character = probe.store.character(probe.account["id"], probe.character["id"])
    build = character["builds"][character["active_build_index"]]
    deck = validate_deck(
        bytes.fromhex(build["deck"]),
        character["breed"],
        character["level"],
        character=character,
    )
    return tuple(
        sorted(
            dict.fromkeys(deck["active"]),
            key=lambda spell_id: (-_HUPPER_BASE_RANGES.get(spell_id, 1), spell_id),
        )
    )


def _play_already_started_fight(
    probe, fight_id, wire_start, *, timeout=180, resume_existing=False
):
    runner = Rank23NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    # Login may already have delivered the participant bootstrap and its
    # end-turn witness before the caller locates the durable encounter. Those
    # packets must be acknowledged to release staged summon presentations;
    # a later recovery request intentionally cannot bypass that fence.
    runner.wire_cursor = 0 if resume_existing else wire_start
    runner.native_global_turn = 0
    runner.native_turn_actor = None
    runner.native_timeline_phase = None
    runner.native_timeline_members = frozenset()
    runner.last_begin_identity = None
    runner.last_acked_turn = None
    if resume_existing:
        probe.peer.send(13332, struct.pack(">i", fight_id))
    else:
        probe.peer.send(12523, b"\x01")
    deadline = time.monotonic() + timeout
    casts = 0
    paid_spells = []
    spell_ids = _owned_class_spell_ids(probe)
    if not spell_ids:
        raise AssertionError("Selected character build has no owned active spells")
    no_damage_turns = 0
    last_enemy_hp = None
    while time.monotonic() < deadline:
        snapshot = runner.ready_for_input()
        if snapshot["phase"] == "finished":
            break
        hero = snapshot["actors"][str(probe.character["id"])]
        enemies = [
            actor
            for actor in snapshot["actors"].values()
            if actor["team"] != hero["team"] and actor["hp"] > 0
        ]
        if not enemies:
            break
        here = tuple(hero["position"])
        enemy = min(
            enemies,
            key=lambda actor: abs(actor["position"][0] - here[0])
            + abs(actor["position"][1] - here[1]),
        )
        target = tuple(enemy["position"])
        enemy_hp = sum(actor["hp"] for actor in enemies)
        if last_enemy_hp is None or enemy_hp < last_enemy_hp:
            no_damage_turns = 0
        last_enemy_hp = enemy_hp
        if hero["ap"] < 2:
            runner.end_turn()
            no_damage_turns += 1
            if no_damage_turns >= 4:
                raise AssertionError(
                    ("No native spell damage after four owned turns", fight_id, enemy)
                )
            continue
        # Try only active spells from the character's selected, validated deck.
        # The server remains the range/LOS/cost authority; rejected casts are
        # inert. This lets a native ranged spell hit a faster fleeing enemy.
        distance = abs(here[0] - target[0]) + abs(here[1] - target[1])
        aligned = here[0] == target[0] or here[1] == target[1]
        cast_candidates = [
            spell_id
            for spell_id in spell_ids
            if aligned and distance <= _HUPPER_BASE_RANGES.get(spell_id, 1)
        ]
        cast_landed = False
        for spell_id in cast_candidates:
            if hero["ap"] < 2:
                break
            before_hp = enemy["hp"]
            try:
                after = runner.cast(spell_id, target, class_spell=True)
            except AssertionError as error:
                message = str(error)
                if "maximum casts per turn" in message:
                    break
                if (
                    "Action rejected cast" in message
                    or "Action rejected spell" in message
                ):
                    continue
                raise
            casts += 1
            paid_spells.append(spell_id)
            cast_landed = True
            current_enemy = after.get("actors", {}).get(str(enemy["id"]))
            if current_enemy is None or current_enemy["hp"] < before_hp:
                no_damage_turns = 0
                break
            # A legal non-damaging owned spell can consume its native cost;
            # don't claim progress and don't keep retrying it this turn.
        if cast_landed:
            continue
        if no_damage_turns >= 3:
            raise AssertionError(
                (
                    "No legal damaging owned spell against native encounter",
                    fight_id,
                    here,
                    target,
                    spell_ids,
                )
            )
        graph = {}
        for left, right in snapshot["edges"]:
            graph.setdefault(tuple(left), []).append(tuple(right))
        occupied = {
            tuple(actor["position"])
            for actor in snapshot["actors"].values()
            if actor["hp"] > 0 and tuple(actor["position"]) != here
        }
        max_range = max(_HUPPER_BASE_RANGES.get(spell, 1) for spell in spell_ids)
        ranged_positions = {
            tuple(cell)
            for edge in snapshot["edges"]
            for cell in edge
            if cell[2] == target[2]
            and 1 <= abs(cell[0] - target[0]) + abs(cell[1] - target[1]) <= max_range
            and (cell[0] == target[0] or cell[1] == target[1])
        }
        previous, pending, goal = {here: None}, deque([here]), None
        while pending:
            cell = pending.popleft()
            if cell != here and cell in ranged_positions:
                goal = cell
                break
            for nxt in graph.get(cell, ()):
                if nxt not in previous and nxt not in occupied:
                    previous[nxt] = cell
                    pending.append(nxt)
        if goal is None:
            previous, pending = {here: None}, deque([here])
            while pending and goal is None:
                cell = pending.popleft()
                if abs(cell[0] - target[0]) + abs(cell[1] - target[1]) == 1:
                    goal = cell
                    break
                for nxt in graph.get(cell, ()):
                    if nxt not in previous and nxt not in occupied:
                        previous[nxt] = cell
                        pending.append(nxt)
        if goal is None:
            raise AssertionError(
                ("No native reachable spell line or melee position", here, target)
            )
        path = []
        while goal != here:
            path.append(goal)
            goal = previous[goal]
        path.reverse()
        if not path or hero["mp"] <= 0:
            runner.end_turn()
            no_damage_turns += 1
            if no_damage_turns >= 4:
                raise AssertionError(
                    ("No native spell damage after four owned turns", fight_id, enemy)
                )
        else:
            runner.action(
                12161,
                struct.pack(">q", probe.character["id"])
                + b"".join(struct.pack(">iih", *cell) for cell in path[: hero["mp"]]),
                label="native Sewers source-combat movement",
            )
    snapshot = runner.checkpoint()
    hero = snapshot["actors"][str(probe.character["id"])]
    if snapshot["phase"] != "finished" or snapshot["winner"] != hero["team"]:
        raise AssertionError(
            ("Actual native encounter was not won", fight_id, snapshot)
        )
    end_mark = probe.peer.mark()
    probe.peer.send(12925, struct.pack(">iB", fight_id, 1))
    probe.peer.matching(
        13046,
        end_mark,
        lambda body: len(body) == 15
        and struct.unpack_from(">q", body)[0] == probe.character["id"]
        and body[10] == 17
        and struct.unpack_from(">i", body, 11)[0] == -1,
        timeout=30,
    )
    probe.receipt.setdefault("fights", []).append(
        {"fight_id": fight_id, "casts": casts, "native_paid_spells": paid_spells}
    )
    probe.save()


def _wait_room(store, instance_id, order, timeout=40):
    def current():
        with store.connection() as db:
            row = db.execute(
                "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
        if row and row["status"] == "completed":
            return row
        if row and row["current_room"] == order and row["status"] == "active":
            return row
        return None

    return _wait_until(current, timeout=timeout, label=f"dungeon 65 room {order}")


def _wait_exterior(probe, timeout=40):
    return _wait_until(
        lambda: _character_when(
            probe,
            lambda current: current["map_id"] == 546 and current["instance_id"] == 0,
        ),
        timeout=timeout,
        label="native dungeon 65 exterior return",
    )


def _reward_receipts(store, character_id, quest_id):
    with store.connection() as db:
        return db.execute(
            "SELECT reward_key,payload,delivered_at IS NOT NULL AS delivered "
            "FROM character_achievement_reward_outbox "
            "WHERE character_id=%s AND achievement_id=%s ORDER BY reward_key",
            (character_id, quest_id),
        ).fetchall()


def _expected_native_rewards(store, quest_id):
    """Use the exact active reviewed board publication as the reward oracle."""
    from wakfu_server.maps import mercenary_boards

    with store.connection() as db:
        publication = mercenary_boards._publication(db)
    if publication is None:
        raise AssertionError("The reviewed native mercenary board is not installed")
    document, _ = publication
    definitions = {
        row["d"]: row
        for row in document.get("definitions", ())
        if isinstance(row, dict) and type(row.get("d")) is int
    }
    definition = definitions.get(quest_id)
    if definition is None:
        raise AssertionError(("Native mercenary definition is missing", quest_id))
    rewards = definition.get("cjK")
    if not isinstance(rewards, list):
        raise AssertionError(("Native reward list is malformed", quest_id, rewards))
    expected = {}
    for reward in rewards:
        if not isinstance(reward, dict) or type(reward.get("d")) is not int:
            raise AssertionError(
                ("Native reward identity is malformed", quest_id, reward)
            )
        key = str(reward["d"])
        if key in expected:
            raise AssertionError(
                ("Native reward identities are not unique", quest_id, key)
            )
        expected[key] = reward
    return expected


def _run_dungeon(probe):
    store = probe.store
    before = probe.peer.mark()
    dungeon_instances.load_runtime_routes(store)
    configured = dungeon_instances.route(ROUTE_KEY)
    with store.connection() as db:
        configuration = dungeon_runtime_config.active_configuration(db, ROUTE_KEY)
    if configuration is None:
        raise ValueError("The active native dungeon 65 configuration is missing")
    if (
        configured.entry_object_id != ENTRY_OBJECT
        or configured.destination_id != ENTRY_DESTINATION
    ):
        raise ValueError(
            "The active dungeon 65 native entrance differs from the reviewed route"
        )
    current = probe.current()
    if current.get("instance_id", 0) > 0:
        membership = _active_native_dungeon_instance(
            store, probe.account["id"], probe.character["id"], current
        )
        if membership is None:
            raise ValueError(
                "Refusing to resume a dungeon instance without the selected character's active membership"
            )
        instance_id = current["instance_id"]
        probe.receipt["journey"].append(
            {"boundary": "resumed active native dungeon 65", "instance_id": instance_id}
        )
        probe.save()
    else:
        if current.get("map_id") != 546:
            raise ValueError("A fresh native dungeon 65 entry requires public map 546")
        _walk_probe(probe, (-49, 16, -1))
        probe.peer.send(
            12296, struct.pack(">qiBi", ENTRY_OBJECT, ENTRY_DESTINATION, 0, 2)
        )
        entry_packet = probe.peer.matching(13974, before, timeout=30)
        probe.peer.send(12449)
        current = probe.current()
        if current["map_id"] != 902 or current["instance_id"] <= 0:
            raise AssertionError(
                ("Native dungeon transport did not commit", entry_packet.hex(), current)
            )
        instance_id = current["instance_id"]
        probe.receipt["journey"].append(
            {
                "boundary": "native dungeon 65 entry",
                "instance_id": instance_id,
                "native_object": ENTRY_OBJECT,
                "destination_id": ENTRY_DESTINATION,
            }
        )
        probe.receipt["trace"].extend(probe.peer.gameplay_trace(before))
        probe.save()

    # The runtime profile has room anchors/rosters but intentionally no
    # exploration-geometry copy. Reuse the exact installed geometry for the
    # character's current native map; never invent or widen walkable cells.
    from wakfu_server.combat_terrain import published_geometry

    walk_configuration = dict(configuration)
    walk_configuration["topology"] = dict(configuration["topology"])
    walk_configuration["topology"]["exploration_geometry"] = published_geometry(
        current["map_id"]
    )

    with store.connection() as db:
        room_progress = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
            (instance_id,),
        ).fetchone()
    if room_progress is None:
        raise ValueError("Native dungeon 65 has no durable room progression to resume")
    first_order = room_progress["current_room"]
    if room_progress["status"] == "completed":
        first_order = len(configuration["topology"]["rooms"]) + 1

    for order in range(first_order, len(configuration["topology"]["rooms"]) + 1):
        _wait_room(store, instance_id, order)
        with store.connection() as db:
            encounter = db.execute(
                "SELECT g.status,g.fight_id FROM dungeon_room_spawn_receipts r "
                "JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id "
                "AND g.group_id=r.group_id WHERE r.instance_id=%s AND r.room_order=%s",
                (instance_id, order),
            ).fetchone()
        if encounter is None:
            raise ValueError(
                ("Dungeon room has no authenticated encounter receipt", order)
            )
        if encounter["status"] == "fighting":
            # Continue the already registered fight after a legitimate reconnect.
            _play_already_started_fight(
                probe,
                encounter["fight_id"],
                probe.peer.mark(),
                timeout=600,
                resume_existing=True,
            )
            result = {"fight_id": encounter["fight_id"], "resumed": True}
        elif encounter["status"] == "available":
            result = fight_owned_room(probe, walk_configuration, room_order=order)
        elif encounter["status"] == "defeated":
            _wait_room(store, instance_id, order + 1)
            continue
        else:
            raise ValueError(
                ("Unexpected durable dungeon encounter state", order, encounter)
            )
        probe.peer.send(12449)
        probe.receipt.setdefault("dungeon_rooms", []).append(result)
        probe.save()
        if order < len(configuration["topology"]["rooms"]):
            next_room = configuration["topology"]["rooms"][order]
            anchor = tuple(next_room["anchor"])
            try:
                _walk_probe(probe, anchor)
            except AssertionError:
                # Automatic arrival may already have advanced into the next room.
                current = probe.current()
                with store.connection() as db:
                    run = db.execute(
                        "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()
                if not run or run["status"] != "active" or run["current_room"] <= order:
                    raise
            _wait_room(store, instance_id, order + 1)
    exterior = _wait_exterior(probe)
    state = probe.progress()
    if (
        FINAL_QUEST not in state["completed"]
        or OBJECTIVES[FINAL_QUEST] not in state["objectives"]
    ):
        raise AssertionError(("Native 2139 terminal was not earned", state))
    trace = probe.peer.gameplay_trace(before)
    _assert_wire(trace, objective=True, completion=True, reward=True)
    probe.receipt["trace"].extend(trace)
    with store.connection() as db:
        membership = db.execute(
            "SELECT party_id,status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
            (instance_id, probe.character["id"]),
        ).fetchone()
        run = db.execute(
            "SELECT status FROM dungeon_instances WHERE instance_id=%s", (instance_id,)
        ).fetchone()
        pending = db.execute(
            "SELECT count(*) AS count FROM dungeon_transition_outbox "
            "WHERE instance_id=%s AND character_id=%s AND status='pending'",
            (instance_id, probe.character["id"]),
        ).fetchone()["count"]
        company = db.execute(
            "SELECT party_id FROM player_party_members WHERE character_id=%s",
            (probe.character["id"],),
        ).fetchone()
    probe.receipt["dungeon_exit"] = {
        "position": {k: exterior[k] for k in ("map_id", "instance_id", "x", "y", "z")},
        "membership": None if membership is None else membership["status"],
        "instance_party_id": None if membership is None else membership["party_id"],
        "current_company_party_id": None if company is None else company["party_id"],
        "instance_status": None if run is None else run["status"],
        "pending_transition_count": pending,
        "rewards": _reward_receipts(store, probe.character["id"], FINAL_QUEST),
    }
    if membership is None or membership["status"] not in ("returned", "closed"):
        raise AssertionError(("Dungeon membership did not close on exit", membership))
    if run is None or run["status"] not in ("completed", "closed"):
        raise AssertionError(("Dungeon run did not complete", run))
    if pending:
        raise AssertionError(("Dungeon exit transition remains undelivered", pending))
    probe.save()


def _verify_completed_rewards(
    probe,
    quest_id,
    before_mark,
    *,
    require_objective=True,
    require_completion=True,
    require_reward=True,
):
    state = probe.progress()
    if quest_id not in state["completed"]:
        raise AssertionError(("Quest did not complete naturally", quest_id, state))
    _await_wire(
        probe,
        before_mark,
        objective=require_objective,
        completion=require_completion,
        reward=require_reward,
    )
    trace = probe.peer.gameplay_trace(before_mark)
    _assert_wire(
        trace,
        objective=require_objective,
        completion=require_completion,
        reward=require_reward,
    )
    receipts = _reward_receipts(probe.store, probe.character["id"], quest_id)
    expected = _expected_native_rewards(probe.store, quest_id)
    actual_keys = [row["reward_key"] for row in receipts]
    if (
        len(actual_keys) != len(set(actual_keys))
        or set(actual_keys) != set(expected)
        or len(receipts) != len(expected)
    ):
        raise AssertionError(
            (
                "Native reward receipt set differs from the exact quest rewards",
                quest_id,
                sorted(expected),
                sorted(actual_keys),
            )
        )
    for row in receipts:
        if row["payload"] != expected[row["reward_key"]]:
            raise AssertionError(
                (
                    "Native reward receipt payload differs from its contract",
                    quest_id,
                    row["reward_key"],
                    expected[row["reward_key"]],
                    row["payload"],
                )
            )
        if not row["delivered"]:
            raise AssertionError(
                ("Native reward receipt is not delivered", quest_id, row)
            )
    probe.receipt["trace"].extend(trace)
    probe.receipt.setdefault("reward_receipts", {})[str(quest_id)] = receipts
    probe.save()


def run(store, account_id, character_id, receipt_path, *, resume=False):
    attestation = _preflight(store, account_id, character_id, resume=resume)
    resolved_path = receipt_path.resolve()
    private_root = PRIVATE_RECEIPT_ROOT.resolve()
    if resolved_path != private_root and private_root not in resolved_path.parents:
        raise ValueError("QA receipts must remain under .local-state/wakemu/qa")
    previous_receipt = None
    if receipt_path.exists():
        if not resume:
            raise ValueError("Refusing to overwrite an existing private QA receipt")
        previous_receipt = json.loads(receipt_path.read_text())
        if (
            previous_receipt.get("account_id") != account_id
            or previous_receipt.get("character_id") != character_id
        ):
            raise ValueError("Resume receipt belongs to another QA account/character")
    elif resume:
        raise ValueError("--resume requires the existing private QA receipt")
    probe = RegionalProbe(store, account_id, character_id, receipt_path)
    if previous_receipt is not None:
        probe.receipt = previous_receipt
    else:
        probe.receipt.update(
            {
                "scope": "natural 2150/2151 source contracts and native dungeon 65/2139; no quest/stat/item/win fixtures",
                "prerequisites": attestation["prerequisites"],
                "journey": [],
                "trace": [],
            }
        )
    attempt = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "resume" if resume else "fresh",
        "journey_start": len(probe.receipt.setdefault("journey", [])),
        "trace_start": len(probe.receipt.setdefault("trace", [])),
        "status": "running",
    }
    probe.receipt.setdefault("attempts", []).append(attempt)
    probe.receipt["prerequisites"] = attestation["prerequisites"]
    probe.character = store.character(account_id, character_id)
    probe.peer = ObservedPeer()
    probe.save()
    try:
        probe.generation = login(store, probe.peer, probe.account, probe.character)
        probe.receipt["generation"] = str(probe.generation)
        probe.save()
        for quest_id in RANK_TWO:
            _accept_board_quest(probe, quest_id)

        # 2150 uses the exact source-owned original three-monster formation.
        before_2150 = probe.progress()
        mark = probe.peer.mark()
        _source_click(probe, *SOURCE_2150)
        objective_2150 = OBJECTIVES[2150]
        _verify_completed_rewards(
            probe,
            2150,
            mark,
            require_objective=objective_2150 not in set(before_2150["objectives"]),
            require_completion=2150 not in set(before_2150["completed"]),
            require_reward=not _reward_receipts(store, character_id, 2150),
        )

        before_2151 = probe.progress()
        mark_2151 = probe.peer.mark()
        for source_id, objective_id, approach, mode in SOURCES_2151:
            _source_click(probe, source_id, objective_id, approach, mode)
        _verify_completed_rewards(
            probe,
            2151,
            mark_2151,
            require_objective=bool(
                set(OBJECTIVES[2151]).difference(before_2151["objectives"])
            ),
            require_completion=2151 not in set(before_2151["completed"]),
            require_reward=not _reward_receipts(store, character_id, 2151),
        )

        _accept_board_quest(probe, FINAL_QUEST)
        before_2139 = probe.progress()
        if FINAL_QUEST not in set(before_2139["completed"]):
            mark = probe.peer.mark()
            _run_dungeon(probe)
        else:
            mark = probe.peer.mark()
        _verify_completed_rewards(
            probe,
            FINAL_QUEST,
            mark,
            require_objective=OBJECTIVES[FINAL_QUEST]
            not in set(before_2139["objectives"]),
            require_completion=FINAL_QUEST not in set(before_2139["completed"]),
            require_reward=not _reward_receipts(store, character_id, FINAL_QUEST),
        )

        # Close/reopen the ordinary client lease and prove progress/rewards persist.
        final_before = probe.progress()
        reward_before = {
            qid: _reward_receipts(store, character_id, qid)
            for qid in (*RANK_TWO, FINAL_QUEST)
        }
        probe.peer.close()
        time.sleep(0.5)
        probe.peer = ObservedPeer()
        probe.character = store.character(account_id, character_id)
        probe.generation = login(store, probe.peer, probe.account, probe.character)
        after_reconnect = probe.progress()
        if after_reconnect != final_before:
            raise AssertionError(
                (
                    "Reconnect changed earned native progress",
                    final_before,
                    after_reconnect,
                )
            )
        if {
            qid: _reward_receipts(store, character_id, qid) for qid in reward_before
        } != reward_before:
            raise AssertionError(
                "Reconnect duplicated or altered native reward receipts"
            )

        # A repeated completed source must remain inert and cannot spawn a second fight.
        repeat_mark = probe.peer.mark()
        probe.peer.send(12870, struct.pack(">qHH", 24126, 0, 0))
        time.sleep(0.5)
        repeat_opcodes = [opcode for opcode, _ in probe.peer.records[repeat_mark:]]
        if 13652 in repeat_opcodes:
            raise AssertionError(
                "Repeated completed source spawned another native fight"
            )
        if probe.progress() != final_before:
            raise AssertionError(
                "Repeated completed source changed objective/reward state"
            )
        for quest_id, rows in reward_before.items():
            if _reward_receipts(store, character_id, quest_id) != rows:
                raise AssertionError(
                    ("Repeated source changed reward outbox", quest_id)
                )
        probe.receipt["trace"].extend(probe.peer.gameplay_trace(repeat_mark))
        probe.receipt.setdefault("checks", []).extend(
            [
                "preflight required durable natural 2147 and 2149 acceptance/completion receipts",
                "native board acceptance was verified before resuming or accepting downstream contracts",
                "2150 and 2151 progressed only through original native sources and real paid-cast fights",
                "2139 progressed through native dungeon 65 rooms and Shin Larva 2157",
                "immediate objective/completion/reward packets and durable once receipts were observed",
                "dungeon membership and instance closed on configured exterior return",
                "reconnect preserved progress and repeated source remained inert",
            ]
        )
        probe.receipt["success"] = True
        attempt["status"] = "completed"
        attempt["finished_at"] = datetime.now(timezone.utc).isoformat()
        probe.save()
        return probe.receipt
    except BaseException as error:
        attempt["status"] = "failed"
        attempt["error"] = repr(error)
        attempt["finished_at"] = datetime.now(timezone.utc).isoformat()
        probe.save()
        raise
    finally:
        if probe.peer is not None:
            probe.peer.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--character-id", type=int, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume an existing receipt and already accepted downstream contracts",
    )
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    local_connection(os.environ.get("WAKFU_DATABASE_URL", ""))
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        if args.preflight:
            checked = _preflight(
                store, args.account_id, args.character_id, resume=args.resume
            )
            print(
                json.dumps(
                    {"ready": True, "prerequisites": checked["prerequisites"]},
                    default=str,
                )
            )
            return
        receipt = args.receipt or (
            PRIVATE_RECEIPT_ROOT
            / f"line2-rank23-{args.account_id}-{args.character_id}.json"
        )
        result = run(
            store, args.account_id, args.character_id, receipt, resume=args.resume
        )
        print(json.dumps(result, indent=2, default=str))
    finally:
        store.close()


if __name__ == "__main__":
    main()
