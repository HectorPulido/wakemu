"""Validate or atomically publish a reviewed local mission content bundle.

The manifest pins source files and the imported native metadata revision.
Only fixed publisher kinds are available; a manifest cannot import Python or
escape the server tree. Dry-run executes the same publication transaction and
rolls it back, including configuration changes made by earlier publishers.
Player data, catalog compilation and service lifecycle are outside this tool.
"""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from psycopg.conninfo import conninfo_to_dict

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from wakfu_server.postgres import Database

SCHEMA = "wakemu.mission-bundle-v1"
KINDS = frozenset(
    (
        "combat",
        "recurring",
        "conversation",
        "toolkit",
        "interactive",
        "owned_instance",
        "mercenary_board",
        "source_quest",
        "native_generic",
        "quest_chest_supply",
        "encounter_roles",
    )
)
DEFAULT_MANIFEST = (
    SERVER_ROOT / "wakfu_server/achievements/mission_batches/mission-bundle-v1.json"
)


def local_connection(dsn):
    """Accept libpq DSNs and PostgreSQL URLs with explicit loopback addresses."""
    values = conninfo_to_dict(dsn)
    if values.get("host") not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            "Mission bundle CLI requires an explicit local PostgreSQL host"
        )
    if values.get("hostaddr") not in (None, "127.0.0.1", "::1"):
        raise ValueError("Mission bundle CLI refuses a nonlocal PostgreSQL address")
    if not values.get("dbname", "").startswith("wakemu"):
        raise ValueError("Mission bundle CLI requires a Wakemu database")
    port = values.get("port", "5432")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("Invalid local PostgreSQL port")
    return values


def load_bundle(manifest, *, root=SERVER_ROOT):
    """Authenticate every bounded, relative source path before publication."""
    document = json.loads(Path(manifest).read_text())
    if (
        type(document) is not dict
        or set(document)
        != {"schema", "id", "native_metadata_revision", "minimum_schema", "entries"}
        or document["schema"] != SCHEMA
        or type(document["id"]) is not str
        or not document["id"].strip()
        or type(document["minimum_schema"]) is not int
        or not 375 <= document["minimum_schema"] < 2**31
        or not isinstance(document["entries"], list)
        or not document["entries"]
    ):
        raise ValueError("Unsupported mission bundle manifest")
    revision = document["native_metadata_revision"]
    if (
        type(revision) is not str
        or len(revision) != 64
        or any(c not in "0123456789abcdef" for c in revision)
    ):
        raise ValueError("Invalid mission bundle native revision")
    root = Path(root).resolve()
    seen, entries = set(), []
    for entry in document["entries"]:
        if type(entry) is not dict or set(entry) != {"kind", "path", "sha256"}:
            raise ValueError("Unsupported mission bundle entry")
        if entry["kind"] not in KINDS:
            raise ValueError("Unsupported mission bundle publisher")
        relative = entry["path"]
        if type(relative) is not str or not relative or "\\" in relative:
            raise ValueError("Invalid mission bundle source path")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
            raise ValueError("Mission bundle source must remain inside the server tree")
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Mission bundle source escapes the server tree")
        if resolved in seen:
            raise ValueError("Duplicate mission bundle source")
        seen.add(resolved)
        raw = resolved.read_bytes()
        if sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Mission bundle source attestation changed: " + relative)
        entries.append(
            {
                **entry,
                "document": json.loads(raw),
                "native_revision": revision,
            }
        )
    return {**document, "entries": entries}


def _preflight(db, bundle):
    """Check the shared schema, native identity and conversation attestation."""
    schema = db.execute(
        "SELECT 1 FROM schema_migrations WHERE version=%s", (bundle["minimum_schema"],)
    ).fetchone()
    if schema is None:
        raise ValueError(
            f"Apply mission bundle schema migration {bundle['minimum_schema']} first"
        )
    native = db.execute(
        "SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
    ).fetchone()
    if native is None or native["revision"] != bundle["native_metadata_revision"]:
        raise ValueError("Mission bundle belongs to another native quest publication")
    from wakfu_server import quest_npc
    from wakfu_server.achievements import conversation

    for entry in bundle["entries"]:
        if (
            entry["kind"] == "conversation"
            and conversation._digest(entry["document"])
            != quest_npc.source_contract_digest()
        ):
            raise ValueError(
                "Mission bundle conversation differs from its reviewed source"
            )


def _publish_entry(db, entry):
    """Fixed adapters keep all mutation semantics in existing publishers."""
    document = entry["document"]
    if entry["kind"] == "encounter_roles":
        from tools.publish_encounter_roles import install

        return install(db, document)
    if entry["kind"] == "quest_chest_supply":
        from tools.publish_quest_chest_supplies import install

        return install(db, document)
    if entry["kind"] == "native_generic":
        from tools.publish_native_generic_rewards import install

        return install(db, document)
    if entry["kind"] == "combat":
        from tools.install_combat_mission_bindings import install

        return install(db, document, write=True)
    if entry["kind"] == "recurring":
        from tools.recurring_quest_batch import install

        return install(db, document, apply=True)
    if entry["kind"] == "conversation":
        from tools.publish_conversation_archetypes import publish

        return publish(db, document)
    if entry["kind"] == "toolkit":
        from wakfu_server.achievements.mission_toolkit import install

        return install(db, document, activate=True)
    if entry["kind"] == "interactive":
        from tools.install_quest_interactions import install

        return dict(
            bindings=install(db, document, entry["native_revision"]),
        )
    if entry["kind"] == "owned_instance":
        from wakfu_server.dungeon_runtime_config import install_configuration

        install_configuration(db, document)
        return dict(
            route_key=document["route"]["key"], policy_version=document["version"]
        )
    if entry["kind"] == "mercenary_board":
        from wakfu_server.mercenary_boards import install

        return install(db, document)
    if entry["kind"] == "source_quest":
        from wakfu_server.achievements.source_quest_encounters import publish

        return publish(db, document, entry["native_revision"])
    raise ValueError("Unsupported mission bundle publisher")


def install_bundle(db, bundle, *, apply=False):
    """Run all publishers in one commit, or roll back every configuration write."""
    if type(apply) is not bool:
        raise ValueError("Invalid mission bundle apply flag")
    results = []
    with db.transaction(force_rollback=not apply):
        _preflight(db, bundle)
        db.execute("SELECT pg_advisory_xact_lock(%s)", (202611150880,))
        for entry in bundle["entries"]:
            result = _publish_entry(db, entry)
            results.append(
                {"kind": entry["kind"], "path": entry["path"], "result": result}
            )
    return {
        "bundle": bundle["id"],
        "native_metadata_revision": bundle["native_metadata_revision"],
        "applied": apply,
        "rolled_back": not apply,
        "player_progress_modified": False,
        "steps": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dsn = os.environ.get("WAKFU_DATABASE_URL", "")
    local_connection(dsn)
    bundle = load_bundle(args.manifest)
    database = Database(
        dsn, password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    )
    try:
        with database.connection() as db:
            print(
                json.dumps(install_bundle(db, bundle, apply=args.apply), sort_keys=True)
            )
    finally:
        database.close()


if __name__ == "__main__":
    main()
