"""Validate a prepared dungeon configuration bundle or install it atomically.

The caller selects the database explicitly. This tool does not restart world.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from wakfu_server.maps.dungeon_runtime_config import (
    install_configuration,
    prepare_configuration,
)


def validate_bundle(bundle):
    if bundle.get("schema_version") != 1 or not isinstance(
        bundle.get("configurations"), list
    ):
        raise ValueError("Invalid dungeon configuration bundle")
    configurations = bundle["configurations"]
    if not configurations:
        raise ValueError("No ready dungeon configurations")
    keys, slugs, entries = set(), set(), set()
    for config in configurations:
        route = config["route"]
        entry = (
            route["entry_map_id"],
            route["entry_object_id"],
            route["destination_id"],
        )
        if config["slug"] in slugs or route["key"] in keys or entry in entries:
            raise ValueError("Duplicate dungeon slug, route or native entrance")
        keys.add(route["key"])
        slugs.add(config["slug"])
        entries.add(entry)
        expected = prepare_configuration(
            config["compiled_plan"],
            config["topology"],
            route,
            version=config["version"],
            provenance=config["provenance"],
        )
        if config != expected:
            raise ValueError("Bundle contains unvalidated configuration")
    from wakfu_server.dungeon_instances import _load_routes

    _load_routes([config["route"] for config in configurations])
    return tuple(sorted(configurations, key=lambda config: config["route"]["key"]))


def install_bundle(db, bundle):
    """Caller owns transaction; all configurations and route registry commit together."""
    configurations = validate_bundle(bundle)
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended('dungeon_runtime_routes',0))"
    )
    existing = db.execute(
        "SELECT value FROM settings WHERE name='dungeon_runtime_routes' FOR UPDATE"
    ).fetchone()
    if existing is not None:
        registry = existing["value"]
        if (
            not isinstance(registry, dict)
            or set(registry) != {"schema_version", "routes"}
            or type(registry["schema_version"]) is not int
            or registry["schema_version"] != 1
            or not isinstance(registry["routes"], list)
        ):
            raise ValueError("Malformed installed dungeon route registry")
        from wakfu_server.dungeon_instances import _load_routes

        _load_routes(registry["routes"])
    routes = (
        {}
        if existing is None
        else {route["key"]: route for route in existing["value"]["routes"]}
    )
    for config in configurations:
        route = config["route"]
        old = routes.get(route["key"])
        if old is not None and old != route:
            raise ValueError("Installed native route identity is immutable")
        install_configuration(db, config)
        routes[route["key"]] = route
    ordered = [routes[key] for key in sorted(routes)]
    if len(
        {
            (r["entry_map_id"], r["entry_object_id"], r["destination_id"])
            for r in ordered
        }
    ) != len(ordered):
        raise ValueError("Installed dungeon entrances collide")
    db.execute(
        "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
        "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
        (json.dumps(dict(schema_version=1, routes=ordered)),),
    )
    return dict(installed=len(configurations), registered_routes=len(ordered))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = args.bundle.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError("Prepared bundle hash mismatch")
    bundle = json.loads(raw)
    configs = validate_bundle(bundle)
    result = dict(configurations=len(configs), applied=False)
    if args.apply:
        from wakfu_server.store import Store

        store = Store(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        try:
            with store.connection() as db, db.transaction():
                result.update(install_bundle(db, bundle), applied=True)
        finally:
            store.close()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
