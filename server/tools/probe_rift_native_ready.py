"""Opt-in LIVE TLS probe using newly registered QA owners only.

Run after the complete release is active. This is not a clean-install verifier:
it neither invokes nor bypasses its empty-install guard. The only setup writes
are normal Store operations on characters created by this process: one native
key and a verified public portal approach. No level/HP/admin changes are made.
"""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import secrets
import select
import struct
import time

from tools import verify_clean_install as access
from protocol_codec import DIRECTIONS
from wakfu_server.store import Store
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.achievements import rewards
from wakfu_server.rift_key_admission import contract


def wait_for(operation, *, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = operation()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("Expected durable native transition did not complete")


def selected(login, character):
    ticket, _ = access.dispatcher_ticket(login["game_token"])
    peer = access.Peer(access.ACCESS["world_port"])
    try:
        peer.send(426, access.text(ticket) + access.text("rift-native-qa"))
        peer.until(13873)
        peer.send(
            23664, struct.pack(">q", character["id"]) + access.text(character["name"])
        )
        peer.until(630)
        peer.until(711)
        # Existing clean-install cached-join/loaded-scene roundtrip.
        peer.send(12449)
        peer.until(12436)
        peer.until(711)
        peer.send(12449)
        peer.until(711)
        return peer
    except BaseException:
        peer.close()
        raise


def nearby(geometry, source):
    candidates = [
        cell
        for cell in geometry.cells
        if max(abs(cell[0] - source["x"]), abs(cell[1] - source["y"])) <= 3
        and abs(cell[2] - source["z"]) <= 2
    ]
    if not candidates:
        raise ValueError("Native source has no certified approach floor")
    return sorted(
        candidates,
        key=lambda c: (
            abs(c[0] - source["x"]) + abs(c[1] - source["y"]),
            abs(c[2] - source["z"]),
            c,
        ),
    )


def path_to(geometry, start, goals):
    queue, previous = deque([start]), {start: None}
    while queue:
        current = queue.popleft()
        if current in goals:
            path = []
            while previous[current] is not None:
                path.append(current)
                current = previous[current]
            return list(reversed(path))
        for cell in geometry.outgoing.get(current, ()):
            if cell not in previous:
                previous[cell] = current
                queue.append(cell)
    raise ValueError("No native walking route reaches the activator")


def walk(peer, geometry, start, source):
    path = path_to(geometry, start, set(nearby(geometry, source)))
    if len(path) > 255:
        raise ValueError("Native route exceeds one byte path length")
    directions = {(x, y): key for key, (_, x, y) in DIRECTIONS.items()}
    steps, current = bytearray(), start
    for cell in path:
        dz = cell[2] - current[2]
        if not -16 <= dz <= 15:
            raise ValueError("Native walking altitude delta is not encodable")
        steps.append(
            (directions[(cell[0] - current[0], cell[1] - current[1])] << 5) | (dz & 31)
        )
        current = cell
    if steps:
        peer.send(13331, struct.pack(">iiihB", 0, *start, len(steps)) + steps)
    return current


def reconnect_snapshot(peer, current, *, timeout=40):
    """Observe actual restore; a legitimate terminal fight is not a flow error."""
    observed = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (
            not peer.connection.pending()
            and not select.select([peer.connection], [], [], 0.2)[0]
        ):
            if current()["fight_status"] in ("finished", "aborted"):
                return False, observed
            continue
        length = struct.unpack(">I", peer.exact(4))[0]
        assert 6 <= length <= 327670
        payload = peer.exact(length - 4)
        opcode = struct.unpack_from(">H", payload)[0]
        observed.append(opcode)
        if opcode == 12053:
            assert (
                12847 in observed
            ), "Reconnect did not publish its participant bootstrap"
            return True, observed
    return False, observed


def run_one(store, wave):
    # Validate source and terrain BEFORE creating any QA identity.
    with store.connection() as db:
        catalog = db.execute(
            "SELECT value FROM settings WHERE name='rift_catalog'"
        ).fetchone()["value"][str(wave)]
    price = contract(catalog)
    if price is None:
        raise ValueError("This probe requires a native ultimate key contract")
    portal = catalog["entrances"][0]
    outside = published_geometry(portal["map_id"])
    approach = nearby(outside, portal)[0]
    inside = published_geometry(catalog["map_id"])
    activator = next(
        row for row in catalog["objects"] if row["id"] == price["object_id"]
    )
    nearby(inside, activator)
    username, password = "riftqa_" + secrets.token_hex(6), secrets.token_urlsafe(24)
    account = access.post("/register", dict(username=username, password=password))
    login = access.post("/login", dict(username=username, password=password))
    assert login["account"]["id"] == account["id"]
    character = access.post(
        "/characters",
        {
            "name": "Riftqa"
            + "".join(secrets.choice("abcdefghijklmnop") for _ in range(9)),
            "breed": 8,
        },
        login["api_token"],
    )
    print(
        json.dumps(
            {
                "event": "new_qa_created",
                "wave": wave,
                "account_id": account["id"],
                "character_id": character["id"],
            }
        ),
        flush=True,
    )
    generation = store.begin_session(account["id"])
    store.select_character(account["id"], generation, character["id"])
    with store.connection() as db:
        before = store.character(account["id"], character["id"], db)
        assert before["level"] == 1 and before["account_id"] == account["id"]
        assert (
            db.execute(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=%s",
                (character["id"], price["reference"]),
            ).fetchone()["n"]
            == 0
        )
        store.transition_map_in_transaction(
            db,
            account["id"],
            generation,
            character["id"],
            before,
            dict(
                map_id=portal["map_id"],
                instance_id=0,
                x=approach[0],
                y=approach[1],
                z=approach[2],
            ),
        )
        rewards.grant(db, store, before, {"aeV": 5, "ckl": [price["reference"], 1]})
    # Setup lease is replaced by the genuine HTTP/dispatcher/World login.
    login = access.post("/login", dict(username=username, password=password))
    peer = selected(login, character)
    try:
        peer.send(12870, struct.pack(">qHH", portal["object_id"], 11, 0))
        bootstrap = peer.until(13974)
        size = struct.unpack_from(">H", bootstrap)[0]
        fields = struct.unpack(">BqBqiihqBBiihq", bootstrap[2 : 2 + size])
        assert fields[1] == character["id"] and fields[7] == catalog["map_id"]
        arrival = tuple(fields[4:7])
        assert arrival in inside.cells
        peer.send(14689)
        destination = walk(peer, inside, arrival, activator)

        def reached():
            actor = store.character(account["id"], character["id"])
            return tuple(actor[key] for key in ("x", "y", "z")) == destination

        # Wait for the production position journal to persist the real path;
        # authorize_start reads the durable actor, never a probe DB position.
        wait_for(reached)
        peer.send(12870, struct.pack(">qHH", price["object_id"], price["action"], 0))
        peer.until(12847)
        peer.send(12523, b"\x01")
        peer.until(12053)

        def current():
            with store.connection() as db:
                return db.execute(
                    "SELECT r.instance_id,r.fight_id,r.wave,r.status,f.status AS fight_status "
                    "FROM rift_instances r JOIN combat_fights f ON f.id=r.fight_id "
                    "WHERE r.owner_character_id=%s",
                    (character["id"],),
                ).fetchone()

        outcome = wait_for(current)
        with store.connection() as db:
            roster = db.execute(
                "SELECT actor_ids,species_refs FROM rift_wave_rosters WHERE instance_id=%s AND wave=%s",
                (outcome["instance_id"], outcome["wave"]),
            ).fetchone()
        assert roster is not None and len(roster["actor_ids"]) == 2
        assert len(roster["species_refs"]) == 2
        assert set(roster["species_refs"]) <= set(catalog["species_refs"])
    finally:
        peer.close()
    reconnect, observed, cleanup = False, [], "not_requested_terminal_fight"
    terminal_before_reconnect = current()["fight_status"] in ("finished", "aborted")
    login = access.post("/login", dict(username=username, password=password))
    # Combat reconnect has its own native bootstrap, not the world cached-join
    # toggle flow. Reuse the same genuine account and character, without setup.
    ticket, _ = access.dispatcher_ticket(login["game_token"])
    peer = access.Peer(access.ACCESS["world_port"])
    try:
        peer.send(426, access.text(ticket) + access.text("rift-native-qa-reconnect"))
        peer.until(13873)
        peer.send(
            23664, struct.pack(">q", character["id"]) + access.text(character["name"])
        )
        reconnect, observed = reconnect_snapshot(peer, current)
        terminal_during_reconnect = current()["fight_status"] in ("finished", "aborted")
        assert current()["fight_id"] == outcome["fight_id"]
        if current()["fight_status"] == "active":
            # Original cpf13952 and cvF12238 ->12925 continuation. This closes
            # only this newly created sole-owner QA fight through production.
            try:
                peer.send(13952)
                peer.until(12238)
                peer.send(12925, struct.pack(">iB", outcome["fight_id"], 0))
                peer.until(13974)
                cleanup = "native_forfeit_and_return"
            except (TimeoutError, AssertionError):
                cleanup = "NOT_VERIFIED_after_native_forfeit_request"
    finally:
        peer.close()
    with store.connection() as db:
        keys = db.execute(
            "SELECT coalesce(sum(quantity),0) AS n FROM inventory_items WHERE character_id=%s AND reference=%s",
            (character["id"], price["reference"]),
        ).fetchone()["n"]
    assert keys == 0, "The single newly provisioned key was not consumed exactly once"
    after = store.character(account["id"], character["id"])
    return dict(
        status="PASS"
        if reconnect and not cleanup.startswith("NOT_VERIFIED")
        else "PARTIAL",
        entry_ready_status="PASS",
        reconnect_status="PASS" if reconnect else "NOT_VERIFIED",
        reconnect_not_verified_reason=None
        if reconnect
        else (
            "terminal_fight_observed"
            if terminal_during_reconnect
            else "native_restore_not_observed_within_deadline"
        ),
        terminal_before_reconnect=terminal_before_reconnect,
        terminal_during_reconnect=terminal_during_reconnect,
        reconnect_packets=observed,
        final_fight=dict(current()),
        cleanup=cleanup,
        final_health={
            key: after[key] for key in ("level", "hp", "max_hp", "health_dead")
        },
        wave=wave,
        account_id=account["id"],
        character_id=character["id"],
        fight=dict(outcome),
        pool_references=catalog["species_refs"],
        key_reference=price["reference"],
        first_wave=dict(roster),
        key_remaining=keys,
        native_entry=True,
        native_ready=True,
        native_reconnect=reconnect,
        limit="Entry/Ready/reconnect only; no wave victory, all-class or 29-species AI claim",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-url", required=True)
    parser.add_argument("--world-host", default="127.0.0.1")
    parser.add_argument(
        "--dispatcher-port",
        type=int,
        default=15558,
        help="Native dispatcher TCP port (Compose default: 15558)",
    )
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--wave", type=int, choices=(5, 8, 37), action="append")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--execute-new-qa",
        action="store_true",
        help="Explicitly register new QA owners and run after release",
    )
    args = parser.parse_args()
    if not args.execute_new_qa:
        parser.error(
            "No actions performed: pass --execute-new-qa only after release authorization"
        )
    access.ACCESS.update(
        http_url=args.http_url.rstrip("/"),
        world_host=args.world_host,
        dispatcher_port=args.dispatcher_port,
        world_port=args.world_port,
    )
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    results = []
    try:
        for wave in args.wave or [5]:
            results.append(run_one(store, wave))
            args.receipt.write_text(json.dumps({"results": results}, indent=2) + "\n")
    except BaseException as error:
        args.receipt.write_text(
            json.dumps(
                {
                    "status": "FAIL",
                    "failed_wave": wave,
                    "error_type": type(error).__name__,
                    "results": results,
                },
                indent=2,
            )
            + "\n"
        )
        raise
    finally:
        store.close()


if __name__ == "__main__":
    main()
