"""Exercise a real TLS world bootstrap against a disposable candidate database.

Run inside the candidate container. Never run against the live game database.
Only a sanitized PASS summary is printed; generated credentials remain private.
"""
import os
import secrets
import socket
import ssl
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.social_wire import decode_friend_lists
from wakfu_server.store import Store


def main():
    database_url = os.environ["WAKFU_DATABASE_URL"]
    if (
        not conninfo_to_dict(database_url)
        .get("dbname", "")
        .startswith("wakemu_candidate_smoke_")
    ):
        raise ValueError("This smoke requires a dedicated candidate database")
    store = Store(
        database_url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"]
    )
    peer = None
    try:
        account = store.register(
            "smoke_" + secrets.token_hex(4), secrets.token_urlsafe(24)
        )
        name = "Smoke " + "".join(secrets.choice("abcdefghijklmnop") for _ in range(8))
        character = store.create_character(account["id"], name, breed=8)
        generation = store.begin_session(account["id"])
        ticket = store.issue_token(
            account["id"], "ticket", generation=generation, realm_id=10
        )
        # The disposable server has a self-signed localhost certificate.
        peer = ssl._create_unverified_context().wrap_socket(
            socket.create_connection(("127.0.0.1", 15556), timeout=5),
            server_hostname="localhost",
        )
        peer.settimeout(15)

        def text(value):
            encoded = value.encode("utf-8")
            return struct.pack(">I", len(encoded)) + encoded

        def send(opcode, body=b""):
            peer.sendall(struct.pack(">IBH", 7 + len(body), 3, opcode) + body)

        def exact(length):
            result = bytearray()
            while len(result) < length:
                chunk = peer.recv(length - len(result))
                if not chunk:
                    raise AssertionError("World disconnected during bootstrap")
                result.extend(chunk)
            return bytes(result)

        def until(opcode):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                length = struct.unpack(">I", exact(4))[0]
                if not 6 <= length <= 327670:
                    raise AssertionError("Invalid server frame size")
                frame = exact(length - 4)
                if struct.unpack(">H", frame[:2])[0] == opcode:
                    return frame[2:]
            raise AssertionError("Expected bootstrap packet missing")

        send(426, text(ticket) + text("isolated-candidate-smoke"))
        until(13873)
        send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
        assert decode_friend_lists(until(630)) == {"friends": [], "ignored": []}
        # A cached client can omit14689. The first social action must also join
        # the world before dispatch, rather than being silently discarded.
        until(711)
        send(12449)
        until(12436)
        assert until(711) == b"\x01"
        send(12449)
        assert until(711) == b"\x00"
        print(
            "PASS: TLS ticket, character selection, contacts630, cached-map world join, DND toggles"
        )
    finally:
        if peer is not None:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
