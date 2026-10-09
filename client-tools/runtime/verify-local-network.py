#!/usr/bin/env python3
"""Fail closed before client launch, verifying both network barriers."""
import os
from pathlib import Path
import socket
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
profile = root / "client-tools/runtime/local-network.sb"
listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(2)
listener.settimeout(5)
port = listener.getsockname()[1]
native_test = """
import errno, socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('192.0.2.1', 80))
except OSError as error:
    assert error.errno in (errno.EPERM, errno.EACCES), repr(error)
else:
    raise AssertionError('OS sandbox allowed external connection')
s.close()
with socket.create_connection(('127.0.0.1', int(sys.argv[1])), 2) as local:
    local.sendall(b'X')
print('OS sandbox OK: external IP denied by permissions; loopback allowed.')
"""
subprocess.run(
    [
        "/usr/bin/sandbox-exec",
        "-f",
        str(profile),
        sys.executable,
        "-c",
        native_test,
        str(port),
    ],
    check=True,
)
connection, _ = listener.accept()
with connection:
    assert connection.recv(1) == b"X"
java = os.environ["LOCAL_TEST_JAVA"]
runtime = root / ".runtime/local"
subprocess.run(
    [
        "/usr/bin/sandbox-exec",
        "-f",
        str(profile),
        java,
        "-Djava.security.manager=allow",
        "-Djava.net.preferIPv4Stack=true",
        f"-javaagent:{runtime}/network-guard.jar={runtime}/logs/guard-test.log",
        "-cp",
        str(runtime / "classes"),
        "LocalNetworkGuardTest",
        str(port),
    ],
    check=True,
)
connection, _ = listener.accept()
with connection:
    assert connection.recv(1) == b"\x01"
listener.close()
