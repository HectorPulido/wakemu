"""Reuse a sealed combat publication after unrelated runtime-only changes.

This fast path never reads or republishes individual combat records. Unknown
changes, non-shared storage, or incompatible inputs fall back to the compiler.
"""

import hashlib
import json
import sys
from pathlib import Path

from psycopg.types.json import Jsonb


# These modules are exclusively runtime dialogue, group persistence, and
# ecology removal; the static combat compiler does not import or call them.
RUNTIME_ONLY = frozenset(
    {
        "wakfu_server/combat/combat_group_store.py",
        "wakfu_server/combat/rii_lesson_grants.py",
        "wakfu_server/maps/monster_removal_ecology.py",
        "wakfu_server/maps/rii_airyna_dialogue.py",
    }
)

# These modules are entry points for live World interactions.  They are not
# imported by any package module or by the catalog publisher; World dispatches
# them from local_game_server instead.  A regression test checks this boundary
# so adding a new package reference makes the change visible for review.
WORLD_DISPATCH_ONLY = frozenset(
    {
        "wakfu_server/maps/party_dispatch.py",
        "wakfu_server/maps/transport_rejection.py",
        "wakfu_server/maps/dungeon_auto_transition.py",
        "wakfu_server/maps/monster_home_delivery.py",
        "wakfu_server/maps/dungeon_sections.py",
        "wakfu_server/maps/tutorials.py",
        "wakfu_server/maps/dungeon_hydration.py",
        "wakfu_server/maps/test_console.py",
        "wakfu_server/maps/environment_seats.py",
        "wakfu_server/maps/dungeon_local_roster_policy.py",
        "wakfu_server/maps/dungeon_optional_ground_items.py",
        "wakfu_server/maps/nation_board.py",
        "wakfu_server/maps/world_orientation.py",
        "wakfu_server/maps/ecology_admin_runtime.py",
        "wakfu_server/maps/dungeon_excavation_provider.py",
        "wakfu_server/maps/dungeon_physical_choice.py",
        "wakfu_server/maps/ruel_investigation_npc.py",
        "wakfu_server/maps/travel_storage_feedback.py",
        "wakfu_server/maps/monster_removal_ecology.py",
        "wakfu_server/maps/quest_ground_entry.py",
        "wakfu_server/maps/rii_airyna_dialogue.py",
        "wakfu_server/maps/npc_capture_scene.py",
        "wakfu_server/maps/environment_seat_animations.py",
        "wakfu_server/maps/dungeon_scaling_entry.py",
        "wakfu_server/maps/dungeon_auto_exit.py",
        "wakfu_server/maps/command_search.py",
        "wakfu_server/maps/modulox_npc.py",
        "wakfu_server/maps/dungeon_transition_delivery.py",
        "wakfu_server/maps/interactive_publication.py",
        "wakfu_server/maps/dungeon_doors.py",
        "wakfu_server/items/mount_feeding_dispatch.py",
        "wakfu_server/items/inventory_consumable_effects.py",
        "wakfu_server/items/inventory_deferred_journal.py",
        "wakfu_server/items/neutrality_item_actions.py",
        "wakfu_server/items/haven_ranch_portal.py",
        "wakfu_server/items/binding_kit_item_actions.py",
        "wakfu_server/items/exchange_machine.py",
        "wakfu_server/items/restat_item_actions.py",
        "wakfu_server/items/item_teleports.py",
        "wakfu_server/items/mount_publication.py",
        "wakfu_server/items/haven_ranch_authority.py",
        "wakfu_server/items/script_item_actions.py",
        "wakfu_server/items/achievement_item_actions.py",
        "wakfu_server/items/haven_world_bombs.py",
        "wakfu_server/items/consumable_world_publication.py",
        "wakfu_server/items/item_spell_publication.py",
        "wakfu_server/items/temporary_recycling.py",
        "wakfu_server/items/world_marker_item_actions.py",
        "wakfu_server/items/haven_bag_exterior.py",
        "wakfu_server/items/inventory_bags.py",
        "wakfu_server/items/emote_item_actions.py",
        "wakfu_server/items/haven_bag_native_scene.py",
        "wakfu_server/items/scenario_item_actions.py",
        "wakfu_server/items/exchange_dispatch.py",
        "wakfu_server/items/inventory_animation.py",
        "wakfu_server/items/haven_bag_transfer.py",
        "wakfu_server/characters/captured_roster_fresh.py",
        "wakfu_server/characters/private_scene_heroes.py",
        "wakfu_server/characters/guild_member_lifecycle.py",
        "wakfu_server/characters/hero_private_scene.py",
        "wakfu_server/characters/fresh_appearance.py",
        "wakfu_server/characters/national_publication.py",
        "wakfu_server/characters/guild_dispatch.py",
        "wakfu_server/characters/captured_roster_management.py",
        "wakfu_server/characters/guild_primary_policy.py",
        "wakfu_server/characters/world_respawn.py",
        "wakfu_server/characters/captured_roster_selection.py",
        "wakfu_server/characters/level_publication.py",
        "wakfu_server/characters/character_selection_retry.py",
    }
)

PIN_FIELDS = (
    "policy",
    "source_revision",
    "source_inventory_sha256",
    "compiler_contract_sha256",
    "config_sha256",
)

# One-way bridge for the reviewed incremental-publishing change. This exact
# transition only replaces full raw-document serialization and a full shared
# record count with validated reuse of immutable collection contents. Any
# subsequent edit to the publisher changes its digest and forces compilation.
PUBLISHER_SOURCE = "tools/publish_compiled_combat_catalog.py"
REVIEWED_PUBLISHER_TRANSITIONS = frozenset(
    {
        (
            "71e4575e73f3b8f7494257ebdb97e6bc4a8fa40b2eedb1c487042caad65a900c",
            "0275c577cda683e4afc988c162103d02ad1adf27a05c824c9b28846d51724c40",
        ),
    }
)

# One-time transition to reviewed variant-group reuse, including the identity
# change that makes the new helper a compiler input on every future start.
REVIEWED_VARIANT_REUSE_BUNDLE = {
    PUBLISHER_SOURCE: (
        "0275c577cda683e4afc988c162103d02ad1adf27a05c824c9b28846d51724c40",
        "7b302368df8004c29ec8d0b9aab7096fb194dc4cc259c513f04a7613684bd623",
    ),
    "wakfu_server/storage/native_compiled_catalog.py": (
        "cdb6520f48e03cb9577595908e7041cee132f8b0a161e4afad95f71bccb5cda7",
        "31a82ab0d94ef123f564fd3f427647748aad63aa63e8e094eb680bda1f53aebf",
    ),
    "tools/reuse_compiled_variants.py": (
        None,
        "3f1690a98fb24a62fb20d49f76ae471803eca5e6a955981a4363b4401e65efce",
    ),
}

# This exact one-way loader change adds an opt-in selection override without
# changing any producer or compiled record. Later loader edits remain inputs.
REVIEWED_LOADER_OVERRIDE = {
    "wakfu_server/storage/native_compiled_catalog.py": (
        "31a82ab0d94ef123f564fd3f427647748aad63aa63e8e094eb680bda1f53aebf",
        "1a9d22d572dcfb716ae539ed7d39948cce126fdf8c81db2b301c064c9c2f460c",
    ),
}


def compatible(previous, current, proved_paths=()):
    """Recognize only explicitly reviewed changes to non-compiler modules."""
    if any(
        previous.get(k) != current.get(k)
        for k in PIN_FIELDS
        if k != "compiler_contract_sha256"
    ):
        return False
    if previous.get("source_documents") != current.get(
        "source_documents"
    ) or previous.get("config") != current.get("config"):
        return False
    old, new = previous.get("compiler_sources"), current.get("compiler_sources")
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    if changed == set(REVIEWED_VARIANT_REUSE_BUNDLE) and all(
        (old.get(path), new.get(path)) == hashes
        for path, hashes in REVIEWED_VARIANT_REUSE_BUNDLE.items()
    ):
        return True
    if changed == set(REVIEWED_LOADER_OVERRIDE) and all(
        (old.get(path), new.get(path)) == hashes
        for path, hashes in REVIEWED_LOADER_OVERRIDE.items()
    ):
        return True
    reviewed_transition = (
        PUBLISHER_SOURCE in changed
        and (old.get(PUBLISHER_SOURCE), new.get(PUBLISHER_SOURCE))
        in REVIEWED_PUBLISHER_TRANSITIONS
    )
    allowed = RUNTIME_ONLY | WORLD_DISPATCH_ONLY | set(proved_paths)
    if reviewed_transition:
        # Do not combine the one-time migration with other source edits.
        return changed == {PUBLISHER_SOURCE}
    return bool(changed) and changed <= allowed


def try_reuse(db, identity, canonical_bytes):
    """Seal a new header and collection references in the caller transaction."""
    pins = tuple(identity[key] for key in PIN_FIELDS)
    db.execute(
        "SELECT pg_advisory_xact_lock_shared(hashtextextended("
        "current_database()||':'||current_schema()||':compiled_catalog_maintenance',0))"
    )
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (
            "native_compiled_catalog:"
            + hashlib.sha256(canonical_bytes(pins)).hexdigest(),
        ),
    )
    existing = db.execute(
        "SELECT generation FROM native_compiled_catalog_releases WHERE policy=%s AND source_revision=%s "
        "AND source_inventory_sha256=%s AND compiler_contract_sha256=%s AND config_sha256=%s AND complete",
        pins,
    ).fetchone()
    if existing:
        return existing["generation"]
    # Aliasing requires shared immutable content. Legacy per-generation record
    # tables would require copying all records, so use the normal compiler there.
    storage = db.execute(
        "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records')"
    ).fetchone()
    if not storage or storage["relkind"] != "v":
        return None
    candidates = db.execute(
        "SELECT generation,manifest_raw,manifest FROM native_compiled_catalog_releases "
        "WHERE policy=%s AND source_revision=%s AND source_inventory_sha256=%s AND config_sha256=%s "
        "AND complete ORDER BY completed_at DESC",
        (pins[0], pins[1], pins[2], pins[4]),
    ).fetchall()
    for candidate in candidates:
        raw = bytes(candidate["manifest_raw"])
        if hashlib.sha256(raw).hexdigest() != candidate["generation"]:
            continue
        previous = candidate["manifest"]
        if canonical_bytes(previous) != raw:
            continue
        if not compatible(previous, identity):
            from tools.compiled_runtime_attestations import verified_unchanged_paths

            proved = verified_unchanged_paths(
                db,
                candidate["generation"],
                previous,
                identity,
                Path(__file__).resolve().parents[1],
            )
            if not compatible(previous, identity, proved):
                continue
        rows = db.execute(
            "SELECT c.collection,c.kind,c.record_count,c.ordered_keys_raw,c.ordered_keys_sha256,c.content_id, "
            "s.complete AS content_complete,s.collection AS content_collection,s.kind AS content_kind, "
            "s.representation AS content_representation,s.record_count AS content_count, "
            "s.ordered_keys_sha256 AS content_keys_sha256,s.records_sha256 AS content_records_sha256 "
            "FROM native_compiled_catalog_collections c "
            "LEFT JOIN native_compiled_collection_contents s ON s.content_id=c.content_id "
            "WHERE c.generation=%s",
            (candidate["generation"],),
        ).fetchall()
        declared = previous.get("collections", {})
        if len(rows) != len(declared) or any(
            row["collection"] not in declared
            or not row["content_complete"]
            or row["kind"] != declared[row["collection"]].get("kind")
            or row["record_count"] != declared[row["collection"]].get("count")
            or row["ordered_keys_sha256"]
            != declared[row["collection"]].get("ordered_keys_sha256")
            or row["content_collection"] != row["collection"]
            or row["content_kind"] != row["kind"]
            or row["content_count"] != row["record_count"]
            or row["content_representation"]
            != declared[row["collection"]].get("representation")
            or row["content_keys_sha256"] != row["ordered_keys_sha256"]
            or row["content_records_sha256"]
            != declared[row["collection"]].get("records_sha256")
            or hashlib.sha256(bytes(row["ordered_keys_raw"])).hexdigest()
            != row["ordered_keys_sha256"]
            for row in rows
        ):
            continue
        manifest = dict(previous)
        manifest.update(identity)
        manifest_raw = canonical_bytes(manifest)
        generation = hashlib.sha256(manifest_raw).hexdigest()
        db.execute(
            "INSERT INTO native_compiled_catalog_releases "
            "(generation,policy,source_revision,source_inventory_sha256,compiler_contract_sha256,config_sha256,manifest_raw,manifest) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (generation, *pins, manifest_raw, Jsonb(manifest)),
        )
        db.execute(
            "INSERT INTO native_compiled_catalog_collections "
            "(generation,collection,kind,record_count,ordered_keys_raw,ordered_keys_sha256,content_id) "
            "SELECT %s,collection,kind,record_count,ordered_keys_raw,ordered_keys_sha256,content_id "
            "FROM native_compiled_catalog_collections WHERE generation=%s",
            (generation, candidate["generation"]),
        )
        db.execute(
            "UPDATE native_compiled_catalog_releases SET complete=true,completed_at=now() WHERE generation=%s",
            (generation,),
        )
        return generation
    return None


def main():
    from wakfu_server import native_catalog
    from wakfu_server.native_compiled_catalog import (
        expected_publication_identity,
        canonical_bytes,
    )

    identity = expected_publication_identity()
    with native_catalog._database().connection() as db:
        if len(sys.argv) == 3 and sys.argv[1] == "--record":
            from tools.compiled_runtime_attestations import record_exact_publication

            generation = sys.argv[2]
            count = record_exact_publication(
                db,
                generation,
                identity,
                Path(__file__).resolve().parents[1],
                canonical_bytes,
            )
            print(
                json.dumps(
                    {"event": "compiled_runtime_projections_recorded", "count": count}
                ),
                file=sys.stderr,
                flush=True,
            )
            return
        if len(sys.argv) != 1:
            raise SystemExit(
                "Usage: reuse_unchanged_compiled_catalog.py [--record GENERATION]"
            )
        generation = try_reuse(db, identity, canonical_bytes)
    if generation:
        print(
            json.dumps(
                {
                    "event": "compiled_publication_reuse_checked",
                    "generation": generation,
                }
            ),
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    main()
