#!/usr/bin/env python3
"""Minimal local TBinaryProtocol launcher bridge; never reads real credentials."""
import os
import sys
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import threading
import json
import urllib.request

from portable_config import settings, package_root, pin_dns

pin_dns(settings())
ROOT = package_root()
from local_launcher_auth import LauncherAuthentication

AUTH = LauncherAuthentication(
    os.environ["WAKFU_GAME_LOGIN_FILE"], api_url=settings()["api_url"]
)
HASH = secrets.token_hex(24)
SESSION = secrets.token_hex(24)


def receive(connection, count):
    data = bytearray()
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise EOFError()
        data.extend(chunk)
    return bytes(data)


def string(value):
    data = value.encode()
    return struct.pack(">i", len(data)) + data


def read_string(connection):
    length = struct.unpack(">i", receive(connection, 4))[0]
    if not 0 <= length <= 65536:
        raise ValueError("Invalid string size")
    return receive(connection, length).decode()


def serve(connection):
    try:
        with connection:
            while True:
                version = struct.unpack(">I", receive(connection, 4))[0]
                if version != 0x80010001:
                    raise ValueError("Expected versioned Thrift call")
                method = read_string(connection)
                sequence = receive(connection, 4)
                arguments = {}
                while True:
                    kind = receive(connection, 1)[0]
                    if kind == 0:
                        break
                    field = struct.unpack(">h", receive(connection, 2))[0]
                    if kind == 11:
                        arguments[field] = read_string(connection)
                    elif kind == 8:
                        arguments[field] = struct.unpack(">i", receive(connection, 4))[
                            0
                        ]
                    elif kind == 2:
                        arguments[field] = bool(receive(connection, 1)[0])
                    else:
                        raise ValueError("Unsupported argument type")
                try:
                    if method == "connect":
                        if arguments.get(1) != "wakfu" or arguments.get(4) != HASH:
                            raise ValueError("Invalid local bridge credentials")
                        result = SESSION
                        status_path = os.environ.get("WAKFU_LAUNCH_STATUS_FILE")
                        if status_path:
                            from launcher_backend import private_write

                            private_write(
                                Path(status_path),
                                {"status": "ready", "bridge_pid": os.getpid()},
                            )
                    else:
                        if arguments.get(1) != SESSION:
                            raise ValueError("Invalid local bridge session")
                        if method in {
                            "auth_getGameToken",
                            "auth_getGameTokenWithWindowId",
                        }:
                            if arguments.get(2) != 3:
                                raise ValueError("Unsupported game")
                            result = AUTH.game_token()
                        elif method in {
                            "updater_isUpdateAvailable",
                            "zaapMustUpdate_get",
                        }:
                            result = False
                        elif method == "zaapVersion_get":
                            result = "wakfu-local-python"
                        elif method == "userInfo_get":
                            result = AUTH.user_info()
                        else:
                            raise ValueError("Unsupported local RPC")
                    body = (
                        b"\x02\x00\x00" + bytes([result])
                        if isinstance(result, bool)
                        else b"\x0b\x00\x00" + string(result)
                    ) + b"\x00"
                    reply_type = 0x80010002
                except ValueError as error:
                    body = (
                        b"\x0b\x00\x01"
                        + string(str(error))
                        + b"\x08\x00\x02"
                        + struct.pack(">i", 6)
                        + b"\x00"
                    )
                    reply_type = 0x80010003
                connection.sendall(
                    struct.pack(">I", reply_type) + string(method) + sequence + body
                )
                print("Local launcher RPC:", method, flush=True)
    except (EOFError, OSError, ValueError):
        pass


def accept(listener):
    while True:
        try:
            connection, _ = listener.accept()
        except OSError:
            return
        threading.Thread(target=serve, args=(connection,), daemon=True).start()


def main():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        port = listener.getsockname()[1]
        threading.Thread(target=accept, args=(listener,), daemon=True).start()
        environment = dict(
            os.environ,
            ZAAP_PORT=str(port),
            ZAAP_HASH=HASH,
            ZAAP_GAME="wakfu",
            ZAAP_RELEASE="main",
            ZAAP_INSTANCE_ID="1",
        )
        print(
            f"Python launcher bridge on 127.0.0.1:{port}; fictitious token only.",
            flush=True,
        )
        return subprocess.call(
            [
                sys.executable,
                "-B",
                str(ROOT / "run-client.py"),
                "--use-local-auth",
                "--profile",
                os.environ.get("WAKFU_LOCAL_PROFILE", "main"),
            ],
            env=environment,
        )


if __name__ == "__main__":
    raise SystemExit(main())
