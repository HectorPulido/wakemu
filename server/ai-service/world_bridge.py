"""World-side SDK kept in ai-service; the final world shim only loads it.

Transport the complete catalogue, engine and native instance graph. No fields,
assets, actors or history are selected away to satisfy a packet-size limit.
Large objects are streamed as verified content-addressed blocks.
"""
import base64
import hashlib
import io
import gzip
import json
from pathlib import Path
import urllib.request
import urllib.error
import uuid
import tempfile
import os
import weakref
import re
import threading
import time
from types import SimpleNamespace

if __package__:
    from .native_context import encode
    from .native_fingerprint import fingerprint
    from .native_deadline import check, remaining
else:
    from native_context import encode
    from native_fingerprint import fingerprint
    from native_deadline import check, remaining


def _json_bytes(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def _file_hash(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


class CompleteContextExporter:
    def __init__(self, roots, *, files=None, cache_root=None):
        if not isinstance(roots, dict) or not roots:
            raise ValueError("Complete context needs native source roots")
        self.roots = {name: Path(path) for name, path in roots.items()}
        self.files = {name: Path(path) for name, path in (files or {}).items()}
        self.cache = {}
        self._snapshot_identities = {}
        self._cache_index = None
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
        except (OSError, ValueError, UnicodeError):
            # A missing/damaged hint can only cause a full recapture. It can
            # never remove a source or truncate the freshly enumerated graph.
            self.cache.clear()

    def _save_cache_index(self):
        if self._cache_index is None:
            return
        records = []
        for key, (signature, digest, snapshot) in self.cache.items():
            check()
            if isinstance(key, tuple):
                expected = self._snapshot_identities[digest]
                if self._file_identity(snapshot.stat()) != expected:
                    raise ValueError("Native catalogue snapshot changed")
                records.append(
                    dict(
                        key=list(key),
                        signature=list(signature),
                        sha256=digest,
                        snapshotIdentity=list(expected),
                    )
                )
        with tempfile.NamedTemporaryFile(
            dir=self._snapshots.name, delete=False
        ) as target:
            temporary = Path(target.name)
            target.write(_json_bytes(records))
        try:
            check()
            os.replace(temporary, self._cache_index)
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
        entries, sources, names = [], {}, set()

        def files(root):
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
                            result.append((relative, Path(entry.path)))
            # Preserve the previous Path ordering while retaining the exact
            # relative name from enumeration, without rebuilding ancestors.
            return sorted(result, key=lambda pair: pair[1])

        def register(name, path):
            check()
            if name in names:
                raise ValueError("Duplicate complete context asset path")
            names.add(name)
            stat = path.stat()

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
            entries.append(dict(path=name, sha256=digest, size=stat.st_size))
            sources[digest] = snapshot

        for name, root in sorted(self.roots.items()):
            if not root.is_dir():
                raise ValueError("Missing complete context source root: " + name)
            for relative, path in files(root):
                register(name + "/" + relative, path)
        for name, path in sorted(self.files.items()):
            if not path.is_file():
                raise ValueError("Missing complete context source file: " + name)
            register(name, path)
        manifest = dict(format="wakfu-complete-context-1", entries=entries)
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
        self, url, *, timeout=10, block_bytes=1024 * 1024, native_graph_parts=False
    ):
        if type(block_bytes) is not int or not 1 <= block_bytes <= 2 * 1024 * 1024:
            raise ValueError("Invalid context transport block size")
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.block_bytes = block_bytes
        if type(native_graph_parts) is not bool:
            raise ValueError("Invalid native graph parts switch")
        self.native_graph_parts = native_graph_parts

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

    def request(self, endpoint, payload):
        check()
        request = urllib.request.Request(
            self.url + endpoint,
            data=_json_bytes(payload),
            headers={"Content-Type": "application/json"},
        )
        available = remaining()
        timeout = self.timeout if available is None else min(self.timeout, available)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
        check()
        return result

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
            reply = self._retry_request(
                "/v3/context/block",
                dict(
                    sha256=digest,
                    size=size,
                    offset=offset,
                    data=base64.b64encode(block).decode("ascii"),
                ),
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

    def catalog(self, exporter):
        manifest, sources = exporter.inventory()
        digest = self.bytes(_json_bytes(manifest))
        sealed = self._retry_request("/v3/context/seal", dict(sha256=digest))
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
                self._upload(source, checksum, entry["size"])
        sealed = self._retry_request("/v3/context/seal", dict(sha256=digest))
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
        self.policy, self.policy_version = policy, policy_version
        self.fight_instance_id = fight_instance_id
        check()
        if catalog_manifest is not None and (
            not isinstance(catalog_manifest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", catalog_manifest)
        ):
            raise ValueError("Invalid complete native catalogue manifest")
        # A turn can reuse its fully transferred catalogue. The receiver
        # still verifies the complete manifest on each new search session;
        # runtime snapshots and source guards remain fresh for every action.
        self.catalog = (
            transport.catalog(exporter)
            if catalog_manifest is None
            else catalog_manifest
        )
        self.request_id = uuid.uuid4().hex
        self.states = {}
        self.state_identities = {}
        self.source = self._source_hash()
        self.root = self.register(oracle.runtime)

    def _source_hash(self):
        return fingerprint(
            dict(
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
        )

    def guard(self):
        check()
        if self.source != self._source_hash():
            raise ValueError("Native oracle source changed during decision")

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
            digest = self.transport.instance_bytes(
                self.oracle.complete_state_bytes(runtime)
            )
        else:
            digest = self.transport.instance(self.oracle.complete_state(runtime))
        if digest not in self.states:
            self.states[digest] = runtime
            self.state_identities[digest] = (
                self.oracle.state_identity(runtime)
                if hasattr(self.oracle, "state_identity")
                else hashlib.sha256(
                    _json_bytes(self.oracle.complete_state(runtime))
                ).hexdigest()
            )
        return digest

    def describe(self, key):
        from wakfu_server.combat_obstacle_condition import footprint

        if __package__:
            from .topology_distance import measure
            from .native_facings import measure as facing_measure
        else:
            from topology_distance import measure
            from native_facings import measure as facing_measure
        if key not in self.states:
            raise ValueError("Unknown native oracle state")
        runtime, actors = self.states[key], []
        for actor in sorted(runtime.fight.actors.values(), key=lambda a: a.id):
            # Public metrics are convenient views. The complete native fields
            # remain in the associated verified native snapshot, without loss.
            if not isinstance(actor.effect_stats, dict) or any(
                k not in actor.effect_stats for k in (4, 97)
            ):
                raise ValueError("Missing complete native actor resource context")
            actors.append(
                dict(
                    id=actor.id,
                    team=actor.team,
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
        description = dict(
            key=key,
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
        if hasattr(self.oracle, "outcome_features"):
            measurements = self.oracle.outcome_features(runtime)
            if measurements is not None:
                description["outcomeFeatures"] = measurements
        return description

    @staticmethod
    def _budget_hint():
        available = remaining()
        return {} if available is None else dict(nativeBudgetMs=available * 1000)

    def envelope(self):
        if __package__:
            from .team_blackboard import team_context
        else:
            from team_blackboard import team_context
        self.guard()
        root = self.describe(self.root)
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
            teamContext=team_context(
                self.oracle.runtime.fight,
                self.fight_instance_id,
                self.oracle.runtime.fight.current.id,
            ),
            operations=list(self.OPERATIONS),
            **self._budget_hint()
        )

    def decide(self, *, max_queries=8192, certify=True):
        """Drive HTTP negotiation on the owner thread; never commit previews."""
        if type(certify) is not bool:
            raise ValueError("Invalid native decision certification mode")
        if type(max_queries) is not int or max_queries < 1:
            raise ValueError("Invalid native query budget")
        payload, count = self.envelope(), 0
        while True:
            self.guard()
            reply = self.transport._retry_request("/v3/decide", payload)
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
            count += 1
            if count > max_queries:
                raise ValueError("Native AI query budget exhausted")
            response = self.query(queries[0])
            payload = dict(
                requestId=self.request_id, sourceKey=self.source, response=response
            )

    def cancel(self):
        # One bounded attempt; retries must not extend an exhausted turn.
        return self.transport.request(
            "/v3/cancel", dict(requestId=self.request_id, sourceKey=self.source)
        )

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
            result = self._query(operation, key, request)
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
        return dict(
            id=request["id"], supported=True, result=result, **self._budget_hint()
        )

    def _query(self, operation, key, request):
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
                ) = self.oracle.preview_with_evidence(runtime, action)
            else:
                private, packets, transaction = self.oracle.preview(runtime, action)
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
            if __package__:
                from .native_damage_observer import evidence
            else:
                from native_damage_observer import evidence
            result["damageContextEvidence"] = evidence(samples)
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
            owned = self.oracle.owned_spells(runtime.fight, actor_id)
            metadata = dict(
                actorId=actor_id,
                spells=[
                    dict(
                        spellId=spell,
                        level=level,
                        casting=native_casting().get(str(spell)),
                        classDefinition=native_effects()["spells"].get(str(spell)),
                        classInventory=SPELLS.get(spell),
                    )
                    for spell, level in sorted(owned.items())
                ],
            )
            result = dict(nativeMetadata=self.transport.instance(encode(metadata)))
        elif operation == "project_turn":
            target = request.get("actorId")
            maximum = request.get("maxTurns", len(runtime.fight.actors))
            if (
                type(target) is not int
                or target not in runtime.fight.actors
                or runtime.fight.actors[target].hp <= 0
                or type(maximum) is not int
                or not 1 <= maximum <= len(runtime.fight.actors)
            ):
                raise ValueError("Invalid native turn projection")
            private = self.oracle.fork(runtime=runtime)
            skipped = []
            for _ in range(maximum):
                if private.fight.phase != "active" or private.fight.current is None:
                    raise ValueError("Combat finished before requested native turn")
                if private.fight.current.id == target:
                    break
                skipped.append(private.fight.current.id)
                private, _, _ = self.oracle.preview(private, {"type": "end_turn"})
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
