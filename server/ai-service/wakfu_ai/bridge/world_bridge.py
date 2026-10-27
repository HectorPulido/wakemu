"""World-side SDK kept in ai-service; the final world shim only loads it.

Transport the complete catalogue, engine and native instance graph. No fields,
assets, actors or history are selected away to satisfy a packet-size limit.
Large objects are streamed as verified content-addressed blocks.
"""
import base64
from ..native.native_control import effective_affiliation
import importlib.util
import hashlib
import io
import gzip
import json
from pathlib import Path
import urllib.request
import http.client
import socket
import urllib.parse
import urllib.error
import uuid
import tempfile
import os
import weakref
import re
import threading
import time
import math
from types import SimpleNamespace
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy

from ..context.native_context import encode, encode_bytes
from ..context.native_fingerprint import fingerprint
from ..native.native_deadline import (
    check,
    remaining,
    query_budget,
    NativeSearchAllowanceExceeded,
    clock_now,
)
from ..planning import turn_continuation
from ..native.repertoire_metadata import SpellMetadataCache


def _json_bytes(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def _advisory_spell_capabilities(spell, level):
    """Missing advisory effect metadata must not remove an owned ability."""
    from wakfu_server.combat_ai_capabilities import describe_spell

    try:
        return describe_spell(spell, level)
    except (KeyError, TypeError, ValueError):
        return None


def _prepare_advisory_spell_capabilities(pairs):
    from wakfu_server import combat_ai_capabilities

    prepare = getattr(combat_ai_capabilities, "prepare_spell_capabilities", None)
    if callable(prepare):
        try:
            return prepare(pairs)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            # Mandatory ordinary lookups still validate every owned spell;
            # missing advisory/batch metadata cannot remove its book entry.
            return False
    return False


_advisory_spell_capabilities.prepare = _prepare_advisory_spell_capabilities


def _file_hash(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


class DatabaseCatalogSource:
    """Read immutable catalog bytes only when the receiver needs an asset."""

    def __init__(self, revision, path, digest, size):
        self.revision, self.path, self.digest, self.size = revision, path, digest, size

    def open(self, mode="rb"):
        if mode != "rb":
            raise ValueError("Catalog context sources are binary and read-only")
        from wakfu_server import native_catalog

        with native_catalog._database().connection() as db:
            row = db.execute(
                "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (self.revision, self.path),
            ).fetchone()
        if row is None:
            raise ValueError("Missing pinned database catalog document")
        raw = bytes(row["raw"])
        if len(raw) != self.size or hashlib.sha256(raw).hexdigest() != self.digest:
            raise ValueError("Database catalog context checksum mismatch")
        return io.BytesIO(raw)


class CompleteContextExporter:
    def __init__(self, roots, *, files=None, cache_root=None, source_only=False):
        if not isinstance(roots, dict) or not roots:
            raise ValueError("Complete context needs native source roots")
        self.roots = {name: Path(path) for name, path in roots.items()}
        self.files = {name: Path(path) for name, path in (files or {}).items()}
        self.source_only = source_only
        self.cache = {}
        self._snapshot_identities = {}
        self._cache_index = None
        self._cache_index_identity = None
        if cache_root is None:
            self._snapshots = tempfile.TemporaryDirectory(
                prefix="wakfu-native-catalog-"
            )
            self._cleanup = weakref.finalize(self, self._snapshots.cleanup)
        else:
            namespace = hashlib.sha256(
                _json_bytes(
                    dict(
                        roots={
                            name: str(path.resolve())
                            for name, path in sorted(self.roots.items())
                        },
                        files={
                            name: str(path.resolve())
                            for name, path in sorted(self.files.items())
                        },
                    )
                )
            ).hexdigest()
            directory = Path(cache_root) / namespace
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._snapshots = SimpleNamespace(name=str(directory))
            self._cleanup = weakref.finalize(self, lambda: None)
            self._cache_index = directory / "index.json"
            self._restore_cache_index()
        self._inventory_condition = threading.Condition()
        self._inventory_batches = []
        self._inventory_scanning = None
        self._inventory_admission_seconds = 0.002

    def close(self):
        self._cleanup()

    @staticmethod
    def _file_identity(status):
        return (
            status.st_dev,
            status.st_ino,
            status.st_size,
            status.st_mtime_ns,
            status.st_ctime_ns,
        )

    def _restore_cache_index(self):
        try:
            index_identity = self._file_identity(self._cache_index.stat())
            records = json.loads(self._cache_index.read_bytes())
            if not isinstance(records, list):
                return
            for record in records:
                check()
                if (
                    not isinstance(record, dict)
                    or set(record) != {"key", "signature", "sha256", "snapshotIdentity"}
                    or not isinstance(record["key"], list)
                    or len(record["key"]) != 2
                    or not isinstance(record["signature"], list)
                    or len(record["signature"]) != 5
                    or not isinstance(record["snapshotIdentity"], list)
                    or len(record["snapshotIdentity"]) != 5
                    or any(
                        type(value) is not int
                        for value in record["key"]
                        + record["signature"]
                        + record["snapshotIdentity"]
                    )
                    or record["key"] != record["signature"][:2]
                    or type(record["sha256"]) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
                ):
                    continue
                snapshot = Path(self._snapshots.name) / record["sha256"]
                try:
                    status = snapshot.stat()
                except OSError:
                    continue
                if (
                    list(self._file_identity(status)) != record["snapshotIdentity"]
                    or status.st_size != record["signature"][2]
                ):
                    continue
                self.cache[tuple(record["key"])] = (
                    tuple(record["signature"]),
                    record["sha256"],
                    snapshot,
                )
                self._snapshot_identities[record["sha256"]] = tuple(
                    record["snapshotIdentity"]
                )
            self._cache_index_identity = index_identity
        except TimeoutError:
            raise
        except (OSError, ValueError, UnicodeError):
            # A missing/damaged hint can only cause a full recapture. It can
            # never remove a source or truncate the freshly enumerated graph.
            self.cache.clear()

    def _save_cache_index(self):
        if self._cache_index is None:
            return
        records = []
        verified_snapshots = set()
        for key, (signature, digest, snapshot) in self.cache.items():
            check()
            if isinstance(key, tuple):
                expected = self._snapshot_identities[digest]
                if digest not in verified_snapshots:
                    if self._file_identity(snapshot.stat()) != expected:
                        raise ValueError("Native catalogue snapshot changed")
                    verified_snapshots.add(digest)
                records.append(
                    dict(
                        key=list(key),
                        signature=list(signature),
                        sha256=digest,
                        snapshotIdentity=list(expected),
                    )
                )
        payload = _json_bytes(records)
        # Validate the snapshots above even when the index is unchanged. An
        # identical index needs no atomic replacement, but timestamps alone
        # are not evidence that its actual bytes still match this scan.
        try:
            before = self._file_identity(self._cache_index.stat())
            if before[2] == len(payload):
                with self._cache_index.open("rb") as existing:
                    identical = existing.read(len(payload) + 1) == payload
                check()
                after = self._file_identity(self._cache_index.stat())
                if identical and before == after:
                    self._cache_index_identity = after
                    return
        except OSError:
            pass
        with tempfile.NamedTemporaryFile(
            dir=self._snapshots.name, delete=False
        ) as target:
            temporary = Path(target.name)
            target.write(payload)
        try:
            check()
            os.replace(temporary, self._cache_index)
            self._cache_index_identity = self._file_identity(self._cache_index.stat())
        finally:
            temporary.unlink(missing_ok=True)

    def inventory(self):
        # Callers may share only a batch whose complete scan has not started.
        # Once the admission window closes, later callers queue a distinct
        # full scan so newly-created files can never be hidden by a prior
        # caller's manifest.
        check()
        with self._inventory_condition:
            now = time.monotonic()
            if (
                self._inventory_batches
                and not self._inventory_batches[-1]["closed"]
                and now
                >= (
                    self._inventory_batches[-1]["created"]
                    + self._inventory_admission_seconds
                )
            ):
                self._inventory_batches[-1]["closed"] = True
                self._inventory_condition.notify_all()
            # A queued batch has not observed any files yet. It can include
            # every caller arriving before its scan actually starts, even if
            # its initial admission window has elapsed behind another scan.
            # The active scan is never shared with a later caller.
            if (
                self._inventory_batches
                and self._inventory_batches[-1] is not self._inventory_scanning
            ):
                batch = self._inventory_batches[-1]
            else:
                batch = dict(
                    created=now,
                    closed=False,
                    done=False,
                    result=None,
                    error=None,
                    waiters=0,
                )
                self._inventory_batches.append(batch)
            batch["waiters"] += 1

        try:
            closes_at = batch["created"] + self._inventory_admission_seconds
            while True:
                check()
                completed = False
                with self._inventory_condition:
                    if not batch["closed"] and time.monotonic() >= closes_at:
                        batch["closed"] = True
                        self._inventory_condition.notify_all()
                    if batch["done"]:
                        result, error = batch["result"], batch["error"]
                        completed = True
                    if (
                        not completed
                        and batch["closed"]
                        and self._inventory_batches
                        and self._inventory_batches[0] is batch
                        and self._inventory_scanning is None
                    ):
                        self._inventory_scanning = batch
                        leader = True
                    else:
                        leader = False
                    if not completed and not leader:
                        remaining_admission = max(0.0, closes_at - time.monotonic())
                        # This wait remains under the condition lock so a scan
                        # completion cannot notify just before the waiter sleeps.
                        deadline_remaining = remaining()
                        wait_for = 0.05
                        if remaining_admission:
                            wait_for = min(wait_for, remaining_admission)
                        if deadline_remaining is not None:
                            wait_for = min(wait_for, deadline_remaining)
                        self._inventory_condition.wait(timeout=max(0.0001, wait_for))
                if completed:
                    check()
                    if error is not None:
                        raise error
                    manifest, sources = result
                    copied = (
                        dict(
                            format=manifest["format"],
                            entries=[dict(entry) for entry in manifest["entries"]],
                        ),
                        dict(sources),
                    )
                    check()
                    return copied
                if leader:
                    break

            try:
                result = self._inventory_scan()
                error = None
            except BaseException as caught:
                result, error = None, caught
            with self._inventory_condition:
                batch["result"] = result
                batch["error"] = error
                batch["done"] = True
                self._inventory_scanning = None
                if self._inventory_batches and self._inventory_batches[0] is batch:
                    self._inventory_batches.pop(0)
                self._inventory_condition.notify_all()
            if error is not None:
                raise error
            manifest, sources = result
            copied = (
                dict(
                    format=manifest["format"],
                    entries=[dict(entry) for entry in manifest["entries"]],
                ),
                dict(sources),
            )
            check()
            return copied
        finally:
            with self._inventory_condition:
                batch["waiters"] -= 1
                if batch["waiters"] == 0 and not batch["done"]:
                    if batch is not self._inventory_scanning:
                        try:
                            self._inventory_batches.remove(batch)
                        except ValueError:
                            pass
                        self._inventory_condition.notify_all()

    def _inventory_scan(self):
        # Provisioning can publish an index while this exporter is already
        # alive. Import those verified hints before fresh full enumeration;
        # source signatures and snapshot identities are still checked below.
        if self._cache_index is not None:
            try:
                identity = self._file_identity(self._cache_index.stat())
            except FileNotFoundError:
                identity = None
            if identity is not None and identity != self._cache_index_identity:
                self._restore_cache_index()
        check()
        entries, sources, names = [], {}, set()
        # This cache lasts for one fresh scan only. Source changes and newly
        # created files remain visible on the next inventory call.
        verified_sources = {}
        enumerated_roots = {}
        resolved_roots = {root: root.resolve() for root in self.roots.values()}

        def files(root):
            resolved = resolved_roots[root]
            # Logical roots may overlap (engine and server, for example).
            # Enumerate their containing physical root once in THIS scan;
            # retain every logical alias and its original component ordering.
            outer = min(
                (
                    candidate
                    for candidate in resolved_roots.values()
                    if resolved.is_relative_to(candidate)
                ),
                key=lambda candidate: len(candidate.parts),
            )
            if outer not in enumerated_roots:
                enumerated_roots[outer] = walk(outer)
            if root == outer:
                return enumerated_roots[outer]
            result = []
            prefix = resolved.relative_to(outer).as_posix()
            prefix = "" if prefix == "." else prefix + "/"
            for relative, path, status in enumerated_roots[outer]:
                check()
                if relative.startswith(prefix):
                    suffix = relative[len(prefix) :]
                    result.append((suffix, root / suffix, status))
            return result

        def walk(root):
            # DirEntry classifies ordinary files from directory metadata;
            # avoid repeated Path.is_file/stat calls while still enumerating
            # every entry. register performs the full source identity checks.
            pending, result = [(root, "")], []
            while pending:
                check()
                directory_path, prefix = pending.pop()
                with os.scandir(directory_path) as directory:
                    for entry in directory:
                        check()
                        relative = prefix + "/" + entry.name if prefix else entry.name
                        if entry.is_dir():
                            if entry.is_symlink():
                                raise ValueError(
                                    "Unenumerated linked context directory: "
                                    + entry.path
                                )
                            pending.append((Path(entry.path), relative))
                        elif entry.is_file():
                            result.append((relative, Path(entry.path), entry.stat()))

            # Preserve the previous Path ordering while retaining the exact
            # relative name from enumeration, without rebuilding ancestors.
            # All paths share this root. Path ordering compares normalized
            # component tuples, not the slash-joined string. Build relative
            # components once instead of invoking Path comparison and parsing
            # ancestors for every O(n log n) sorting comparison.
            def ordering_key(pair):
                check()
                return tuple(pair[0].split("/"))

            result.sort(key=ordering_key)
            check()
            return result

        def register(name, path, status=None):
            check()
            if name in names:
                raise ValueError("Duplicate complete context asset path")
            names.add(name)
            stat = path.stat() if status is None else status

            def file_identity(status):
                return (
                    status.st_dev,
                    status.st_ino,
                    status.st_size,
                    status.st_mtime_ns,
                    status.st_ctime_ns,
                )

            signature = file_identity(stat)
            # Aliases such as catalog/foo and server/protocol/foo describe
            # the same physical file. Retain both manifest entries while
            # freezing that identical source only once per file signature.
            # stat already identifies the physical file across aliases and
            # hard links. Resolving every ancestor of every asset repeats
            # tens of thousands of filesystem calls per concurrent turn.
            # Retain full enumeration/signature checks; no cached manifest.
            cache_key = (
                (stat.st_dev, stat.st_ino) if stat.st_ino else str(path.resolve())
            )
            # Aliases keep their logical manifest entries, but the same
            # physical source signature needs one snapshot validation per scan.
            scan_key = cache_key, signature
            verified = verified_sources.get(scan_key)
            if verified is not None:
                digest, snapshot = verified
                entries.append(dict(path=name, sha256=digest, size=stat.st_size))
                sources[digest] = snapshot
                return
            cached = self.cache.get(cache_key)
            if cached is not None and self._cache_index is not None:
                try:
                    intact = self._file_identity(
                        cached[2].stat()
                    ) == self._snapshot_identities.get(cached[1])
                except OSError:
                    intact = False
                if not intact:
                    cached = None
            if cached is not None and cached[0] == signature:
                digest, snapshot = cached[1:]
            else:
                # Transfer exactly the bytes used for the manifest, even if
                # a concurrent build replaces the original file afterward.
                checksum = hashlib.sha256()
                with tempfile.NamedTemporaryFile(
                    dir=self._snapshots.name, delete=False
                ) as target:
                    temporary = Path(target.name)
                    with path.open("rb") as source:
                        if signature != file_identity(os.fstat(source.fileno())):
                            temporary.unlink()
                            raise ValueError(
                                "Native catalogue file changed while opening: " + name
                            )
                        for block in iter(lambda: source.read(1024 * 1024), b""):
                            check()
                            target.write(block)
                            checksum.update(block)
                        if signature != file_identity(os.fstat(source.fileno())):
                            temporary.unlink()
                            raise ValueError(
                                "Native catalogue file changed while reading: " + name
                            )
                after = path.stat()
                if signature != file_identity(after):
                    temporary.unlink()
                    raise ValueError(
                        "Native catalogue file changed while snapshotting: " + name
                    )
                digest = checksum.hexdigest()
                snapshot = Path(self._snapshots.name) / digest
                os.replace(temporary, snapshot)
                self.cache[cache_key] = (signature, digest, snapshot)
                self._snapshot_identities[digest] = self._file_identity(snapshot.stat())
            verified_sources[scan_key] = (digest, snapshot)
            entries.append(dict(path=name, sha256=digest, size=stat.st_size))
            sources[digest] = snapshot

        database_catalog = None
        protocol_root = None
        if not self.source_only and "catalog" in self.roots:
            from wakfu_server.paths import DATA_ROOT

            # Older sealed-file world images do not ship the optional database
            # catalogue module. Keep their existing complete file authority;
            # an installed module still fails closed on database errors.
            if (
                self.roots["catalog"].resolve() == DATA_ROOT.resolve()
                and importlib.util.find_spec("wakfu_server.native_catalog") is not None
            ):
                from wakfu_server import native_catalog

                protocol_root = DATA_ROOT.resolve()
                revision = native_catalog.release()
                with native_catalog._database().connection() as db:
                    database_catalog = db.execute(
                        "SELECT path,sha256,source_bytes FROM native_catalog_documents "
                        "WHERE revision=%s ORDER BY path",
                        (revision,),
                    ).fetchall()
                if not database_catalog:
                    raise ValueError("Empty authoritative database catalog")
        for name, root in sorted(self.roots.items()):
            if database_catalog is not None and name == "catalog":
                for row in database_catalog:
                    asset_name = name + "/" + row["path"]
                    names.add(asset_name)
                    entries.append(
                        dict(
                            path=asset_name,
                            sha256=row["sha256"],
                            size=row["source_bytes"],
                        )
                    )
                    sources[row["sha256"]] = DatabaseCatalogSource(
                        revision,
                        row["path"],
                        row["sha256"],
                        row["source_bytes"],
                    )
                continue
            if not root.is_dir():
                raise ValueError("Missing complete context source root: " + name)
            for relative, path, status in files(root):
                if (
                    protocol_root is not None
                    and relative.endswith(".json")
                    and relative.rsplit("/", 1)[-1] != ".json"
                    and path.resolve().is_relative_to(protocol_root)
                ):
                    continue
                register(name + "/" + relative, path, status)
            if database_catalog is not None and protocol_root.is_relative_to(
                root.resolve()
            ):
                prefix = protocol_root.relative_to(root.resolve()).as_posix()
                for row in database_catalog:
                    asset_name = name + "/" + prefix + "/" + row["path"]
                    if asset_name in names:
                        raise ValueError("Duplicate database catalog context path")
                    names.add(asset_name)
                    entries.append(
                        dict(
                            path=asset_name,
                            sha256=row["sha256"],
                            size=row["source_bytes"],
                        )
                    )
        for name, path in sorted(self.files.items()):
            if not path.is_file():
                raise ValueError("Missing complete context source file: " + name)
            register(name, path)
        manifest = dict(format="wakfu-complete-context-1", entries=entries)
        if any(root.resolve() != resolved for root, resolved in resolved_roots.items()):
            raise ValueError("Complete context source root changed while scanning")
        self._save_cache_index()
        return manifest, sources

    @staticmethod
    def instance(runtime, *, authorities, policy, flags, source):
        # encode traverses every instance field. Runtime.fight and any other
        # references to the same Fight remain references to one complete node.
        return encode(
            dict(
                runtime=runtime,
                authorities=authorities,
                policy=policy,
                flags=flags,
                source=source,
            )
        )


class ContextTransport:
    def __init__(
        self,
        url,
        *,
        timeout=10,
        block_bytes=1024 * 1024,
        native_graph_parts=False,
        persistent=True
    ):
        if type(block_bytes) is not int or not 1 <= block_bytes <= 2 * 1024 * 1024:
            raise ValueError("Invalid context transport block size")
        if type(persistent) is not bool:
            raise ValueError("Invalid persistent transport switch")
        self.persistent = persistent
        self._connection = None
        self.metrics = dict(
            requests=0, tcpOpens=0, sentBytes=0, receivedBytes=0, requestSeconds=0.0
        )
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.block_bytes = block_bytes
        if type(native_graph_parts) is not bool:
            raise ValueError("Invalid native graph parts switch")
        self.native_graph_parts = native_graph_parts
        self._context_bundle = None

    def begin_context_bundle(self):
        """Stage only final context blocks for the next query continuation."""
        if getattr(self, "_context_bundle", None) is not None:
            raise ValueError("Native context bundle already active")
        self._context_bundle = []

    def abort_context_bundle(self):
        self._context_bundle = None

    def _flush_context_block(self, block):
        reply = self._retry_request("/v3/context/block", block)
        if reply != dict(complete=True, offset=block["size"]):
            raise ValueError("Incomplete deferred native context attachment")

    def continue_with_context(self, payload):
        from ..transport.context_bundle import BUNDLE_LIMIT, bundle_size

        blocks = getattr(self, "_context_bundle", None)
        if not blocks:
            reply = self._retry_request("/v3/decide", payload)
            self._context_bundle = None
            return reply
        bundle = dict(request=payload, blocks=blocks)
        # Continuation descriptions are not truncated to fit a frame. Flush
        # earlier objects normally until the complete envelope fits instead.
        while blocks and bundle_size(payload, blocks) > BUNDLE_LIMIT:
            self._flush_context_block(blocks[0])
            del blocks[0]
        if not blocks:
            reply = self._retry_request("/v3/decide", payload)
        else:
            reply = self._retry_request("/v3/context/continue", bundle)
        self._context_bundle = None
        return reply

    def _defer_context_block(self, block):
        from ..transport.context_bundle import (
            BUNDLE_LIMIT,
            MAX_ATTACHMENTS,
            bundle_size,
        )

        blocks = getattr(self, "_context_bundle", None)
        if blocks is None:
            return False
        # A single object may be registered twice in a query. Its immutable
        # digest still needs only one final attachment.
        if any(entry == block for entry in blocks):
            return True
        while blocks and (
            len(blocks) >= MAX_ATTACHMENTS
            or bundle_size({}, blocks + [block]) > BUNDLE_LIMIT
        ):
            self._flush_context_block(blocks[0])
            del blocks[0]
        if bundle_size({}, [block]) > BUNDLE_LIMIT:
            return False
        blocks.append(block)
        return True

    def instance_parts(self, parts):
        manifest, blobs = parts
        for digest, body in blobs.items():
            check()
            if type(body) is not bytes or hashlib.sha256(body).hexdigest() != digest:
                raise ValueError("Native fragment checksum mismatch")
            # Existing complete objects acknowledge the first block after
            # full checksum verification; new objects receive ALL blocks.
            self._upload(io.BytesIO(body), digest, len(body))
        return self.instance_bytes(_json_bytes(manifest))

    def __del__(self):
        # Explicit turn cleanup is primary; abandoned fixtures and standalone
        # callers must not leak their owned socket during object collection.
        connection = getattr(self, "_connection", None)
        if connection is not None:
            connection.close()

    def close(self):
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()

    def _timeout(self, connection=None):
        available = remaining()
        timeout = self.timeout if available is None else min(self.timeout, available)
        if connection is not None:
            connection.timeout = timeout
            if connection.sock is not None:
                connection.sock.settimeout(timeout)
        return timeout

    def request(self, endpoint, payload):
        check()
        body = _json_bytes(payload)
        check()
        started = time.monotonic()
        self.metrics["requests"] += 1
        self.metrics["sentBytes"] += len(body)
        try:
            if not self.persistent:
                request = urllib.request.Request(
                    self.url + endpoint,
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                self.metrics["tcpOpens"] += 1
                with urllib.request.urlopen(
                    request, timeout=self._timeout()
                ) as response:
                    data = response.read()
                self.metrics["receivedBytes"] += len(data)
                check()
                return json.loads(data)
            parsed = urllib.parse.urlsplit(self.url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError("Invalid native transport URL")
            connection = self._connection
            if connection is None:
                cls = (
                    http.client.HTTPSConnection
                    if parsed.scheme == "https"
                    else http.client.HTTPConnection
                )
                connection = self._connection = cls(
                    parsed.hostname, parsed.port, timeout=self._timeout()
                )
            expired = threading.Event()
            peer_socket = connection.sock

            def expire():
                expired.set()
                # Socket timeouts alone can be renewed indefinitely by a
                # dripping peer. Interrupt this request at its absolute limit.
                peer = peer_socket if peer_socket is not None else connection.sock
                if peer is not None:
                    try:
                        peer.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                connection.close()

            timer = threading.Timer(self._timeout(), expire)
            timer.daemon = True
            timer.start()
            try:
                self._timeout(connection)
                if connection.sock is None:
                    connection.connect()
                    self.metrics["tcpOpens"] += 1
                peer_socket = connection.sock
                check()
                if expired.is_set():
                    raise TimeoutError("Native HTTP request deadline reached")
                connection.request(
                    "POST",
                    parsed.path.rstrip("/") + endpoint,
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Wakfu-Keepalive": "1",
                    },
                )
                self._timeout(connection)
                response = connection.getresponse()
                chunks = []
                while True:
                    self._timeout(connection)
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    self.metrics["receivedBytes"] += len(chunk)
                    check()
                data = b"".join(chunks)
                if response.length not in (None, 0):
                    raise http.client.IncompleteRead(data, response.length)
                check()
                if expired.is_set():
                    raise TimeoutError("Native HTTP request deadline reached")
                if response.status >= 400:
                    raise urllib.error.HTTPError(
                        self.url + endpoint,
                        response.status,
                        response.reason,
                        response.headers,
                        io.BytesIO(data),
                    )
                if response.will_close:
                    self.close()
                return json.loads(data)
            except BaseException as error:
                self.close()
                if expired.is_set():
                    raise TimeoutError(
                        "Native HTTP request deadline reached"
                    ) from error
                if isinstance(error, http.client.HTTPException):
                    raise urllib.error.URLError(error) from error
                raise
            finally:
                timer.cancel()
                timer.join()
        finally:
            self.metrics["requestSeconds"] += time.monotonic() - started

    def _retry_request(self, endpoint, payload):
        for attempt in range(3):
            check()
            try:
                return self.request(endpoint, payload)
            except urllib.error.HTTPError as error:
                if error.code not in (408, 429, 502, 503, 504) or attempt == 2:
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise

    def _upload(self, source, digest, size):
        offset = 0
        while offset < size or size == 0:
            check()
            block = source.read(min(self.block_bytes, size - offset))
            if not block and offset < size:
                raise ValueError("Native context source ended before declared size")
            attachment = dict(
                sha256=digest,
                size=size,
                offset=offset,
                data=base64.b64encode(block).decode("ascii"),
            )
            if offset + len(block) == size and self._defer_context_block(attachment):
                return digest
            reply = self._retry_request(
                "/v3/context/block",
                attachment,
            )
            expected = offset + len(block)
            if (
                not isinstance(reply, dict)
                or type(reply.get("offset")) is not int
                or type(reply.get("complete")) is not bool
                or not expected <= reply["offset"] <= size
                or reply["complete"] != (reply["offset"] == size)
            ):
                raise ValueError("Invalid native context transfer acknowledgment")
            if reply["complete"]:
                return digest
            offset = reply["offset"]
            source.seek(offset)
        raise ValueError("Incomplete native context transfer")

    def bytes(self, payload):
        check()
        import io

        digest = hashlib.sha256(payload).hexdigest()
        status = self._retry_request(
            "/v3/context/status", dict(objects=[dict(sha256=digest, size=len(payload))])
        )
        if status.get("present") != [digest]:
            self._upload(io.BytesIO(payload), digest, len(payload))
        return digest

    def _measure_context(self, stage, operation):
        started = time.monotonic()
        try:
            return operation()
        finally:
            phases = self.metrics.setdefault("contextPreparationMs", {})
            phases[stage] = phases.get(stage, 0.0) + (time.monotonic() - started) * 1000

    def catalog(self, exporter):
        manifest, sources = self._measure_context("inventory", exporter.inventory)
        manifest_bytes = self._measure_context(
            "manifest_encoding", lambda: _json_bytes(manifest)
        )
        digest = self._measure_context(
            "manifest_transfer", lambda: self.bytes(manifest_bytes)
        )
        sealed = self._measure_context(
            "seal", lambda: self._retry_request("/v3/context/seal", dict(sha256=digest))
        )
        if (
            not isinstance(sealed, dict)
            or type(sealed.get("complete")) is not bool
            or sealed.get("entries") != len(manifest["entries"])
        ):
            raise ValueError("Invalid complete catalogue verification")
        if sealed["complete"]:
            # The receiver returns a complete, privately owned byte snapshot;
            # later turns can reuse it without rereading mutable canonical files.
            return digest
        # The seal operation identifies every missing hash. Upload only those
        # objects, then seal again so publication follows complete validation.
        entries = manifest["entries"]
        objects = {}
        for entry in entries:
            digest_key = entry["sha256"]
            previous = objects.get(digest_key)
            if previous is not None and previous["size"] != entry["size"]:
                raise ValueError("Conflicting complete context object sizes")
            objects[digest_key] = entry
        missing = sealed.get("missing")
        if (
            not isinstance(missing, list)
            or not missing
            or any(
                not isinstance(value, str) or value not in objects for value in missing
            )
            or len(set(missing)) != len(missing)
        ):
            raise ValueError("Invalid complete catalogue missing objects")
        for checksum in missing:
            check()
            entry = objects[checksum]
            with sources[checksum].open("rb") as source:
                self._measure_context(
                    "asset_transfer",
                    lambda: self._upload(source, checksum, entry["size"]),
                )
        sealed = self._measure_context(
            "seal", lambda: self._retry_request("/v3/context/seal", dict(sha256=digest))
        )
        if sealed.get("complete") is not True or sealed.get("entries") != len(entries):
            raise ValueError("Native context catalogue is incomplete")
        return digest

    def instance(self, graph):
        # Lossless compression changes transport bytes, never graph fields,
        # references, identities, or the total decoded context available to AI.
        return self.instance_bytes(_json_bytes(graph))

    def instance_bytes(self, payload):
        if not isinstance(payload, bytes):
            raise ValueError("Native complete context must be JSON bytes")
        check()
        import io

        compressed = gzip.compress(payload, compresslevel=1, mtime=0)
        check()
        digest = hashlib.sha256(compressed).hexdigest()
        # A transient snapshot normally has a new digest. The block endpoint
        # already verifies an existing object and acknowledges its full size,
        # including retries after a lost response. Uploading its first block
        # directly removes a redundant status round trip without weakening
        # checksum validation or omitting any part of a large snapshot.
        return self._upload(io.BytesIO(compressed), digest, len(compressed))


_TURN_CATALOGUES = ContextVar("wakfu_native_turn_catalogues", default=None)


@contextmanager
def turn_catalogue_scope():
    """Reuse complete immutable manifests only within one owner turn."""
    token = _TURN_CATALOGUES.set({})
    try:
        yield
    finally:
        _TURN_CATALOGUES.reset(token)


class NativeSession:
    """One source-bound native oracle session for service-directed exploration.

    The service requests facts/transitions; this SDK never chooses a candidate or
    prunes legal options. Every complete descendant snapshot is available by hash."""

    OPERATIONS = ("state", "repertoire", "preview", "line_of_sight", "project_turn")

    def __init__(
        self,
        oracle,
        transport,
        exporter,
        *,
        policy,
        policy_version,
        fight_instance_id,
        catalog_manifest=None
    ):
        self.oracle, self.transport = oracle, transport
        self.preparation_stages_ms = {}
        self.native_query_metrics = {}
        transport_metrics = getattr(transport, "metrics", None)
        if isinstance(transport_metrics, dict):
            transport_metrics["nativeSessionPreparationMs"] = self.preparation_stages_ms
            transport_metrics["nativeQueryMetrics"] = self.native_query_metrics
        self.policy, self.policy_version = policy, policy_version
        self.fight_instance_id = fight_instance_id
        check()
        if catalog_manifest is not None and (
            not isinstance(catalog_manifest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", catalog_manifest)
        ):
            raise ValueError("Invalid complete native catalogue manifest")
        catalogue_scope = _TURN_CATALOGUES.get()
        catalogue_key = (
            id(exporter),
            getattr(transport, "url", None),
            fight_instance_id,
        )
        if catalog_manifest is None and catalogue_scope is not None:
            catalog_manifest = catalogue_scope.get(catalogue_key)
        # A turn can reuse its fully transferred catalogue. The receiver
        # still verifies the complete manifest on each new search session;
        # runtime snapshots and source guards remain fresh for every action.
        self.catalog = (
            self._measure_preparation(
                "catalog_transfer", lambda: transport.catalog(exporter)
            )
            if catalog_manifest is None
            else catalog_manifest
        )
        if catalogue_scope is not None:
            catalogue_scope[catalogue_key] = self.catalog
        self.request_id = uuid.uuid4().hex
        self.states = {}
        self.state_identities = {}
        metadata_cache_key = ("spell-metadata", catalogue_key, self.catalog)
        self._spell_metadata_cache = (
            catalogue_scope.setdefault(metadata_cache_key, SpellMetadataCache())
            if catalogue_scope is not None
            else SpellMetadataCache()
        )
        self._certified_root_actions = set()
        self.needs_cleanup = False
        # Forecasts keep the complete native world for legality, but may not
        # teach the planner where an unseen opponent is, or which guessed
        # area attack would damage it. Freeze this observer scope for this
        # decision: a real reveal is observed by the next decision session.
        observer = getattr(oracle.runtime.fight, "current", None)
        property_provider = getattr(oracle, "observation_properties", None)
        observed_properties = (
            property_provider(oracle.runtime)
            if callable(property_provider)
            else {
                actor.id: getattr(actor, "native_fight_properties", None)
                for actor in getattr(oracle.runtime.fight, "actors", {}).values()
            }
        )
        if hasattr(oracle.runtime.fight, "native_global_pv_collections"):
            for actor in oracle.runtime.fight.actors.values():
                if actor.hp <= 0:
                    continue
                properties = observed_properties.get(actor.id)
                if not isinstance(properties, frozenset) or any(
                    type(value) is not int for value in properties
                ):
                    raise ValueError("Missing complete native AI visibility properties")
        self.unobserved_actor_ids = frozenset(
            actor.id
            for actor in getattr(oracle.runtime.fight, "actors", {}).values()
            if observer is not None
            and effective_affiliation(oracle.runtime.fight, actor)
            != effective_affiliation(oracle.runtime.fight, observer)
            and {5, 18}.intersection(observed_properties.get(actor.id) or ())
        )
        area_provider = getattr(oracle, "unobserved_areas", None)
        self.unobserved_area_ids = (
            area_provider(oracle.runtime) if callable(area_provider) else frozenset()
        )

        def capture_source_baseline():
            components = self._source_components()
            source = fingerprint(components)
            baseline_started = time.monotonic()
            self._source_diagnostic_baseline = self._fingerprint_source_diagnostics(
                components
            )
            self.source_diagnostic_baseline_ms = max(
                0.0, (time.monotonic() - baseline_started) * 1000
            )
            return source

        self.source = self._measure_preparation("source_hash", capture_source_baseline)
        self.root = self._measure_preparation(
            "root_register", lambda: self.register(oracle.runtime)
        )
        self.continuation_binding = turn_continuation.binding(
            oracle.runtime,
            instance=self.fight_instance_id,
            catalog=self.catalog,
            policy_version=self.policy_version,
            policy=self.policy,
            source=self.source,
            root=self.root,
            request=self.request_id,
        )

    def _measure_preparation(self, stage, operation):
        started = time.monotonic()
        try:
            return operation()
        finally:
            self.preparation_stages_ms[stage] = (
                self.preparation_stages_ms.get(stage, 0.0)
                + (time.monotonic() - started) * 1000
            )

    def _source_components(self):
        return dict(
            runtime=self.oracle.runtime,
            authorities=self.oracle.authorities(),
            policy=self.policy,
            flags=self.oracle.flags,
            source=dict(
                catalog=self.catalog,
                fightInstanceId=self.fight_instance_id,
                policyVersion=self.policy_version,
            ),
        )

    @staticmethod
    def _fingerprint_source_diagnostics(components):
        """Store value-free fingerprints used only to explain fatal mismatches."""
        runtime = components["runtime"]
        fields = vars(runtime) if hasattr(runtime, "__dict__") else {}
        return dict(
            components={name: fingerprint(value) for name, value in components.items()},
            runtime_fields={name: fingerprint(value) for name, value in fields.items()},
        )

    @staticmethod
    def _source_change_labels(components, baseline):
        current = NativeSession._fingerprint_source_diagnostics(components)
        changed_components = sorted(
            name
            for name, digest in baseline["components"].items()
            if current["components"].get(name) != digest
        )
        changed_components.extend(
            sorted(set(current["components"]) - set(baseline["components"]))
        )
        fields = current["runtime_fields"]
        old_fields = baseline["runtime_fields"]
        changed_fields = sorted(
            name
            for name in set(fields) | set(old_fields)
            if fields.get(name) != old_fields.get(name)
        )
        # The aggregate source fingerprint also covers aliases across component
        # boundaries. If those change while every component hash remains equal,
        # keep the rejection fatal and label the cause as opaque aliasing.
        if not changed_components:
            changed_components = ["unknown_alias_or_structure"]
        return changed_components, changed_fields

    def guard(self):
        check()

        def current_source():
            components = self._source_components()
            return components, fingerprint(components)

        components, current = self._measure_native_query("source_guard", current_source)
        if self.source != current:
            changed_components, changed_fields = self._source_change_labels(
                components, self._source_diagnostic_baseline
            )
            detail = ", ".join(changed_components)
            if changed_fields:
                detail += "; runtime_fields=" + ",".join(changed_fields)
            raise ValueError(
                "Native oracle source changed during decision [" + detail + "]"
            )

    def register(self, runtime, *, transition=None):
        check()
        if getattr(self.transport, "native_graph_parts", False) and hasattr(
            self.oracle, "complete_state_parts"
        ):
            digest = self.transport.instance_parts(
                self.oracle.complete_state_parts(runtime, transition)
            )
        elif transition is not None:
            if hasattr(self.oracle, "complete_transition_bytes") and hasattr(
                self.transport, "instance_bytes"
            ):
                digest = self.transport.instance_bytes(
                    self.oracle.complete_transition_bytes(runtime, transition)
                )
            elif hasattr(self.oracle, "complete_transition_state"):
                digest = self.transport.instance(
                    self.oracle.complete_transition_state(runtime, transition)
                )
            else:
                # Legacy/custom oracle: retain its entire original graph too,
                # rather than replacing any future fields with SDK guesses.
                digest = self.transport.instance(
                    encode(
                        dict(
                            runtime=runtime,
                            completeState=self.oracle.complete_state(runtime),
                            transition=transition,
                        )
                    )
                )
        elif hasattr(self.oracle, "complete_state_bytes") and hasattr(
            self.transport, "instance_bytes"
        ):
            payload = self._measure_preparation(
                "state_encoding", lambda: self.oracle.complete_state_bytes(runtime)
            )
            digest = self._measure_preparation(
                "state_publication", lambda: self.transport.instance_bytes(payload)
            )
        else:
            digest = self.transport.instance(self.oracle.complete_state(runtime))
        if digest not in self.states:
            self.states[digest] = runtime
            self.state_identities[digest] = (
                self._measure_preparation(
                    "runtime_identity", lambda: self.oracle.state_identity(runtime)
                )
                if hasattr(self.oracle, "state_identity")
                else hashlib.sha256(
                    _json_bytes(self.oracle.complete_state(runtime))
                ).hexdigest()
            )
        return digest

    def describe(self, key):
        from wakfu_server.combat_obstacle_condition import footprint

        from ..planning.topology_distance import measure
        from ..native.native_control import effective_affiliation
        from ..native.native_facings import measure as facing_measure

        if key not in self.states:
            raise ValueError("Unknown native oracle state")
        runtime, actors = self.states[key], []
        for actor in sorted(runtime.fight.actors.values(), key=lambda a: a.id):
            if actor.id in getattr(self, "unobserved_actor_ids", ()):
                continue
            # Public metrics are convenient views. The complete native fields
            # remain in the associated verified native snapshot, without loss.
            if not isinstance(actor.effect_stats, dict) or any(
                k not in actor.effect_stats for k in (4, 97)
            ):
                raise ValueError("Missing complete native actor resource context")
            actors.append(
                dict(
                    id=actor.id,
                    team=effective_affiliation(runtime.fight, actor),
                    controlled=actor.controlled,
                    position=list(actor.position),
                    hp=actor.hp,
                    max_hp=actor.max_hp,
                    ap=actor.ap,
                    mp=actor.mp,
                    wp=actor.effect_stats[4],
                    armor=actor.effect_stats[97],
                    registeredSummon=actor.id
                    in getattr(runtime.fight, "native_summon_registrations", {}),
                    blockingFootprint=(
                        [
                            list(cell)
                            for cell in footprint(actor.position, actor.physical_radius)
                        ]
                        if hasattr(actor, "physical_radius")
                        else None
                    ),
                    blocksNativeLos=(
                        actor.native_obstacle_id
                        not in getattr(
                            runtime.fight,
                            "native_los_ignored_affiliations",
                            frozenset(),
                        )
                        if hasattr(actor, "native_obstacle_id")
                        else None
                    ),
                    direction=getattr(actor, "direction", None),
                )
            )
        fight = runtime.fight
        from .actor_repertoires import actor_repertoires

        repertoire_cache = getattr(self, "_actor_repertoire_cache", None)
        if repertoire_cache is None:
            repertoire_cache = self._actor_repertoire_cache = {}
        observation_key = (key, tuple(actor["id"] for actor in actors))
        if observation_key not in repertoire_cache:
            repertoire_cache[observation_key] = actor_repertoires(
                self.oracle,
                fight,
                actors,
                source_state=key,
                capabilities=_advisory_spell_capabilities,
            )
        repertoires = repertoire_cache[observation_key]
        description = dict(
            key=key,
            actorRepertoires=repertoires,
            nativeContext=key,
            runtimeIdentity=self.state_identities[key],
            actors=actors,
            phase=fight.phase,
            currentId=fight.current.id if fight.current is not None else None,
            turnId=fight.turn_id,
            stateRevision=fight.sequence,
            **facing_measure(fight),
            **measure(
                fight.walkable,
                fight.edges,
                actors,
                actor_id=fight.current.id if fight.current is not None else None,
            )
        )
        # Facings are also position information. They must follow exactly
        # the same observation scope as topology and scoring actor metrics.
        for identity in getattr(self, "unobserved_actor_ids", ()):
            description["nativeFacings"].pop(str(identity), None)
        if hasattr(self.oracle, "outcome_features"):
            measurements = self.oracle.outcome_features(runtime)
            # Arbitrary feature providers operate on complete authority and
            # have no visibility contract; do not expose their private deltas.
            if measurements is not None and not (
                getattr(self, "unobserved_actor_ids", ())
                or getattr(self, "unobserved_area_ids", ())
            ):
                description["outcomeFeatures"] = measurements
        return description

    @staticmethod
    def _budget_hint():
        available = remaining()
        return {} if available is None else dict(nativeBudgetMs=available * 1000)

    def envelope(self):
        from ..planning.team_blackboard import team_context

        self.guard()
        root = self.describe(self.root)
        coordination = team_context(
            self.oracle.runtime.fight,
            self.fight_instance_id,
            self.oracle.runtime.fight.current.id,
        )
        if coordination.get("focusId") in self.unobserved_actor_ids:
            coordination = dict(coordination, focusId=None)
        if self.unobserved_actor_ids and "corridors" in coordination:
            corridors = [
                row
                for row in coordination["corridors"]
                if row.get("targetId") not in self.unobserved_actor_ids
            ]
            coordination = dict(
                coordination,
                corridors=corridors,
                reservedCells=[
                    list(cell)
                    for cell in sorted(
                        {tuple(cell) for row in corridors for cell in row["cells"]}
                    )
                ],
            )
        holder = turn_continuation.current()
        continuation = (
            holder.proposal(self.oracle.runtime, self.continuation_binding)
            if holder is not None
            else None
        )
        return dict(
            protocol=3,
            requestId=self.request_id,
            sourceKey=self.source,
            fightInstanceId=self.fight_instance_id,
            fight_id=self.oracle.runtime.fight.id,
            actor_id=self.oracle.runtime.fight.current.id,
            current_id=root["currentId"],
            turnId=root["turnId"],
            stateRevision=root["stateRevision"],
            catalogManifest=self.catalog,
            policyVersion=self.policy_version,
            policy=self.policy,
            rootState=self.root,
            root=root,
            teamContext=coordination,
            operations=list(self.OPERATIONS),
            **({"warmStart": continuation} if continuation is not None else {}),
            **self._budget_hint()
        )

    def decide(self, *, max_queries=8192, certify=True):
        """Drive HTTP negotiation on the owner thread; never commit previews."""
        if type(certify) is not bool:
            raise ValueError("Invalid native decision certification mode")
        if type(max_queries) is not int or max_queries < 1:
            raise ValueError("Invalid native query budget")
        payload, count = self.envelope(), 0
        incumbent = None
        backend_started = False
        begin_bundle = getattr(self.transport, "begin_context_bundle", None)
        continue_bundle = getattr(self.transport, "continue_with_context", None)
        abort_bundle = getattr(self.transport, "abort_context_bundle", None)
        bundled = all(
            callable(method)
            for method in (
                begin_bundle,
                continue_bundle,
                abort_bundle,
            )
        )
        while True:
            self.guard()
            rpc_started = clock_now()
            try:
                with query_budget(reserve_ms=self.policy.get("commitReserveMs", 500)):
                    backend_started = True
                    reply = (
                        continue_bundle(payload)
                        if bundled
                        else self.transport._retry_request("/v3/decide", payload)
                    )
            except TimeoutError:
                if bundled:
                    abort_bundle()
                self.needs_cleanup = backend_started
                return self._partial_decision(incumbent)
            except urllib.error.URLError as error:
                if not isinstance(error.reason, TimeoutError):
                    raise
                if bundled:
                    abort_bundle()
                self.needs_cleanup = backend_started
                return self._partial_decision(incumbent)
            if not isinstance(reply, dict):
                raise ValueError("Invalid AI native search reply")
            if reply.get("status") == "decided":
                decision = reply.get("decision")
                if (
                    not isinstance(decision, dict)
                    or decision.get("protocol") != 3
                    or decision.get("requestId") != self.request_id
                    or decision.get("sourceKey") != self.source
                    or decision.get("rootState") != self.root
                ):
                    raise ValueError("AI decision belongs to a foreign source")
                # Standalone callers receive a freshly certified action. The
                # turn driver immediately stages an authoritative commit,
                # which already validates the action against the live source.
                # Avoid simulating that same action a second time there.
                if certify:
                    self.oracle.preview(self.oracle.runtime, decision.get("action"))
                self.guard()
                return decision
            queries = reply.get("queries")
            if (
                reply.get("status") != "query"
                or reply.get("requestId") != self.request_id
                or reply.get("sourceKey") != self.source
                or not isinstance(queries, list)
                or len(queries) != 1
            ):
                raise ValueError("Invalid AI native search query exchange")
            if "incumbent" in reply:
                if reply["incumbent"] is None:
                    # Risk evaluation explicitly retires an earlier raw
                    # outcome until a comparable assessed option is ready.
                    incumbent = None
                else:
                    proposed = self._certified_incumbent(reply["incumbent"])
                    if proposed is not None:
                        incumbent = proposed
            count += 1
            if count > max_queries:
                raise ValueError("Native AI query budget exhausted")
            query = queries[0]
            allowance = (
                query.get("searchAllowanceMs") if isinstance(query, dict) else None
            )
            if (
                type(allowance) in (int, float)
                and math.isfinite(allowance)
                and allowance >= 0
            ):
                # A frozen retry reply must not restart an old risk/search
                # slice after network delay. Subtract the full observed RPC
                # interval conservatively, without comparing remote clocks.
                query = dict(
                    query,
                    searchAllowanceMs=max(
                        0.0, allowance - max(0.0, clock_now() - rpc_started) * 1000
                    ),
                )
            if bundled:
                begin_bundle()
            try:
                response = self.query(query)
            except BaseException:
                if bundled:
                    abort_bundle()
                raise
            if bundled and (
                not isinstance(response, dict) or response.get("supported") is not True
            ):
                # A rejected query cannot refer to partially produced context.
                abort_bundle()
            payload = dict(
                requestId=self.request_id, sourceKey=self.source, response=response
            )

    @staticmethod
    def _action_key(action):
        try:
            return json.dumps(
                action, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError):
            return None

    def _certified_incumbent(self, candidate):
        """Accept only a current-source first action already previewed by World."""
        required = {
            "protocol",
            "requestId",
            "sourceKey",
            "rootState",
            "action",
            "plan",
            "partial",
            "unknownDependencies",
        }
        if (
            not isinstance(candidate, dict)
            or set(candidate) != required
            or type(candidate["protocol"]) is not int
            or candidate["protocol"] != 3
            or candidate["requestId"] != self.request_id
            or candidate["sourceKey"] != self.source
            or candidate["rootState"] != self.root
            or candidate["partial"] is not True
            or not isinstance(candidate["action"], dict)
            or not isinstance(candidate["plan"], list)
            or len(candidate["plan"]) != 1
            or candidate["plan"][0] != candidate["action"]
            or not isinstance(candidate["unknownDependencies"], list)
            or not 1 <= len(candidate["unknownDependencies"]) <= 16
            or any(
                not isinstance(value, str) or len(value) > 256
                for value in candidate["unknownDependencies"]
            )
        ):
            return None
        identity = self._action_key(candidate["action"])
        if identity is None or identity not in getattr(
            self, "_certified_root_actions", ()
        ):
            return None
        return deepcopy(candidate)

    def _partial_decision(self, incumbent):
        # The owner deadline and complete source guard still apply. A timed
        # out RPC never authorizes a forecast adoption or revives the turn.
        self.guard()
        decision = dict(
            protocol=3,
            requestId=self.request_id,
            sourceKey=self.source,
            rootState=self.root,
            action=dict(type="end_turn"),
            plan=[],
            partial=True,
            reason="native_search_allowance_exhausted",
            unknownDependencies=["native_search_budget_partial"],
        )
        if incumbent is not None:
            try:
                # Mandatory even when decide(certify=False) was requested:
                # timeout recovery must recertify its earlier first action.
                self.oracle.preview(self.oracle.runtime, incumbent["action"])
            except ValueError:
                decision["unknownDependencies"].append(
                    "native_partial_action_recertification_rejected"
                )
            else:
                decision["action"] = deepcopy(incumbent["action"])
                decision["plan"] = [deepcopy(incumbent["action"])]
                decision["unknownDependencies"] = list(
                    dict.fromkeys(
                        incumbent["unknownDependencies"]
                        + decision["unknownDependencies"]
                    )
                )
        self.guard()
        return decision

    def cancel(self):
        # One bounded attempt; retries must not extend an exhausted turn.
        abort_bundle = getattr(self.transport, "abort_context_bundle", None)
        if callable(abort_bundle):
            abort_bundle()
        response = self.transport.request(
            "/v3/cancel", dict(requestId=self.request_id, sourceKey=self.source)
        )
        self.needs_cleanup = False
        return response

    def query(self, request):
        self.guard()
        if not isinstance(request, dict) or type(request.get("id")) is not str:
            raise ValueError("Invalid native oracle request")
        operation, key = request.get("operation"), request.get("state")
        if key not in self.states:
            raise ValueError("Native oracle query referenced a foreign state")
        if operation not in self.OPERATIONS:
            raise ValueError("Unknown native oracle operation")
        try:
            with query_budget(
                allowance_ms=request.get("searchAllowanceMs"),
                reserve_ms=self.policy.get("commitReserveMs", 500),
            ):
                result = self._query(operation, key, request)
        except NativeSearchAllowanceExceeded:
            self.guard()
            return dict(
                id=request["id"],
                supported=False,
                unknownDependencies=["native_search_allowance_exhausted"],
                **self._budget_hint()
            )
        except ValueError as error:
            # An illegal or unsupported native candidate is a query outcome.
            # Source mismatch and foreign references remain fatal above/below.
            self.guard()
            return dict(
                id=request["id"],
                supported=False,
                unknownDependencies=[str(error)],
                **self._budget_hint()
            )
        self.guard()
        if operation == "preview" and key == getattr(self, "root", None):
            identity = self._action_key(request.get("action"))
            if identity is not None:
                if not hasattr(self, "_certified_root_actions"):
                    self._certified_root_actions = set()
                self._certified_root_actions.add(identity)
        return dict(
            id=request["id"], supported=True, result=result, **self._budget_hint()
        )

    def _measure_native_query(self, name, operation):
        started, cpu_started = time.monotonic(), time.thread_time()
        failed = False
        try:
            return operation()
        except BaseException:
            failed = True
            raise
        finally:
            wall_ms = max(0.0, (time.monotonic() - started) * 1000)
            cpu_ms = max(0.0, (time.thread_time() - cpu_started) * 1000)
            metric = self.native_query_metrics.setdefault(
                name,
                dict(calls=0, failures=0, wallMs=0.0, threadCpuMs=0.0, maxWallMs=0.0),
            )
            metric["calls"] += 1
            metric["failures"] += int(failed)
            metric["wallMs"] += wall_ms
            metric["threadCpuMs"] += cpu_ms
            metric["maxWallMs"] = max(metric["maxWallMs"], wall_ms)

    def _query(self, operation, key, request):
        name = operation
        action = request.get("action")
        if operation == "preview" and isinstance(action, dict):
            kind = action.get("type")
            name += ":" + (
                kind
                if kind in ("cast", "move", "portal_travel", "end_turn")
                else "other"
            )
        from wakfu_server.combat_observation_scope import unobserved_area_forecast

        # This encloses preview, fallback previews, and every projected turn
        # boundary. The scope ends before certification or real publication.
        with unobserved_area_forecast(getattr(self, "unobserved_area_ids", ())):
            return self._measure_native_query(
                name, lambda: self._query_unmeasured(operation, key, request)
            )

    def _query_unmeasured(self, operation, key, request):
        runtime = self.states[key]
        if operation == "state":
            result = self.describe(key)
        elif operation == "preview":
            action = request.get("action")
            samples = []
            if hasattr(self.oracle, "preview_with_evidence"):
                (
                    private,
                    packets,
                    transaction,
                    samples,
                ) = self._measure_native_query(
                    "preview_execution",
                    lambda: self.oracle.preview_with_evidence(runtime, action),
                )
            else:
                private, packets, transaction = self._measure_native_query(
                    "preview_execution", lambda: self.oracle.preview(runtime, action)
                )
            check()
            result = self.describe(
                self.register(
                    private,
                    transition=dict(
                        sourceState=key,
                        action=action,
                        packets=packets,
                        transaction=transaction,
                        damageContexts=samples,
                        publication="uncommitted_native_preview",
                    ),
                )
            )
            result["transitionContext"] = result["nativeContext"]
            from ..native.native_damage_observer import evidence

            observed_damage = evidence(samples)
            hidden = getattr(self, "unobserved_actor_ids", ())
            result["damageContextEvidence"] = [
                row
                for row in observed_damage
                if not hidden
                or (
                    not row.get("observationUnavailable")
                    and row.get("casterId") not in hidden
                    and row.get("targetId") not in hidden
                )
            ]
        elif operation == "line_of_sight":
            result = dict(
                visible=self.oracle.visible(
                    runtime.fight, tuple(request["source"]), tuple(request["target"])
                )
            )
        elif operation == "repertoire":
            from wakfu_server.combat_native_spell_casting import (
                catalog as native_casting,
            )
            from wakfu_server.spell_audit import catalog as native_effects
            from wakfu_server.spells import SPELLS

            actor_id = request.get("actorId", runtime.fight.current.id)
            if actor_id in getattr(self, "unobserved_actor_ids", ()):
                raise ValueError("Unobserved actor cannot supply AI repertoire")
            owned = self.oracle.owned_spells(runtime.fight, actor_id)
            metadata = dict(
                actorId=actor_id,
                spells=self._spell_metadata_cache.rows(
                    owned,
                    lambda spell, level: dict(
                        spellId=spell,
                        level=level,
                        casting=native_casting().get(str(spell)),
                        classDefinition=native_effects()["spells"].get(str(spell)),
                        classInventory=SPELLS.get(spell),
                        advisoryCapabilities=_advisory_spell_capabilities(spell, level),
                    ),
                ),
            )
            from ..native.native_portal_travel import portal_destinations

            metadata["nativePortalTravel"] = self._measure_native_query(
                "repertoire_portal_travel",
                lambda: portal_destinations(
                    self.oracle, runtime, actor_id, source_state=key
                ),
            )
            prerequisite_provider = getattr(
                self.oracle, "native_casting_root_prerequisites", None
            )
            prerequisites = (
                self._measure_native_query(
                    "repertoire_casting_prerequisites",
                    lambda: prerequisite_provider(
                        runtime.fight,
                        actor_id,
                        source_state=key,
                        owned_spells=owned,
                    ),
                )
                if callable(prerequisite_provider)
                else None
            )
            if prerequisites is not None:
                metadata["nativeCastingPrerequisites"] = prerequisites
            from ..planning.casting_prerequisites import (
                all_owned_spells_unavailable,
            )

            all_unavailable = all_owned_spells_unavailable(
                metadata,
                dict(key=key, stateRevision=runtime.fight.sequence),
                actor_id,
            )
            target_envelope_provider = getattr(
                self.oracle, "native_target_envelope", None
            )
            target_envelope = (
                self._measure_native_query(
                    "repertoire_target_envelope",
                    lambda: target_envelope_provider(
                        runtime.fight, actor_id, action_id=runtime.action_id
                    ),
                )
                if callable(target_envelope_provider) and not all_unavailable
                else None
            )
            if target_envelope is not None:
                metadata["nativeTargetEnvelope"] = target_envelope
            instance_bytes = getattr(self.transport, "instance_bytes", None)
            if callable(instance_bytes):
                # Preserve the identical complete graph while serializing
                # nodes directly, avoiding a second full mutable graph tree.
                metadata_instance = instance_bytes(encode_bytes(metadata))
            else:
                metadata_instance = self.transport.instance(encode(metadata))
            result = dict(nativeMetadata=metadata_instance)
        elif operation == "project_turn":
            target = request.get("actorId")
            maximum = request.get("maxTurns", len(runtime.fight.actors))
            if (
                type(target) is not int
                or target in getattr(self, "unobserved_actor_ids", ())
                or target not in runtime.fight.actors
                or runtime.fight.actors[target].hp <= 0
                or type(maximum) is not int
                or not 1 <= maximum <= len(runtime.fight.actors)
            ):
                raise ValueError("Invalid native turn projection")
            private = self._measure_native_query(
                "projection_fork", lambda: self.oracle.fork(runtime=runtime)
            )
            skipped = []
            for _ in range(maximum):
                if private.fight.phase != "active" or private.fight.current is None:
                    raise ValueError("Combat finished before requested native turn")
                if private.fight.current.id == target:
                    break
                skipped.append(private.fight.current.id)
                private, _, _ = self._measure_native_query(
                    "projection_boundary",
                    lambda: self.oracle.preview(private, {"type": "end_turn"}),
                )
            if private.fight.current is None or private.fight.current.id != target:
                raise ValueError("Native turn projection horizon exhausted")
            result = dict(
                **self.describe(self.register(private)),
                skippedActorIds=skipped,
                unknownDependencies=["intervening_actor_actions_not_projected"]
                if skipped
                else []
            )
        else:
            raise ValueError("Unknown native oracle operation")
        return result
