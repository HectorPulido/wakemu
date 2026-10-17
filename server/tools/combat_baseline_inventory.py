"""Read-only combat provenance and static route inventory.

The AST report is evidence of source call sites, not a runtime trace. Catalog
identity comes from the published native_catalog API; offline evidence is never
promoted to a verified publication. No environment values or exception messages
are included in output.
"""

import argparse
import ast
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from pathlib import Path


SCHEMA_VERSION = 1
SNAPSHOT_VERIFIER_VERSION = 3
DECLARED_INTERNAL_INPUTS = frozenset(
    {
        "agents_docs/reports/combat-resilience-phase1-2/source-scenarios.json",
    }
)
SOURCE_SCOPE = (
    "server/**/*.py (excluding hidden paths, caches and symlinks)",
    "server/**/requirements*.txt",
    "server/migrations/*.sql",
    "server/protocol/**/*.json",
    "server/{tests/fixtures,test-fixtures,ai-service/tests/fixtures}/**/*.{json,gz,bin,csv,tsv,txt}",
    "server/**/*.{js,html,css,svg,png}",
    "server/**/Dockerfile and server/**/*.sh",
    "compose*.yml, compose*.yaml, docker-compose*.yml, docker-compose*.yaml",
    "validation-snapshot.json and its verified public source/input members, when present",
)


def canonical_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf8")
    ).hexdigest()


def _safe_relative(path):
    """Accept relative artifact names, never traversal, URLs or secret files."""
    if not isinstance(path, str) or not path or "\\" in path:
        return False
    candidate = Path(path)
    if candidate.is_absolute() or any(part in (".", "..") for part in candidate.parts):
        return False
    return (
        all(
            not part.startswith(".")
            and not re.search(
                r"(?i)(credential|secret|password|private.?key|\.pem$|\.key$)", part
            )
            for part in candidate.parts
        )
        and ":" not in path
    )


def _safe_source_relative(path):
    """Public code names can describe secret mechanics or credential handling.

    Such identifiers are not secret values. Preserve complete public Python,
    migration and native-probe code while excluding actual private directories,
    hidden files, keys and traversal. Non-code artifact names remain strict.
    """
    if not isinstance(path, str) or not path or "\\" in path or ":" in path:
        return False
    relative = Path(path)
    if relative.suffix not in (".py", ".sql", ".java"):
        return _safe_relative(path)
    return (
        not relative.is_absolute()
        and not any(
            part in (".", "..") or part.startswith(".") for part in relative.parts
        )
        and not any(
            part.lower() in ("secrets", "credentials", "passwords", "private_keys")
            for part in relative.parts[:-1]
        )
    )


def _source_paths(root):
    server = root / "server"
    candidates = set()
    for pattern in ("*.py", "requirements*.txt", "Dockerfile", "*.sh"):
        candidates.update(server.rglob(pattern))
    candidates.update((server / "migrations").glob("*.sql"))
    candidates.update((server / "protocol").rglob("*.json"))
    for directory in ("tests/fixtures", "test-fixtures", "ai-service/tests/fixtures"):
        candidates.update(
            path
            for path in (server / directory).rglob("*")
            if path.suffix in (".json", ".gz", ".bin", ".csv", ".tsv", ".txt")
        )
    for suffix in (".js", ".html", ".css", ".svg", ".png"):
        candidates.update(server.rglob("*" + suffix))
    for pattern in (
        "compose*.yml",
        "compose*.yaml",
        "docker-compose*.yml",
        "docker-compose*.yaml",
    ):
        candidates.update(root.glob(pattern))
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if not path.is_file() or not _safe_source_relative(relative.as_posix()):
            continue
        if any(part == "__pycache__" for part in relative.parts):
            continue
        if any(part in ("node_modules", "venv") for part in relative.parts):
            continue
        # Parent symlinks can lead outside the checkout even if the file itself
        # is regular; omit both rather than hashing private external material.
        if any(
            part.is_symlink() for part in (path, *path.parents) if part != root.parent
        ):
            continue
        yield path


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validation_snapshot(root, files):
    """Verify snapshot members without exposing its private root metadata.

    Verified snapshot members extend the source identity to data, oracle and
    documentation inputs the snapshot command explicitly copied. A mismatch is
    evidence of an invalid snapshot; it is never labeled verified.
    """
    path = root / "validation-snapshot.json"
    verifier = {
        "version": SNAPSHOT_VERIFIER_VERSION,
        "implementation_sha256": _hash_file(Path(__file__).resolve()),
        "policy": "public-code-identifiers-and-private-artifact-exclusions",
    }
    if not path.exists():
        return {"status": "absent", "verifier": verifier}
    allowed_suffixes = {
        ".py",
        ".json",
        ".gz",
        ".bin",
        ".csv",
        ".tsv",
        ".txt",
        ".sql",
        ".sh",
        ".html",
        ".css",
        ".js",
        ".svg",
        ".png",
        ".java",
        ".md",
        ".yaml",
        ".yml",
    }
    try:
        if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Invalid snapshot manifest")
        raw = path.read_bytes()
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Invalid snapshot manifest")
        evidence = json.loads(raw)
        members = evidence.get("files") if isinstance(evidence, dict) else None
        if not isinstance(members, dict) or not members:
            raise ValueError("Missing snapshot members")
        checked = {}
        mismatches = 0
        for name, digest in members.items():
            relative = Path(name) if isinstance(name, str) else None
            if (
                relative is None
                or not _safe_source_relative(name)
                or name == "validation-snapshot.json"
                or relative.parts[0] == "client"
                or relative.parts[0] == "agents_docs"
                and name not in DECLARED_INTERNAL_INPUTS
                or any(
                    part in ("node_modules", "__pycache__", "venv")
                    for part in relative.parts
                )
                or relative.suffix not in allowed_suffixes
                and relative.name != "Dockerfile"
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise ValueError("Unsafe snapshot member")
            member = root / relative
            if any(
                parent.is_symlink()
                for parent in (member, *member.parents)
                if parent != root.parent
            ):
                raise ValueError("Symlink snapshot member")
            actual = files.get(name)
            if actual is None:
                actual = _hash_file(member)
            checked[name] = actual
            mismatches += actual != digest
        # Even an invalidated snapshot must identify the actual bytes that were
        # observed. Callers can reject its explicit mismatch status.
        files.update(checked)
        files["validation-snapshot.json"] = hashlib.sha256(raw).hexdigest()
        return {
            "status": "verified" if not mismatches else "mismatch",
            "verifier": verifier,
            "manifest_sha256": files["validation-snapshot.json"],
            "member_count": len(members),
            "mismatch_count": mismatches,
            "members_sha256": canonical_digest(checked),
        }
    except (OSError, ValueError, TypeError) as error:
        return {
            "status": "invalid",
            "error_type": type(error).__name__,
            "verifier": verifier,
        }


def _git_identity(root):
    def run(*args):
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    try:
        commit = run("rev-parse", "--verify", "HEAD")
        branch = run("symbolic-ref", "--short", "-q", "HEAD")
        status = run("status", "--porcelain=v1", "-z", "--untracked-files=normal")
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    if status is None:
        return {"available": False}
    # Count records without publishing any tracked/untracked path. Rename
    # records have a second NUL-delimited path and count as one changed entry.
    records = status.split("\0") if status else []
    count = 0
    index = 0
    while index < len(records):
        record = records[index]
        if record:
            count += 1
            if "R" in record[:2] or "C" in record[:2]:
                index += 1
        index += 1
    return {
        "available": True,
        "commit": commit,
        "branch": branch,
        "dirty": bool(status),
        "changed_path_count": count,
    }


def source_manifest(root):
    """Return stable explicit source hashes and sanitized checkout identity."""
    root = Path(root).resolve()
    files = {}
    for path in _source_paths(root):
        files[path.relative_to(root).as_posix()] = _hash_file(path)
    validation_snapshot = _validation_snapshot(root, files)
    files = dict(sorted(files.items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": list(SOURCE_SCOPE),
        "files": files,
        "sha256": canonical_digest(files),
        "file_count": len(files),
        "git": _git_identity(root),
        "validation_snapshot": validation_snapshot,
        "limitations": [
            "Scoped source identity, not a complete checkout or container image identity.",
            "Private artifact names/directories, hidden paths and symlinks are excluded; public code identifiers are retained.",
            "Catalog contents are identified separately by catalog_manifest.",
            "Sequential reads require before/after comparison to establish a stable run.",
        ],
    }


def _catalog_identity(revision, documents, status):
    if not isinstance(revision, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]{1,128}", revision
    ):
        raise ValueError("Invalid catalog revision")
    if not isinstance(documents, dict) or not documents:
        raise ValueError("Missing catalog document hashes")
    if any(
        not _safe_relative(path)
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        for path, digest in documents.items()
    ):
        raise ValueError("Invalid catalog document hashes")
    identity = {"revision": revision, "documents": dict(sorted(documents.items()))}
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        **identity,
        "document_count": len(documents),
        "sha256": canonical_digest(identity),
    }


def catalog_manifest(offline_manifest=None):
    """Read published identity only, or explicitly unverified offline evidence.

    The offline file must contain ``revision`` and a ``documents`` mapping. It
    may be a previous output of this function. No catalog file fallback occurs.
    """
    if offline_manifest is not None:
        path = Path(offline_manifest)
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Offline catalog manifest exceeds size limit")
        raw = path.read_bytes()
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Offline catalog manifest exceeds size limit")
        evidence = json.loads(raw)
        if not isinstance(evidence, dict):
            raise ValueError("Invalid offline catalog manifest")
        result = _catalog_identity(
            evidence.get("revision"), evidence.get("documents"), "offline_unverified"
        )
        result["publication_verified"] = False
        result["evidence_sha256"] = hashlib.sha256(raw).hexdigest()
        return result
    try:
        # The package exposes storage modules through its extended path. Use
        # the canonical identity also patched by offline catalog replay;
        # importing storage.native_catalog creates a second unpatched module.
        from wakfu_server import native_catalog

        revision = native_catalog.release()
        documents = native_catalog.document_hashes()
        result = _catalog_identity(revision, documents, "published")
        result["publication_verified"] = True
        result["authority"] = "wakfu_server.native_catalog"
        result["limitations"] = [
            "Published inventory metadata; document bytes are not re-read or checksum-verified here.",
            "Uses the process-pinned release, matching native_catalog reader semantics.",
        ]
        return result
    except Exception as error:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "unavailable",
            "publication_verified": False,
            "revision": None,
            "documents": {},
            "sha256": None,
            "error_type": type(error).__name__,
        }


def environment_manifest():
    """Identify runtime packages without paths, environment or direct URLs."""
    packages = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if (
            name
            and re.fullmatch(r"[A-Za-z0-9_.-]+", name)
            and re.fullmatch(r"[A-Za-z0-9_.+!-]+", version)
        ):
            packages[name.lower().replace("_", "-")] = version
    identity = {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "packages": dict(sorted(packages.items())),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        **identity,
        "sha256": canonical_digest(identity),
    }


def _expression_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expression_name(node.value)
        return prefix + "." + node.attr if prefix else node.attr
    return None


def route_inventory(root):
    """Map static call evidence in server combat and its integration layer.

    Simple unqualified calls are candidates by symbol name, not confirmed
    dynamic dispatch. Runtime-injected callbacks and imports are unresolved.
    """
    root = Path(root).resolve()
    paths = [root / "server/local_game_server.py"]
    paths.extend(sorted((root / "server/wakfu_server/combat").glob("*.py")))
    definitions = []
    parse_errors = []
    for path in paths:
        if not path.exists() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf8"))
        except (SyntaxError, UnicodeError, OSError) as error:
            parse_errors.append({"path": relative, "error_type": type(error).__name__})
            continue

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.stack = []

            def visit_ClassDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_FunctionDef(self, node):
                qualified = ".".join([*self.stack, node.name])
                # Nested definitions get their own call sites. Do not attribute
                # their deferred execution to the containing function.
                calls = []

                class Calls(ast.NodeVisitor):
                    def visit_FunctionDef(self, child):
                        pass

                    visit_AsyncFunctionDef = visit_FunctionDef

                    def visit_ClassDef(self, child):
                        pass

                    def visit_Call(self, child):
                        expression = _expression_name(child.func)
                        if expression:
                            calls.append(
                                {"expression": expression, "line": child.lineno}
                            )
                        self.generic_visit(child)

                for statement in node.body:
                    Calls().visit(statement)
                definitions.append(
                    {
                        "id": relative + ":" + qualified,
                        "path": relative,
                        "symbol": qualified,
                        "line": node.lineno,
                        "calls": calls,
                    }
                )
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

        Visitor().visit(tree)

    by_name = {}
    for definition in definitions:
        by_name.setdefault(definition["symbol"].split(".")[-1], []).append(
            definition["id"]
        )
    inbound = {}
    for definition in definitions:
        for call in definition["calls"]:
            # Dotted attribute dispatch can target arbitrary runtime objects.
            # Report its text but do not fabricate a resolved edge.
            candidates = by_name.get(call["expression"], [])
            call["candidate_targets"] = candidates
            for candidate in candidates:
                inbound.setdefault(candidate, []).append(
                    {
                        "caller": definition["id"],
                        "line": call["line"],
                        "resolution": "unqualified_name_candidate",
                    }
                )
    route_words = re.compile(
        r"(spell|fight|combat|summon|weapon|move|turn|cast|attack|placement|teleport)",
        re.I,
    )
    routes = []
    for definition in definitions:
        if not route_words.search(definition["symbol"]):
            continue
        callers = inbound.get(definition["id"], [])
        symbol = definition["symbol"]
        compatibility = bool(re.search(r"(legacy|compat|deprecated)", symbol, re.I))
        routes.append(
            {
                **definition,
                "candidate_callers": callers,
                "classification": (
                    "compatibility_name_candidate"
                    if compatibility
                    else "referenced_static_candidate"
                    if callers
                    else "no_unqualified_caller_found"
                ),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "method": "ast_call_sites",
        "files_scanned": len(paths),
        "definitions_scanned": len(definitions),
        "routes": routes,
        "parse_errors": parse_errors,
        "limitations": [
            "Static candidates do not establish active runtime reachability or obsolescence.",
            "Dotted calls, imports, aliases, callback injection and dynamic dispatch are not resolved.",
            "No caller found means unknown usage; test-prefixed functions may serve live traffic.",
            "Scope is combat modules and local_game_server, excluding AI decision making.",
        ],
    }


def build_inventory(root, offline_catalog_manifest=None):
    before = source_manifest(root)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": before,
        "catalog": catalog_manifest(offline_catalog_manifest),
        "environment": environment_manifest(),
        "routes": route_inventory(root),
    }
    after = source_manifest(root)
    result["source_after_sha256"] = after["sha256"]
    result["source_stable"] = before["files"] == after["files"]
    result["validation_snapshot_valid"] = all(
        manifest["validation_snapshot"]["status"] in ("absent", "verified")
        for manifest in (before, after)
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline-catalog-manifest", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output.resolve()
    try:
        output.relative_to(root / ".runtime")
    except ValueError:
        parser.error("--output must be inside the checkout .runtime directory")
    result = build_inventory(root, args.offline_catalog_manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf8"
    )
    print(
        json.dumps(
            {
                "source_sha256": result["source"]["sha256"],
                "source_stable": result["source_stable"],
                "validation_snapshot_valid": result["validation_snapshot_valid"],
                "catalog_status": result["catalog"]["status"],
                "route_count": len(result["routes"]["routes"]),
            },
            sort_keys=True,
        )
    )
    return 0 if result["source_stable"] and result["validation_snapshot_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
