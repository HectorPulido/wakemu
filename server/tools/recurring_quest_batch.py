"""Compile and publish additive native-backed daily hunter/Modulox contracts.

Build consumes read-only native snapshots. Publish revalidates native quest and
monster identity, immutable plan hashes and existing NPC category contracts.
It never changes player progress, current-day choices, routes or old contracts.
"""

import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import unicodedata

SCHEMA = "wakemu.recurring-quest-batch-v1"
DAILY = "wakemu.daily-hunter-native-objective-final-room-v1"
MODULOX = "wakemu.modulox-native-adjusted-final-room-v1"
SELECTOR = "wakemu.daily-hunter-utc-sorted-rotation-v1"
DAILY_MINIMUM = "wakemu-reconstruction:original-native-category-bracket-minimum"
SOURCE = (
    "Wakemu-native-objective+multilingual-boss+original-aKU+BOSS43+immutable-final-room"
)


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def plan_digest(value):
    """Use the existing dungeon publication canonicalization, including Unicode."""
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def normalize(value):
    return (
        re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).replace("’", "'"))
        .strip()
        .casefold()
    )


def compile_batch(
    quests,
    dungeons,
    monsters,
    routes,
    translations,
    context,
    *,
    reconstruct_native_aliases=False,
):
    """Join numerical native identities; preserve unresolved or ambiguous rows."""
    client_jar = "client/lib/wakfu-client.jar"
    if quests["source_sha256"][client_jar] != dungeons["source_sha256"][client_jar]:
        raise ValueError("Native quest and dungeon client versions differ")
    for language in ("en", "fr", "es"):
        archive = f"client/contents/i18n/i18n_{language}.jar"
        if translations["source_sha256"].get(archive) != quests["source_sha256"].get(
            archive
        ):
            raise ValueError(
                "Native quest and monster/dungeon localization versions differ"
            )
    native_monsters = {row["ref"]: row for row in monsters["monsters"]}
    known = set(context["known_ids"])
    categories = {row["category_id"]: row for row in context["modulox_categories"]}
    names = {}
    for language in ("en", "fr", "es"):
        names[language] = defaultdict(set)
        for key, value in translations[language].items():
            match = re.fullmatch(r"content\.7\.([0-9]+)", key)
            if match:
                names[language][normalize(value)].add(int(match[1]))
                if reconstruct_native_aliases and "," in value:
                    names[language][normalize(value.split(",", 1)[0])].add(
                        int(match[1])
                    )
    localizations = quests["translations"]

    def text(language, kind, identity):
        return localizations[language].get(f"content.{kind}.{identity}", "")

    qualified, pending = [], []
    for definition in sorted(quests["definitions"], key=lambda row: row["d"]):
        identity = definition["d"]
        category = definition["cjG"]
        category_en = text("en", 61, category)
        family = (
            MODULOX
            if category in categories
            else (
                DAILY
                if re.fullmatch(r"Boss Hunt \[[0-9]{3}-[0-9]{3}\]", category_en)
                else None
            )
        )
        if family is None or identity in known:
            continue
        reason = None
        objectives = definition.get("cjJ", ())
        if (
            definition.get("aqb") is not False
            or definition.get("cjU") != 86400
            or definition.get("cjL") != 0
            or definition.get("getDuration") != 0
            or definition.get("cjR") is not True
            or len(objectives) != 1
            or any(objectives[0].get(k) for k in ("ckc", "ckd", "cke", "ckf"))
        ):
            reason = "unsupported_native_lifecycle_or_objective"
        if reason:
            pending.append({"quest_id": identity, "reason": reason})
            continue
        objective = objectives[0]["d"]
        objective_texts = {
            language: text(language, 64, objective) for language in names
        }
        titles = {language: text(language, 62, identity) for language in names}
        votes = Counter()
        for language, title in titles.items():
            suffix = title.split(":", 1)[1].strip() if ":" in title else ""
            votes.update(names[language].get(normalize(suffix), ()))
        boss_candidates = {
            reference for reference, count in votes.items() if count >= 2
        }
        pairs = []
        unique_membership_pairs = []
        for original in dungeons["definitions"]:
            if original.get("native_class") != "aKU":
                continue
            dungeon_id = original["d"]
            literal_languages = [
                language
                for language in names
                if translations[language].get(f"content.137.{dungeon_id}")
                and normalize(translations[language][f"content.137.{dungeon_id}"])
                in normalize(objective_texts[language])
            ]
            for boss in sorted(boss_candidates.intersection(original["cno"])):
                actor = native_monsters.get(boss)
                if actor is None or 43 not in actor.get("raw_visual_arrays", {}).get(
                    "csc", ()
                ):
                    continue
                unique_membership_pairs.append((boss, original, literal_languages))
                if literal_languages:
                    pairs.append((boss, original, literal_languages))
        reconstructed_membership = False
        if (
            not pairs
            and reconstruct_native_aliases
            and len(unique_membership_pairs) == 1
        ):
            pairs = unique_membership_pairs
            reconstructed_membership = True
        if len(pairs) != 1:
            pending.append(
                {
                    "quest_id": identity,
                    "reason": "native_dungeon_boss_pair_not_unique",
                    "pair_count": len(pairs),
                }
            )
            continue
        boss, original, literal_languages = pairs[0]
        prepared = []
        for route in routes:
            config = route["configuration"]
            plan = config["compiled_plan"]
            if (
                plan["definition_id"] != original["d"]
                or config["route"]["start_map_id"] not in original["aHA"]
                or not plan["rooms"]
            ):
                continue
            final = max(plan["rooms"], key=lambda row: row["order"])
            final_bosses = {
                row["ref_id"] for row in final["monsters"] if row["role"] == "boss"
            }
            if final_bosses == {boss} or (
                family == DAILY and reconstruct_native_aliases and boss in final_bosses
            ):
                prepared.append((route, final))
        if len(prepared) != 1:
            pending.append(
                {
                    "quest_id": identity,
                    "reason": "active_final_room_not_unique_strict_boss",
                    "route_count": len(prepared),
                    "boss_reference": boss,
                    "dungeon_definition_id": original["d"],
                }
            )
            continue
        route, final = prepared[0]
        rewards = definition["cjK"]
        expected = {5, 17} if family == MODULOX else {5, 6}
        if len(rewards) != 2 or {row["aeV"] for row in rewards} != expected:
            pending.append(
                {"quest_id": identity, "reason": "native_reward_family_changed"}
            )
            continue
        if family == MODULOX:
            minimum = re.fullmatch(r"GetRealLevel\(\) >= ([0-9]+)", definition["cjI"])
            target = re.fullmatch(
                r"Complete .+ at level ([0-9]+)", objective_texts["en"]
            )
            if (
                minimum is None
                or target is None
                or definition["aHe"] != f"IsAchievementRunning({identity})"
            ):
                pending.append(
                    {
                        "quest_id": identity,
                        "reason": "native_modulox_offer_or_level_unsupported",
                    }
                )
                continue
            minimum_level = max(
                int(minimum[1]), categories[category]["offer_minimum_level"]
            )
            effective_level = int(target[1])
        else:
            if definition["aHe"] or definition["cjI"]:
                pending.append(
                    {
                        "quest_id": identity,
                        "reason": "native_daily_eligibility_requires_adapter",
                    }
                )
                continue
            minimum_level = int(
                re.fullmatch(r"Boss Hunt \[([0-9]{3})-[0-9]{3}\]", category_en)[1]
            )
            effective_level = None
        occurrences = [
            {"monster_index": index, "planned_role": row["role"], "count": row["count"]}
            for index, row in enumerate(final["monsters"])
            if row["ref_id"] == boss
        ]
        proof = {
            "native_definition_sha256": digest(definition),
            "native_dungeon": original,
            "native_dungeon_source_sha256": dungeons["source_sha256"],
            "objective_localizations": objective_texts,
            "title_localizations": titles,
            "literal_dungeon_languages": literal_languages,
            "native_boss_reference": boss,
            "native_boss_property": 43,
            "native_monster_names": {
                language: translations[language].get(f"content.7.{boss}")
                for language in names
            },
            "native_dungeon_names": {
                language: translations[language].get(f"content.137.{original['d']}")
                for language in names
            },
            "target_occurrences": occurrences,
        }
        if reconstruct_native_aliases:
            exact_votes = sum(
                normalize(titles[language].split(":", 1)[1])
                == normalize(translations[language].get(f"content.7.{boss}", ""))
                for language in names
                if ":" in titles[language]
            )
            extensions = []
            if exact_votes < 2:
                extensions.append(
                    "exact-native-name-head-before-comma-in-at-least-two-locales"
                )
            if reconstructed_membership:
                extensions.append(
                    "unique-native-boss-to-aKU-membership-plus-actual-final-room"
                )
            if (
                len(
                    {
                        monster["ref_id"]
                        for monster in final["monsters"]
                        if monster["role"] == "boss"
                    }
                )
                > 1
            ):
                extensions.append(
                    "named-native-boss-occurrence-in-completed-multiple-boss-final-room"
                )
            if extensions:
                proof["reviewed_binding_extensions"] = extensions
        qualified.append(
            {
                "definition_id": identity,
                "version": 1,
                "objective_id": objective,
                "category_id": category,
                "minimum_level": minimum_level,
                "required_distinct": 1,
                "anchor_ms": definition["cjT"],
                "period_ms": 86400000,
                "cooldown_ms": 0,
                "interpretation_policy": family,
                "boss_reference": boss,
                "dungeon_definition_id": original["d"],
                "route_key": route["route_key"],
                "route_policy_version": route["policy_version"],
                "final_room_order": final["order"],
                "plan_sha256": plan_digest(route["configuration"]["compiled_plan"]),
                "native_catalog_revision": context["native_revision"],
                "monsters_path": "monsters.json",
                "monsters_sha256": context["monsters_sha256"],
                "native_definition_sha256": digest(definition),
                "original_activation_criterion": definition["aHe"],
                "original_eligibility_criterion": definition["cjI"],
                "original_objective_en": objective_texts["en"],
                "target_effective_level": effective_level,
                "rewards": rewards,
                "offer": categories.get(category),
                "proof": proof,
                "proof_sha256": digest(proof),
                "occurrences": occurrences,
            }
        )
    return {
        "schema": SCHEMA,
        "native_quest_inventory_sha256": digest(quests),
        "source_policy": SOURCE,
        "native_input_sources": {
            "quest_export": quests["source_sha256"],
            "dungeon_export": dungeons["source_sha256"],
            "translations": translations["source_sha256"],
        },
        "qualified": qualified,
        "pending": pending,
        "counts": {
            "qualified": len(qualified),
            "daily": sum(row["interpretation_policy"] == DAILY for row in qualified),
            "modulox": sum(
                row["interpretation_policy"] == MODULOX for row in qualified
            ),
            "pending": len(pending),
        },
    }


def _insert_exact(db, table, row):
    """Insert immutable operator data; reject conflicting replay instead of overwrite."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    columns = tuple(row)
    values = tuple(
        Jsonb(value) if isinstance(value, dict) else value for value in row.values()
    )
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(",").join(sql.Placeholder() for _ in columns),
    )
    db.execute(query, values)
    key = ("definition_id", "version") if "definition_id" in row else ("pool_version",)
    if table == "recurring_hunter_targets":
        key += ("boss_reference",)
    elif table == "recurring_hunter_rewards":
        key += ("reward_id",)
    elif table == "recurring_hunter_native_target_occurrences":
        key += ("monster_index",)
    elif table == "recurring_hunter_acceptance_sources":
        key += ("source_kind", "source_reference", "action_id")
    elif table == "recurring_hunter_daily_members":
        key = ("pool_version", "category_id", "definition_id", "version")
    elif table == "recurring_hunter_catalog_sources":
        key = ("native_catalog_revision", "monsters_path", "monsters_sha256")
    found = db.execute(
        sql.SQL("SELECT {} FROM {} WHERE {}").format(
            sql.SQL(",").join(map(sql.Identifier, columns)),
            sql.Identifier(table),
            sql.SQL(" AND ").join(
                sql.SQL("{}=%s").format(sql.Identifier(name)) for name in key
            ),
        ),
        tuple(row[name] for name in key),
    ).fetchone()
    if found is None or any(found[name] != row[name] for name in columns):
        raise ValueError("Conflicting immutable recurring publication: " + table)


def install(db, manifest, *, apply=False):
    """Revalidate and atomically publish a reviewed batch and additive daily pool."""
    from wakfu_server import native_catalog
    from wakfu_server.native_catalog_compatibility import require_source_revision
    from wakfu_server.objectives import environmental_recurring_storage as recurring
    from wakfu_server.achievements import rewards as native_rewards

    if manifest.get("schema") != SCHEMA or manifest.get("source_policy") != SOURCE:
        raise ValueError("Unsupported recurring batch manifest")
    rows = manifest["qualified"]
    ids = [row["definition_id"] for row in rows]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate recurring batch")
    added = 0
    with db.transaction():
        db.execute("SELECT pg_advisory_xact_lock(%s)", (202611150381,))
        active = db.execute(
            "SELECT a.*,p.interpretation_policy,p.sealed FROM recurring_hunter_daily_active a JOIN recurring_hunter_daily_pools p USING(pool_version) WHERE a.singleton FOR UPDATE OF a"
        ).fetchone()
        if (
            not active
            or not active["sealed"]
            or active["interpretation_policy"] != SELECTOR
        ):
            raise ValueError("Existing qualified daily selector required")
        members = [
            dict(row)
            for row in db.execute(
                "SELECT category_id,definition_id,version FROM recurring_hunter_daily_members WHERE pool_version=%s ORDER BY category_id,definition_id,version",
                (active["pool_version"],),
            ).fetchall()
        ]
        for row in rows:
            identity, version = row["definition_id"], row["version"]
            source = db.execute(
                "SELECT data FROM native_quest_metadata_definitions WHERE definition_id=%s AND revision=(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1)",
                (identity,),
            ).fetchone()
            if (
                not source
                or digest(source["data"]["native"]) != row["native_definition_sha256"]
            ):
                raise ValueError("Native quest definition differs from reviewed batch")
            definition = source["data"]["native"]
            if (
                row["version"] != 1
                or definition.get("aqb") is not False
                or definition.get("cjU") != 86400
                or definition.get("cjL") != 0
                or definition.get("getDuration") != 0
                or definition.get("cjR") is not True
                or len(definition["cjJ"]) != 1
                or definition["cjJ"][0]["d"] != row["objective_id"]
                or any(
                    definition["cjJ"][0].get(key)
                    for key in ("ckc", "ckd", "cke", "ckf")
                )
                or row["category_id"] != definition["cjG"]
                or row["anchor_ms"] != definition["cjT"]
                or row["period_ms"] != 86400000
                or row["cooldown_ms"] != 0
                or row["required_distinct"] != 1
                or row["original_activation_criterion"] != definition["aHe"]
                or row["original_eligibility_criterion"] != definition["cjI"]
            ):
                raise ValueError("Reviewed batch changes native lifecycle or objective")
            if (
                definition["cjK"] != row["rewards"]
                or digest(row["proof"]) != row["proof_sha256"]
            ):
                raise ValueError(
                    "Native reward or provenance differs from reviewed batch"
                )
            for reward in row["rewards"]:
                native_rewards.validate(reward)
            require_source_revision(
                row["native_catalog_revision"], (row["monsters_path"],)
            )
            actor = native_catalog.record(
                native_catalog.DATA_ROOT / "monsters.json",
                "monsters",
                row["boss_reference"],
            )
            if (
                not actor
                or 43 not in actor.get("raw_visual_arrays", {}).get("csc", ())
                or native_catalog.document_hashes()["monsters.json"]
                != row["monsters_sha256"]
            ):
                raise ValueError("Native boss identity/source changed")
            route = db.execute(
                "SELECT c.configuration FROM dungeon_runtime_configurations c JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version) WHERE c.route_key=%s AND c.policy_version=%s",
                (row["route_key"], row["route_policy_version"]),
            ).fetchone()
            if (
                not route
                or plan_digest(route["configuration"]["compiled_plan"])
                != row["plan_sha256"]
            ):
                raise ValueError("Active immutable dungeon plan changed")
            final = max(
                route["configuration"]["compiled_plan"]["rooms"],
                key=lambda room: room["order"],
            )
            original = row["proof"]["native_dungeon"]
            actual_occurrences = [
                dict(
                    monster_index=index,
                    planned_role=monster["role"],
                    count=monster["count"],
                )
                for index, monster in enumerate(final["monsters"])
                if monster["ref_id"] == row["boss_reference"]
            ]
            if (
                row["proof"]["native_definition_sha256"]
                != row["native_definition_sha256"]
                or original.get("native_class") != "aKU"
                or row["proof"]["native_boss_reference"] != row["boss_reference"]
                or row["proof"]["native_boss_property"] != 43
                or original["d"] != row["dungeon_definition_id"]
                or row["boss_reference"] not in original["cno"]
                or route["configuration"]["route"]["start_map_id"]
                not in original["aHA"]
                or route["configuration"]["compiled_plan"]["definition_id"]
                != original["d"]
                or final["order"] != row["final_room_order"]
                or actual_occurrences != row["occurrences"]
                or actual_occurrences != row["proof"]["target_occurrences"]
            ):
                raise ValueError(
                    "Native dungeon identity or final target occurrence changed"
                )
            final_bosses = {
                m["ref_id"] for m in final["monsters"] if m["role"] == "boss"
            }
            multiple_boss_daily = (
                row["interpretation_policy"] == DAILY
                and row["boss_reference"] in final_bosses
                and "named-native-boss-occurrence-in-completed-multiple-boss-final-room"
                in row["proof"].get("reviewed_binding_extensions", ())
            )
            if final_bosses != {row["boss_reference"]} and not multiple_boss_daily:
                raise ValueError("Final room lost its exact boss role")
            family = row["interpretation_policy"]
            if family == MODULOX:
                offer = db.execute(
                    "SELECT * FROM recurring_modulox_category_sources WHERE category_id=%s",
                    (row["category_id"],),
                ).fetchone()
                if not offer or dict(offer) != row["offer"]:
                    raise ValueError("Original Modulox category offer changed")
                minimum = re.fullmatch(
                    r"GetRealLevel\(\) >= ([0-9]+)", definition["cjI"]
                )
                target = re.fullmatch(
                    r"Complete .+ at level ([0-9]+)", row["original_objective_en"]
                )
                native_en = source["data"]["objective_texts"][str(row["objective_id"])][
                    "en"
                ]
                if (
                    minimum is None
                    or target is None
                    or definition["aHe"] != f"IsAchievementRunning({identity})"
                    or native_en != row["original_objective_en"]
                    or row["minimum_level"]
                    != max(int(minimum[1]), offer["offer_minimum_level"])
                    or row["target_effective_level"] != int(target[1])
                ):
                    raise ValueError("Reviewed batch changes native Modulox level")
                npc_ref, action, source_policy = (
                    4399,
                    884,
                    "wakemu.reconstructed-modulox-haven-bag-v1",
                )
            elif family == DAILY:
                offer = db.execute(
                    "SELECT 1 FROM recurring_hunter_native_offers WHERE category_id=%s",
                    (row["category_id"],),
                ).fetchone()
                if not offer:
                    raise ValueError(
                        "Daily hunt category has no existing native hunter offer"
                    )
                bracket = re.fullmatch(
                    r"Boss Hunt \[([0-9]{3})-[0-9]{3}\]",
                    source["data"]["category"]["en"],
                )
                if (
                    bracket is None
                    or definition["aHe"]
                    or definition["cjI"]
                    or row["minimum_level"] != int(bracket[1])
                    or row["target_effective_level"] is not None
                ):
                    raise ValueError(
                        "Reviewed batch changes native daily level interpretation"
                    )
                npc_ref, action, source_policy = (
                    3819,
                    703,
                    "wakemu.hunter-choice-daily-and-weekly-v1",
                )
            else:
                raise ValueError("Unsupported recurring contract family")
            existing = db.execute(
                "SELECT 1 FROM recurring_hunter_contracts WHERE definition_id=%s AND version=%s",
                (identity, version),
            ).fetchone()
            added += existing is None
            if not apply:
                continue
            contract = {
                name: row[name]
                for name in (
                    "definition_id",
                    "version",
                    "objective_id",
                    "minimum_level",
                    "required_distinct",
                    "anchor_ms",
                    "period_ms",
                    "cooldown_ms",
                    "interpretation_policy",
                )
            }
            contract["source_authority"] = SOURCE + ":" + row["proof_sha256"]
            _insert_exact(db, "recurring_hunter_contracts", contract)
            _insert_exact(
                db,
                "recurring_hunter_catalog_sources",
                {
                    name: row[name]
                    for name in (
                        "native_catalog_revision",
                        "monsters_path",
                        "monsters_sha256",
                    )
                },
            )
            _insert_exact(
                db,
                "recurring_hunter_targets",
                dict(
                    definition_id=identity,
                    version=version,
                    boss_reference=row["boss_reference"],
                    variable_name=f"wakemu.{ 'modulox' if family == MODULOX else 'daily' }.boss.{row['boss_reference']}",
                ),
            )
            for reward in row["rewards"]:
                kind, params = reward["aeV"], reward["ckl"]
                _insert_exact(
                    db,
                    "recurring_hunter_rewards",
                    dict(
                        definition_id=identity,
                        version=version,
                        reward_id=reward["d"],
                        native_type=kind,
                        reference=params[0] if kind == 5 else None,
                        amount=params[1] if kind == 5 else params[0],
                        native_flag=reward["ckk"],
                    ),
                )
            authority = {
                name: row[name]
                for name in (
                    "definition_id",
                    "version",
                    "boss_reference",
                    "dungeon_definition_id",
                    "route_key",
                    "route_policy_version",
                    "final_room_order",
                    "category_id",
                    "minimum_level",
                    "native_catalog_revision",
                    "monsters_path",
                    "monsters_sha256",
                    "plan_sha256",
                    "interpretation_policy",
                )
            }
            authority.update(
                minimum_level_authority=(
                    "native-definition+original-node3972-offer-maximum"
                    if family == MODULOX
                    else DAILY_MINIMUM
                ),
                reward_policy=(
                    "native17-frozen-real-level-no-subscription"
                    if family == MODULOX
                    else "fixed-native-parameter-no-booster"
                ),
                native_reward_order=[r["d"] for r in row["rewards"]],
                source_authority=SOURCE,
            )
            if family == MODULOX:
                authority.update(
                    {
                        name: row[name]
                        for name in (
                            "target_effective_level",
                            "original_activation_criterion",
                            "original_eligibility_criterion",
                            "original_objective_en",
                        )
                    }
                )
                authority.update(
                    {
                        name: row["offer"][name]
                        for name in (
                            "offer_node_id",
                            "offer_choice_id",
                            "offer_criterion",
                            "offer_source_sha256",
                        )
                    }
                )
                authority["public_corroborated"] = False
                _insert_exact(db, "recurring_modulox_authority", authority)
            else:
                authority.update(
                    native_property_id=43,
                    proof_sha256=row["proof_sha256"],
                    provenance=row["proof"],
                )
                _insert_exact(db, "recurring_hunter_native_target_authority", authority)
                for occurrence in row["occurrences"]:
                    _insert_exact(
                        db,
                        "recurring_hunter_native_target_occurrences",
                        dict(definition_id=identity, version=version, **occurrence),
                    )
            _insert_exact(
                db,
                "recurring_hunter_acceptance_sources",
                dict(
                    definition_id=identity,
                    version=version,
                    source_kind="npc_dialogue",
                    source_reference=npc_ref,
                    action_id=action,
                    source_authority=source_policy,
                ),
            )
            recurring._load(db, identity, version)
            member = dict(
                category_id=row["category_id"], definition_id=identity, version=version
            )
            if member not in members:
                members.append(member)
        if apply:
            members.sort(
                key=lambda member: (
                    member["category_id"],
                    member["definition_id"],
                    member["version"],
                )
            )
            pool_sha = digest(members)
            pool = "wakemu.quest-toolkit-recurring-" + pool_sha[:16]
            found = db.execute(
                "SELECT * FROM recurring_hunter_daily_pools WHERE pool_version=%s",
                (pool,),
            ).fetchone()
            if found is None:
                _insert_exact(
                    db,
                    "recurring_hunter_daily_pools",
                    dict(
                        pool_version=pool,
                        interpretation_policy=SELECTOR,
                        source_sha256=pool_sha,
                        sealed=False,
                    ),
                )
                for member in members:
                    _insert_exact(
                        db,
                        "recurring_hunter_daily_members",
                        dict(pool_version=pool, **member),
                    )
                db.execute(
                    "UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version=%s",
                    (pool,),
                )
            elif found["source_sha256"] != pool_sha or not found["sealed"]:
                raise ValueError("Conflicting sealed daily pool")
            db.execute(
                "UPDATE recurring_hunter_daily_active SET pool_version=%s WHERE singleton",
                (pool,),
            )
        else:
            pool = active["pool_version"]
    return dict(
        applied=apply,
        incoming=len(rows),
        new_contracts=added,
        pool_version=pool,
        player_progress_modified=False,
    )


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    build = sub.add_parser("build")
    build.add_argument(
        "--reconstruct-native-aliases",
        action="store_true",
        help="Review exact native comma-appositions, unique boss/aKU membership and named daily targets in multi-boss final rooms",
    )
    for name in (
        "quests",
        "dungeons",
        "monsters",
        "routes",
        "translations",
        "context",
        "output",
    ):
        build.add_argument("--" + name, type=Path, required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("manifest", type=Path)
    publish.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.operation == "build":
        result = compile_batch(
            *(
                read(getattr(args, name))
                for name in (
                    "quests",
                    "dungeons",
                    "monsters",
                    "routes",
                    "translations",
                    "context",
                )
            ),
            reconstruct_native_aliases=args.reconstruct_native_aliases,
        )
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result["counts"]))
    else:
        from wakfu_server.postgres import Database

        database = Database(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        try:
            with database.connection() as db:
                print(json.dumps(install(db, read(args.manifest), apply=args.apply)))
        finally:
            database.close()


if __name__ == "__main__":
    main()
