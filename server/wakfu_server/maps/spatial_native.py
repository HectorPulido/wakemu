"""Native spatial authority and shared nonspatial character projections.

The library owns positions, leases and membership. Python retains references to
character-domain metadata for protocol publication, never a second spatial index.
Loading occurs when an engine is constructed, not while catalogues are imported.
"""

import ctypes
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
import threading
import uuid

from wakfu_server.paths import SERVER_ROOT

ABI_VERSION = 1
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
DEFAULT_CAPACITY = 100000
MAX_BINARY_BUFFERS = 131072
MAX_BINARY_INTEGERS = 1000000
_SPATIAL_FIELDS = frozenset(
    {
        "id",
        "account_id",
        "generation",
        "map_id",
        "instance_id",
        "x",
        "y",
        "z",
        "direction",
        "presence_generation",
        "empty_generation",
        "_ecology_active",
    }
)
_default_engine = None
_default_lock = threading.Lock()


def configure_spatial(native):
    """Select the shared bootstrap owner before public spatial consumers start."""
    if not isinstance(native, NativeSpatial):
        raise TypeError("The spatial owner must be a NativeSpatial engine")
    global _default_engine
    with _default_lock:
        previous = _default_engine
        _default_engine = native
        return previous


def get_spatial():
    """Construct the isolated default only when an actual spatial call needs it."""
    global _default_engine
    with _default_lock:
        if _default_engine is None:
            _default_engine = NativeSpatial()
        return _default_engine


# These names expose the same owner to the native navigation adapters.
default_spatial = get_spatial
set_default_spatial = configure_spatial


class NativeSpatialError(ValueError):
    """A rejected native command, with a stable code for public adapters."""

    def __init__(self, code, message):
        self.code = code
        self.native_code = code
        super().__init__(message)


class _NativeBuffer(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("len", ctypes.c_size_t),
        ("capacity", ctypes.c_size_t),
    ]


class _NativeSlice(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("len", ctypes.c_size_t)]


def _library_name():
    if sys.platform == "win32":
        return "wakemu_world_spatial.dll"
    if sys.platform == "darwin":
        return "libwakemu_world_spatial.dylib"
    return "libwakemu_world_spatial.so"


def _library_path():
    configured = os.environ.get("WAKFU_SPATIAL_LIBRARY")
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"Configured Rust spatial library is missing: {path}")
        return str(path)
    name = _library_name()
    candidates = [Path("/usr/local/lib/wakemu") / name]
    candidates.extend(
        SERVER_ROOT / "rust-services/target" / profile / name
        for profile in ("debug", "release")
    )
    for path in candidates:
        if path.is_file():
            return str(path.resolve())
    raise RuntimeError(
        "Rust spatial library is missing; build wakemu-world-spatial --lib "
        "or set WAKFU_SPATIAL_LIBRARY to the compiled library"
    )


@lru_cache(maxsize=4)
def _load_library(path):
    try:
        # CDLL releases the GIL while Rust works. No native call invokes Python.
        library = ctypes.CDLL(path)
        library.wakemu_spatial_abi_version.argtypes = []
        library.wakemu_spatial_abi_version.restype = ctypes.c_uint32
        library.wakemu_spatial_create.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_size_t,
        ]
        library.wakemu_spatial_create.restype = ctypes.c_uint64
        library.wakemu_spatial_call.argtypes = [
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        library.wakemu_spatial_call.restype = _NativeBuffer
        library.wakemu_wire_call.argtypes = [
            ctypes.c_uint64,
            ctypes.c_uint32,
            ctypes.POINTER(_NativeSlice),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_int64),
            ctypes.c_size_t,
        ]
        library.wakemu_wire_call.restype = _NativeBuffer
        library.wakemu_spatial_free.argtypes = [_NativeBuffer]
        library.wakemu_spatial_free.restype = None
        library.wakemu_spatial_drop.argtypes = [ctypes.c_uint64]
        library.wakemu_spatial_drop.restype = None
    except (AttributeError, OSError) as error:
        raise RuntimeError(f"Cannot load Rust spatial ABI from {path}") from error
    if library.wakemu_spatial_abi_version() != ABI_VERSION:
        raise RuntimeError(f"Unsupported Rust spatial ABI in {path}")
    return library


def _owner_key(owner):
    if isinstance(owner, dict):
        owner = (
            owner.get("account_id"),
            owner.get("generation"),
            owner.get("character_id", owner.get("id")),
        )
    if (
        not isinstance(owner, (tuple, list))
        or len(owner) != 3
        or type(owner[0]) is not int
        or owner[0] <= 0
        or type(owner[2]) is not int
        or owner[2] <= 0
        or not isinstance(owner[1], str)
        or not 1 <= len(owner[1]) <= 512
    ):
        raise ValueError("Invalid spatial metadata owner")
    return tuple(owner)


class NativeSpatial:
    def __init__(self, epoch=None, *, capacity=DEFAULT_CAPACITY):
        epoch = uuid.uuid4().hex if epoch is None else epoch
        if not isinstance(epoch, str):
            raise ValueError("Invalid spatial epoch")
        encoded = epoch.encode("utf-8")
        if not 1 <= len(encoded) <= 128:
            raise ValueError("Invalid spatial epoch")
        if (
            type(capacity) is not int
            or capacity <= 0
            or capacity > ctypes.c_size_t(-1).value
        ):
            raise ValueError("Invalid spatial capacity")
        self.epoch = epoch
        self._condition = threading.Condition()
        self._inflight = 0
        self._closing = False
        self._handle = 0
        self.bindings = {}
        self._binding_domains = {}
        self._library = _load_library(_library_path())
        self._handle = self._library.wakemu_spatial_create(
            encoded, len(encoded), capacity
        )
        if not self._handle:
            raise RuntimeError("Rust spatial engine rejected its configuration")

    def call(self, op, **kwargs):
        if not isinstance(op, str) or not op:
            raise ValueError("Invalid spatial operation")
        try:
            request = json.dumps(
                {"op": op, "args": kwargs},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as error:
            raise ValueError("Invalid spatial command JSON") from error
        if len(request) > MAX_MESSAGE_BYTES:
            raise ValueError("Spatial command exceeds the native byte limit")
        with self._condition:
            if self._closing or not self._handle:
                raise RuntimeError("Rust spatial engine is closed")
            handle = self._handle
            self._inflight += 1
        try:
            buffer = self._library.wakemu_spatial_call(handle, request, len(request))
            try:
                if not buffer.data or not 0 < buffer.len <= MAX_MESSAGE_BYTES:
                    raise RuntimeError("Rust spatial ABI returned an invalid buffer")
                try:
                    response = json.loads(ctypes.string_at(buffer.data, buffer.len))
                except (ValueError, UnicodeError) as error:
                    raise RuntimeError(
                        "Rust spatial ABI returned invalid JSON"
                    ) from error
            finally:
                self._library.wakemu_spatial_free(buffer)
            if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                raise RuntimeError("Rust spatial ABI returned an invalid envelope")
            if response["ok"]:
                if "result" not in response:
                    raise RuntimeError("Rust spatial ABI omitted its result")
                return response["result"]
            error = response.get("error")
            if (
                not isinstance(error, dict)
                or not isinstance(error.get("code"), str)
                or not isinstance(error.get("message"), str)
            ):
                raise RuntimeError("Rust spatial ABI returned an invalid error")
            if error["code"] in ("panic", "internal", "internal_error", "closed"):
                raise RuntimeError(error["message"])
            raise NativeSpatialError(error["code"], error["message"])
        finally:
            with self._condition:
                self._inflight -= 1
                self._condition.notify_all()

    def call_binary(self, op, *, buffers=(), integers=()):
        """Encode immutable borrowed inputs without JSON or payload copies."""
        if type(op) is not int or not 0 <= op < 1 << 32:
            raise ValueError("Invalid native wire operation")
        if not isinstance(buffers, (tuple, list)) or len(buffers) > MAX_BINARY_BUFFERS:
            raise ValueError("Invalid native wire buffers")
        if (
            not isinstance(integers, (tuple, list))
            or len(integers) > MAX_BINARY_INTEGERS
        ):
            raise ValueError("Invalid native wire integers")
        if any(type(value) is not bytes for value in buffers):
            raise ValueError("Native wire inputs must be immutable bytes")
        if any(
            type(value) is not int or not -(1 << 63) <= value < 1 << 63
            for value in integers
        ):
            raise ValueError("Invalid native wire signed integer")
        if sum(map(len, buffers)) + len(integers) * 8 > MAX_MESSAGE_BYTES:
            raise ValueError("Native wire input exceeds limit")
        # Keep the exact bytes objects and their c_char_p references alive while
        # CDLL releases the GIL. c_char_p(bytes) borrows their immutable storage.
        retained = tuple(buffers)
        pointers = tuple(ctypes.c_char_p(value) for value in retained)
        descriptors = (_NativeSlice * len(retained))(
            *(
                _NativeSlice(ctypes.cast(pointer, ctypes.c_void_p), len(value))
                for pointer, value in zip(pointers, retained)
            )
        )
        numbers = (ctypes.c_int64 * len(integers))(*integers)
        with self._condition:
            if self._closing or not self._handle:
                raise RuntimeError("Rust spatial engine is closed")
            handle = self._handle
            self._inflight += 1
        try:
            result = self._library.wakemu_wire_call(
                handle,
                op,
                descriptors,
                len(retained),
                numbers,
                len(integers),
            )
            try:
                if (
                    not result.data
                    or not 1 <= result.len <= MAX_MESSAGE_BYTES + 1
                    or result.capacity < result.len
                ):
                    raise RuntimeError("Rust wire ABI returned an invalid buffer")
                status = result.data[0]
                payload = ctypes.string_at(
                    ctypes.cast(result.data, ctypes.c_void_p).value + 1,
                    result.len - 1,
                )
            finally:
                self._library.wakemu_spatial_free(result)
            if status == 0:
                return payload
            if status not in (1, 2):
                raise RuntimeError("Rust wire ABI returned an invalid status")
            try:
                message = payload.decode("utf-8")
            except UnicodeError as error:
                raise RuntimeError("Rust wire ABI returned an invalid error") from error
            if status == 2:
                raise RuntimeError(message)
            code, separator, detail = message.partition("\x00")
            if separator:
                if not code:
                    raise RuntimeError("Rust wire ABI returned an invalid error code")
                raise NativeSpatialError(code, detail)
            raise NativeSpatialError("invalid", message)
        finally:
            with self._condition:
                self._inflight -= 1
                self._condition.notify_all()

    def bind_character(self, owner, character, *, domain="world"):
        key = _owner_key(owner)
        if domain not in ("world", "positions"):
            raise ValueError("Invalid spatial metadata binding domain")
        if not isinstance(character, dict):
            raise ValueError("Invalid nonspatial character projection")
        metadata = {
            name: value
            for name, value in character.items()
            if name not in _SPATIAL_FIELDS and not name.startswith("_spatial_")
        }
        with self._condition:
            if self._closing or not self._handle:
                raise RuntimeError("Rust spatial engine is closed")
            binding = (key, domain)
            previous = self.bindings.get(binding)
            if previous is None:
                self.bindings[binding] = metadata
            else:
                previous.clear()
                previous.update(metadata)
                metadata = previous
            self.retain_character(key, domain)
            return metadata

    def character(self, owner, *, domain="world"):
        if domain not in ("world", "positions"):
            raise ValueError("Invalid spatial metadata binding domain")
        with self._condition:
            return self.bindings.get((_owner_key(owner), domain))

    def retain_character(self, owner, domain):
        if domain not in ("world", "positions"):
            raise ValueError("Invalid spatial metadata binding domain")
        with self._condition:
            self._binding_domains.setdefault(_owner_key(owner), set()).add(domain)

    def release_character(self, owner, domain):
        if domain not in ("world", "positions"):
            raise ValueError("Invalid spatial metadata binding domain")
        key = _owner_key(owner)
        with self._condition:
            removed = self.bindings.pop((key, domain), None) is not None
            domains = self._binding_domains.get(key)
            if domains is not None:
                domains.discard(domain)
            if domains:
                return removed
            self._binding_domains.pop(key, None)
            return removed

    def unbind_character(self, owner):
        key = _owner_key(owner)
        with self._condition:
            if self._binding_domains.get(key):
                return False
            removed = False
            for domain in ("world", "positions"):
                removed |= self.bindings.pop((key, domain), None) is not None
            return removed

    def close(self):
        with self._condition:
            self._closing = True
            handle, self._handle = self._handle, 0
        # Native drop cancels pending scope waits and wakes their condition
        # variables. Existing calls retain their Rust Arc until they return.
        if handle:
            self._library.wakemu_spatial_drop(handle)
        with self._condition:
            while self._inflight:
                self._condition.wait()
            self.bindings.clear()
            self._binding_domains.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_error):
        self.close()

    def __del__(self):
        # Construction can fail before the condition or native library exists.
        if getattr(self, "_handle", 0):
            try:
                self.close()
            except Exception:
                pass  # Interpreter shutdown may already have torn down modules.
