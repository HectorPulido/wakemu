"""Hash-bound reuse of complete offline module passes observed by a parent.

This module neither executes tests nor qualifies dependency closures. Trusted
callers supply an audited declaration and the actual child exit observation.
"""
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile


SCHEMA = "wakemu-validation-reuse-v1"
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class ReuseIneligible(ValueError):
    """Evidence cannot establish a compatible, complete executed pass."""


class StoreIntegrityError(RuntimeError):
    """Previously published evidence is missing, malformed or altered."""


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _hash(value):
    if type(value) is not str or not _HASH.fullmatch(value):
        raise ReuseIneligible("Explicit SHA256 required")
    return value


def _ids(values):
    if (
        type(values) not in (tuple, list)
        or not values
        or any(type(value) is not str or not value for value in values)
        or len(set(values)) != len(values)
    ):
        raise ReuseIneligible("Complete unique test IDs required")
    return list(values)


def _files(values):
    if type(values) is not dict:
        raise ReuseIneligible("Explicit dependency hash mapping required")
    for name, checksum in values.items():
        path = PurePosixPath(name) if type(name) is str else None
        if (
            path is None
            or not name
            or path.is_absolute()
            or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
        ):
            raise ReuseIneligible("Safe relative dependency name required")
        _hash(checksum)
    return dict(sorted(values.items()))


@dataclass(frozen=True)
class ValidationManifest:
    """Immutable canonical document; accessors always return detached data."""

    encoded: bytes

    def __post_init__(self):
        if type(self.encoded) is not bytes or len(self.encoded) > MAX_ARTIFACT_BYTES:
            raise ReuseIneligible("Canonical manifest bytes required")
        try:
            doc = json.loads(self.encoded)
            canonical = canonical_bytes(doc)
        except (ValueError, UnicodeError) as error:
            raise ReuseIneligible("Invalid manifest JSON") from error
        if canonical != self.encoded:
            raise ReuseIneligible("Noncanonical manifest")
        _validate_manifest(doc)

    @property
    def key(self):
        return hashlib.sha256(self.encoded).hexdigest()

    def as_dict(self):
        return json.loads(self.encoded)


def qualification_binding(document):
    """Bind the declared closure, test selection and verifier implementation."""
    fields = (
        "schema",
        "scope",
        "module",
        "test_ids",
        "source",
        "fixtures",
        "catalog",
        "oracles",
        "declaration",
        "runner",
        "environment",
        "policies",
        "rng",
    )
    return digest({name: document[name] for name in fields})


def _validate_manifest(doc):
    fields = {
        "schema",
        "scope",
        "module",
        "test_ids",
        "source",
        "fixtures",
        "catalog",
        "oracles",
        "declaration",
        "runner",
        "environment",
        "policies",
        "rng",
        "qualification",
    }
    if type(doc) is not dict or set(doc) != fields or doc["schema"] != SCHEMA:
        raise ReuseIneligible("Unsupported manifest schema")
    if type(doc["scope"]) is not str or not doc["scope"]:
        raise ReuseIneligible("Explicit scope required")
    if type(doc["module"]) is not str or not re.fullmatch(
        r"test[A-Za-z0-9_]+", doc["module"]
    ):
        raise ReuseIneligible("Explicit module identity required")
    if doc["test_ids"] != _ids(doc["test_ids"]):
        raise ReuseIneligible("Canonical exact test selection required")
    for name in ("source", "fixtures", "catalog", "oracles"):
        _files(doc[name])
    if not doc["source"]:
        raise ReuseIneligible("Source closure cannot be empty")
    for name in ("declaration", "runner", "environment"):
        _hash(doc[name])
    for name in ("policies", "rng"):
        if type(doc[name]) is not dict:
            raise ReuseIneligible("Explicit policy and RNG inputs required")
    proof = doc["qualification"]
    if (
        type(proof) is not dict
        or set(proof)
        != {"kind", "complete", "deterministic", "external_state", "closure_sha256"}
        or proof["kind"] != "audited-offline-closure-v1"
        or proof["complete"] is not True
        or proof["deterministic"] is not True
        or proof["external_state"] != "none"
        or proof["closure_sha256"] != qualification_binding(doc)
    ):
        raise ReuseIneligible("Complete hash-bound offline qualification required")


def build_manifest(
    *,
    module,
    test_ids,
    source,
    fixtures,
    catalog,
    oracles,
    declaration,
    runner,
    environment,
    policies,
    rng,
    qualification,
    scope="offline-module"
):
    document = dict(
        schema=SCHEMA,
        scope=scope,
        module=module,
        test_ids=_ids(test_ids),
        source=_files(source),
        fixtures=_files(fixtures),
        catalog=_files(catalog),
        oracles=_files(oracles),
        declaration=declaration,
        runner=runner,
        environment=environment,
        policies=policies,
        rng=rng,
        qualification=qualification,
    )
    return ValidationManifest(canonical_bytes(document))


@dataclass(frozen=True)
class ParentObservation:
    status: str
    return_code: int | None
    normal_exit: bool
    invocation_id: str
    invoked_module: str
    scope: str
    runner_sha256: str


@dataclass(frozen=True)
class TerminalReceipt:
    encoded: bytes

    def as_dict(self):
        if type(self.encoded) is not bytes or len(self.encoded) > MAX_ARTIFACT_BYTES:
            raise ReuseIneligible("Bounded terminal receipt bytes required")
        try:
            document = json.loads(self.encoded)
        except (ValueError, UnicodeError) as error:
            raise ReuseIneligible("Invalid receipt JSON") from error
        if type(document) is not dict:
            raise ReuseIneligible("Typed receipt document required")
        return document


@dataclass(frozen=True)
class VerifiedResult:
    receipt: TerminalReceipt
    report_bytes: bytes


def _validate_report(report, manifest):
    document = manifest.as_dict()
    expected = document["test_ids"]
    if type(report) is not dict:
        raise ReuseIneligible("Child report required")
    discovery, result = report.get("discovery", {}), report.get("result", {})
    if type(discovery) is not dict or type(result) is not dict:
        raise ReuseIneligible("Typed discovery and result evidence required")
    if (
        discovery.get("module_names") != [manifest.as_dict()["module"]]
        or type(discovery.get("tests")) is not int
        or discovery["tests"] != len(expected)
        or discovery.get("test_ids") != expected
        or discovery.get("loader_errors") != []
    ):
        raise ReuseIneligible("Incomplete or different discovered test selection")
    if (
        result.get("successful") is not True
        or type(result.get("tests_run")) is not int
        or result["tests_run"] != len(expected)
    ):
        raise ReuseIneligible("Incomplete test execution")
    for field in (
        "failures",
        "errors",
        "skipped",
        "expected_failures",
        "unexpected_successes",
    ):
        if type(result.get(field)) is not int or result[field] != 0:
            raise ReuseIneligible("Only unconditional complete passes can be reused")
    if any(report.get(name) != [] for name in ("failures", "errors", "skipped")):
        raise ReuseIneligible("Contradictory or missing test diagnostics")
    origins = document["policies"].get("import_origins")
    if origins is not None:
        actual = report.get("import_origins")
        if (
            type(origins) is not dict
            or not origins
            or type(actual) is not dict
            or any(actual.get(name) != path for name, path in origins.items())
        ):
            raise ReuseIneligible(
                "Child imported origins differ from qualified closure"
            )
    startup = document["policies"].get("python_startup")
    if startup is not None:
        actual = report.get("python_startup")
        if (
            type(startup) is not dict
            or not startup
            or type(actual) is not dict
            or set(actual) != set(startup)
            or any(
                type(value) is not bool or actual.get(name) is not value
                for name, value in startup.items()
            )
        ):
            raise ReuseIneligible(
                "Child Python startup differs from qualified contract"
            )
    outcomes = report.get("test_outcomes")
    if (
        type(outcomes) is not list
        or len(outcomes) != len(expected)
        or any(
            type(row) is not dict
            or set(row) != {"test_id", "status"}
            or row["status"] != "passed"
            for row in outcomes
        )
        or [row["test_id"] for row in outcomes] != expected
    ):
        raise ReuseIneligible("Exact terminal passing case outcomes required")


def terminal_receipt(manifest_before, manifest_after, observation, report_bytes):
    if (
        type(manifest_before) is not ValidationManifest
        or type(manifest_after) is not ValidationManifest
        or manifest_before.encoded != manifest_after.encoded
    ):
        raise ReuseIneligible("Complete stable before/after inputs required")
    if (
        type(observation) is not ParentObservation
        or observation.status != "completed"
        or type(observation.return_code) is not int
        or observation.return_code != 0
        or observation.normal_exit is not True
        or type(observation.invocation_id) is not str
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", observation.invocation_id)
    ):
        raise ReuseIneligible("Parent-observed normal exit zero required")
    identity = manifest_before.as_dict()
    if (
        observation.invoked_module != identity["module"]
        or observation.scope != identity["scope"]
        or observation.runner_sha256 != identity["runner"]
    ):
        raise ReuseIneligible("Parent invocation differs from manifest")
    if type(report_bytes) is not bytes or len(report_bytes) > MAX_ARTIFACT_BYTES:
        raise ReuseIneligible("Bounded child report bytes required")
    try:
        report = json.loads(report_bytes)
    except (ValueError, UnicodeError) as error:
        raise ReuseIneligible("Invalid child report JSON") from error
    _validate_report(report, manifest_before)
    return TerminalReceipt(
        canonical_bytes(
            dict(
                schema=SCHEMA,
                origin="executed",
                manifest=manifest_before.as_dict(),
                key=manifest_before.key,
                report_sha256=hashlib.sha256(report_bytes).hexdigest(),
                parent=dict(
                    status=observation.status,
                    return_code=observation.return_code,
                    normal_exit=observation.normal_exit,
                    invocation_id=observation.invocation_id,
                    invoked_module=observation.invoked_module,
                    scope=observation.scope,
                    runner_sha256=observation.runner_sha256,
                ),
            )
        )
    )


class LocalResultStore:
    """Private immutable entries retaining original executed evidence only."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise StoreIntegrityError(
                "Result store must be a private nonsymlink directory"
            )

    def _read(self, path):
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > MAX_ARTIFACT_BYTES
        ):
            raise StoreIntegrityError("Missing or unsafe result artifact")
        if path.stat().st_mode & 0o077:
            raise StoreIntegrityError("Result artifact permissions are not private")
        return path.read_bytes()

    def lookup(self, manifest):
        if type(manifest) is not ValidationManifest:
            raise ReuseIneligible("Validated manifest required")
        entry = self.root / manifest.key
        if not entry.exists() and not entry.is_symlink():
            return None
        try:
            if entry.is_symlink() or not entry.is_dir() or entry.stat().st_mode & 0o077:
                raise StoreIntegrityError("Unsafe result entry")
            receipt_bytes = self._read(entry / "receipt.json")
            report_bytes = self._read(entry / "report.json")
            receipt = json.loads(receipt_bytes)
            if (
                set(receipt)
                != {"schema", "origin", "manifest", "key", "report_sha256", "parent"}
                or receipt["schema"] != SCHEMA
                or receipt["origin"] != "executed"
                or receipt["key"] != manifest.key
                or receipt["manifest"] != manifest.as_dict()
                or receipt["report_sha256"] != hashlib.sha256(report_bytes).hexdigest()
            ):
                raise StoreIntegrityError("Result receipt or artifact differs")
            rebuilt = terminal_receipt(
                manifest, manifest, ParentObservation(**receipt["parent"]), report_bytes
            )
            if rebuilt.encoded != receipt_bytes:
                raise StoreIntegrityError("Receipt is not canonical terminal evidence")
            return VerifiedResult(rebuilt, report_bytes)
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise StoreIntegrityError("Invalid stored result evidence") from error

    def publish(self, receipt, report_bytes):
        if type(receipt) is not TerminalReceipt:
            raise ReuseIneligible("Terminal parent receipt required")
        document = receipt.as_dict()
        try:
            manifest = ValidationManifest(canonical_bytes(document["manifest"]))
            parent = ParentObservation(**document["parent"])
        except (KeyError, TypeError) as error:
            raise ReuseIneligible("Malformed terminal parent receipt") from error
        rebuilt = terminal_receipt(manifest, manifest, parent, report_bytes)
        if rebuilt.encoded != receipt.encoded:
            raise ReuseIneligible("Receipt and original report differ")
        existing = self.lookup(manifest)
        if existing is not None:
            return existing
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.root))
        try:
            for name, raw in (
                ("receipt.json", receipt.encoded),
                ("report.json", report_bytes),
            ):
                descriptor = os.open(
                    staging / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            try:
                os.rename(staging, self.root / manifest.key)
            except OSError as error:
                if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                    raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return self.lookup(manifest)
