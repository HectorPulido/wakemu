"""Check seven native lesson starts over TLS against the local World.

Creates one named QA account per exercise. Prerequisites are fixture
data; dialogue, encounter, readiness and surrender use the real server path.
Receipts remain private. This verifies initialization, not seven victories or
rendering in the graphical client.
"""

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import struct
import threading
import time

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from tools.candidate_friendly_duel_socket_smoke import Peer, frame, login, placement
from tools.tls_smoke_io import recv_exact, send_all
from wakfu_server.achievements import storage
from wakfu_server.store import Store

OBJECTIVES = (10574, 10575, 10576, 10608, 10609, 10610, 10611)
# Profiles, actual MP pools and temporary spells observed in the official run.
EXPECTED = (
    (None, None, None),
    (5519, 0, {7963, 7964, 7965, 7966}),
    (5520, 20, {7967}),
    (5521, 20, {7968}),
    (5522, 0, {7969, 7970, 7971}),
    (5524, 0, {7972, 7973, 7974, 7975}),
    (5520, 20, {7967}),
)


class LocalPeer(Peer):
    """Serialize access to the shared OpenSSL object during burst delivery."""

    def __init__(self):
        self.io_lock = threading.Lock()
        super().__init__()
        self.socket.settimeout(0.1)

    def _exact(self, size):
        return recv_exact(self.socket, size, closed=self.closed, io_lock=self.io_lock)

    def send(self, opcode, body=b""):
        self.sent.append(opcode)
        send_all(self.socket, frame(opcode, body), io_lock=self.io_lock)


def main():
    dsn = os.environ["WAKFU_DATABASE_URL"]
    if conninfo_to_dict(dsn).get("host") not in ("127.0.0.1", "localhost"):
        raise ValueError("This gameplay probe is local only")
    store = Store(dsn, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    suffix = secrets.token_hex(4)
    name_suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8))
    receipt = {"lessons": []}

    def checkpoint(fight_id):
        with store.connection() as db:
            row = db.execute(
                "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()
        return row["snapshot"] if row else None

    try:
        start_index = int(os.environ.get("WAKFU_RII_PARITY_START", "0"))
        if not 0 <= start_index < len(OBJECTIVES):
            raise ValueError("Invalid first lesson index")
        for index in range(start_index, len(OBJECTIVES)):
            objective = OBJECTIVES[index]
            account = store.register(
                "rii_parity_" + suffix + "_" + str(index), secrets.token_urlsafe(24)
            )
            char = store.create_character(
                account["id"], "Rii QA " + name_suffix + " " + chr(65 + index), breed=8
            )
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=1388,instance_id=0,x=0,y=-18,z=0 WHERE id=%s",
                    (char["id"],),
                )
                state = storage.load_locked(db, char["id"])
                state.update(
                    running=[5143, 5160],
                    tracking=[5143, 5160],
                    objectives=[10606, 10614, *OBJECTIVES[:index]],
                    completed=[5154],
                )
                storage.store(db, char["id"], state)
                db.execute(
                    "INSERT INTO character_achievement_authority"
                    "(character_id,snapshot,revision,provenance) VALUES (%s,%s,1,'rii-parity-probe') "
                    "ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,"
                    "revision=character_achievement_authority.revision+1",
                    (
                        char["id"],
                        Jsonb(
                            {
                                k: state[k]
                                for k in ("running", "completed", "objectives")
                            }
                        ),
                    ),
                )
            peer = LocalPeer()
            fight_id = None
            abandoned = False
            try:
                login(store, peer, account, char, "rii-parity")
                peer.send(13222, struct.pack(">qq", -1706442046308339, 1389))
                body, _ = peer.wait(12969, timeout=12)
                assert struct.unpack_from(">i", body)[0] == 5787
                peer.send(12058, struct.pack(">ii", 5787, 13322 + index))
                body, _ = peer.wait(13652, timeout=15)
                fight_id, actors = placement(body)
                peer.send(12523, b"\x01")
                _, packets = peer.wait(13482, timeout=15)
                # The active recovery checkpoint intentionally projects only
                # recovery fields. Surrender publishes a complete terminal
                # snapshot, including the retained morph and area records.
                peer.send(13952)
                peer.wait(12238, timeout=12)
                abandoned = True
                profile, mp, spells = EXPECTED[index]
                until = time.monotonic() + 10
                snap = checkpoint(fight_id)

                def initialized(value):
                    return bool(
                        value
                        and value["phase"] == "finished"
                        and (
                            profile is None
                            or str(char["id"])
                            in value.get("native_morph_spellbooks", {})
                        )
                    )

                while not initialized(snap) and time.monotonic() < until:
                    time.sleep(0.1)
                    snap = checkpoint(fight_id)
                assert snap and snap["phase"] == "finished", snap
                hero = snap["actors"][str(char["id"])]
                morph = snap.get("native_morph_spellbooks", {}).get(str(char["id"]))
                if profile is None:
                    assert morph is None, morph
                else:
                    assert morph and morph["profile_id"] == profile, morph
                    assert set(map(int, morph["levels"])) == spells, morph
                    assert (hero["ap"], hero["mp"]) == (6, mp), (hero["ap"], hero["mp"])
                area_references = sorted(
                    {
                        area["reference"]
                        for area in snap.get("native_effect_areas", {}).values()
                    }
                )
                required_areas = {
                    2: {1102, 1103},
                    3: {1808},
                    5: {1807},
                    6: {1102, 1103},
                }
                assert required_areas.get(index, set()) <= set(
                    area_references
                ), area_references
                if index == 4:
                    assert any(
                        1799 <= ref <= 1806 for ref in area_references
                    ), area_references
                row = {
                    "objective": objective,
                    "character_id": char["id"],
                    "account_id": account["id"],
                    "fight_id": fight_id,
                    "profile": profile,
                    "ap": hero["ap"],
                    "mp": hero["mp"],
                    "spells": sorted(spells) if spells else None,
                    "actors": actors,
                    "initial_packet_opcodes": [op for op, _ in packets],
                    "native_area_count": len(snap.get("native_effect_areas", {})),
                    "native_area_references": area_references,
                }
                receipt["lessons"].append(row)
                print(json.dumps(row), flush=True)
            finally:
                if fight_id is not None and not abandoned:
                    peer.send(13952)
                    # Abandonment returns directly through cvF, without the
                    # victory/defeat rewards report (12755).
                    peer.wait(12238, timeout=12)
                peer.close()
    finally:
        default_output = (
            ".local-state/wakemu/qa/rii-lesson-parity-"
            + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            + ".json"
        )
        output = Path(os.environ.get("WAKFU_RII_PARITY_RECEIPT", default_output))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2) + "\n")
        store.close()


if __name__ == "__main__":
    main()
