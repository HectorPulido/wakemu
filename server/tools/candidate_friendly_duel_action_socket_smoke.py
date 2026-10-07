"""Two-peer TLS duel action/timeout/abandon smoke for a disposable candidate.

This extends the existing invitation-only duel smoke with real player casts,
the shared turn ACK barrier, deadline expiry, both 13952 paths, and a PvE fight
started by the same still-connected session after duel return. Run only against
a disposable ``wakemu_candidate_smoke_*`` database and candidate world.
"""
import os
import secrets
import struct
import time

from psycopg.conninfo import conninfo_to_dict

from candidate_friendly_duel_socket_smoke import Peer, login, challenge_body, placement
from candidate_combat_socket_reward_smoke import _spawned_actors
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_los import static_visible
from wakfu_server.spells import default_deck, validate_deck
from wakfu_server.store import Store


def _wait_pair(peers, opcode, timeout=40):
    return [peer.wait(opcode, timeout=timeout)[0] for peer in peers]


def _turn_actor(body):
    # 13337/13482 are cvF packets: the common action prefix is 12 bytes,
    # followed by current actor UID and native turn duration.
    if len(body) < 28:
        raise AssertionError(f"short native turn packet: {len(body)} bytes")
    return struct.unpack_from(">q", body, 12)[0]


def _checkpoint(db, fight_id):
    row = db.execute(
        "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if row is None:
        raise AssertionError("fight checkpoint was not persisted")
    return row["snapshot"]


def _poll(store, fight_id, predicate, *, timeout=45, description):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        with store.connection() as db:
            last = _checkpoint(db, fight_id)
        if predicate(last):
            return last
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {description}; last={last}")


def _accepted_duel(store, challenger, target, peer_challenger, peer_target):
    peer_challenger.send(12117, challenge_body(target["id"], (999, 999, 0)))
    invite_body, _ = peer_target.wait(13179)
    expected = struct.pack(">qB", challenger["id"], 1)
    if invite_body != expected:
        raise AssertionError("native invite names a different challenger")
    peer_target.send(13520, struct.pack(">qBB", challenger["id"], 1, 0))
    bodies = _wait_pair((peer_challenger, peer_target), 13652)
    fight_ids = {placement(body)[0] for body in bodies}
    if len(fight_ids) != 1:
        raise AssertionError("accepted duel peers received different fight IDs")
    fight_id = fight_ids.pop()
    with store.connection() as db:
        row = db.execute(
            "SELECT status,fight_kind FROM combat_fights WHERE id=%s", (fight_id,)
        ).fetchone()
    if row is None or (row["status"], row["fight_kind"]) != ("placement", "duel"):
        raise AssertionError("duel was not durable before placement")
    return fight_id


def _return_pair(peers, fight_id):
    for peer in peers:
        peer.send(12925, struct.pack(">iB", fight_id, 0))
    _wait_pair(peers, 13974, timeout=40)


def _await_ack(store, peers, fight_id, *, timeout=40):
    snapshot = _poll(
        store,
        fight_id,
        lambda value: value.get("runtime", {}).get("awaiting_ack") is not None,
        timeout=timeout,
        description="both-recipient 13510 ACK barrier",
    )
    turn = snapshot["runtime"]["awaiting_ack"]
    _wait_pair(peers, 12502, timeout=10)
    for peer in peers:
        peer.send(13510, struct.pack(">i", turn))
    snapshot = _poll(
        store,
        fight_id,
        lambda value: value.get("runtime", {}).get("awaiting_ack") is None,
        timeout=10,
        description="both clients releasing 13510 barrier",
    )
    order = snapshot.get("order")
    turn_index = snapshot.get("turn_index")
    if (
        not isinstance(order, list)
        or type(turn_index) is not int
        or not order
        or not 0 <= turn_index < len(order)
    ):
        raise AssertionError("ACK released to a fight without an active actor")
    current = order[turn_index]
    turn_bodies = _wait_pair(peers, 13482, timeout=15)
    if any(_turn_actor(body) != current for body in turn_bodies):
        raise AssertionError("clients received a different turn after ACK release")
    return current


def _end_turn(store, peers, fight_id, actor_id):
    with store.connection() as db:
        snapshot = _checkpoint(db, fight_id)
    actor_turn = snapshot["actors"][str(actor_id)]["turn_count"]
    peer_by_character = peers[0] if actor_id == peers[0].character_id else peers[1]
    peer_by_character.send(12403, struct.pack(">qh", actor_id, actor_turn))
    _poll(
        store,
        fight_id,
        lambda value: value.get("runtime", {}).get("awaiting_ack") is not None,
        timeout=10,
        description=f"turn-end ACK barrier for actor {actor_id}",
    )


def _cast(store, peers, fight_id, actor_id, enemy_id, enemy_cell):
    peer = next(p for p in peers if p.character_id == actor_id)
    actor = next(c for c in peer.characters if c["id"] == actor_id)
    active = validate_deck(default_deck(actor), actor["breed"], actor["level"])[
        "active"
    ]
    spell = int(os.environ.get("WAKFU_DUEL_SMOKE_SPELL", "6266"))
    if spell not in active:
        raise AssertionError(
            f"spell {spell} is not in the character's native default deck"
        )
    uid = (actor_id << 32) | spell
    before = _poll(
        store,
        fight_id,
        lambda value: value.get("phase") == "active",
        timeout=5,
        description="active duel checkpoint before cast",
    )
    prior_action = before.get("runtime", {}).get("action_id", 0)
    peer.send(13260, struct.pack(">qqiih", actor_id, uid, *enemy_cell))
    _poll(
        store,
        fight_id,
        lambda value: value.get("runtime", {}).get("action_id", 0) > prior_action,
        timeout=20,
        description=f"committed native 13260 cast by {actor_id}",
    )
    with store.connection() as db:
        after = _checkpoint(db, fight_id)
    hp_before = before["actors"][str(enemy_id)]["hp"]
    hp_after = after["actors"][str(enemy_id)]["hp"]
    if hp_after >= hp_before:
        raise AssertionError(
            f"13260 spell {spell} did not damage opponent {enemy_id}: {hp_before}->{hp_after}"
        )


def _placement_forfeit(store, owners, peers):
    fight_id = _accepted_duel(store, owners[0][1], owners[1][1], peers[0], peers[1])
    peers[0].send(13952, b"")
    deadline = time.monotonic() + 25
    outcome = None
    while time.monotonic() < deadline:
        with store.connection() as db:
            outcome = db.execute(
                "SELECT reason FROM friendly_duel_outcomes WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()
        if outcome is not None:
            break
        time.sleep(0.1)
    if outcome is None or outcome["reason"] != "defeat":
        raise AssertionError(
            "placement-phase native 13952 did not create a defeat outcome"
        )
    _return_pair(peers, fight_id)
    return fight_id


def main():
    database = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError(
            "Friendly-duel action smoke requires a disposable candidate DB"
        )
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peers = []
    try:
        owners = []
        for label in "abcd":
            account = store.register(
                "duel_action_" + label + "_" + secrets.token_hex(4),
                secrets.token_urlsafe(24),
            )
            if label == "c":
                # The follow-up !mob is an administrator-only development
                # command. Grant it only to this disposable smoke account and
                # record the grant through the normal audit helper.
                from wakfu_server.command_permissions import set_admin

                set_admin(
                    store,
                    account["id"],
                    True,
                    operator="candidate-duel-action-smoke",
                    reason="Create one PvE encounter after the duel lifecycle check",
                )
            character = store.create_character(
                account["id"],
                "Action "
                + label.upper()
                + " "
                + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(6)),
                breed=15,
            )
            owners.append((account, character))

        # Reuse two native adjacent world tiles for the isolated sequential
        # duel pairs; only one pair fights at a time in this candidate.
        world_cells = map_geometry(1134)["edges"][0]
        if len(world_cells) < 2:
            raise AssertionError("native test map has no adjacent world-edge pair")
        for index, (account, character) in enumerate(owners):
            cell = world_cells[index % 2]
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=1134,instance_id=0,x=%s,y=%s,z=%s,"
                    "hp=max_hp,hp_damage=0,health_dead=false WHERE id=%s AND account_id=%s",
                    (*cell, character["id"], account["id"]),
                )
        for index, (account, character) in enumerate(owners):
            peer = Peer()
            peers.append(peer)
            peer.account_id = account["id"]
            peer.character_id = character["id"]
            peer.characters = [c for _, c in owners]
            peer.generation = login(store, peer, account, character, f"action-{index}")

        # 13952 during placement must durably settle this separate accepted
        # duel before the main active-turn case.
        placement_fight = _placement_forfeit(store, owners[:2], peers[:2])

        duel_fight = _accepted_duel(
            store, owners[2][1], owners[3][1], peers[2], peers[3]
        )
        progression_before = {}
        for account, character in owners[2:4]:
            with store.connection() as db:
                row = db.execute(
                    "SELECT p.xp,w.kamas FROM character_progression p "
                    "JOIN characters c ON c.id=p.character_id "
                    "JOIN account_wallets w ON w.account_id=c.account_id "
                    "WHERE p.character_id=%s AND c.account_id=%s",
                    (character["id"], account["id"]),
                ).fetchone()
            progression_before[character["id"]] = (row["xp"], row["kamas"])
        with store.connection() as db:
            layout = db.execute(
                "SELECT layout FROM fight_placement_layouts WHERE fight_id=%s",
                (duel_fight,),
            ).fetchone()["layout"]
        team0 = [tuple(cell) for cell in layout["placement"]["0"]]
        team1 = [tuple(cell) for cell in layout["placement"]["1"]]
        pairs = []
        for left in team0:
            for right in team1:
                dx, dy = abs(left[0] - right[0]), abs(left[1] - right[1])
                distance = dx + dy
                if (
                    left[2] == right[2]
                    and 1 <= distance <= 3
                    and (dx == 0 or dy == 0)
                    and static_visible(1134, left, right)
                ):
                    pairs.append((distance, left, right))
        if not pairs:
            raise AssertionError(
                "frozen duel layout has no linear level-1 Iop cast pair"
            )
        _, cell_a, cell_b = min(pairs)
        for peer, actor_id, cell in (
            (peers[2], owners[2][1]["id"], cell_a),
            (peers[3], owners[3][1]["id"], cell_b),
        ):
            peer.send(12806, struct.pack(">qiih", actor_id, *cell))
            _wait_pair(peers[2:4], 13652, timeout=10)
        peers[2].send(12523, b"\x01")
        peers[3].send(12523, b"\x01")
        start = _wait_pair(peers[2:4], 13482, timeout=20)
        actor_id = _turn_actor(start[0])
        if actor_id != _turn_actor(start[1]):
            raise AssertionError("duel owners received different active-turn actors")

        roster = {owners[2][1]["id"], owners[3][1]["id"]}
        cast_actors = []
        for _ in range(2):
            if actor_id not in roster:
                raise AssertionError("duel turn advanced to an unowned actor")
            enemy_id = next(identity for identity in roster if identity != actor_id)
            enemy_cell = cell_b if enemy_id == owners[3][1]["id"] else cell_a
            _cast(store, peers[2:4], duel_fight, actor_id, enemy_id, enemy_cell)
            cast_actors.append(actor_id)
            _end_turn(store, peers[2:4], duel_fight, actor_id)
            actor_id = _await_ack(store, peers[2:4], duel_fight)
        if set(cast_actors) != roster:
            raise AssertionError(f"both duel owners did not issue 13260: {cast_actors}")

        # Leave the next active owner idle until the server's real timer ends
        # the turn. Both sockets must ACK the same 13510 barrier.
        timed = _poll(
            store,
            duel_fight,
            lambda value: value.get("runtime", {}).get("awaiting_ack") is not None,
            timeout=45,
            description="natural active-turn deadline expiry",
        )
        expired_turn = timed["runtime"]["awaiting_ack"]
        _wait_pair(peers[2:4], 12502, timeout=10)
        for peer in peers[2:4]:
            peer.send(13510, struct.pack(">i", expired_turn))
        post_expiry = _poll(
            store,
            duel_fight,
            lambda value: value.get("runtime", {}).get("awaiting_ack") is None,
            timeout=10,
            description="both owner ACKs after deadline expiry",
        )
        if post_expiry.get("phase") != "active":
            raise AssertionError("deadline ACK did not preserve active duel")
        expired_turn_bodies = _wait_pair(peers[2:4], 13482, timeout=15)
        if any(
            _turn_actor(body) != post_expiry["order"][post_expiry["turn_index"]]
            for body in expired_turn_bodies
        ):
            raise AssertionError(
                "deadline ACKs did not publish the current shared actor"
            )

        # Prove the explicit client abandon request, rather than disconnect,
        # wins the still-active encounter.
        peers[2].send(13952, b"")
        deadline = time.monotonic() + 30
        outcome = None
        while time.monotonic() < deadline:
            with store.connection() as db:
                outcome = db.execute(
                    "SELECT reason,winner_character_id,loser_character_id "
                    "FROM friendly_duel_outcomes WHERE fight_id=%s",
                    (duel_fight,),
                ).fetchone()
            if outcome is not None:
                break
            time.sleep(0.1)
        if outcome is None or outcome["reason"] != "defeat":
            raise AssertionError("active native 13952 did not durably forfeit the duel")
        with store.connection() as db:
            fight = db.execute(
                "SELECT status,fight_kind FROM combat_fights WHERE id=%s", (duel_fight,)
            ).fetchone()
            for table in (
                "fight_rewards",
                "fight_drop_awards",
                "fight_drop_attempt_receipts",
                "fight_drop_delivery_receipts",
            ):
                if db.execute(
                    f"SELECT 1 FROM {table} WHERE fight_id=%s LIMIT 1", (duel_fight,)
                ).fetchone():
                    raise AssertionError(
                        f"duel created forbidden PvE receipt in {table}"
                    )
        if fight["status"] != "finished" or fight["fight_kind"] != "duel":
            raise AssertionError("active abandon failed to finish the duel")
        _return_pair(peers[2:4], duel_fight)
        for account, character in owners[2:4]:
            with store.connection() as db:
                row = db.execute(
                    "SELECT p.xp,w.kamas FROM character_progression p "
                    "JOIN characters c ON c.id=p.character_id "
                    "JOIN account_wallets w ON w.account_id=c.account_id "
                    "WHERE p.character_id=%s AND c.account_id=%s",
                    (character["id"], account["id"]),
                ).fetchone()
            if (row["xp"], row["kamas"]) != progression_before[character["id"]]:
                raise AssertionError("active duel forfeit changed XP or kamas")

        # The same still-live socket starts a normal PvE fight after the duel
        # return, proving the shared registry released its actor/session slots.
        def command_text(body):
            if not body:
                return ""
            name_length = body[0]
            text_length_offset = 1 + name_length + 11
            if len(body) < text_length_offset + 2:
                return ""
            text_length = struct.unpack_from(">H", body, text_length_offset)[0]
            start = text_length_offset + 2
            if len(body) != start + text_length:
                return ""
            return body[start:].decode("utf-8")

        # 13974 is sent before the server finishes restoring the world session.
        # A harmless public position command gives a protocol-level barrier:
        # the same dispatcher has completed the return before !mob is sent.
        readiness = "!pos"
        peers[2].send(12366, struct.pack(">H", len(readiness)) + readiness.encode())
        readiness_body, _ = peers[2].wait(674, timeout=15)
        if "Termina el combate" in command_text(readiness_body):
            raise AssertionError("world return did not clear the combat session")

        command = "!mob 4196 1 1"
        peers[2].send(12366, struct.pack(">H", len(command)) + command.encode())
        command_packets = []
        command_deadline = time.monotonic() + 30
        response_text = ""
        while time.monotonic() < command_deadline:
            response, seen = peers[2].wait(
                674, timeout=max(0.1, command_deadline - time.monotonic())
            )
            command_packets.extend(seen)
            response_text = command_text(response)
            if "grupo=" in response_text:
                break
        if "grupo=" not in response_text:
            raise AssertionError(
                f"!mob did not return its group receipt: {response_text!r}"
            )

        monster = None
        spawn_bodies = [body for opcode, body in command_packets if opcode == 12608]
        skipped_spawn_prefixes = []
        while time.monotonic() < command_deadline:
            for spawn_body in spawn_bodies:
                if len(spawn_body) < 2 or spawn_body[0] != 0 or spawn_body[1] == 0:
                    skipped_spawn_prefixes.append(spawn_body[:24].hex())
                    continue
                try:
                    actors = _spawned_actors(spawn_body)
                except AssertionError:
                    skipped_spawn_prefixes.append(spawn_body[:24].hex())
                    continue
                if len(actors) == 1 and actors[0]["reference"] == 4196:
                    monster = actors[0]
                    break
            if monster is not None:
                break
            spawn_body, _ = peers[2].wait(
                12608, timeout=max(0.1, command_deadline - time.monotonic())
            )
            spawn_bodies = [spawn_body]
        if monster is None:
            raise AssertionError(
                "!mob 4196 response had no matching singleton appearance; "
                f"skipped 12608 prefixes={skipped_spawn_prefixes}"
            )
        x, y, z = monster["position"]
        peers[2].send(13130, struct.pack(">qiihB", monster["id"], x, y, z, 1))
        # 13652 carries the full placement roster; 13026 is only the fight ID.
        placement_body, _ = peers[2].wait(13652, timeout=40)
        pve_fight, actors = placement(placement_body)
        if peers[2].character_id not in actors or monster["id"] not in actors:
            raise AssertionError("same-session PvE join omitted the prior duelist")
        with store.connection() as db:
            pve = db.execute(
                "SELECT status,fight_kind FROM combat_fights WHERE id=%s", (pve_fight,)
            ).fetchone()
            duel_row = db.execute(
                "SELECT status,fight_kind FROM combat_fights WHERE id=%s",
                (placement_fight,),
            ).fetchone()
        if pve is None or pve["fight_kind"] != "pve":
            raise AssertionError("same-session interaction did not create a PvE fight")
        if duel_row is None or duel_row["status"] != "finished":
            raise AssertionError(
                "placement abandon was not terminal before active duel"
            )

        # Regression from the user's Mimic test: ordinary shared PvE must
        # also accept 13952 and release its Registry identity after 12925.
        peers[2].send(13952, b"")
        peers[2].wait(12238, timeout=40)
        peers[2].send(12925, struct.pack(">iB", pve_fight, 0))
        peers[2].wait(13974, timeout=40)
        peers[2].send(12366, struct.pack(">H", len(readiness)) + readiness.encode())
        position_reply, _ = peers[2].wait(674, timeout=15)
        if "Termina el combate" in command_text(position_reply):
            raise AssertionError("PvE surrender did not restore world control")
        with store.connection() as db:
            terminal = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (pve_fight,)
            ).fetchone()
        if terminal is None or terminal["status"] not in ("finished", "aborted"):
            raise AssertionError("PvE surrender did not durably terminate the fight")
        peers[2].send(13130, struct.pack(">qiihB", monster["id"], x, y, z, 1))
        next_placement, _ = peers[2].wait(13652, timeout=40)
        next_pve, next_actors = placement(next_placement)
        if next_pve == pve_fight or peers[2].character_id not in next_actors:
            raise AssertionError(
                "PvE surrender left a Registry identity blocking a new fight"
            )

        # The reported residual also occurred after closing the entire
        # client. Wait for durable abort before issuing the next session,
        # then prove Registry and encounter availability through a new fight.
        peers[2].close()
        disconnect_deadline = time.monotonic() + 40
        while time.monotonic() < disconnect_deadline:
            with store.connection() as db:
                disconnected = db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (next_pve,)
                ).fetchone()
            if disconnected is not None and disconnected["status"] == "aborted":
                break
            time.sleep(0.1)
        else:
            raise AssertionError("last PvE socket disconnect did not persist abort")
        replacement = Peer()
        peers[2] = replacement
        account, original_character = owners[2]
        replacement.account_id = account["id"]
        replacement.character_id = original_character["id"]
        replacement.characters = [c for _, c in owners]
        replacement.generation = login(
            store, replacement, account, original_character, "pve-reconnect"
        )
        replacement.send(12366, struct.pack(">H", len(readiness)) + readiness.encode())
        world_reply, _ = replacement.wait(674, timeout=15)
        if "Termina el combate" in command_text(world_reply):
            raise AssertionError("PvE reconnect retained the previous fight session")
        replacement.send(13130, struct.pack(">qiihB", monster["id"], x, y, z, 1))
        reconnect_placement, _ = replacement.wait(13652, timeout=40)
        reconnect_pve, reconnect_actors = placement(reconnect_placement)
        if (
            reconnect_pve in (next_pve, pve_fight)
            or replacement.character_id not in reconnect_actors
        ):
            raise AssertionError("PvE reconnect left Fight/actor already registered")

        print(
            {
                "placement_13952": placement_fight,
                "active_duel_13952": duel_fight,
                "native_casts_13260_by_both": cast_actors,
                "deadline_expired_acknowledged_by_both": expired_turn,
                "same_session_pve_fight": pve_fight,
                "pve_surrender_then_new_fight": next_pve,
                "pve_disconnect_reconnect_new_fight": reconnect_pve,
            },
            flush=True,
        )
    finally:
        for peer in peers:
            try:
                peer.close()
            except Exception:
                pass
        store.close()


if __name__ == "__main__":
    main()
