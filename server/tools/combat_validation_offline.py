"""Reviewed offline module closures; lookup never imports gameplay or tests."""
from dataclasses import dataclass
import hashlib
from importlib.machinery import EXTENSION_SUFFIXES
import json
from pathlib import Path, PurePosixPath
import re
import sys

from tools.combat_validation_reuse import (
    SCHEMA,
    ReuseIneligible,
    ValidationManifest,
    build_manifest,
    qualification_binding,
)


REGISTRY = "server/tools/combat_validation_offline_qualifications.json"
IMPLEMENTATIONS = (
    "server/tools/combat_validation_offline.py",
    "server/tools/combat_validation_reuse.py",
)
MAX_INPUT_BYTES = 32 * 1024 * 1024
PYTHON_STARTUP = dict(isolated=True, no_site=True, ignore_environment=True)


@dataclass(frozen=True)
class Eligibility:
    manifest: ValidationManifest | None
    reason: str


def _path(root, name, *, directory=False):
    if directory and name == ".":
        return root
    path = PurePosixPath(name) if type(name) is str else None
    if (
        path is None
        or not name
        or path.is_absolute()
        or "\\" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
    ):
        raise ReuseIneligible("Unsafe qualification input path")
    result = root.joinpath(*path.parts)
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ReuseIneligible("Symlink qualification input")
    return result


def _read(root, name):
    path = _path(root, name)
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ReuseIneligible("Missing or oversized qualification input")
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ReuseIneligible("Oversized qualification input")
    return raw


def _reviewed(root, mapping):
    if type(mapping) is not dict:
        raise ReuseIneligible("Reviewed dependency hashes required")
    for name, checksum in mapping.items():
        if hashlib.sha256(_read(root, name)).hexdigest() != checksum:
            raise ReuseIneligible("Reviewed dependency changed: " + name)
    return mapping


def _candidates(directory, name):
    yield directory / name
    for suffix in (".py", ".pyc", *EXTENSION_SUFFIXES):
        yield directory / (name + suffix)


def _resolution(root, declarations):
    if type(declarations) is not dict or set(declarations) != {
        "stdlib_search_dirs",
        "imports",
    }:
        raise ReuseIneligible("Explicit import resolution guards required")
    search_dirs = declarations["stdlib_search_dirs"]
    if type(search_dirs) is not list or not search_dirs:
        raise ReuseIneligible("Standard library search guards required")
    for directory in search_dirs:
        base = _path(root, directory, directory=True)
        for name in sys.stdlib_module_names:
            if any(
                path.exists() or path.is_symlink() for path in _candidates(base, name)
            ):
                raise ReuseIneligible("Local standard library shadow: " + name)
    imports = declarations["imports"]
    if type(imports) is not dict or not imports:
        raise ReuseIneligible("Expected imported origins required")
    origins = {}
    for name, declaration in imports.items():
        if (
            type(name) is not str
            or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", name)
            or type(declaration) is not dict
            or set(declaration) != {"origin", "search_dirs"}
            or type(declaration["search_dirs"]) is not list
            or not declaration["search_dirs"]
        ):
            raise ReuseIneligible("Malformed import origin guard")
        expected = _path(root, declaration["origin"])
        leaf = name.rsplit(".", 1)[-1]
        found = False
        for directory in declaration["search_dirs"]:
            base = _path(root, directory, directory=True)
            matches = [
                path
                for path in _candidates(base, leaf)
                if path.exists() or path.is_symlink()
            ]
            if not matches:
                continue
            if len(matches) != 1:
                raise ReuseIneligible("Ambiguous imported origin: " + name)
            selected = matches[0]
            if selected.is_dir():
                selected = selected / "__init__.py"
            if selected != expected or not selected.is_file():
                raise ReuseIneligible("Imported origin changed: " + name)
            _read(root, declaration["origin"])
            found = True
            break
        if not found:
            raise ReuseIneligible("Missing imported origin: " + name)
        origins[name] = declaration["origin"]
    return origins


def eligibility(root, module, *, runner_sha256, environment_sha256, policies):
    """Return conservative fresh-run diagnostics for missing/invalid evidence."""
    root = Path(root).absolute()
    try:
        if root.is_symlink() or not root.is_dir():
            raise ReuseIneligible("Invalid qualification root")
        registry_bytes = _read(root, REGISTRY)
        registry = json.loads(registry_bytes)
        if (
            type(registry) is not dict
            or set(registry) != {"schema", "modules"}
            or registry["schema"] != "audited-offline-modules-v1"
            or type(registry["modules"]) is not dict
        ):
            raise ReuseIneligible("Unsupported offline qualification registry")
        entry = registry["modules"].get(module)
        if entry is None:
            return Eligibility(None, "Module has no reviewed offline qualification")
        fields = {
            "scope",
            "test_ids",
            "source",
            "fixtures",
            "catalog",
            "oracles",
            "rng",
            "resolution",
            "deterministic",
            "external_state",
        }
        if type(entry) is not dict or set(entry) != fields:
            raise ReuseIneligible("Malformed offline qualification declaration")
        if entry["deterministic"] is not True or entry["external_state"] != "none":
            raise ReuseIneligible("Offline deterministic qualification required")
        maps = {
            name: _reviewed(root, entry[name])
            for name in ("source", "fixtures", "catalog", "oracles")
        }
        origins = _resolution(root, entry["resolution"])
        if any(origin not in maps["source"] for origin in origins.values()):
            raise ReuseIneligible("Imported origin absent from reviewed source closure")
        if type(policies) is not dict:
            raise ReuseIneligible("Explicit runtime policies required")
        startup = policies.get("python_startup")
        if (
            policies.get("python_import_mode") != "isolated-no-site-v1"
            or type(startup) is not dict
            or set(startup) != set(PYTHON_STARTUP)
            or any(startup[name] is not True for name in PYTHON_STARTUP)
        ):
            raise ReuseIneligible("Isolated no-site Python startup contract required")
        actual_policies = dict(policies)
        if (
            "import_origins" in actual_policies
            and actual_policies["import_origins"] != origins
        ):
            raise ReuseIneligible(
                "Caller import origin policy differs from declaration"
            )
        actual_policies["import_origins"] = origins
        source = dict(maps.pop("source"))
        for name in (*IMPLEMENTATIONS, REGISTRY):
            source[name] = hashlib.sha256(_read(root, name)).hexdigest()
        document = dict(
            schema=SCHEMA,
            scope=entry["scope"],
            module=module,
            test_ids=entry["test_ids"],
            source=source,
            **maps,
            declaration=hashlib.sha256(registry_bytes).hexdigest(),
            runner=runner_sha256,
            environment=environment_sha256,
            policies=actual_policies,
            rng=entry["rng"]
        )
        proof = dict(
            kind="audited-offline-closure-v1",
            complete=True,
            deterministic=True,
            external_state="none",
            closure_sha256=qualification_binding(document),
        )
        document.pop("schema")
        return Eligibility(
            build_manifest(**document, qualification=proof),
            "Qualified reviewed offline closure",
        )
    except ReuseIneligible as error:
        return Eligibility(None, str(error))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
        return Eligibility(
            None, "Offline qualification unavailable: " + type(error).__name__
        )


def qualified_manifest(root, module, *, runner_sha256, environment_sha256, policies):
    return eligibility(
        root,
        module,
        runner_sha256=runner_sha256,
        environment_sha256=environment_sha256,
        policies=policies,
    ).manifest
