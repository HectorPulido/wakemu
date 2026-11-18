"""Drive an actual native Pizz'larva hard-mode attempt over local World TLS.

This tool never fabricates quest state, score, combat stats, actors, or wins. It
requires naturally completed 2147 and an explicitly enabled, source-attested
2149 capability before it logs in or sends gameplay packets. After the native
fight starts, commands are sent as ordinary character actions and the displayed
score is read only from the accepted fight checkpoint.

Usage (repository root):
  PYTHONPATH=server:server/tools python3 server/tools/line2_pizzlarva_2149_native_tls_driver.py \
    --account-id ACCOUNT --character-id CHARACTER --preflight
  PYTHONPATH=server:server/tools python3 server/tools/line2_pizzlarva_2149_native_tls_driver.py \
    --account-id ACCOUNT --character-id CHARACTER --run
  PYTHONPATH=server:server/tools python3 server/tools/line2_pizzlarva_2149_native_tls_driver.py \
    --account-id ACCOUNT --character-id CHARACTER --resume

Interactive combat commands: status; move X Y Z; cast SPELL X Y Z; end; withdraw.
The optional --auto400 controller uses the same native inputs and returns to
the interactive prompt at the checkpoint threshold. It never withdraws.
"""

from __future__ import annotations

import argparse
from collections import deque
import json
import os
from pathlib import Path
import struct
import time

from tools.install_mission_bundle import local_connection
from tools.rii_departure_probe import ObservedPeer, login
from protocol_codec import DIRECTIONS
from wakfu_server import native_order_trial_admission
from wakfu_server.combat_terrain import published_geometry
from wakfu_server.store import Store


QUEST = 2149
OBJECTIVE = 4261
BOARD = 24110
BOARD_APPROACH = (-20, 14, 0)
SPELLS = frozenset((4535, 4538, 4537, 4536))
RECEIPTS = Path(".local-state/wakemu/qa/line2-pizzlarva-2149.json")


def _progress(store, character_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT state FROM character_achievement_progress WHERE character_id=%s",
            (character_id,),
        ).fetchone()
    if row is None or not isinstance(row["state"], dict):
        raise ValueError("The QA character has no persisted achievement progress")
    return row["state"]


def _receipt_count(store, character_id, prefix):
    with store.connection() as db:
        rows = db.execute(
            "SELECT event_key FROM character_achievement_events "
            "WHERE character_id=%s AND event_key LIKE %s ORDER BY event_key",
            (character_id, prefix + "%"),
        ).fetchall()
    return len(rows)


def _information_text(body):
    if len(body) < 4:
        return "malformed server information packet"
    size = struct.unpack_from(">h", body, 2)[0]
    if size < 0 or 4 + size > len(body):
        return "malformed server information packet"
    return body[4 : 4 + size].decode("utf-8", "replace")


def _reject_after(probe, wire_start, request):
    with probe.peer.observation_lock:
        rows = tuple(probe.peer.records[wire_start:])
    for opcode, body in rows:
        if opcode == 349:
            raise AssertionError(
                f"World rejected {request} (349): {_information_text(body)}"
            )


def _wait_response(probe, opcode, wire_start, *, timeout, request):
    deadline = time.monotonic() + timeout
    latest = []
    while time.monotonic() < deadline:
        with probe.peer.observation_lock:
            latest = tuple(probe.peer.records[wire_start:])
        for observed, body in latest:
            if observed == 349:
                raise AssertionError(
                    f"World rejected {request} (349): {_information_text(body)}"
                )
            if observed == opcode:
                return body
        time.sleep(0.05)
    snapshot = probe.checkpoint() if probe.fight_id is not None else None
    context = _checkpoint_context(probe, snapshot)
    tail = [observed for observed, _ in latest[-12:]]
    raise AssertionError(
        f"Timed out waiting for {request} response opcode {opcode}; "
        f"recent_opcodes={tail}; {context}"
    )


def _checkpoint_context(probe, snapshot):
    if not isinstance(snapshot, dict):
        snapshot = probe.checkpoint() if probe.fight_id is not None else None
    if not isinstance(snapshot, dict):
        checkpoint = "checkpoint=missing"
    else:
        runtime = snapshot.get("runtime", {})
        order = snapshot.get("order", ())
        turn_index = snapshot.get("turn_index", 0)
        current = (
            order[turn_index]
            if type(turn_index) is int and 0 <= turn_index < len(order)
            else None
        )
        checkpoint = (
            f"checkpoint_phase={snapshot.get('phase')} "
            f"awaiting_ack={runtime.get('awaiting_ack')} "
            f"turn={current} action_id={runtime.get('action_id')} "
            f"native_action_id={runtime.get('native_action_id')}"
        )
    with probe.peer.observation_lock:
        recent = tuple(probe.peer.records[-8:])
    native = [
        f"{opcode}:{_information_text(body)}" if opcode == 349 else str(opcode)
        for opcode, body in recent
    ]
    return f"{checkpoint}; last_native_context={native}"


def _capability():
    capability = native_order_trial_admission.document()
    if capability.get("enabled") is not True:
        return capability, "native admission capability is disabled"
    if capability.get("id") != "astrub-pizzlarva-native-admission":
        return capability, "unexpected native admission capability identity"
    return capability, None


def _source_id(kind):
    return native_order_trial_admission.document()["sources"][kind]["object_id"]


def _source_approach(kind):
    approaches = native_order_trial_admission.document()["sources"][kind]["approaches"]
    if not approaches:
        raise ValueError("Native source has no pinned approach cell")
    return tuple(approaches[0])


def preflight(store, account_id, character_id, *, resume=False, retry=False):
    """Read-only checks; disabled/mismatched source refuses before login."""
    character = store.character(account_id, character_id)
    if character is None or character.get("account_id") != account_id:
        raise ValueError("The supplied character is not owned by this account")
    state = _progress(store, character_id)
    completed = set(state.get("completed", ()))
    running = set(state.get("running", ()))
    if 2147 not in completed:
        raise ValueError("2147 must be naturally completed before 2149 acceptance")
    if resume:
        if QUEST not in running or QUEST in completed:
            raise ValueError(
                "Resume requires the naturally accepted, still-running 2149"
            )
        if (
            _receipt_count(
                store, character_id, "native-mercenary-board-acceptance:2149"
            )
            < 1
        ):
            raise ValueError(
                "Resume requires the durable native 2149 board-acceptance receipt"
            )
        if character.get("map_id") != 885 or character.get("instance_id", 0) <= 0:
            raise ValueError(
                "Resume requires the character's existing owned 885 context"
            )
        from wakfu_server import dungeon_runtime, native_order_trial_context

        with store.connection() as db:
            instance = db.execute(
                "SELECT i.instance_id,i.start_map_id,i.entry_map_id,i.entry_object_id "
                "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
                "WHERE i.instance_id=%s AND m.character_id=%s AND m.status='active'",
                (character["instance_id"], character_id),
            ).fetchone()
            members = db.execute(
                "SELECT character_id FROM dungeon_instance_members "
                "WHERE instance_id=%s AND status='active' ORDER BY character_id",
                (character["instance_id"],),
            ).fetchall()
            _, configuration = dungeon_runtime.configuration_for_instance(
                db, character["instance_id"]
            )
            context = native_order_trial_context.policy(configuration)
        if (
            instance is None
            or [row["character_id"] for row in members] != [character_id]
            or instance["start_map_id"] != 885
            or context is None
        ):
            raise ValueError(
                "Resume requires this character's exact pinned solo order-trial context"
            )
    else:
        if QUEST in completed or (QUEST in running and not retry):
            raise ValueError(
                "Fresh run requires an unaccepted 2149; use --resume for an accepted attempt"
            )
        if retry and (
            QUEST not in running
            or _receipt_count(
                store, character_id, "native-mercenary-board-acceptance:2149"
            )
            < 1
        ):
            raise ValueError(
                "Retry requires the original running quest and board receipt"
            )
        if character.get("map_id") != 546 or character.get("instance_id") != 0:
            raise ValueError("Place the selected character in public map 546 first")
    if OBJECTIVE in set(state.get("objectives", ())):
        raise ValueError("Objective 4261 already exists; refusing to replay it")
    if character.get("level", 0) < 6 or character.get("effective_level", 0) < 6:
        raise ValueError("The native board requires both real and effective level 6")
    capability, disabled_reason = _capability()
    geometry = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/achievements/order_trial_profiles/astrub_pizzlarva.geometry.json"
        ).read_text()
    )
    scoring = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/achievements/order_trial_profiles/astrub_pizzlarva.scoring.json"
        ).read_text()
    )
    summary = {
        "account_id": account_id,
        "character_id": character_id,
        "map_id": character["map_id"],
        "instance_id": character["instance_id"],
        "level": character.get("level"),
        "effective_level": character.get("effective_level"),
        "2147_completed": True,
        "2149_state": "resume" if resume else "fresh",
        "capability_enabled": capability.get("enabled") is True,
        "capability_id": capability.get("id"),
        "geometry_metadata_status": geometry.get("status"),
        "scoring_provenance": scoring.get("provenance", {}).get("kind"),
        "score_threshold": scoring.get("score_threshold"),
        "runtime_ready": disabled_reason is None,
    }
    if disabled_reason:
        summary["refusal"] = disabled_reason
    return summary


class ExistingTrialProbe:
    """NativeRun bound to an existing selected character; creates nothing."""

    def __init__(self, store, account_id, character_id):
        self.store = store
        self.account = {"id": account_id}
        self.char = store.character(account_id, character_id)
        if self.char is None:
            raise ValueError("Selected QA character disappeared")
        self.receipt = {
            "account_id": account_id,
            "character_id": character_id,
            "scope": "native client actions only; no quest, inventory, actor, stat, or win fixtures",
            "actions": [],
            "events": [],
        }
        self.peer = None
        self.fight_id = None
        self.wire_cursor = 0
        self.native_global_turn = 0
        self.native_turn_actor = None
        self.last_begin_identity = None
        self.last_acked_turn = None
        self.ack_request_start = None

    def _owned_configuration(self):
        from wakfu_server import dungeon_runtime

        with self.store.connection() as db:
            _selected, configuration = dungeon_runtime.configuration_for_instance(
                db, self.char["instance_id"]
            )
        return configuration

    def connect(self):
        self.peer = ObservedPeer()
        self.generation = login(self.store, self.peer, self.account, self.char)

    def poll_checkpoint(
        self, predicate, *, timeout=12, label="checkpoint", request_start=None
    ):
        deadline = time.monotonic() + timeout
        latest = None
        while time.monotonic() < deadline:
            if request_start is not None:
                _reject_after(self, request_start, label)
            latest = self.checkpoint()
            if latest is not None and predicate(latest):
                return latest
            time.sleep(0.08)
        raise AssertionError(("Timed out waiting for " + label, latest))

    def ready_for_input(self, *, request_start=None):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if request_start is not None:
                _reject_after(self, request_start, "native combat request")
            if self.ack_request_start is not None:
                _reject_after(
                    self, self.ack_request_start, "native shared-turn acknowledgement"
                )
            with self.peer.observation_lock:
                messages = self.peer.records[self.wire_cursor :]
                self.wire_cursor = len(self.peer.records)
            for opcode, body in messages:
                if len(body) < 4 or struct.unpack_from(">i", body)[0] != self.fight_id:
                    continue
                if opcode in (12847, 12053):
                    from wakfu_server import combat_core_reconstruction

                    recovery = combat_core_reconstruction.decode_core_packet(
                        opcode, body
                    )
                    timeline = recovery["timeline"]
                    self.native_global_turn = timeline["turn"]
                    self.native_turn_actor = timeline["current"]
                    self.native_timeline_phase = timeline["phase"]
                    self.native_timeline_members = frozenset(timeline["available"])
                    self.last_begin_identity = None
                    self.last_acked_turn = None
                    self.ack_request_start = None
                elif opcode == 13482 and len(body) >= 20:
                    action_id = struct.unpack_from(">i", body, 4)[0]
                    actor_id = struct.unpack_from(">q", body, 12)[0]
                    identity = (action_id, actor_id)
                    if identity != self.last_begin_identity:
                        if not (
                            getattr(self, "native_timeline_phase", None) == 1
                            and self.native_turn_actor == actor_id
                        ):
                            self.native_global_turn += 1
                        self.native_turn_actor = actor_id
                        self.native_timeline_phase = 1
                        self.last_begin_identity = identity
                        self.ack_request_start = None
                elif opcode == 12502 and len(body) >= 20:
                    actor_id = struct.unpack_from(">q", body, 12)[0]
                    if (
                        (
                            actor_id == self.native_turn_actor
                            or (
                                self.native_turn_actor is None
                                and actor_id
                                in getattr(self, "native_timeline_members", ())
                            )
                        )
                        and self.native_global_turn > 0
                        and self.last_acked_turn != self.native_global_turn
                    ):
                        self.ack_request_start = self.peer.mark()
                        self.peer.send(
                            13510, struct.pack(">i", self.native_global_turn)
                        )
                        self.last_acked_turn = self.native_global_turn
                        self.native_turn_actor = None
                        self.native_timeline_phase = 2
            snapshot = self.checkpoint()
            if snapshot:
                pending_ack = snapshot.get("runtime", {}).get("awaiting_ack")
                if pending_ack is not None and (
                    type(pending_ack) is not int or pending_ack <= 0
                ):
                    raise AssertionError(
                        f"Malformed committed native ACK token: {pending_ack!r}"
                    )
                if snapshot.get("phase") == "finished":
                    return snapshot
                order = snapshot.get("order", ())
                turn_index = snapshot.get("turn_index", 0)
                runtime = snapshot.get("runtime", {})
                if (
                    snapshot.get("phase") == "active"
                    and type(turn_index) is int
                    and 0 <= turn_index < len(order)
                    and order[turn_index] == self.char["id"]
                    and self.native_turn_actor == self.char["id"]
                    and getattr(self, "native_timeline_phase", None) == 1
                ):
                    return snapshot
            time.sleep(0.05)
        snapshot = self.checkpoint()
        raise AssertionError(
            f"No native order-trial input turn; fight={self.fight_id}; "
            f"{_checkpoint_context(self, snapshot)}"
        )

    def action(self, opcode, body, *, label):
        before = self.ready_for_input()
        if before.get("phase") == "finished":
            return before
        prior = before.get("runtime", {}).get("action_id", 0)
        prior_native = before.get("runtime", {}).get("native_action_id", 0)
        with self.peer.observation_lock:
            wire_start = len(self.peer.records)
        self.peer.send(opcode, body)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            _reject_after(self, wire_start, label)
            after = self.checkpoint()
            if after and (
                after.get("phase") == "finished"
                or after.get("runtime", {}).get("action_id", 0) > prior
                or after.get("runtime", {}).get("native_action_id", 0) > prior_native
                or after.get("actors") != before.get("actors")
            ):
                return after
            with self.peer.observation_lock:
                rejected = [
                    body for op, body in self.peer.records[wire_start:] if op == 674
                ]
            if rejected:
                raise AssertionError(
                    (
                        "Native action rejected",
                        label,
                        rejected[-1].decode("utf8", "replace"),
                    )
                )
            time.sleep(0.08)
        raise AssertionError(("Native action was not committed", label))

    def cast(self, spell, cell):
        return self.action(
            13260,
            struct.pack(">qqiih", self.char["id"], spell, *cell),
            label=f"cast {spell} at {cell}",
        )

    def end_turn(self):
        snapshot = self.ready_for_input()
        if snapshot.get("phase") == "finished":
            return snapshot
        wire_start = self.peer.mark()
        self.peer.send(
            12403,
            struct.pack(
                ">qh", self.char["id"], snapshot.get("native_timeline_round", 1)
            ),
        )
        self.poll_checkpoint(
            lambda current: current.get("phase") == "finished"
            or current.get("runtime", {}).get("awaiting_ack") is not None,
            timeout=15,
            label="native end-turn checkpoint barrier",
            request_start=wire_start,
        )
        return self.ready_for_input(request_start=wire_start)

    def occupied_area_cells(self):
        """Mirror NativeRun's area-occupancy exclusion from captured packets."""
        from wakfu_server.combat_protocol_reconstruction import decode_packet

        with self.peer.observation_lock:
            records = tuple(self.peer.records)
        areas = {}
        for opcode, body in records:
            if opcode == 13726 and len(body) == 20:
                areas.pop(struct.unpack_from(">q", body, 12)[0], None)
            elif opcode in (12613, 13497, 13560):
                try:
                    effect = decode_packet(opcode, body).get("effect", {})
                except (ValueError, KeyError, TypeError):
                    continue
                if effect.get("family") in (308, 315) and opcode != 13560:
                    areas[effect["area_uid"]] = effect
        return {
            tuple(area["cell"])
            for area in areas.values()
            if area.get("prototype") == 1808 and area.get("cell") is not None
        }

    def move(self, goal):
        goal = tuple(goal)
        for _ in range(12):
            snapshot = self.ready_for_input()
            if snapshot.get("phase") == "finished":
                return snapshot
            hero = snapshot["actors"][str(self.char["id"])]
            here = tuple(hero["position"])
            if here == goal:
                return snapshot
            path = self.combat_path(snapshot, goal)
            if path is None:
                raise AssertionError(("No native combat path", here, goal))
            segment = path[: max(0, hero.get("mp", 0))]
            if not segment:
                self.end_turn()
                continue
            snapshot = self.action(
                12161,
                struct.pack(">q", self.char["id"])
                + b"".join(struct.pack(">iih", *point) for point in segment),
                label=f"move to {goal}",
            )
            if tuple(snapshot["actors"][str(self.char["id"])]["position"]) == goal:
                return snapshot
        raise AssertionError(("Movement budget exhausted before goal", goal))

    def combat_path(self, snapshot, goal):
        hero = snapshot["actors"][str(self.char["id"])]
        here = tuple(hero["position"])
        goal = tuple(goal)
        occupied = {
            tuple(actor["position"])
            for identity, actor in snapshot["actors"].items()
            if int(identity) != self.char["id"] and actor.get("hp", 0) > 0
        }
        occupied.update(self.occupied_area_cells())
        graph = {}
        for left, right in snapshot.get("edges", ()):
            graph.setdefault(tuple(left), []).append(tuple(right))
        previous, pending = {here: None}, deque([here])
        while pending and goal not in previous:
            cell = pending.popleft()
            for nxt in graph.get(cell, ()):
                if nxt not in occupied and nxt not in previous:
                    previous[nxt] = cell
                    pending.append(nxt)
        if goal not in previous:
            return None
        path, cell = [], goal
        while cell != here:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return path

    def auto400(self, *, max_actions=600):
        """Use only current checkpoint state and ordinary native client inputs."""
        from wakfu_server import native_order_trial_context

        if max_actions < 1:
            raise ValueError("auto400 requires a positive bounded action count")
        geometry = native_order_trial_context.geometry(self._owned_configuration())
        layout = geometry["reviewed_arcade_layout"]
        hard_geometry = layout["hard"]
        # Use the last reviewed oven contact as the operator station, one
        # native floor cell east of its staging cell. Barrel approaches are
        # one cell north of each actual barrel position in the same pinned
        # layout. These are navigation choices only; scoring remains native.
        staging = tuple(hard_geometry["oven_contacts"][-1]["bake_staging_cell"])
        oven = (staging[0] + 1, staging[1], staging[2])
        barrels = {}
        barrel_targets = {}
        for row in layout["barrels"]:
            ingredient = row["ingredient"]
            target = tuple(row["position"])
            barrel_targets[ingredient] = target
            barrels[ingredient] = (target[0], target[1] + 1, target[2])
        weights = None
        last_progress = None

        def remaining_demand(trial, ingredient):
            return sum(
                1 for _color, requested in trial.orders if requested == ingredient
            )

        def stock_covers_remaining_orders(trial):
            return (
                trial.ingredient is not None
                and trial.charges >= remaining_demand(trial, trial.ingredient)
                and remaining_demand(trial, trial.ingredient) > 0
            )

        def preferred_ingredient(trial, rules):
            nonlocal weights
            if weights is None:
                weights = {
                    (color, ingredient): value
                    for (color, ingredient), value in rules.weights
                }
            ingredients = {ingredient for _color, ingredient in trial.orders}
            if not ingredients:
                return None
            return max(
                ingredients,
                key=lambda candidate: (
                    sum(
                        weights[(color, candidate)]
                        for color, ingredient in trial.orders
                        if ingredient == candidate
                    ),
                    candidate,
                ),
            )

        for action_index in range(max_actions):
            current = self.validated_trial()
            if current is None:
                raise ValueError(
                    "auto400 requires a validated native order-trial checkpoint"
                )
            proof, rules, trial, snapshot = current
            if not proof.hard_mode:
                raise ValueError("auto400 refuses normal mode")
            progress = (trial.score, trial.strikes, tuple(trial.orders))
            if progress != last_progress:
                print(
                    f"auto400 turn={snapshot.get('turn_id')} score={trial.score}/{rules.score_threshold} "
                    f"strikes={trial.strikes} orders={list(trial.orders)} "
                    f"ingredient={trial.ingredient} charges={trial.charges}",
                    flush=True,
                )
                last_progress = progress
            if snapshot.get("phase") == "finished":
                self.finish_and_return(snapshot)
                return
            if trial.score >= rules.score_threshold:
                self.status()
                print(
                    "Score threshold reached from the native checkpoint. Manual controls are available; no withdrawal was sent.",
                    flush=True,
                )
                return

            hero = snapshot["actors"][str(self.char["id"])]
            hero_pos = tuple(hero["position"])
            alive = [
                larva
                for larva in trial.larvae
                if (actor := snapshot.get("actors", {}).get(str(larva.actor_id)))
                and actor.get("hp", 0) > 0
            ]
            baking = any(
                (actor := snapshot.get("actors", {}).get(str(larva.actor_id)))
                and tuple(actor.get("position", ())) == (-7, -4, 0)
                for larva in trial.larvae
            )
            if baking:
                snap = self.end_turn()
                self.record_action(
                    {"type": "end_turn", "reason": "await_native_bake_terminal"}, snap
                )
                continue
            if not alive:
                orders = tuple(trial.orders)
                has_usable_stock = stock_covers_remaining_orders(trial)
                hero = snapshot["actors"][str(self.char["id"])]
                if orders and not has_usable_stock:
                    ingredient = preferred_ingredient(trial, rules)
                    if ingredient is not None:
                        approach, target = (
                            barrels[ingredient],
                            barrel_targets[ingredient],
                        )
                        path = self.combat_path(snapshot, approach)
                        if path is not None:
                            snap = self.move(approach)
                            self.record_action(
                                {
                                    "type": "move",
                                    "to": list(approach),
                                    "purpose": "native_barrel",
                                },
                                snap,
                            )
                            for _ in range(3):
                                picked = self.validated_trial()
                                if picked is None:
                                    break
                                _p, _r, held, held_snapshot = picked
                                held_hero = held_snapshot["actors"][
                                    str(self.char["id"])
                                ]
                                if held.ingredient == ingredient and held.charges >= 6:
                                    break
                                if held_hero.get("ap", 0) < 2:
                                    snap = self.end_turn()
                                    self.record_action(
                                        {
                                            "type": "end_turn",
                                            "reason": "native_barrel_ap",
                                        },
                                        snap,
                                    )
                                    picked = self.validated_trial()
                                    if picked is None:
                                        break
                                    (
                                        _picked_proof,
                                        _picked_rules,
                                        held,
                                        held_snapshot,
                                    ) = picked
                                    held_hero = held_snapshot["actors"][
                                        str(self.char["id"])
                                    ]
                                    if held_hero.get("ap", 0) < 2:
                                        break
                                before = (
                                    held.charges if held.ingredient == ingredient else 0
                                )
                                snap = self.cast(4538, target)
                                self.record_action(
                                    {
                                        "type": "cast",
                                        "spell": 4538,
                                        "ingredient": ingredient,
                                    },
                                    snap,
                                )
                                after = self.validated_trial()
                                if after is None or after[2].charges <= before:
                                    break
                            return_snapshot = self.checkpoint()
                            return_path = self.combat_path(return_snapshot, oven)
                            if return_path is not None:
                                snap = self.move(oven)
                                self.record_action(
                                    {
                                        "type": "move",
                                        "to": list(oven),
                                        "purpose": "return_oven",
                                    },
                                    snap,
                                )
                            continue
                snap = self.end_turn()
                self.record_action(
                    {"type": "end_turn", "reason": "await_native_conveyor"}, snap
                )
                continue
            larva = alive[0]
            actor = snapshot["actors"][str(larva.actor_id)]
            larva_pos = tuple(actor["position"])

            # Hold the native oven staging cell. If a conveyor token gets past
            # the mouth, recover only with a native paid walk and actual hits.
            if hero_pos != oven:
                path = self.combat_path(snapshot, oven)
                if path is not None:
                    snap = self.move(oven)
                    self.record_action({"type": "move", "to": list(oven)}, snap)
                    continue

            if larva_pos[1] < -4:
                snap = self.end_turn()
                self.record_action(
                    {"type": "end_turn", "reason": "wait_for_native_conveyor"}, snap
                )
                continue

            if larva_pos[1] > -4:
                intercept = (-5, larva_pos[1], larva_pos[2])
                path = self.combat_path(snapshot, intercept)
                if path is None:
                    snap = self.end_turn()
                    self.record_action(
                        {"type": "end_turn", "reason": "conveyor_overrun_unreachable"},
                        snap,
                    )
                    continue
                snap = self.move(intercept)
                self.record_action({"type": "move", "to": list(intercept)}, snap)
                continue

            orders = tuple(trial.orders)
            usable_stock = stock_covers_remaining_orders(trial)
            wanted = (larva.color, trial.ingredient) if usable_stock else None
            cook = (
                bool(wanted in orders and hero.get("mp", 0) >= 2) if wanted else False
            )

            if cook and not larva.tenderized:
                snap = self.cast(4535, larva_pos)
                self.record_action(
                    {"type": "cast", "spell": 4535, "target": larva.actor_id}, snap
                )
                continue
            if cook:
                live = next(
                    (item for item in trial.larvae if item.actor_id == larva.actor_id),
                    None,
                )
                if live is None:
                    continue
                if live.ingredient is None:
                    snap = self.cast(4537, larva_pos)
                    self.record_action(
                        {"type": "cast", "spell": 4537, "target": larva.actor_id}, snap
                    )
                    continue
                snap = self.cast(4536, larva_pos)
                self.record_action(
                    {"type": "cast", "spell": 4536, "target": larva.actor_id}, snap
                )
                continue

            # Wrong-color/currently-unrequested larvae are removed by the
            # original double-tenderize path, which the server classifies as
            # zero-strike native death.
            snap = self.cast(4535, larva_pos)
            self.record_action(
                {"type": "cast", "spell": 4535, "target": larva.actor_id}, snap
            )
            if snap.get("actors", {}).get(str(larva.actor_id), {}).get("hp", 0) > 0:
                continue

            # If the held topping is no longer requested, select an actual
            # remaining recipe ingredient from the validated score matrix.
            current = self.validated_trial()
            if current is None:
                continue
            _proof, rules, trial_after, snapshot_after = current
            if trial_after.finished or not trial_after.orders:
                continue
            if stock_covers_remaining_orders(trial_after):
                continue
            ingredient = preferred_ingredient(trial_after, rules)
            if ingredient is not None:
                approach = barrels[ingredient]
                target = barrel_targets[ingredient]
                after_hero = snapshot_after["actors"][str(self.char["id"])]
                path = self.combat_path(snapshot_after, approach)
                if path is not None:
                    snap = self.move(approach)
                    self.record_action(
                        {
                            "type": "move",
                            "to": list(approach),
                            "purpose": "native_barrel",
                        },
                        snap,
                    )
                    # Stop at the native capacity; only accept checkpointed
                    # pickup events and never invent a topping/charge count.
                    for _ in range(3):
                        current_pickup = self.validated_trial()
                        if current_pickup is None:
                            break
                        _p, _r, held, held_snapshot = current_pickup
                        held_hero = held_snapshot["actors"][str(self.char["id"])]
                        if held.ingredient == ingredient and held.charges >= 6:
                            break
                        if held_hero.get("ap", 0) < 2:
                            snap = self.end_turn()
                            self.record_action(
                                {"type": "end_turn", "reason": "native_barrel_ap"}, snap
                            )
                            current_pickup = self.validated_trial()
                            if current_pickup is None:
                                break
                            _p, _r, held, held_snapshot = current_pickup
                            held_hero = held_snapshot["actors"][str(self.char["id"])]
                            if held_hero.get("ap", 0) < 2:
                                break
                        before_charges = (
                            held.charges if held.ingredient == ingredient else 0
                        )
                        snap = self.cast(4538, target)
                        self.record_action(
                            {"type": "cast", "spell": 4538, "ingredient": ingredient},
                            snap,
                        )
                        after_pickup = self.validated_trial()
                        if (
                            after_pickup is None
                            or after_pickup[2].charges <= before_charges
                        ):
                            break
                    return_snapshot = self.checkpoint()
                    return_path = self.combat_path(return_snapshot, oven)
                    if return_path is not None:
                        snap = self.move(oven)
                        self.record_action(
                            {
                                "type": "move",
                                "to": list(oven),
                                "purpose": "return_oven",
                            },
                            snap,
                        )
            # A bounded controller iteration corresponds only to committed
            # actions above; no synthetic clock advancement or event writes.
        current = self.validated_trial()
        if current is not None:
            self.status()
            print(
                "auto400 action bound reached; manual controls are available, with no completion claim.",
                flush=True,
            )

    def world_walk(self, goal):
        goal = tuple(goal)
        for waypoint in self._world_waypoints(goal):
            self._send_world_path(waypoint)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                current = self.store.character(self.account["id"], self.char["id"])
                if tuple(current[k] for k in ("x", "y", "z")) == waypoint:
                    self.char = current
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(("World walk did not settle", waypoint))

    def _send_world_path(self, goal):
        current = self.store.character(self.account["id"], self.char["id"])
        start = tuple(current[k] for k in ("x", "y", "z"))
        graph = published_geometry(current["map_id"]).outgoing
        previous, pending = {start: None}, deque([start])
        while pending and goal not in previous:
            cell = pending.popleft()
            for nxt in graph.get(cell, ()):
                if nxt not in previous:
                    previous[nxt] = cell
                    pending.append(nxt)
        if goal not in previous:
            raise AssertionError(("No published native route", start, goal))
        path, cell = [], goal
        while cell != start:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        direction_by_delta = {
            (value[1], value[2]): key for key, value in DIRECTIONS.items()
        }
        encoded, point = bytearray(), start
        for step in path:
            delta = step[0] - point[0], step[1] - point[1]
            encoded.append(
                (direction_by_delta[delta] << 5) | ((step[2] - point[2]) & 31)
            )
            point = step
        if not path or len(path) > 255:
            raise AssertionError("World path segment must contain 1..255 native steps")
        self.peer.send(13331, struct.pack(">iiihB", 0, *start, len(path)) + encoded)

    def _world_waypoints(self, goal):
        current = self.store.character(self.account["id"], self.char["id"])
        start = tuple(current[k] for k in ("x", "y", "z"))
        graph = published_geometry(current["map_id"]).outgoing
        previous, pending = {start: None}, deque([start])
        while pending and goal not in previous:
            cell = pending.popleft()
            for nxt in graph.get(cell, ()):
                if nxt not in previous:
                    previous[nxt] = cell
                    pending.append(nxt)
        if goal not in previous:
            raise AssertionError(("No published native route", start, goal))
        path, cell = [], goal
        while cell != start:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return [
            tuple(path[i + 59]) if i + 59 < len(path) else tuple(path[-1])
            for i in range(0, len(path), 60)
        ]

    def checkpoint(self):
        if self.fight_id is None:
            return None
        with self.store.connection() as db:
            row = db.execute(
                "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchone()
        return None if row is None else row["snapshot"]

    def validated_trial(self):
        snapshot = self.checkpoint()
        if not snapshot:
            return None
        from wakfu_server import native_order_trial_checkpoint as checkpoint

        document = snapshot.get(checkpoint.FIELD)
        if document is None:
            return None
        proof, rules, state = checkpoint.validate(document, encounter_id=self.fight_id)
        if (
            proof.owner_id != self.char["id"]
            or proof.account_id != self.account["id"]
            or not proof.hard_mode
        ):
            raise ValueError(
                "Checkpoint is not this character's authenticated hard attempt"
            )
        return proof, rules, state, snapshot

    def save(self):
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        RECEIPTS.write_text(json.dumps(self.receipt, indent=2, sort_keys=True) + "\n")

    def status(self):
        current = self.validated_trial()
        if current is None:
            print("No accepted order-trial checkpoint yet.", flush=True)
            return None
        proof, _rules, state, snapshot = current
        actors = snapshot.get("actors", {})
        hero = actors.get(str(self.char["id"]), {})
        view = {
            "fight_id": self.fight_id,
            "mode": proof.mode,
            "turn": state.turn,
            "player": {
                "position": hero.get("position"),
                "ap": hero.get("ap"),
                "mp": hero.get("mp"),
                "hp": hero.get("hp"),
            },
            "score": state.score,
            "strikes": state.strikes,
            "orders_remaining": [list(v) for v in state.orders],
            "larvae": [
                {
                    "actor_id": larva.actor_id,
                    "color": larva.color,
                    "position": actors.get(str(larva.actor_id), {}).get("position"),
                    "hp": actors.get(str(larva.actor_id), {}).get("hp"),
                    "tenderized": larva.tenderized,
                    "ingredient": larva.ingredient,
                }
                for larva in state.larvae
            ],
            "ingredient": state.ingredient,
            "charges": state.charges,
            "phase": snapshot.get("phase"),
            "score_threshold": 400,
        }
        print(json.dumps(view, sort_keys=True), flush=True)
        return current

    def record_action(self, command, snapshot):
        current = self.validated_trial()
        state = current[2] if current is not None else None
        self.receipt["actions"].append(
            {
                "command": command,
                "phase": None if snapshot is None else snapshot.get("phase"),
                "turn": None if state is None else state.turn,
                "score": None if state is None else state.score,
                "strikes": None if state is None else state.strikes,
                "checkpoint_events": 0 if state is None else len(state.receipts),
            }
        )
        self.save()

    def finish_and_return(self, snapshot=None):
        """Close a genuinely finished fight, then use the original free exit."""
        snapshot = snapshot or self.checkpoint()
        if not snapshot or snapshot.get("phase") != "finished":
            raise ValueError(
                "Native result return requires an already-finished checkpoint"
            )
        self.report_result(snapshot)
        start = self.peer.mark()
        self.peer.send(12925, struct.pack(">iB", self.fight_id, 0))
        self.peer.matching(13974, start, timeout=30)

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            current = self.store.character(self.account["id"], self.char["id"])
            if current and current["map_id"] == 885 and current["instance_id"] > 0:
                self.char = current
                break
            time.sleep(0.1)
        else:
            raise AssertionError(
                "Combat close did not restore the owned 885 world context"
            )

        exit_anchor = (0, 1, 0)
        self.world_walk(exit_anchor)
        start = self.peer.mark()
        self.peer.send(12296, struct.pack(">qiBi", 23627, 2016, 0, 2))
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            _reject_after(self, start, "native free 885 exit")
            current = self.store.character(self.account["id"], self.char["id"])
            if current and current["map_id"] == 546 and current["instance_id"] == 0:
                self.char = current
                self.peer.send(12449)
                self.receipt["native_exit"] = {
                    "source_id": 23627,
                    "destination_map_id": current["map_id"],
                    "destination_position": [current["x"], current["y"], current["z"]],
                }
                self.save()
                print(
                    json.dumps(self.receipt["native_exit"], sort_keys=True), flush=True
                )
                return
            time.sleep(0.1)
        raise AssertionError(
            "Original native 23627 exit did not return the character to public 546"
        )

    def interactive(self, *, actions_allowed=True):
        print(
            "Native Pizz'larva controls: status | move X Y Z | cast SPELL X Y Z | end | withdraw | quit",
            flush=True,
        )
        print(
            "All actions use native client requests; score and receipts come from the saved checkpoint.",
            flush=True,
        )
        while True:
            line = input("pizzlarva> ").strip().split()
            if not line:
                continue
            command = line[0].lower()
            if command == "quit":
                print(
                    "Disconnecting without a score claim; reconnect normally to resume.",
                    flush=True,
                )
                return
            if command == "status":
                self.status()
                continue
            if not actions_allowed and command != "quit":
                print(
                    "Combat input is not currently authorized by the live checkpoint; connection remains open.",
                    flush=True,
                )
                continue
            if command == "move" and len(line) == 4:
                target = tuple(int(v) for v in line[1:])
                try:
                    snap = self.move(target)
                except AssertionError as error:
                    print(
                        f"Action rejected without closing the session: {error}",
                        flush=True,
                    )
                    continue
                self.record_action({"type": "move", "to": list(target)}, snap)
                continue
            if command == "cast" and len(line) == 5:
                spell, x, y, z = map(int, line[1:])
                if spell not in SPELLS:
                    raise ValueError(
                        "Only original native order-book spells are accepted"
                    )
                try:
                    snap = self.cast(spell, (x, y, z))
                except AssertionError as error:
                    print(
                        f"Action rejected without closing the session: {error}",
                        flush=True,
                    )
                    continue
                self.record_action(
                    {"type": "cast", "spell": spell, "cell": [x, y, z]}, snap
                )
                continue
            if command == "end" and len(line) == 1:
                try:
                    snap = self.end_turn()
                except AssertionError as error:
                    print(
                        f"Action rejected without closing the session: {error}",
                        flush=True,
                    )
                    continue
                self.record_action({"type": "end_turn"}, snap)
                if snap.get("phase") == "finished":
                    self.finish_and_return(snap)
                    return
                continue
            if command == "withdraw" and len(line) == 1:
                current = self.validated_trial()
                if current is None:
                    raise ValueError(
                        "No validated order-trial checkpoint to withdraw from"
                    )
                start = self.peer.mark()
                self.peer.send(13952)
                try:
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        _reject_after(self, start, "native withdrawal")
                        snapshot = self.checkpoint()
                        if snapshot and snapshot.get("phase") == "finished":
                            break
                        time.sleep(0.15)
                except AssertionError as error:
                    print(
                        f"Withdrawal rejected without closing the session: {error}",
                        flush=True,
                    )
                    continue
                self.record_action({"type": "native_withdrawal"}, snapshot)
                self.finish_and_return(snapshot)
                return
            print(
                "Unknown command; use status, move, cast, end, withdraw, or quit.",
                flush=True,
            )

    def report_result(self, snapshot=None):
        snapshot = snapshot or self.checkpoint()
        result = {
            "finished_checkpoint": False,
            "score_400_proven": False,
            "objective_4261": False,
            "quest_2149_completed": False,
        }
        if snapshot and snapshot.get("phase") == "finished":
            current = self.validated_trial()
            if current is None:
                raise ValueError(
                    "Finished fight has no validated order-trial checkpoint"
                )
            proof, rules, state, accepted_snapshot = current
            progress = _progress(self.store, self.char["id"])
            objective = OBJECTIVE in set(progress.get("objectives", ()))
            completed = QUEST in set(progress.get("completed", ()))
            from tools.native_order_trial_receipts import receipt_for_fight

            document = accepted_snapshot.get("native_order_trial", {})
            admission = (
                document.get("admission", {}) if isinstance(document, dict) else {}
            )
            with self.store.connection() as db:
                receipt = receipt_for_fight(
                    db,
                    self.char["id"],
                    self.fight_id,
                    expected_map_id=admission.get("source_map_id"),
                )
            receipts = int(receipt is not None)
            result = {
                "finished_checkpoint": snapshot.get("phase") == "finished",
                "trial_finished": state.finished,
                "hard_mode": proof.hard_mode,
                "score": state.score,
                "threshold": rules.score_threshold,
                "score_400_proven": state.hard_mode and state.score >= 400,
                "objective_4261": objective,
                "quest_2149_completed": completed,
                "native_settlement_receipts": receipts,
                "earned": bool(
                    state.hard_mode
                    and state.score >= 400
                    and objective
                    and completed
                    and receipts
                ),
            }
        self.receipt["result"] = result
        self.save()
        print(json.dumps(result, sort_keys=True), flush=True)


def _start_hard_trial(probe, *, auto400=False):
    probe.world_walk(_source_approach("hard"))
    mark = probe.peer.mark()
    probe.peer.send(12870, struct.pack(">qHH", _source_id("hard"), 0, 0))
    body = _wait_response(
        probe, 13652, mark, timeout=30, request="native hard-mode control"
    )
    probe.fight_id = struct.unpack_from(">i", body)[0]
    ready_mark = probe.peer.mark()
    probe.peer.send(12523, b"\x01")
    probe.ready_for_input(request_start=ready_mark)
    if probe.validated_trial() is None:
        raise AssertionError(
            "Native hard-mode start lacks its accepted score checkpoint"
        )
    probe.receipt.update({"fight_id": probe.fight_id, "started": True})
    probe.receipt.setdefault("events", []).append(
        {
            "kind": "native_hard_mode_started",
            "fight_id": probe.fight_id,
            "wire_frames_after_interaction": len(probe.peer.records) - mark,
        }
    )
    probe.save()
    if auto400:
        probe.auto400()
        snapshot = probe.checkpoint()
        if not snapshot or snapshot.get("phase") != "finished":
            probe.interactive()
    else:
        probe.interactive()


def _hold_connected_session(probe, error):
    print(
        f"Native request rejected; keeping the authenticated session open: {error}",
        flush=True,
    )
    print(
        "Use `status` to inspect the saved character state or `quit` to disconnect deliberately.",
        flush=True,
    )
    probe.interactive(actions_allowed=probe.validated_trial() is not None)


def run_resume(store, account_id, character_id, *, auto400=False):
    character = store.character(account_id, character_id)
    if character is not None and (
        character.get("map_id"),
        character.get("instance_id"),
    ) == (546, 0):
        return run_start(store, account_id, character_id, auto400=auto400, retry=True)
    ready = preflight(store, account_id, character_id, resume=True)
    if not ready["runtime_ready"]:
        raise ValueError(
            "Refusing to resume before the native admission capability is enabled"
        )
    probe = ExistingTrialProbe(store, account_id, character_id)
    probe.connect()
    try:
        with store.connection() as db:
            active = db.execute(
                "SELECT f.id,f.status,c.snapshot FROM combat_fight_participants p "
                "JOIN combat_fights f ON f.id=p.fight_id "
                "LEFT JOIN fight_checkpoints c ON c.fight_id=f.id "
                "WHERE p.character_id=%s AND p.account_id=%s "
                "AND f.status IN ('placement','active') ORDER BY f.id DESC LIMIT 1",
                (character_id, account_id),
            ).fetchone()
        if active is not None:
            snapshot = active["snapshot"]
            from wakfu_server import native_order_trial_checkpoint as checkpoint

            if (
                not isinstance(snapshot, dict)
                or snapshot.get("phase") not in ("placement", "active")
                or snapshot.get("phase") != active["status"]
            ):
                raise ValueError(
                    "Durable combat row is not a resumable placement/active checkpoint"
                )
            document = (
                snapshot.get(checkpoint.FIELD) if isinstance(snapshot, dict) else None
            )
            proof, _rules, _trial = checkpoint.validate(
                document, encounter_id=active["id"]
            )
            if (
                proof.owner_id != character_id
                or proof.account_id != account_id
                or proof.hard_mode is not True
            ):
                raise ValueError("Active combat is not this owner's native hard trial")
            probe.fight_id = active["id"]
            ready_mark = None
            if snapshot.get("phase") == "placement":
                # Match the existing native combat resume helper: a reconnect
                # can receive placement state through checkpoint recovery
                # without replaying the original13652 start packet.
                ready_mark = probe.peer.mark()
                probe.peer.send(12523, b"\x01")
            else:
                ready_mark = probe.peer.mark()
                probe.peer.send(13332, struct.pack(">i", probe.fight_id))
            try:
                probe.ready_for_input(request_start=ready_mark)
            except AssertionError as error:
                _hold_connected_session(probe, error)
                return
            probe.receipt.update(
                {"fight_id": probe.fight_id, "resumed_existing_fight": True}
            )
            probe.save()
            if auto400:
                probe.auto400()
                snapshot = probe.checkpoint()
                if not snapshot or snapshot.get("phase") != "finished":
                    probe.interactive()
            else:
                probe.interactive()
            return
        probe.receipt["resumed_accepted_quest"] = True
        probe.save()
        try:
            _start_hard_trial(probe, auto400=auto400)
        except AssertionError as error:
            _hold_connected_session(probe, error)
    except AssertionError as error:
        _hold_connected_session(probe, error)
    finally:
        if probe.peer is not None:
            probe.peer.close()


def run_start(store, account_id, character_id, *, auto400=False, retry=False):
    ready = preflight(store, account_id, character_id, retry=retry)
    if not ready["runtime_ready"]:
        raise ValueError(
            "Refusing to start before the native admission and arena are enabled: "
            + ready.get("refusal", "incomplete capability")
        )
    probe = ExistingTrialProbe(store, account_id, character_id)
    probe.connect()
    try:
        state = _progress(store, character_id)
        if QUEST not in state["running"]:
            probe.world_walk(BOARD_APPROACH)
            mark = probe.peer.mark()
            probe.peer.send(12870, struct.pack(">qHH", BOARD, 0, 0))
            _reject_after(probe, mark, "native mercenary board open")
            probe.peer.send(12864, struct.pack(">iqB", QUEST, -1, 1))
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                _reject_after(probe, mark, "native board acceptance of 2149")
                state = _progress(store, character_id)
                if QUEST in state["running"]:
                    break
                time.sleep(0.1)
            if QUEST not in state["running"]:
                raise AssertionError("Native board did not naturally accept 2149")
            probe.receipt["board_acceptance"] = {
                "quest_id": QUEST,
                "event_receipts": _receipt_count(
                    store, character_id, "native-mercenary-board-acceptance:2149"
                ),
                "wire_opcodes": [
                    op
                    for op, _ in probe.peer.records[mark:]
                    if op in (13205, 13312, 13422)
                ],
            }
            probe.save()

        probe.world_walk(_source_approach("entrance"))
        entry_mark = probe.peer.mark()
        probe.peer.send(12870, struct.pack(">qHH", _source_id("entrance"), 0, 0))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            _reject_after(probe, entry_mark, "native arcade entrance")
            probe.char = store.character(account_id, character_id)
            if probe.char["map_id"] == 885 and probe.char["instance_id"] > 0:
                break
            time.sleep(0.1)
        else:
            raise AssertionError(
                "Original native entrance did not create the owned arcade context"
            )
        probe.peer.send(12449)
        try:
            _start_hard_trial(probe, auto400=auto400)
        except AssertionError as error:
            _hold_connected_session(probe, error)
    except AssertionError as error:
        _hold_connected_session(probe, error)
    finally:
        if probe.peer is not None:
            probe.peer.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, type=int)
    parser.add_argument("--character-id", required=True, type=int)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--auto400",
        action="store_true",
        help="use only native client actions to reach 400, then return to manual controls",
    )
    args = parser.parse_args(argv)
    dsn = os.environ["WAKFU_DATABASE_URL"]
    local_connection(dsn)
    store = Store(dsn, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    if args.preflight:
        result = preflight(store, args.account_id, args.character_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["runtime_ready"]:
            return 2
        return 0
    if args.resume:
        run_resume(store, args.account_id, args.character_id, auto400=args.auto400)
        return 0
    run_start(store, args.account_id, args.character_id, auto400=args.auto400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
