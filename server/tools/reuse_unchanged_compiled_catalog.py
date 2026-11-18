"""Reuse a sealed combat publication after unrelated runtime-only changes.

This fast path never reads or republishes individual combat records. Unknown
changes, non-shared storage, or incompatible inputs fall back to the compiler.
"""

import hashlib
import json
import sys
from pathlib import Path

from psycopg.types.json import Jsonb

# These modules handle live world operations and event settlement; the static
# combat compiler does not invoke their runtime or instance-authoring paths.
RUNTIME_ONLY = frozenset(
    {
        "wakfu_server/combat/combat_group_store.py",
        "wakfu_server/combat/rii_lesson_grants.py",
        "wakfu_server/maps/monster_removal_ecology.py",
        "wakfu_server/maps/rii_airyna_dialogue.py",
        "wakfu_server/maps/owned_physical_entry.py",
        "wakfu_server/maps/dungeon_transport.py",
        "wakfu_server/maps/dungeon_fight_binding.py",
        "wakfu_server/maps/owned_story_controller.py",
        "wakfu_server/maps/owned_story_admission.py",
        "wakfu_server/maps/owned_story_configuration.py",
        "wakfu_server/maps/owned_story_terminal_returns.py",
        "wakfu_server/maps/owned_story_defeat_qualification.py",
        "wakfu_server/combat/combat_death_events.py",
        "wakfu_server/application/session_travel.py",
        "wakfu_server/maps/dungeon_criteria.py",
        "wakfu_server/maps/owned_story_mechanics.py",
        "wakfu_server/maps/owned_story_native_links.py",
        "wakfu_server/application/owned_story_generic_entry_dispatch.py",
        "wakfu_server/maps/owned_story_dynamic_pickups.py",
        "wakfu_server/maps/owned_story_object_operations.py",
        "wakfu_server/maps/seasonal_native_gateway.py",
        "wakfu_server/achievements/source_quest_encounters.py",
        "wakfu_server/maps/monster_idle_distribution_store.py",
        "wakfu_server/application/owned_story_dispatch.py",
        "wakfu_server/maps/owned_story_npcs.py",
        "wakfu_server/maps/owned_story_reentry.py",
        "wakfu_server/maps/dungeon_progression.py",
        "wakfu_server/maps/quest_chest_supplies.py",
        "wakfu_server/maps/owned_story_reviewed_items.py",
        "wakfu_server/combat/combat_scene_controlled_states.py",
        "wakfu_server/combat/combat_scene_ball_follow.py",
        "wakfu_server/combat/combat_area_transaction.py",
        "wakfu_server/combat/combat_controller_transfer.py",
        "wakfu_server/combat/combat_ai_control.py",
        "wakfu_server/combat/combat_scene_ball_goals.py",
        "wakfu_server/combat/combat_encounter_scene_policy.py",
        "wakfu_server/combat/combat_environment_glyphs.py",
        "wakfu_server/combat/combat_ordinary_authority.py",
    }
)

# These modules are entry points for live World interactions. They are not
# imported outside the World application or by the catalog publisher; World dispatches
# them from the World application instead. A regression test checks references
# outside that application boundary so compiler dependencies remain reviewable.
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

# The Crow supplement extends the runtime book loader while the compiler reads
# the unchanged native_class_morph_profiles() domain. The payment adapter only
# forwards event replay options during live casts. The heal changes resolve
# the source and apply HP during a fight without changing compiled definitions;
# orientation resolves the already registered construction scope at execution.
REVIEWED_COMBAT_RUNTIME = {
    "wakfu_server/combat/combat_morph_spellbook.py": (
        "2405d0e1d2a9f0bb1a3742732df4ba9901cf7759fad72294e209718ca5425f74",
        "481e23d656048c282e692119bc80443d741f0abde310478a3d98a95b10674832",
    ),
    "wakfu_server/combat/combat_cost_payment_events.py": (
        "a98de7868329105d1873944ddab1c1988413745293148c9e82405aa3baef2c09",
        "68278492c6e4c9b23e12382a25862110e59d819cdeedc4482ffa541e3cf058bf",
    ),
    "wakfu_server/combat/combat_healing_handler.py": (
        "77547a6f7364f72c25df5acd4038c8b7eeb0d4d7eaac47e9aa2925c838336698",
        "ee47b93a723eef95f60662086856f77b0749f2ca8a271911e5726f78e43dedd0",
    ),
    "wakfu_server/combat/combat_orientation_effect.py": (
        "fc53ce73fc8af2d5935510ca7bd32ab981f8e2734537877aca9469707fbba4d4",
        "152da8b8df7af6a49c9348617a31231e6df67f252d28b7fe41928bd2d62b13c2",
    ),
    "wakfu_server/combat/combat_state.py": (
        "047e609ab9bae7cd96acf71a081665d97c5740f201c32e836246cac7337e1057",
        "6a1359a7ed69fd515ebd3efc37e50eaea7540de64d55a25a1041d9be592fdf54",
    ),
    "wakfu_server/combat/combat_vitality_execution.py": (
        "83d68504269882ede1dd44c621de70406cd1e722115ba0066264881bdfd47aac",
        "2ec531199cf799467fcb32920faac9e016e4d20048eadab6ab6cd24546c24303",
    ),
}


# Exact one-way removal of superseded autonomous ecology planners from the
# reviewed Rust ecology rollout. World-owned commit/validation bodies and all
# compiled records are unchanged. The baseline publication is bb2e6f0010fb...;
# every changed source must match this whole bundle, including deleted modules.
# Later edits, other source changes and catalog/config changes fail closed.
REVIEWED_ECOLOGY_REMOVAL_BUNDLE = {
    "wakfu_server/maps/monster_active_clocks.py": (
        "371b0bfd853a6cab98fbd29344db7d060a148936cf69f0f4c34ad33e0737d92e",
        None,
    ),
    "wakfu_server/maps/monster_birth_home.py": (
        "c3718cb83db83318e2d0bd10f177eefaa57df8088c38ab27550e3a96968123eb",
        None,
    ),
    "wakfu_server/maps/monster_home_delivery.py": (
        "b215db95879b4dcfb7f4ab597048e55f926367b467d15fff170325f4cff7d6ab",
        None,
    ),
    "wakfu_server/maps/monster_home_paths.py": (
        "d4e2f2f9016623f72427bf8de076193ed0c50179cddc14f53d5f14d039c9c455",
        None,
    ),
    "wakfu_server/maps/monster_idle_distribution.py": (
        "636ff9e292422cb6889419387bf7da23453ee70b3310d91bc44bd7b5c5fccf18",
        None,
    ),
    "wakfu_server/maps/monster_idle_distribution_store.py": (
        "5f5f7ba5d364b6aa909f34dda4139cdff298ed6848d52dcad218eba8bf0d6e93",
        "1c4e6a7d40aa8cac87aeb8c34b5054243a054826dfda36a3bb3fd8096e6b1085",
    ),
    "wakfu_server/maps/monster_life_plans.py": (
        "215a78d08ea5f0e3b53421dcfd9b2a6caa47ff9e766c64897d727277295a9f9b",
        "9bca5683334cef854cd8306891420b98fe7d1f216bdffe364e27f2a9ad6eac6b",
    ),
    "wakfu_server/maps/monster_maturation.py": (
        "358b61f5c2d84b77475c52b75e663218ca3709245ebf124ce081b2bcc60e19e4",
        "392dd52a97c45789f35e62ed25551751f643a5ba3cc2dbdf01c13b6fa2678843",
    ),
    "wakfu_server/maps/monster_reproduction.py": (
        "96d4d441763ea97d044360b44342096f3ffb704fbf75a83e7bb355394be654da",
        "f746c3538f20f48ee934635b9989b516b6a1445b80a089cf49e3355530fd052b",
    ),
    "wakfu_server/maps/monster_wander.py": (
        "56dfb764dfd99d79fb65ff5e16cd3dec963e5bf380fce132467e21335591fe03",
        "a55a7f0864fed2bfdec1ce48fba012b6b40b195948e03f8d71daa5a0ec124087",
    ),
}

# Concurrent retained-Python mission hooks, reviewed only for static artifact
# compatibility. Both edits are function-body runtime actions; no compiler
# entry, static definition or top-level import changes. This is not gameplay
# acceptance of those mission features. Approve them only together with the
# exact ecology removal above, never as a general exemption for Store/missions.
REVIEWED_MISSION_RUNTIME_BUNDLE = {
    "wakfu_server/storage/store.py": (
        "753c63a0ad151b38f22602d2a942d4b531a42bc44c5946edf1253f592ed2f4b6",
        "9fe144032050f6cee56d6b09da44870edb5702635dd1738fc056a1510b0380ff",
    ),
    "wakfu_server/application/session_objectives.py": (
        "2484878dcba6744b2fa93a64c56ef4e929f3b053580f83efff59a090c5f82177",
        "2bc0915e988b356ca132e04b8deea9f4a409de9c03cd66fe6ff9a88ee595c95b",
    ),
}


# Follow-up to sealed publication ae4d8d2f40f8...: retire the remaining inline
# ecology producers and require Rust-prepared proposals. The World validators,
# commit/receipt paths and native static catalog definitions remain authoritative.
# This whole exact seven-source transition stands alone: it cannot be combined
# with other changes or used to approve future edits to these modules.
REVIEWED_ECOLOGY_PREPARED_ONLY_BUNDLE = {
    "wakfu_server/application/bootstrap.py": (
        "48888f11935aaff72e362c77bd2a7529bcb9035a594a97187dc1d33233be19f7",
        "5b24a97c09ff862163b5d19e30162f4bc822bf6e6405896e4a5754ddbb70709d",
    ),
    "wakfu_server/application/session_inventory.py": (
        "583e863422146adb2c33b966bb2b8115d1209ffa249e463ce76e7b18d9bdde0b",
        "e84a3e2d5c7c03557928f3be12168666baa51bca0b35df4f9b9645f80c0cb219",
    ),
    "wakfu_server/maps/monster_group_balance.py": (
        "e6e13d04163ae6cede7bd75a16a940cecea2d278da1e5d4ba49dab48481ef5e4",
        "80d4e2e3c82ca894d243b06e8c213853a48400c7dc81b38a7f3d4443e6b376cb",
    ),
    "wakfu_server/maps/monster_maturation.py": (
        "392dd52a97c45789f35e62ed25551751f643a5ba3cc2dbdf01c13b6fa2678843",
        "fa16e631f05231a0126e06bf92445dfd6718696a1d8bb40cdc0401495573c447",
    ),
    "wakfu_server/maps/monster_reproduction.py": (
        "f746c3538f20f48ee934635b9989b516b6a1445b80a089cf49e3355530fd052b",
        "dee52e361eb10a245e53e8d4cae6f258800ee2ffef76fce96d6adb995baccb74",
    ),
    "wakfu_server/maps/planting_probability.py": (
        "7d26eaaa8b1d49e317ba463beb3037cf608cb0b204a0f8c9a8d2a14758020487",
        "26a751a610b9b0becf3f0d2cf209f2c1f970eef3c98684cc0065fe15f1dcf87d",
    ),
    "wakfu_server/maps/planting_runtime.py": (
        "72ca6957995e157724428397402edd6aed5ed46803d85eafee65932dfd886d55",
        "5ce1b33bf2b13242ec851077b1e7974c20289bb5da9e397fd34d05c295fa9a15",
    ),
}


# Exact one-way bridge: serialize only coordinates in live walking adapters.
# These functions are not called by static combat publication; native kernels,
# topology, source documents and compiler configuration remain unchanged.
REVIEWED_SPATIAL_WIRE_PROJECTION_BUNDLE = {
    "wakfu_server/maps/movement.py": (
        "b4d6dcf085ae84c2570de50be1ea8f4b0a482f4dde2eb8a60d0b52dbe3e215b8",
        "53bbb3ad44246b8cc9c4f632947444fb45e7b3647b66ad3c44879fca434655a0",
    ),
    "wakfu_server/maps/teleporter_approach.py": (
        "a46674e29305e17914b1c4d85dc0236bea301f5c54c95232f497bfd12f69311b",
        "35a109d0968a8bc176a12010eb205dc956b5a65ac15d949b18b7fbf86864ecc0",
    ),
    "wakfu_server/maps/world_scene_sync.py": (
        "aec553664f7167306ba0793c4eb761e67b28ace81bd3aecaef3ab72e7fe79721",
        "f9f7971c93329fad21c4676d7766fac9a2b73f9f7bee80da4a8c4c390ca0a56f",
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
    if changed == set(REVIEWED_SPATIAL_WIRE_PROJECTION_BUNDLE) and all(
        (old.get(path), new.get(path)) == hashes
        for path, hashes in REVIEWED_SPATIAL_WIRE_PROJECTION_BUNDLE.items()
    ):
        return True
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
    if changed == set(REVIEWED_ECOLOGY_REMOVAL_BUNDLE) and all(
        (old.get(path), new.get(path)) == hashes
        for path, hashes in REVIEWED_ECOLOGY_REMOVAL_BUNDLE.items()
    ):
        return True
    ecology_and_missions = {
        **REVIEWED_ECOLOGY_REMOVAL_BUNDLE,
        **REVIEWED_MISSION_RUNTIME_BUNDLE,
    }
    if changed == set(ecology_and_missions) and all(
        (old.get(path), new.get(path)) == hashes
        for path, hashes in ecology_and_missions.items()
    ):
        return True
    if changed == set(REVIEWED_ECOLOGY_PREPARED_ONLY_BUNDLE) and all(
        (old.get(path), new.get(path)) == hashes
        for path, hashes in REVIEWED_ECOLOGY_PREPARED_ONLY_BUNDLE.items()
    ):
        return True
    reviewed_transition = (
        PUBLISHER_SOURCE in changed
        and (old.get(PUBLISHER_SOURCE), new.get(PUBLISHER_SOURCE))
        in REVIEWED_PUBLISHER_TRANSITIONS
    )
    allowed = RUNTIME_ONLY | WORLD_DISPATCH_ONLY | set(proved_paths)
    allowed |= {
        path
        for path, hashes in REVIEWED_COMBAT_RUNTIME.items()
        if (old.get(path), new.get(path)) == hashes
    }
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
