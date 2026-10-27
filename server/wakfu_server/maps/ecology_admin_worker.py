"""Private, bounded subprocess preparation for administrative ecology jobs."""
import contextlib
import io
import os
import pickle
import select
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Mapping

MAX_BYTES = 64 * 1024 * 1024


def plain(value):
    """Export immutable planner records while retaining tuple and integer keys."""
    if isinstance(value, Mapping):
        return {plain(key): plain(row) for key, row in value.items()}
    if isinstance(value, tuple):
        return tuple(plain(row) for row in value)
    if isinstance(value, list):
        return [plain(row) for row in value]
    if value is None or type(value) in (str, int, float, bool, bytes):
        return value
    raise ValueError("Unsupported administrative preparation value")


class _DataOnly(pickle.Unpickler):
    def find_class(self, module, name):
        raise ValueError("Administrative preparation must contain data only")


def encode(value):
    payload = pickle.dumps(plain(value), protocol=4)
    if len(payload) > MAX_BYTES:
        raise ValueError("Administrative preparation exceeds bounded capacity")
    return struct.pack(">I", len(payload)) + payload


def decode(payload):
    return _DataOnly(io.BytesIO(payload)).load()


class PreparationProcess:
    """One spawned child per job; no World locks or database pools are forked."""

    def __init__(self, *, timeout=180, command=None):
        self.timeout = timeout
        self.command = command or [
            sys.executable,
            "-m",
            "wakfu_server.ecology_admin_worker",
        ]
        self.process = None
        self.last_pid = None
        self.failures = []
        self.closed = False
        self.lock = threading.Lock()

    @property
    def pid(self):
        return self.last_pid

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.cancel()
        with self.lock:
            child, self.process = self.process, None
        if child is None:
            return
        if child.stdin is not None:
            child.stdin.close()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if child.stdout is not None:
            child.stdout.close()

    def cancel(self):
        with self.lock:
            self.closed = True
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()

    def _read(self, count, deadline):
        result = bytearray()
        while len(result) < count:
            remaining = deadline - time.monotonic()
            if (
                remaining <= 0
                or not select.select([self.process.stdout], [], [], remaining)[0]
            ):
                raise TimeoutError("Administrative preparation timed out")
            chunk = os.read(
                self.process.stdout.fileno(), min(65536, count - len(result))
            )
            if not chunk:
                raise RuntimeError("Administrative preparation worker exited")
            result.extend(chunk)
        return bytes(result)

    def __call__(self, domain, map_id, region_id):
        with self.lock:
            if self.closed:
                raise RuntimeError("Administrative preparation worker is stopping")
            if self.process is None:
                self.process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    bufsize=0,
                )
                self.last_pid = self.process.pid
        self.process.stdin.write(encode((domain, map_id, region_id)))
        self.process.stdin.flush()
        deadline = time.monotonic() + self.timeout
        length = struct.unpack(">I", self._read(4, deadline))[0]
        if not 0 < length <= MAX_BYTES:
            raise ValueError("Invalid administrative preparation size")
        response = decode(self._read(length, deadline))
        if not isinstance(response, dict) or response.get("ok") is not True:
            error_type = (
                response.get("error_type", "UnknownError")
                if isinstance(response, dict)
                else "InvalidResponse"
            )
            if not isinstance(error_type, str) or not error_type.isidentifier():
                error_type = "UnknownError"
            if len(self.failures) < 64:
                self.failures.append(
                    dict(
                        domain=domain,
                        map_id=map_id,
                        region_id=region_id,
                        error_type=error_type,
                    )
                )
            raise ValueError(
                f"Administrative native habitat preparation failed ({error_type})"
            )
        from wakfu_server import native_catalog

        if response.get("revision") != native_catalog.release():
            raise ValueError("Administrative preparation catalog is stale")
        result = response.get("prepared")
        if not isinstance(result, dict) or (
            result.get("map_id"),
            result.get("region_id"),
        ) != (map_id, region_id):
            raise ValueError("Administrative preparation scope differs")
        return result


def main():
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    os.nice(10)
    source, destination = sys.stdin.buffer, sys.stdout.buffer
    # Catalog diagnostics belong to stderr, never the private framed channel.
    with contextlib.redirect_stdout(sys.stderr):
        while header := source.read(4):
            if len(header) != 4:
                return
            length = struct.unpack(">I", header)[0]
            if not 0 < length <= 4096:
                return
            payload = source.read(length)
            if len(payload) != length:
                return
            try:
                domain, map_id, region_id = decode(payload)
                if domain == "monsters":
                    from wakfu_server.ecology_admin_planner import prepare
                elif domain == "flora":
                    from wakfu_server.ecology_flora_planner import prepare
                else:
                    raise ValueError("Unsupported administrative ecology domain")
                from wakfu_server import native_catalog

                response = dict(
                    ok=True,
                    revision=native_catalog.release(),
                    prepared=prepare(map_id, region_id),
                )
                packed = encode(response)
            except Exception as error:
                packed = encode(dict(ok=False, error_type=type(error).__name__))
            destination.write(packed)
            destination.flush()


if __name__ == "__main__":
    main()
