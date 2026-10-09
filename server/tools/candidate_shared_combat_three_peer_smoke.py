"""Three-owner PvE TLS gate on a disposable candidate database only.

The first owner starts a test Mimic, two peers join successively during
placement, and the leader withdraws while the two peers are ready but the
leader is not. Pass ``--withdraw-phase active`` to ready A too and withdraw
only after A's connection receives active-fight opcode 13482. The remaining
two owners win, receive one durable reward each, reconnect to exploration
without replaying consumed fight packets, and can start another encounter.
This script refuses any DB whose name is not ``wakemu_candidate_smoke_*``.
"""

import argparse
import json
import os
import secrets
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.command_permissions import set_admin
from wakfu_server.store import Store

from candidate_shared_combat_push_smoke import (
    Peer,
    _path_to_melee_range,
    login,
    placement,
    spawned_actor,
)
from three_peer_harness import decode_turn, initial_survivor_turns


def wait_own_withdrawal_return(peer, fight_id, character_id):
    peer.send(12925, struct.pack(">iB", fight_id, 1))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        body, _ = peer.wait(12436, timeout=max(0.1, deadline - time.monotonic()))
        if len(body) == 16 and struct.unpack_from(">q", body)[0] == character_id:
            return body
    raise AssertionError("withdrawn leader received no own health continuation")


def wait_sql(store, query, parameters, predicate, label, timeout=10):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        with store.connection() as db:
            last = db.execute(query, parameters).fetchone()
        if predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"{label}; last durable row={last!r}")


def wait_placement(peer):
    body, packets = peer.wait(12847, timeout=20)
    placement_body = next((raw for opcode, raw in packets if opcode == 13652), None)
    if placement_body is None:
        placement_body, _ = peer.wait(13652, timeout=20)
    return placement(placement_body)


def create_character(store, label):
    account = store.register(
        "shared3_" + label + "_" + secrets.token_hex(4), secrets.token_urlsafe(24)
    )
    set_admin(
        store,
        account["id"],
        True,
        operator="candidate-shared-three-peer",
        reason="isolated three-owner PvE TLS gate",
    )
    character = store.create_character(
        account["id"],
        "Gate "
        + label.upper()
        + " "
        + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(6)),
        breed=8,
    )
    return account, character


def spawn_test_mimic(peer):
    command = "!mob 4196 1 1"
    peer.send(12366, struct.pack(">H", len(command)) + command.encode())
    peer.wait(674)
    for _ in range(30):
        body, _ = peer.wait(12608, timeout=10)
        actor = spawned_actor(body)
        if actor is not None and actor[1] == 4196:
            return actor
    raise AssertionError("candidate test command did not publish the Mimic")


def join_placement(peer, target_character_id, expected_fight_id):
    peer.send(13241, struct.pack(">qB", target_character_id, 0))
    fight_id, actors = wait_placement(peer)
    if fight_id != expected_fight_id:
        raise AssertionError("successive join opened or selected another fight")
    return actors


def wait_roster_update(peer, fight_id, expected_actor_ids, *, timeout=20):
    """Skip the initial four-byte 13026 start notification and stale rosters."""
    deadline = time.monotonic() + timeout
    last_roster = None
    while time.monotonic() < deadline:
        body, _ = peer.wait(13026, timeout=max(0.1, deadline - time.monotonic()))
        # Native placement start also uses 13026, but carries only fight_id.
        if len(body) == 4:
            if struct.unpack(">i", body)[0] == fight_id:
                continue
            raise AssertionError("received a 13026 start for another fight")
        update_id, rows = placement(body)
        if update_id != fight_id:
            raise AssertionError("received a placement refresh for another fight")
        last_roster = set(rows)
        if set(expected_actor_ids) <= last_roster:
            return rows
    raise AssertionError(
        f"placement refresh did not reach expected roster; last={sorted(last_roster or ())}"
    )


def command_text(body):
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
    return body[start:].decode("utf-8")


def assert_world_reconnect(peer):
    """Require a map bootstrap and a harmless world command, never fight replay."""
    peer.wait(13974, timeout=20)
    peer.send(12366, struct.pack(">H", 4) + b"!pos")
    reply, seen = peer.wait(674, timeout=20)
    packets = list(seen) + list(peer.pending)
    forbidden = {12238, 12755, 12502, 13482, 13509}
    replayed = [opcode for opcode, _body in packets if opcode in forbidden]
    if replayed:
        raise AssertionError(f"world reconnect replayed fight packets: {replayed}")
    text = command_text(reply)
    if not text or "Termina el combate" in text:
        raise AssertionError("reconnected character did not return to exploration")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--withdraw-phase", choices=("placement", "active"), default="placement"
    )
    withdraw_phase = parser.parse_args().withdraw_phase
    dbname = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not dbname.startswith("wakemu_candidate_smoke_"):
        raise ValueError("requires a disposable wakemu_candidate_smoke_* database")
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peers = []
    try:
        owners = [create_character(store, role) for role in ("a", "b", "c")]
        for index, (account, character) in enumerate(owners):
            peer = Peer()
            peers.append(peer)
            login(store, peer, account, character, f"three-peer-{index}")

        first, second, third = peers
        char_a, char_b, char_c = (pair[1] for pair in owners)

        # Isolated deterministic XP input verifies that both surviving owners
        # have an award, while never affecting a non-candidate database.
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_reward_monster_levels "
                "(monster_reference,monster_level,base_xp,min_kamas,max_kamas,source) "
                "VALUES(4196,1,10000,5,5,'isolated three-owner TLS gate') "
                "ON CONFLICT(monster_reference,monster_level) DO UPDATE SET "
                "base_xp=EXCLUDED.base_xp,min_kamas=EXCLUDED.min_kamas,"
                "max_kamas=EXCLUDED.max_kamas,source=EXCLUDED.source"
            )

        monster_id, monster_ref, monster_position = spawn_test_mimic(first)
        first.send(13130, struct.pack(">qiihB", monster_id, *monster_position, 1))
        initial, _ = first.wait(13652)
        fight_id, actors = placement(initial)
        if {char_a["id"], monster_id} - set(actors):
            raise AssertionError("starter placement lacks its owner or Mimic")

        actors_b = join_placement(second, char_a["id"], fight_id)
        if {char_a["id"], char_b["id"], monster_id} - set(actors_b):
            raise AssertionError("first join did not receive the shared roster")
        first.wait(13091, timeout=20)
        wait_roster_update(first, fight_id, {char_a["id"], char_b["id"], monster_id})

        actors_c = join_placement(third, char_a["id"], fight_id)
        expected_roster = {char_a["id"], char_b["id"], char_c["id"], monster_id}
        if expected_roster - set(actors_c):
            raise AssertionError("second join did not receive all three owners")
        first.wait(13091, timeout=20)
        actors_after_c = wait_roster_update(first, fight_id, expected_roster)
        if (
            len(
                {
                    actors_after_c[char_a["id"]],
                    actors_after_c[char_b["id"]],
                    actors_after_c[char_c["id"]],
                }
            )
            != 3
        ):
            raise AssertionError("joined owners were assigned overlapping cells")
        with store.connection() as db:
            teams = {
                row["character_id"]: row["team"]
                for row in db.execute(
                    "SELECT character_id,team FROM combat_fight_participants "
                    "WHERE fight_id=%s",
                    (fight_id,),
                )
            }
        if teams != {char_a["id"]: 0, char_b["id"]: 0, char_c["id"]: 0}:
            raise AssertionError(
                "successive joins were not persisted on the target team"
            )

        # B and C ready first. Placement mode withdraws A before it readies;
        # active mode readies A last and waits for its active-fight turn start.
        second.send(12523, b"\x01")
        third.send(12523, b"\x01")
        active_action_id = None
        active_actor = None
        if withdraw_phase == "active":
            first.send(12523, b"\x01")
            active_start, _ = first.wait(13482, timeout=30)
            active_action_id, active_actor = decode_turn(
                active_start,
                fight_id,
                {char_a["id"], char_b["id"], char_c["id"], monster_id},
            )
        first.send(13952, b"")
        terminal, _ = first.wait(12238, timeout=30)
        if len(terminal) < 4 or struct.unpack_from(">i", terminal)[0] != fight_id:
            raise AssertionError("leader withdrawal terminal belongs to another fight")
        wait_own_withdrawal_return(first, fight_id, char_a["id"])
        wait_sql(
            store,
            "SELECT returned_at FROM combat_pve_withdrawals "
            "WHERE fight_id=%s AND character_id=%s",
            (fight_id, char_a["id"]),
            lambda row: row is not None and row["returned_at"] is not None,
            "leader withdrawal receipt/return was not persisted",
        )

        survivor_ids = {char_b["id"], char_c["id"], monster_id}
        turn_b, turn_c, ack_turn = initial_survivor_turns(
            withdraw_phase,
            second,
            third,
            fight_id,
            survivor_ids,
            {char_a["id"]},
            ack_turn=1,
        )

        controlled = {char_b["id"]: second, char_c["id"]: third}
        positions = dict(actors_after_c)
        positions.pop(char_a["id"], None)
        turn_counts = {char_b["id"]: 1, char_c["id"]: 1}
        last_start = turn_b
        allowed_turn_actors = {char_b["id"], char_c["id"], monster_id}
        last_turn_action_id, _ = decode_turn(turn_b, fight_id, allowed_turn_actors)
        report_b = None
        report_c = None
        for _ in range(100):
            observed_action_id, actor_id = decode_turn(
                last_start,
                fight_id,
                allowed_turn_actors,
                after_action_id=last_turn_action_id - 1,
            )
            if observed_action_id != last_turn_action_id:
                raise AssertionError("turn-start packet changed while being processed")
            if actor_id in controlled:
                actor_peer = controlled[actor_id]
                target = positions[monster_id]
                occupied = {
                    cell for identity, cell in positions.items() if identity != actor_id
                }
                route = _path_to_melee_range(
                    char_a["map_id"], positions[actor_id], target, occupied
                )
                if route is None:
                    raise AssertionError("no native walk path from owner to the Mimic")
                if route:
                    actor_peer.send(
                        12161,
                        struct.pack(">q", actor_id)
                        + b"".join(struct.pack(">iih", *cell) for cell in route),
                    )
                    _, movement_packets = second.wait_any({13624, 674}, timeout=8)
                    if any(opcode == 674 for opcode, _ in movement_packets):
                        raise AssertionError("candidate rejected native combat path")
                    positions[actor_id] = route[-1]

                if (
                    abs(positions[actor_id][0] - target[0])
                    + abs(positions[actor_id][1] - target[1])
                    == 1
                    and positions[actor_id][2] == target[2]
                ):
                    actor_peer.send(
                        12889, struct.pack(">qqbiih", actor_id, -1, 15, *target)
                    )
                    try:
                        _, action_packets = actor_peer.wait_any({12755, 674}, timeout=5)
                    except AssertionError:
                        action_packets = []
                    if any(opcode == 674 for opcode, _ in action_packets):
                        raise AssertionError(
                            "candidate rejected the native unarmed action"
                        )
                    report = next(
                        (body for opcode, body in action_packets if opcode == 12755),
                        None,
                    )
                    if report is not None:
                        if actor_peer is second:
                            report_b = report
                        else:
                            report_c = report
                        break
                actor_peer.send(
                    12403, struct.pack(">qh", actor_id, turn_counts[actor_id])
                )
                turn_counts[actor_id] += 1

            try:
                (opcode, body), _ = second.wait_any({12502, 12755}, timeout=40)
            except AssertionError as error:
                raise AssertionError(
                    f"shared PvE stalled at actor {actor_id}"
                ) from error
            if opcode == 12755:
                report_b = body
                break
            second.send(13510, struct.pack(">i", ack_turn))
            third.send(13510, struct.pack(">i", ack_turn))
            ack_turn += 1
            try:
                (opcode_b, body_b), _ = second.wait_any({13482, 12755}, timeout=40)
                (opcode_c, body_c), _ = third.wait_any({13482, 12755}, timeout=40)
            except AssertionError as error:
                raise AssertionError(
                    "shared next turn was not pushed after ACK"
                ) from error
            if opcode_b != opcode_c:
                raise AssertionError(
                    "owners received different turn/result transitions"
                )
            if opcode_b == 12755:
                report_b, report_c = body_b, body_c
                break
            if body_b != body_c:
                raise AssertionError(
                    "owners received inconsistent repeated turn packets"
                )
            last_turn_action_id, _ = decode_turn(
                body_b,
                fight_id,
                allowed_turn_actors,
                after_action_id=last_turn_action_id,
            )
            last_start = body_b

        if not report_b:
            report_b, _ = second.wait(12755, timeout=10)
        if not report_c:
            report_c, _ = third.wait(12755, timeout=15)
        if not report_b or not report_c:
            raise AssertionError("a surviving owner did not receive a private result")

        with store.connection() as db:
            status = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
            ).fetchone()
            rewards = db.execute(
                "SELECT character_id,xp,kamas FROM fight_rewards WHERE fight_id=%s "
                "ORDER BY character_id",
                (fight_id,),
            ).fetchall()
            withdrawal = db.execute(
                "SELECT returned_at FROM combat_pve_withdrawals "
                "WHERE fight_id=%s AND character_id=%s",
                (fight_id, char_a["id"]),
            ).fetchone()
            reward_count = db.execute(
                "SELECT COUNT(*) AS count FROM fight_rewards WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["count"]
            reward_characters = {row["character_id"] for row in rewards}
            if status is None or status["status"] != "finished":
                raise AssertionError("shared victory was not durably settled")
            if reward_characters != {char_b["id"], char_c["id"]}:
                raise AssertionError("rewards do not match the two surviving owners")
            if withdrawal is None or withdrawal["returned_at"] is None:
                raise AssertionError("leader withdrawal has no durable return receipt")
            if reward_count != 2 or any(row["xp"] <= 0 for row in rewards):
                raise AssertionError(
                    "surviving owners lack exactly one positive reward"
                )
            durable_counts = {
                table: db.execute(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["count"]
                for table in (
                    "fight_rewards",
                    "fight_drop_attempt_receipts",
                    "fight_drop_awards",
                    "fight_drop_delivery_receipts",
                )
            }

        # A's return and B/C's reports are already consumed. Terminal recovery
        # returns a fresh exploration session, not the old private 12755 report.
        second.close()
        replacement = Peer()
        peers[1] = replacement
        login(store, replacement, owners[1][0], char_b, "three-peer-b-reconnect")
        assert_world_reconnect(replacement)
        with store.connection() as db:
            replay_counts = {
                table: db.execute(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["count"]
                for table in durable_counts
            }
        if replay_counts != durable_counts:
            raise AssertionError("settlement replay duplicated reward/drop receipts")

        # C stayed in the original connection and still needs the native return
        # ACK; B is already in exploration after terminal recovery.
        third.send(12925, struct.pack(">iB", fight_id, 0))
        third.wait(13974, timeout=20)
        wait_sql(
            store,
            "SELECT status FROM combat_fights WHERE id=%s",
            (fight_id,),
            lambda row: row is not None and row["status"] == "finished",
            "shared fight return did not remain terminal",
        )

        # Prove a surviving owner can begin a new encounter after the shared
        # fight has fully returned, then close the smoke encounter cleanly.
        next_monster_id, _, next_position = spawn_test_mimic(replacement)
        replacement.send(
            13130, struct.pack(">qiihB", next_monster_id, *next_position, 1)
        )
        next_placement, _ = replacement.wait(13652, timeout=20)
        next_fight_id, next_actors = placement(next_placement)
        if next_fight_id == fight_id or char_b["id"] not in next_actors:
            raise AssertionError("survivor could not start a new PvE after return")
        replacement.send(13952, b"")
        replacement.wait(12238, timeout=20)
        wait_own_withdrawal_return(replacement, next_fight_id, char_b["id"])
        wait_sql(
            store,
            "SELECT status FROM combat_fights WHERE id=%s",
            (next_fight_id,),
            lambda row: row is not None and row["status"] == "aborted",
            "new smoke encounter did not close after placement withdrawal",
        )

        print(
            json.dumps(
                {
                    "result": "PASS",
                    "fight_id": fight_id,
                    "participants": [char_a["id"], char_b["id"], char_c["id"]],
                    "successive_placement_joins": True,
                    "same_team_and_unique_cells": True,
                    "leader_withdrawn_and_returned": True,
                    "withdraw_phase": withdraw_phase,
                    "withdrawn_during_placement": withdraw_phase == "placement",
                    "withdrawn_during_active_fight": withdraw_phase == "active",
                    "leader_active_action_id": active_action_id,
                    "leader_active_turn_actor": active_actor,
                    "survivor_rewards": [
                        {
                            "character_id": row["character_id"],
                            "xp": row["xp"],
                            "kamas": row["kamas"],
                        }
                        for row in rewards
                    ],
                    "withdrawn_leader_reward_absent": char_a["id"]
                    not in reward_characters,
                    "settlement_replay_without_duplicate": True,
                    "durable_counts_before_replay": durable_counts,
                    "durable_counts_after_replay": replay_counts,
                    "next_fight_id": next_fight_id,
                }
            ),
            flush=True,
        )
    finally:
        for peer in peers:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
