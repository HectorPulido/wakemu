"""Validate or stage a complete NPC catalog release; never activate or restart."""
import argparse
import hashlib
import json
from pathlib import Path

from stage_spell_resource_cost_catalog import stage as stage_release

PATHS = {"native-npc-spell-effect-trees.json", "native-class-casting-roots.json"}
COST_PATH = "native-spell-resource-costs.json"
from export_monster_state_resistance import CATALOG_PATH, assert_preserved
from export_monster_cell_groups import (
    CATALOG_PATH as CELL_PATH,
    assert_preserved as preserve_cells,
)
from export_monster_summon_dependencies import (
    CATALOG_PATHS as SUMMON_PATHS,
    assert_preserved as preserve_summons,
)


def documents(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest.get("schema") != "native-npc-activation-candidate-v1"
        or manifest.get("activated") is not False
    ):
        raise ValueError("Invalid inactive NPC activation package")
    changed = set(manifest["changed_documents"])
    if not PATHS <= changed or changed - PATHS - {
        COST_PATH,
        CATALOG_PATH,
        CELL_PATH,
    } - set(SUMMON_PATHS):
        raise ValueError("NPC activation cannot replace class catalog documents")
    entries = []
    for name, checksum in manifest["changed_documents"].items():
        path = directory / name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError("NPC activation package changed after validation")
        entries.append(
            dict(path=name, source=path, sha256=checksum, source_bytes=len(raw))
        )
    return entries


def stage(connection, directory, *, dry_run=True):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    documents(directory)
    # Pin the entire base, including every class definition, before copying it.
    with connection.transaction():
        if dry_run:
            connection.execute("SET TRANSACTION READ ONLY")
        active = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1"
            + ("" if dry_run else " FOR SHARE")
        ).fetchone()
        if active is None or active[0] != manifest["base_revision"]:
            raise ValueError("Active catalog changed; rebuild NPC candidate")
        baseline = dict(
            connection.execute(
                "SELECT path,sha256 FROM native_catalog_documents WHERE revision=%s ORDER BY path",
                (manifest["base_revision"],),
            ).fetchall()
        )
        changed = set(manifest["changed_documents"])
        if COST_PATH in changed and COST_PATH in baseline:
            raise ValueError(
                "NPC activation cannot replace an existing shared resource-cost catalog"
            )
        if CATALOG_PATH in changed:
            raw = bytes(
                connection.execute(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (manifest["base_revision"], CATALOG_PATH),
                ).fetchone()[0]
            )
            if hashlib.sha256(raw).hexdigest() != manifest["base_document_hashes"].get(
                CATALOG_PATH
            ):
                raise ValueError(
                    "Existing resistance metadata differs from tested base"
                )
            assert_preserved(
                json.loads(raw), json.loads((directory / CATALOG_PATH).read_text())
            )
        if CELL_PATH in changed:
            raw = bytes(
                connection.execute(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (manifest["base_revision"], CELL_PATH),
                ).fetchone()[0]
            )
            if hashlib.sha256(raw).hexdigest() != manifest["base_document_hashes"].get(
                CELL_PATH
            ):
                raise ValueError(
                    "Existing cell-group metadata differs from tested base"
                )
            preserve_cells(
                json.loads(raw), json.loads((directory / CELL_PATH).read_text())
            )
        for path in changed & set(SUMMON_PATHS):
            raw = bytes(
                connection.execute(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (manifest["base_revision"], path),
                ).fetchone()[0]
            )
            if hashlib.sha256(raw).hexdigest() != manifest["base_document_hashes"].get(
                path
            ):
                raise ValueError("Existing summon metadata differs from tested base")
            preserve_summons(
                path, json.loads(raw), json.loads((directory / path).read_text())
            )
        unchanged = {
            path: checksum for path, checksum in baseline.items() if path not in changed
        }
        if unchanged != manifest["unchanged_documents"]:
            raise ValueError("Unchanged class/catalog preservation manifest differs")
        if not dry_run:
            if (
                manifest.get("execution_validated") is not True
                or manifest.get("class_regressions_passed") is not True
            ):
                raise ValueError(
                    "NPC staging requires execution and class regression validation"
                )
            receipt = directory / "execution-validation.json"
            if not receipt.is_file() or hashlib.sha256(
                receipt.read_bytes()
            ).hexdigest() != manifest.get("execution_validation_sha256"):
                raise ValueError("NPC staging requires the matching execution receipt")
            tested = manifest.get("tested_runtime_code_sha256")
            if not isinstance(tested, dict) or not tested:
                raise ValueError("NPC staging requires tested runtime source hashes")
            root = Path(__file__).resolve().parents[2]
            if any(
                hashlib.sha256((root / name).read_bytes()).hexdigest() != checksum
                for name, checksum in tested.items()
            ):
                raise ValueError("Tested runtime sources changed before NPC staging")
        result = stage_release(
            connection,
            directory,
            manifest["base_revision"],
            dry_run=dry_run,
            document_provider=documents,
        )
        result["npc_documents"] = result.pop("resource_cost_documents")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Write an inactive release after validation",
    )
    args = parser.parse_args()
    from psycopg import connect

    with connect(
        args.dsn, password=args.password_file.read_text().strip()
    ) as connection:
        print(
            json.dumps(
                stage(connection, args.directory, dry_run=not args.stage),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
