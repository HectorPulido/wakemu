"""TLS acceptance harness for terminal PvE recovery without native12925.

Run inside a disposable candidate world after migrations. The script never
starts/stops a world and rejects every database except a wakemu_candidate_smoke_*
database. ``--phase prepare`` commits a fresh victory and writes an ID-only
manifest; restart the disposable candidate server yourself, then run
``--phase recover`` with the same database and manifest to exercise the
process-restart recovery path. No password, ticket, or packet body is persisted.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.command_permissions import set_admin
from wakfu_server.monsters import reference as monster_reference
from wakfu_server.store import Store

from candidate_combat_socket_reward_smoke import (
    Peer,
    _placement_positions,
    _report,
    _spawned_actor,
    _text,
)


MANIFEST_VERSION = 1
FIGHT_REFERENCE = 4196
RECONNECT_FORBIDDEN_OPCODES = {12238, 12755}


def _candidate_database(url):
    database = conninfo_to_dict(url).get("dbname", "")
    if database in {"wakemu", "wakemu_runtime"} or not database.startswith(
        "wakemu_candidate_smoke_"
    ):
        raise ValueError(
            "Terminal recovery smoke requires a disposable candidate database"
        )
    return database


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
    return body[start:].decode("utf-8")


def _command(peer, text):
    peer.send(12366, struct.pack(">H", len(text)) + text.encode("utf-8"))
    deadline = time.monotonic() + 30
    last_text = ""
    while time.monotonic() < deadline:
        body, _seen = peer.until(674, timeout=max(0.1, deadline - time.monotonic()))
        last_text = _command_text(body)
        if last_text:
            return last_text
    raise AssertionError(f"Console command did not return a message: {text!r}")


def _login(store, account_id, character_id, character_name, label):
    generation = store.begin_session(account_id)
    ticket = store.issue_token(account_id, "ticket", generation=generation, realm_id=10)
    peer = Peer()
    peer.send(426, _text(ticket) + _text(label))
    peer.until(13873)
    peer.send(23664, struct.pack(">q", character_id) + _text(character_name))
    peer.until(630)
    peer.until(711)
    return peer, generation


def _new_monster(peer, *, expected_id=None):
    command = f"!mob {FIGHT_REFERENCE} 1 1"
    before = len(peer.received)
    response = _command(peer, command)
    if "grupo=" not in response:
        raise AssertionError("!mob did not report creation of a new test group")
    group_match = re.search(r"grupo=(\d+)", response)
    if group_match is None:
        raise AssertionError("!mob group receipt had an unexpected format")
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        new_packets = peer.received[before:]
        for opcode, body in new_packets:
            if opcode != 12608:
                continue
            try:
                actor = _spawned_actor(body)
            except AssertionError:
                continue
            if actor["reference"] != FIGHT_REFERENCE:
                continue
            if expected_id is not None and actor["id"] == expected_id:
                continue
            return actor, int(group_match.group(1))
        peer.until(12608, timeout=max(0.1, deadline - time.monotonic()))
    raise AssertionError("!mob returned no new singleton native spawn")


def _setup_terminal_fight(store):
    account = store.register(
        "terminal_recovery_" + secrets.token_hex(5), secrets.token_urlsafe(24)
    )
    account_id = account["id"]
    set_admin(
        store,
        account_id,
        True,
        operator="isolated-terminal-recovery-smoke",
        reason="candidate-only terminal recovery acceptance",
    )
    name = "Recovery " + "".join(
        secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)
    )
    character = store.create_character(account_id, name, breed=8)
    character_id = character["id"]
    peer, _generation = _login(
        store, account_id, character_id, name, "candidate-terminal-recovery-prepare"
    )
    monster_reference(FIGHT_REFERENCE)
    monster, _group = _new_monster(peer)
    x, y, z = monster["position"]
    peer.send(13130, struct.pack(">qiihB", monster["id"], x, y, z, 1))
    _, _, placement_packets = peer.until(13026)
    positions = next(body for opcode, body in placement_packets if opcode == 13652)
    fight_id, actors = _placement_positions(positions)
    if character_id not in actors or monster["id"] not in actors:
        raise AssertionError("Fight placement omitted the candidate player or test mob")
    peer.send(12523, b"\x01")
    _, _, start_packets = peer.until(13482)
    current_actor = next(
        struct.unpack_from(">q", body, 4)[0]
        for opcode, body in reversed(start_packets)
        if opcode == 12873 and len(body) >= 12
    )
    if current_actor == monster["id"]:
        peer.until(12502)
        peer.send(13510, struct.pack(">i", 1))
        _, _, player_packets = peer.until(13482)
        current_actor = next(
            struct.unpack_from(">q", body, 4)[0]
            for opcode, body in reversed(player_packets)
            if opcode == 12873 and len(body) >= 12
        )
    if current_actor != character_id:
        raise AssertionError("Native smoke did not reach the controlled player turn")
    target = actors[monster["id"]]
    peer.send(12889, struct.pack(">qqbiih", character_id, -1, 15, *target))
    _, report_body, _ = peer.until(12755)
    report = _report(fight_id, report_body)
    if report["character_id"] != character_id:
        raise AssertionError("Victory report belongs to another character")
    return peer, dict(
        version=MANIFEST_VERSION,
        database=None,
        account_id=account_id,
        character_id=character_id,
        character_name=name,
        fight_id=fight_id,
        monster_id=monster["id"],
        report_xp=report["won_xp"],
        report_kamas=report["kamas"],
    )


def _reward_snapshot(store, manifest):
    with store.connection() as db:
        fight = db.execute(
            "SELECT status,fight_kind FROM combat_fights WHERE id=%s",
            (manifest["fight_id"],),
        ).fetchone()
        rewards = db.execute(
            "SELECT count(*) AS n,coalesce(sum(xp),0) AS xp,"
            "coalesce(sum(kamas),0) AS kamas FROM fight_rewards "
            "WHERE fight_id=%s AND character_id=%s",
            (manifest["fight_id"], manifest["character_id"]),
        ).fetchone()
        drops = db.execute(
            "SELECT (SELECT count(*) FROM fight_drop_awards WHERE fight_id=%s AND character_id=%s) "
            "AS awards,(SELECT count(*) FROM fight_drop_delivery_receipts "
            "WHERE fight_id=%s AND character_id=%s) AS deliveries",
            (
                manifest["fight_id"],
                manifest["character_id"],
                manifest["fight_id"],
                manifest["character_id"],
            ),
        ).fetchone()
        exits = db.execute(
            "SELECT count(*) AS n FROM fight_health_exits "
            "WHERE fight_id=%s AND character_id=%s AND reason='return'",
            (manifest["fight_id"], manifest["character_id"]),
        ).fetchone()["n"]
    if fight is None or (fight["status"], fight["fight_kind"]) != ("finished", "pve"):
        raise AssertionError("The candidate PvE fight is not durably finished")
    if rewards["n"] > 1:
        raise AssertionError("The victory has duplicate durable reward receipts")
    return dict(
        rewards=dict(n=rewards["n"], xp=rewards["xp"], kamas=rewards["kamas"]),
        drops=dict(awards=drops["awards"], deliveries=drops["deliveries"]),
        return_exits=exits,
    )


def _write_manifest(path, manifest):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    temporary.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _read_manifest(path, database):
    manifest = json.loads(Path(path).read_text(encoding="utf8"))
    required = {
        "version",
        "database",
        "account_id",
        "character_id",
        "character_name",
        "fight_id",
        "monster_id",
        "report_xp",
        "report_kamas",
        "prepare_reward_snapshot",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("Invalid terminal recovery manifest shape")
    if manifest["version"] != MANIFEST_VERSION or manifest["database"] != database:
        raise ValueError("Manifest belongs to another candidate database/version")
    for key in ("account_id", "character_id", "fight_id", "monster_id"):
        if type(manifest[key]) is not int or manifest[key] <= 0:
            raise ValueError(f"Invalid manifest {key}")
    if (
        not isinstance(manifest["character_name"], str)
        or not manifest["character_name"]
    ):
        raise ValueError("Invalid manifest character name")
    return manifest


def _recover(store, manifest):
    peer, _generation = _login(
        store,
        manifest["account_id"],
        manifest["character_id"],
        manifest["character_name"],
        "candidate-terminal-recovery-reconnect",
    )
    try:
        # A harmless world command is a protocol barrier after login recovery.
        position_reply = _command(peer, "!pos")
        if "Termina el combate" in position_reply:
            raise AssertionError("Fresh client retained the prior fight session")
        bad = [
            opcode
            for opcode, _body in peer.received
            if opcode in RECONNECT_FORBIDDEN_OPCODES
        ]
        if bad:
            raise AssertionError(
                f"Fresh world login replayed fight terminal packets: {bad}"
            )

        after = _reward_snapshot(store, manifest)
        expected_rewards = {
            "n": 1,
            "xp": manifest["report_xp"],
            "kamas": manifest["report_kamas"],
        }
        if after["rewards"] != expected_rewards:
            raise AssertionError("PvE rewards changed or duplicated during recovery")
        if after["return_exits"] != 1:
            raise AssertionError(
                "Recovery did not persist exactly one return-health exit"
            )

        monster, group_id = _new_monster(peer, expected_id=manifest["monster_id"])
        if monster["id"] == manifest["monster_id"]:
            raise AssertionError("New !mob reused the finished fight actor")
        return dict(
            recovered_character_id=manifest["character_id"],
            fight_id=manifest["fight_id"],
            replayed_terminal_packets=0,
            reward_receipts=after["rewards"]["n"],
            return_exit_receipts=after["return_exits"],
            new_mob_reference=monster["reference"],
            new_mob_id=monster["id"],
            new_group_id=group_id,
        )
    finally:
        peer.socket.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("full", "prepare", "recover"), default="full"
    )
    parser.add_argument(
        "--manifest",
        default=os.environ.get(
            "WAKEMU_TERMINAL_RECOVERY_MANIFEST",
            "/tmp/wakemu-terminal-recovery-manifest.json",
        ),
    )
    args = parser.parse_args()
    database_url = os.environ["WAKFU_DATABASE_URL"]
    database = _candidate_database(database_url)
    store = Store(
        database_url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"]
    )
    peer = None
    try:
        if args.phase in ("full", "prepare"):
            peer, manifest = _setup_terminal_fight(store)
            peer.socket.close()  # Deliberately no native 12925 return request.
            peer = None
            manifest["database"] = database
            manifest["prepare_reward_snapshot"] = _reward_snapshot(store, manifest)
            if manifest["prepare_reward_snapshot"]["rewards"]["n"] != 1:
                raise AssertionError(
                    "Victory did not commit exactly one reward receipt"
                )
            _write_manifest(args.manifest, manifest)
            print(
                {
                    "phase": "prepared",
                    "fight_id": manifest["fight_id"],
                    "account_id": manifest["account_id"],
                    "character_id": manifest["character_id"],
                    "manifest": args.manifest,
                    "native_12925_sent": False,
                },
                flush=True,
            )
            if args.phase == "prepare":
                return
        manifest = _read_manifest(args.manifest, database)
        result = _recover(store, manifest)
        final_rewards = _reward_snapshot(store, manifest)
        prepared = manifest["prepare_reward_snapshot"]
        if (
            final_rewards["rewards"] != prepared["rewards"]
            or final_rewards["drops"] != prepared["drops"]
        ):
            raise AssertionError(
                "Durable fight rewards/return receipts changed on recovery"
            )
        print({"phase": "recovered", **result}, flush=True)
    finally:
        if peer is not None:
            peer.socket.close()
        store.close()


if __name__ == "__main__":
    main()
