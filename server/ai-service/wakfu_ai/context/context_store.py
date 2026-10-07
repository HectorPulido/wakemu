"""Atomic content-addressed reception of complete contexts and native assets.

Frame size is bounded; total object and catalogue sizes are not truncated.
A context is usable only after every manifest entry has its verified blob.
"""
import hashlib
import gzip
import json
from pathlib import Path, PurePosixPath
import re
import threading
import tempfile
import os
import shutil
import weakref
import uuid


class ContextStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.partial = {}
        self._publication_locks = weakref.WeakValueDictionary()
        self._seal_registry_lock = threading.Lock()
        self._sealed = {}
        self._blob_refs = {}
        self._blob_locks = {}
        self._snapshot_dir = tempfile.mkdtemp(prefix="wakfu-ai-sealed-")
        self._snapshot_cleanup = weakref.finalize(
            self, shutil.rmtree, self._snapshot_dir, True
        )

    def close(self):
        """Close the store and remove its private, immutable catalog copies."""
        with self._seal_registry_lock:
            self._sealed.clear()
            self._blob_refs.clear()
            self._blob_locks.clear()
        # Snapshots are only read through short-lived file handles. Callers
        # must stop using a store before close(), just as for its canonical root.
        self._snapshot_cleanup()

    def _manifest_bytes_and_entries(self, digest):
        manifest = self.json(digest)
        if (
            not isinstance(manifest, dict)
            or set(manifest) != {"format", "entries"}
            or manifest["format"] != "wakfu-complete-context-1"
            or not isinstance(manifest["entries"], list)
        ):
            raise ValueError("Invalid complete context manifest")
        names, objects = set(), {}
        for entry in manifest["entries"]:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
                raise ValueError("Invalid context manifest entry")
            name, size, checksum = entry["path"], entry["size"], entry["sha256"]
            if (
                not isinstance(name, str)
                or not name
                or "\\" in name
                or PurePosixPath(name).is_absolute()
                or any(part in ("", ".", "..") for part in name.split("/"))
                or name in names
                or type(size) is not int
                or size < 0
            ):
                raise ValueError("Invalid context manifest path or size")
            names.add(name)
            self._path(checksum)
            previous = objects.get(checksum)
            if previous is not None and previous != size:
                raise ValueError("Conflicting complete context object sizes")
            objects[checksum] = size
        return manifest, objects

    def _path(self, digest):
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid context content hash")
        return self.root / digest

    def has(self, digest, size=None):
        path = self._path(digest)
        # Canonical blobs are published atomically only after full validation.
        # Hash readers can therefore run concurrently; the global writer lock
        # protects the publication-lock registry and partial-upload metadata.
        # Never cache a successful hash or trust a content-address filename.
        try:
            if not path.is_file() or size is not None and path.stat().st_size != size:
                return False
            checksum = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    checksum.update(block)
            return checksum.hexdigest() == digest
        except FileNotFoundError:
            return False

    def _publication_lock(self, digest):
        # Keep a strong local reference while waiting/working. A lock can
        # disappear only after its last caller releases that reference.
        # Never wait for a digest while holding the registry lock.
        with self.lock:
            lock = self._publication_locks.get(digest)
            if lock is None:
                lock = threading.RLock()
                self._publication_locks[digest] = lock
            return lock

    def put(self, digest, size, offset, data):
        path = self._path(digest)
        if (
            type(size) is not int
            or size < 0
            or type(offset) is not int
            or not 0 <= offset <= size
            or not isinstance(data, bytes)
            or offset + len(data) > size
        ):
            raise ValueError("Invalid context block")
        with self._publication_lock(digest):
            if self.has(digest, size):
                # The same verified object can be retransmitted after a lost
                # response, without creating a second partially-written file.
                # Publication may have succeeded before a subsequent failure
                # prevented removal of its upload metadata.
                (self.root / (digest + ".partial")).unlink(missing_ok=True)
                with self.lock:
                    self.partial.pop(digest, None)
                return dict(complete=True, offset=size)
            temporary = self.root / (digest + ".partial")
            with self.lock:
                entry = self.partial.get(digest)
            if entry is None:
                if offset != 0:
                    raise ValueError("Missing initial context block")
                temporary.write_bytes(b"")
                entry = dict(size=size, offset=0, checksum=hashlib.sha256())
                with self.lock:
                    self.partial[digest] = entry
            if entry["size"] != size:
                raise ValueError("Context object size changed")
            if offset < entry["offset"]:
                with temporary.open("rb") as source:
                    source.seek(offset)
                    previous = source.read(len(data))
                if offset + len(data) > entry["offset"] or previous != data:
                    raise ValueError("Conflicting repeated context block")
                if entry["offset"] != size:
                    return dict(complete=False, offset=entry["offset"])
                # A final hash/replace may have failed after all bytes were
                # written. Reverify and publish on retry instead of reporting
                # a permanently incomplete object at its final offset.
            else:
                if offset != entry["offset"]:
                    raise ValueError("Out-of-order context block")
                with temporary.open("r+b") as target:
                    # Retry from the last acknowledged offset, dropping any
                    # bytes left by an interrupted write.
                    target.truncate(entry["offset"])
                    target.seek(entry["offset"])
                    target.write(data)
                entry["checksum"].update(data)
                entry["offset"] += len(data)
            if entry["offset"] != size:
                return dict(complete=False, offset=entry["offset"])
            actual = hashlib.sha256()
            with temporary.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    actual.update(block)
            if temporary.stat().st_size != size or actual.hexdigest() != digest:
                with self.lock:
                    del self.partial[digest]
                temporary.unlink(missing_ok=True)
                raise ValueError("Context content checksum mismatch")
            temporary.replace(path)
            with self.lock:
                del self.partial[digest]
            return dict(complete=True, offset=size)

    def read(self, digest):
        # Writers publish complete canonical blobs by atomic replacement. A
        # reader verifies the exact bytes it returns, so a prior has() scan
        # and the global partial-upload lock add neither consistency nor data.
        path = self._path(digest)
        try:
            data = path.read_bytes()
        except (FileNotFoundError, IsADirectoryError) as error:
            raise ValueError("Missing verified context content") from error
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Context content changed while reading")
        return data

    def import_file(self, source, digest, size):
        """Import a provisioned asset locally, without HTTP or size limits."""
        destination = self._path(digest)
        with self._publication_lock(digest):
            if self.has(digest, size):
                return
            temporary = None
            try:
                checksum, total = hashlib.sha256(), 0
                with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as target:
                    temporary = Path(target.name)
                    with Path(source).open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            checksum.update(block)
                            total += len(block)
                            target.write(block)
                if total != size or checksum.hexdigest() != digest:
                    raise ValueError("Provisioned catalogue asset changed")
                temporary.replace(destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def json(self, digest):
        data = self.read(digest)
        if data.startswith(b"\x1f\x8b"):
            try:
                data = gzip.decompress(data)
            except (OSError, EOFError) as error:
                raise ValueError("Invalid compressed complete context") from error
        return json.loads(data)

    def manifest(self, digest):
        manifest, objects = self._manifest_bytes_and_entries(digest)
        missing = [
            checksum
            for checksum, size in objects.items()
            if not self.has(checksum, size)
        ]
        return dict(
            complete=not missing,
            missing=sorted(missing),
            entries=len(manifest["entries"]),
        )

    @staticmethod
    def _file_identity(stat):
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )

    def _check_frozen_ref(self, ref):
        try:
            identity = self._file_identity(Path(ref["path"]).stat())
        except FileNotFoundError as error:
            raise ValueError("Sealed catalogue snapshot changed") from error
        if identity != ref["identity"]:
            raise ValueError("Sealed catalogue snapshot changed")

    def _check_snapshot_archives(self, snapshot):
        checked = set()
        for ref in snapshot["blobs"].values():
            key = ref["path"], ref["identity"]
            if key not in checked:
                self._check_frozen_ref(ref)
                checked.add(key)

    def _capture_manifest(self, manifest_digest):
        manifest_raw = self.read(manifest_digest)
        manifest, objects = self._manifest_bytes_and_entries(manifest_digest)
        # Preserve exact manifest bytes, while sharing previously frozen blobs
        # across catalogue versions. Each archive contains only new blobs.
        objects = dict(objects)
        if manifest_digest in objects and objects[manifest_digest] != len(manifest_raw):
            raise ValueError("Conflicting complete context object sizes")
        objects[manifest_digest] = len(manifest_raw)
        missing = []
        refs = {}
        checked_archives = set()
        pending_offsets = {}
        held_locks = []
        temporary = None
        published = None
        registered = False
        try:
            with tempfile.NamedTemporaryFile(
                dir=self._snapshot_dir, delete=False
            ) as target:
                temporary = Path(target.name)
                for digest in sorted(objects):
                    expected_size = objects[digest]
                    with self._seal_registry_lock:
                        ref = self._blob_refs.get(digest)
                        blob_lock = (
                            None
                            if ref is not None
                            else self._blob_locks.setdefault(digest, threading.Lock())
                        )
                    if ref is None:
                        blob_lock.acquire()
                        held_locks.append(blob_lock)
                        with self._seal_registry_lock:
                            ref = self._blob_refs.get(digest)
                    if ref is not None:
                        if ref["size"] != expected_size:
                            raise ValueError(
                                "Conflicting complete context object sizes"
                            )
                        archive_key = ref["path"], ref["identity"]
                        if archive_key not in checked_archives:
                            self._check_frozen_ref(ref)
                            checked_archives.add(archive_key)
                        refs[digest] = ref
                        continue

                    if digest == manifest_digest:
                        offset, size = target.tell(), len(manifest_raw)
                        if hashlib.sha256(manifest_raw).hexdigest() != digest:
                            raise ValueError("Context content checksum mismatch")
                        target.write(manifest_raw)
                    else:
                        path = self._path(digest)
                        try:
                            before_path = path.stat()
                            source = path.open("rb")
                        except FileNotFoundError:
                            missing.append(digest)
                            continue
                        before_fd = os.fstat(source.fileno())
                        if self._file_identity(before_path) != self._file_identity(
                            before_fd
                        ):
                            source.close()
                            raise ValueError("Context content changed while sealing")
                        if before_fd.st_size != expected_size:
                            source.close()
                            raise ValueError("Context content checksum mismatch")
                        checksum = hashlib.sha256()
                        total = 0
                        offset = target.tell()
                        try:
                            while True:
                                block = source.read(1024 * 1024)
                                if not block:
                                    break
                                checksum.update(block)
                                target.write(block)
                                total += len(block)
                            after_fd = os.fstat(source.fileno())
                        finally:
                            source.close()
                        try:
                            after_path = path.stat()
                        except FileNotFoundError as error:
                            raise ValueError(
                                "Context content changed while sealing"
                            ) from error
                        if (
                            self._file_identity(before_fd)
                            != self._file_identity(after_fd)
                            or self._file_identity(before_fd)
                            != self._file_identity(after_path)
                            or total != expected_size
                            or checksum.hexdigest() != digest
                        ):
                            raise ValueError("Context content changed while sealing")
                        size = total
                    if size != expected_size:
                        raise ValueError("Context content checksum mismatch")
                    pending_offsets[digest] = (offset, size)
                target.flush()
                os.fsync(target.fileno())
            if missing:
                return (
                    dict(
                        complete=False,
                        missing=sorted(set(missing)),
                        entries=len(manifest["entries"]),
                    ),
                    None,
                )
            if pending_offsets:
                os.chmod(temporary, 0o400)
                published = Path(self._snapshot_dir) / ("delta-" + uuid.uuid4().hex)
                os.replace(temporary, published)
                temporary = None
                archive_identity = self._file_identity(published.stat())
                pending_refs = {
                    digest: dict(
                        path=str(published),
                        offset=offset,
                        size=size,
                        identity=archive_identity,
                    )
                    for digest, (offset, size) in pending_offsets.items()
                }
                refs.update(pending_refs)
            else:
                pending_refs = {}
            result = dict(complete=True, missing=[], entries=len(manifest["entries"]))
            snapshot = dict(blobs=refs, manifest=manifest)
            # Recheck every reused/new archive just before publishing the
            # manifest, once per archive even when many blobs share its delta.
            self._check_snapshot_archives(snapshot)
            with self._seal_registry_lock:
                # Only verified immutable objects from a complete delta enter
                # the cross-version registry.
                self._blob_refs.update(pending_refs)
                registered = True
            return result, snapshot
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if published is not None and not registered:
                published.unlink(missing_ok=True)
            for blob_lock in reversed(held_locks):
                blob_lock.release()

    def seal_manifest(self, digest):
        """Verify and freeze all catalogue bytes in a private immutable copy.

        Repeated calls for a completed manifest use only the sealed copy;
        canonical blobs are still independently checked by has/read/manifest.
        """
        self._path(digest)
        with self._seal_registry_lock:
            entry = self._sealed.get(digest)
            creator = entry is None
            if creator:
                entry = {
                    "lock": threading.RLock(),
                    "ready": False,
                    "result": None,
                    "snapshot": None,
                }
                entry["lock"].acquire()
                self._sealed[digest] = entry
        if not creator:
            with entry["lock"]:
                if entry["ready"]:
                    self._check_snapshot_archives(entry["snapshot"])
                    return dict(entry["result"])
                if entry.get("error") is not None:
                    raise entry["error"]
                # Incomplete captures are not retained; the caller which sees
                # one can safely retry after uploading the reported objects.
                return dict(
                    entry["result"] or dict(complete=False, missing=[digest], entries=0)
                )
        try:
            result, snapshot = self._capture_manifest(digest)
            entry["result"] = result
            entry["snapshot"] = snapshot
            entry["ready"] = bool(result["complete"])
            return dict(result)
        except BaseException as error:
            entry["error"] = error
            with self._seal_registry_lock:
                if self._sealed.get(digest) is entry:
                    self._sealed.pop(digest, None)
            raise
        finally:
            entry["lock"].release()
            if not entry["ready"]:
                with self._seal_registry_lock:
                    if self._sealed.get(digest) is entry:
                        self._sealed.pop(digest, None)

    def read_catalog(self, manifest_digest, digest):
        self._path(manifest_digest)
        self._path(digest)
        with self._seal_registry_lock:
            entry = self._sealed.get(manifest_digest)
        if entry is None:
            raise ValueError("Catalogue has not been sealed")
        with entry["lock"]:
            snapshot = entry.get("snapshot")
            if not entry.get("ready") or snapshot is None:
                raise ValueError("Catalogue has not been sealed")
            if digest not in snapshot["blobs"]:
                raise ValueError("Content is not part of sealed catalogue")
            ref = snapshot["blobs"][digest]
            self._check_frozen_ref(ref)
            path = Path(ref["path"])
            try:
                with path.open("rb") as source:
                    before_fd = os.fstat(source.fileno())
                    if self._file_identity(before_fd) != ref["identity"]:
                        raise ValueError("Sealed catalogue snapshot changed")
                    source.seek(ref["offset"])
                    data = source.read(ref["size"])
                    after_fd = os.fstat(source.fileno())
                after_path = path.stat()
            except FileNotFoundError as error:
                raise ValueError("Sealed catalogue snapshot changed") from error
            if (
                self._file_identity(after_fd) != ref["identity"]
                or self._file_identity(after_path) != ref["identity"]
            ):
                raise ValueError("Sealed catalogue snapshot changed")
            if len(data) != ref["size"]:
                raise ValueError("Sealed catalogue snapshot is truncated")
            return data
