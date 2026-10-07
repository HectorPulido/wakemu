"""Real TLS marker/spectator/join/withdraw gate in a disposable DB.

Use the existing world temporarily pointed at a wakemu_candidate_smoke_* DB.
Never run against the user's ordinary world DB or characters11/12. The root
agent coordinates that temporary switch; this runner never restarts services.
"""
import json
import os
import secrets
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from candidate_combat_spectator_socket_smoke import (
    Peer,
    _login,
    _placement,
    _spawned_actor,
    _console_text,
)
from wakfu_server.command_permissions import set_admin
from wakfu_server.combat.combat_multiplayer_wire import decode_external
from wakfu_server.combat.combat_spectator_wire import decode_spectator_bootstrap
from wakfu_server.combat.combat_wire import decode_topology
from wakfu_server.store import Store


def marker(peer, fight_id, *, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body, _ = peer.wait(13753, timeout=max(0.1, deadline - time.monotonic()))
        decoded = decode_external(body)
        if decoded["fight_id"] == fight_id:
            return decoded
    raise AssertionError("No external marker for own disposable fight")


def assert_topology_carrier(value):
    topology = decode_topology(value["topology"])
    expected = {
        (x, y)
        for y in range(
            topology["y"] // 18, (topology["y"] + topology["height"] - 1) // 18 + 1
        )
        for x in range(
            topology["x"] // 18, (topology["x"] + topology["width"] - 1) // 18 + 1
        )
    }
    assert set(value["mys"]) == expected, "13753 partitions do not cover QI"
    assert topology["instance_id"] == 0, "13753 is outside public scene"
    return topology


def main():
    url = os.environ["WAKFU_DATABASE_URL"]
    database = conninfo_to_dict(url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError("TLS gate requires disposable wakemu_candidate_smoke_* DB")
    store = Store(url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    peers = []
    fixture = []
    try:
        for role in ("starter", "joining", "watching"):
            account = store.register(
                "r16_" + role + "_" + secrets.token_hex(4), secrets.token_urlsafe(24)
            )
            set_admin(
                store,
                account["id"],
                True,
                operator="isolated-r16-gate",
                reason="disposable marker TLS gate",
            )
            character = store.create_character(
                account["id"],
                "Gate "
                + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)),
                breed=8,
            )
            fixture.append((account, character))
            peer = Peer()
            peers.append(peer)
            _login(store, peer, account, character, role)
        owner, joining, observer = peers
        owner_id, joining_id = fixture[0][1]["id"], fixture[1][1]["id"]
        for peer in peers:
            peer.discard_buffered()
        command = "!mob 4196 1 1"
        owner.send(12366, struct.pack(">H", len(command)) + command.encode())
        console, _ = owner.wait(674)
        import re

        group = re.search(r"grupo=(\d+)", _console_text(console))
        assert group is not None, "Own spawn did not return a group identity"
        actor_id = -int(group.group(1))
        while True:
            body, _ = owner.wait(12608, timeout=15)
            spawned = _spawned_actor(body)
            if spawned is not None and spawned[0] == actor_id:
                break
        owner.send(13130, struct.pack(">qiihB", actor_id, *spawned[2], 1))
        placement, _ = owner.wait(13652)
        fight_id, roster = _placement(placement)
        assert {owner_id, actor_id} <= set(roster)
        placement_marker = marker(observer, fight_id)
        public = assert_topology_carrier(placement_marker)
        # Enter read-only placement as the server's current native spectator.
        observer.send(13413, struct.pack(">i", fight_id))
        body, _ = observer.wait(12044)
        snapshot = decode_spectator_bootstrap(body)
        assert snapshot["fight_id"] == fight_id
        assert {entry["actor_id"] for entry in snapshot["participants"]} == {
            owner_id,
            actor_id,
        }
        observer.send(12154, struct.pack(">i", fight_id))
        observer.wait_any({12608, 12789, 13948, 13984}, timeout=10)
        joining.send(13241, struct.pack(">qB", owner_id, 0))
        joined, _ = joining.wait(13652)
        joined_id, roster = _placement(joined)
        assert joined_id == fight_id and {owner_id, joining_id, actor_id} <= set(roster)
        owner.send(12523, b"\x01")
        joining.send(12523, b"\x01")
        owner.wait(13482)
        joining.wait(13482)
        active_marker = marker(observer, fight_id)
        assert_topology_carrier(active_marker)
        observer.send(13413, struct.pack(">i", fight_id))
        body, _ = observer.wait(12044)
        active = decode_spectator_bootstrap(body)
        assert active["fight_id"] == fight_id
        assert {entry["actor_id"] for entry in active["participants"]} == {
            owner_id,
            joining_id,
            actor_id,
        }
        owner.send(13952)
        owner.wait(12238)
        owner.send(12925, struct.pack(">iB", fight_id, 1))
        owner.wait_any({12608, 12789, 13948, 13984}, timeout=15)
        with store.connection() as db:
            row = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
            ).fetchone()
            assert row["status"] in (
                "placement",
                "active",
            ), "Individual retreat aborted shared fight"
            receipt = db.execute(
                "SELECT returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                (fight_id, owner_id),
            ).fetchone()
            assert receipt is not None and receipt["returned_at"] is not None
        joining.send(13952)
        joining.wait(12238)
        joining.send(12925, struct.pack(">iB", fight_id, 1))
        joining.wait_any({12608, 12789, 13948, 13984}, timeout=15)
        # Active spectator receives its terminal continuation independently.
        observer.wait(12238)
        observer.send(12925, struct.pack(">iB", fight_id, 1))
        observer.wait_any({12608, 12789, 13948, 13984}, timeout=15)
        with store.connection() as db:
            assert (
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"]
                == "aborted"
            )
            assert (
                db.execute(
                    "SELECT COUNT(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["n"]
                == 0
            )
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "fixture_character_ids": [row[1]["id"] for row in fixture],
                    "fight_id": fight_id,
                    "placement_phase": placement_marker["phase_code"],
                    "active_phase": active_marker["phase_code"],
                    "public_origin": [public["x"], public["y"], public["min_z"]],
                    "joined": True,
                    "spectator_placement": True,
                    "spectator_active": True,
                    "individual_withdrawal": True,
                    "last_owner_aborted": True,
                }
            ),
            flush=True,
        )
    finally:
        for peer in peers:
            peer.close()


if __name__ == "__main__":
    main()
