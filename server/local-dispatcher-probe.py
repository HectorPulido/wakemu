#!/usr/bin/env python3
"""TLS protocol probe. Stops at auth; not a working game server."""
import base64
import json
from pathlib import Path
import socket
import ssl
import struct
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent
runtime = root / ".runtime/local"
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(runtime / "server.crt", runtime / "server.key")
key = (runtime / "public-key.der").read_bytes()
log = (runtime / "logs/dispatcher.jsonl").open("a", buffering=1)


def record(**fields):
    log.write(
        json.dumps({"time": datetime.now(timezone.utc).isoformat(), **fields}) + "\n"
    )


def receive(connection, count):
    data = bytearray()
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise EOFError()
        data.extend(chunk)
    return bytes(data)


def send(connection, opcode, body):
    connection.sendall(struct.pack(">IH", 6 + len(body), opcode) + body)
    record(
        direction="server_to_client",
        opcode=opcode,
        body_base64=base64.b64encode(body).decode(),
    )


with socket.socket() as listener:
    listener.bind(("127.0.0.1", 15558))
    listener.listen(4)
    record(event="listening", address="127.0.0.1:15558")
    print("Local TLS dispatcher listening on 127.0.0.1:15558", flush=True)
    while True:
        connection, peer = listener.accept()
        try:
            with context.wrap_socket(connection, server_side=True) as tls:
                record(event="tls_connected", peer=peer, tls=tls.version())
                while True:
                    length = struct.unpack(">I", receive(tls, 4))[0]
                    if not 7 <= length <= 327670:
                        raise ValueError("Invalid frame length")
                    data = receive(tls, length - 4)
                    route, opcode = struct.unpack(">BH", data[:3])
                    record(
                        direction="client_to_server",
                        route=route,
                        opcode=opcode,
                        body_base64=base64.b64encode(data[3:]).decode(),
                    )
                    if opcode == 33:
                        send(tls, 23, b"\x01")
                        send(tls, 309, struct.pack(">I", 12345))
                    elif opcode == 574:
                        send(tls, 400, struct.pack(">q", 123456789) + key)
                    elif opcode == 584:
                        record(
                            event="fake_token_auth_received",
                            note="Probe stops here; no account/world implementation",
                        )
        except (EOFError, OSError, ValueError) as error:
            record(event="disconnected", error=type(error).__name__)
