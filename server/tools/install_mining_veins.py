#!/usr/bin/env python3
"""Validate or install an explicit mining distribution plan; never restart world."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="Install slots in the configured database"
    )
    parser.add_argument(
        "--navigation-dir",
        type=Path,
        help="Offline native navigation evidence; forbidden with --apply",
    )
    args = parser.parse_args()
    if args.apply and args.navigation_dir:
        raise ValueError("Installation requires published navigation authority")
    from wakfu_server import native_catalog
    from wakfu_server.mining_veins import install, validate_placements

    plan = json.loads(args.plan.read_text())
    if (
        plan.get("schema_version") != 1
        or plan.get("catalog_revision") != native_catalog.release()
    ):
        raise ValueError("Mining plan must match the published native catalog revision")
    if plan.get("evidence_kind") != "local_generated_from_native_terrain":
        raise ValueError(
            "Mining distribution must explicitly identify its local policy"
        )
    navigation_surface = None
    if args.navigation_dir:
        from wakfu_server.mining_navigation import _incoming

        indexes = {}

        def navigation_surface(map_id, x, y, z):
            if map_id not in indexes:
                document = json.loads(
                    (args.navigation_dir / f"{map_id}.json").read_text()
                )
                indexes[map_id] = _incoming(document, map_id)
            try:
                return indexes[map_id][(x, y, z)]
            except KeyError as error:
                raise ValueError("Unknown offline mining surface") from error

    placements = validate_placements(
        plan["placements"], navigation_surface=navigation_surface
    )
    output = {"placements": len(placements), "applied": False}
    if args.apply:
        from wakfu_server.store import Store

        store = Store(os.environ["WAKFU_DATABASE_URL"])
        try:
            output["inserted_slots"] = install(store, placements)
            output["applied"] = True
        finally:
            store.close()
    print(json.dumps(output))


if __name__ == "__main__":
    main()
