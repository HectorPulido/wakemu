#!/usr/bin/env python3
"""Author and inspect generic, native-backed mission event profiles.

Usage: python3 server/tools/mission_toolkit.py --help
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from wakfu_server.achievements import counter_missions, mission_toolkit_contract

VERIFIED_WIRED_PRODUCERS = {
    "monster_harvest": "maps/monster_collect.py complete; actual collected item reference and quantity",
    "resource_harvest": "maps/resource_collect.py complete; actual collected resource reference and quantity",
    "planting": "maps/planting.py complete; planted seed reference after successful planting",
    "craft_completed": "items/crafting.py complete; recipe reference and committed recipe-batch executions (not total products)",
    "monster_defeat": "achievements/service.py fresh authenticated victory; original defeated breeds",
    "dungeon_completed": "achievements/service.py fresh validated final-room completion; completed_dungeon_id reference, fight:<id> receipt",
}
SCOPED_WIRED_PRODUCERS = {
    "map_enter": "storage/store.py character creation and maps/mission_transport.py real map/instance transitions only",
    "dialogue": "application/session_objectives.py choose_toolkit_dialogue; plain native fallback accepted choice only, not every custom quest dialogue",
    "item_delivery": "achievements/conversation_turnin.py qualified native conversation turn-ins after actual payment and mission reward commit in the same transaction; consumed item reference and required quantity; observes consumption, does not define NPC delivery contracts",
}
INTERNAL_EVENT_SOURCES = {
    "quest_completed": "mission_toolkit planner emits this only from completions produced within the same active profile settlement; no general external quest-completion producer",
}


def _connection():
    from wakfu_server.postgres import Database

    url = os.environ.get("WAKFU_DATABASE_URL", "")
    parsed = urlparse(url)
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Mission toolkit CLI only connects to a local PostgreSQL host")
    if not parsed.path.strip("/").startswith("wakemu"):
        raise ValueError("Mission toolkit CLI requires a local Wakemu database")
    return Database(
        url,
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        min_size=1,
        max_size=2,
    )


def _native_revision(db):
    row = db.execute(
        "SELECT revision FROM native_quest_metadata_releases "
        "ORDER BY imported_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise ValueError("No imported native quest metadata release")
    return row["revision"]


def native_definitions(db, quest_ids, *, revision=None):
    ids = sorted(set(quest_ids))
    if not ids or any(type(identity) is not int or identity <= 0 for identity in ids):
        raise ValueError("Provide positive native quest IDs")
    revision = revision or _native_revision(db)
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions "
        "WHERE revision=%s AND definition_id=ANY(%s) ORDER BY definition_id",
        (revision, ids),
    ).fetchall()
    definitions = {row["definition_id"]: row["data"]["native"] for row in rows}
    missing = sorted(set(ids) - set(definitions))
    if missing:
        raise ValueError(f"Native quest metadata missing IDs: {missing}")
    return revision, definitions


def referenced_quest_ids(profile):
    identities = set()
    for row in profile.get("bindings", ()):
        if isinstance(row, dict) and type(row.get("quest_id")) is int:
            identities.add(row["quest_id"])
    for row in profile.get("activations", ()):
        if isinstance(row, dict) and type(row.get("quest_id")) is int:
            identities.add(row["quest_id"])
    for row in profile.get("links", ()):
        if not isinstance(row, dict):
            continue
        for key in ("parent_quest_id", "child_quest_id"):
            if type(row.get(key)) is int:
                identities.add(row[key])
    return sorted(identities)


def scaffold_profile(profile_id, quest_ids, definitions, *, instances=()):
    """Create a deliberately incomplete manifest from exact native metadata."""
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError("A profile ID is required")
    counters = counter_missions.bindings(list(definitions.values()))
    bindings = []
    activations = []
    candidates = []
    for quest_id in sorted(set(quest_ids)):
        definition = definitions.get(quest_id)
        if definition is None or definition.get("native_class") != "aJM":
            raise ValueError(f"Quest {quest_id} is not a native quest definition")
        activations.append(
            {
                "id": f"activate-{quest_id}",
                "quest_id": quest_id,
                "event": {"kind": "", "reference": 0},
                **({"instances": sorted(set(instances))} if instances else {}),
            }
        )
        for objective in definition.get("cjJ", ()):
            objective_id = objective["d"]
            rows = [
                row
                for values in counters.values()
                for row in values
                if row[0] == quest_id and row[1] == objective_id
            ]
            binding = {
                "id": f"objective-{quest_id}-{objective_id}",
                "quest_id": quest_id,
                "objective_id": objective_id,
                "event": {"kind": "", "reference": 0},
                "count": "",
                **({"instances": sorted(set(instances))} if instances else {}),
            }
            if len(rows) == 1:
                binding["variable_id"] = rows[0][2]
                candidates.append(
                    {
                        "quest_id": quest_id,
                        "objective_id": objective_id,
                        "variable_id": rows[0][2],
                        "native_threshold": rows[0][3],
                        "status": "counter_candidate_only_needs_producer_binding",
                    }
                )
            else:
                candidates.append(
                    {
                        "quest_id": quest_id,
                        "objective_id": objective_id,
                        "native_objective_class": objective.get("native_class"),
                        "status": "needs_binding",
                    }
                )
            bindings.append(binding)
    return (
        {
            "version": 1,
            "id": profile_id,
            "evidence": [],
            "bindings": bindings,
            "links": [],
            "activations": activations,
        },
        candidates,
    )


def validation_diagnostics(profile, definitions):
    """Return only contract errors; partial profiles may augment other indexes."""
    diagnostics = []
    if not any(profile.get(field) for field in ("bindings", "links", "activations")):
        diagnostics.append("Profile contains no mission declarations.")
    for section in ("bindings", "activations"):
        for row in profile.get(section, ()):
            if not isinstance(row, dict):
                continue
            event = row.get("event")
            if not isinstance(event, dict) or not event.get("kind"):
                diagnostics.append(
                    f"{section[:-1]} {row.get('id', '<unnamed>')} needs an explicit producer binding."
                )
    try:
        mission_toolkit_contract.validate(profile, definitions)
    except (KeyError, TypeError, ValueError) as error:
        diagnostics.append(str(error))
    return diagnostics


def producer_warnings(profile):
    """Explain producer scope gaps even when partial profiles are allowed."""
    declared = (
        set(VERIFIED_WIRED_PRODUCERS)
        | set(SCOPED_WIRED_PRODUCERS)
        | set(INTERNAL_EVENT_SOURCES)
    )
    warnings = []
    for section in ("bindings", "activations"):
        for row in profile.get(section, ()):
            if not isinstance(row, dict):
                continue
            event = row.get("event")
            kind = event.get("kind") if isinstance(event, dict) else None
            if kind == "scenario_completed":
                warnings.append(
                    f"{section[:-1]} {row.get('id', '<unnamed>')} uses scenario_completed, which is declared-only and has no connected producer."
                )
            elif kind and kind not in declared:
                warnings.append(
                    f"{section[:-1]} {row.get('id', '<unnamed>')} uses {kind}, which has no connected producer."
                )
            elif kind in SCOPED_WIRED_PRODUCERS:
                warnings.append(
                    f"{section[:-1]} {row.get('id', '<unnamed>')} uses {kind}; verify it is within the producer scope: {SCOPED_WIRED_PRODUCERS[kind]}."
                )
            elif kind in INTERNAL_EVENT_SOURCES:
                warnings.append(
                    f"{section[:-1]} {row.get('id', '<unnamed>')} uses {kind}, available only for active-profile dependency settlement."
                )
    return warnings


def strict_producer_errors(profile):
    """Reject declarations whose event has no external producer in strict mode."""
    errors = []
    for section in ("bindings", "activations"):
        for row in profile.get(section, ()):
            if not isinstance(row, dict):
                continue
            event = row.get("event")
            kind = event.get("kind") if isinstance(event, dict) else None
            if kind == "scenario_completed" or (
                kind == "quest_completed" and section == "bindings"
            ):
                errors.append(
                    f"{section[:-1]} {row.get('id', '<unnamed>')} uses {kind}, which has no external producer for this declaration."
                )
    return errors


def coverage_warnings(profile, definitions):
    """Report profile-local gaps without rejecting valid partial publications."""
    warnings = []
    quest_ids = referenced_quest_ids(profile)
    binding_targets = {
        (row.get("quest_id"), row.get("objective_id"))
        for row in profile.get("bindings", ())
        if isinstance(row, dict)
    }
    binding_targets.update(
        (row.get("parent_quest_id"), row.get("objective_id"))
        for row in profile.get("links", ())
        if isinstance(row, dict)
    )
    activation_quests = {
        row.get("quest_id")
        for row in profile.get("activations", ())
        if isinstance(row, dict)
    }
    for quest_id in quest_ids:
        if quest_id not in activation_quests:
            warnings.append(
                f"Quest {quest_id} has no activation in this profile; an existing producer may activate it."
            )
        definition = definitions.get(quest_id)
        if definition is None:
            continue
        for objective in definition.get("cjJ", ()):
            if (quest_id, objective.get("d")) not in binding_targets:
                warnings.append(
                    f"Quest {quest_id} objective {objective.get('d')} has no event binding in this profile."
                )
    return warnings + producer_warnings(profile)


def inspect_report(db, quest_ids):
    revision, definitions = native_definitions(db, quest_ids)
    titles = {
        row["definition_id"]: row["title"] or ""
        for row in db.execute(
            "SELECT definition_id,data->'title'->>'es' AS title "
            "FROM native_quest_metadata_definitions "
            "WHERE revision=%s AND definition_id=ANY(%s)",
            (revision, quest_ids),
        ).fetchall()
    }
    counters = counter_missions.bindings(list(definitions.values()))
    profiles = []
    from wakfu_server.achievements import mission_toolkit

    for row in mission_toolkit.installed(db):
        if not row["active"]:
            continue
        profile = mission_toolkit.get_profile(db, row["id"], row["version"])
        if profile is not None:
            profiles.append((row, profile))
    interactive = db.execute(
        "SELECT map_id,object_id,action_id,parameter,quest_id,objective_id "
        "FROM quest_interactive_bindings WHERE quest_id=ANY(%s) "
        "ORDER BY quest_id,objective_id,map_id,object_id",
        (quest_ids,),
    ).fetchall()
    settings = {
        row["name"]: row["value"]
        for row in db.execute(
            "SELECT name,value FROM settings WHERE name=ANY(%s)",
            (["combat_mission_bindings_v1", "native_quest_conversation_contracts"],),
        ).fetchall()
    }
    legacy = {
        identity: {
            "interactive": [],
            "combat": [],
            "item_action": [],
            "conversation": [],
            "links": [],
        }
        for identity in quest_ids
    }
    for binding in interactive:
        legacy[binding["quest_id"]]["interactive"].append(
            {
                key: binding[key]
                for key in (
                    "map_id",
                    "object_id",
                    "action_id",
                    "parameter",
                    "objective_id",
                )
            }
        )
    combat = settings.get("combat_mission_bindings_v1", {})
    for binding in combat.get("bindings", ()):
        if binding.get("quest_id") in legacy:
            legacy[binding["quest_id"]]["combat"].append(binding)
    from wakfu_server.achievements import item_event_missions

    for (
        native_class,
        action_id,
        source_reference,
        output_reference,
    ), binding in item_event_missions.BINDINGS.items():
        quest_id = binding["definition_id"]
        if quest_id in legacy:
            legacy[quest_id]["item_action"].append(
                {
                    "objective_ids": list(binding["objective_ids"]),
                    "native_class": native_class,
                    "action_id": action_id,
                    "source_reference": source_reference,
                    "output_reference": output_reference,
                    "status": "existing_explicit_item_action_binding",
                }
            )
    conversation = settings.get("native_quest_conversation_contracts", {})
    for placement in conversation.get("placements", ()):
        quest_id = placement.get("quest_id")
        if quest_id in legacy:
            legacy[quest_id]["conversation"].append(
                {
                    "kind": "placement_activation",
                    "reference_id": placement["row"].get("reference_id"),
                    "action_ids": placement["row"].get("action_ids", []),
                    "activation_policy": placement.get("activation_policy"),
                }
            )
    for binding in conversation.get("bindings", ()):
        quest_id = binding.get("quest_id")
        if quest_id in legacy:
            legacy[quest_id]["conversation"].append(
                {
                    "kind": "objective_binding",
                    "objective_id": binding.get("objective_id"),
                    "reference_id": binding.get("reference_id"),
                    "action_id": binding.get("action_id"),
                    "node_id": binding.get("node_id"),
                    "choice_id": binding.get("choice_id"),
                }
            )
    for link in conversation.get("activation_links", ()):
        parent, child = link.get("after_quest"), link.get("start_quest")
        if parent in legacy:
            legacy[parent]["links"].append({"role": "parent", **link})
        if child in legacy:
            legacy[child]["links"].append({"role": "child", **link})
    report = {
        "native_revision": revision,
        "coverage_scope": (
            "Generic toolkit, interactive, combat, item-action and conversation indexes; "
            "specialized per-quest adapters may provide additional activation/event coverage."
        ),
        "event_producers": [
            {
                "kind": kind,
                "status": (
                    "wired"
                    if kind in VERIFIED_WIRED_PRODUCERS
                    else (
                        "wired_with_scope"
                        if kind in SCOPED_WIRED_PRODUCERS
                        else (
                            "internal_only"
                            if kind in INTERNAL_EVENT_SOURCES
                            else "declared_only"
                        )
                    )
                ),
                "producer": VERIFIED_WIRED_PRODUCERS.get(
                    kind,
                    SCOPED_WIRED_PRODUCERS.get(kind, INTERNAL_EVENT_SOURCES.get(kind)),
                ),
            }
            for kind in sorted(mission_toolkit_contract.EVENT_KINDS)
        ],
        "quests": [],
    }
    for quest_id in quest_ids:
        definition = definitions[quest_id]
        quest = {
            "quest_id": quest_id,
            "title": titles.get(quest_id, ""),
            "native_class": definition.get("native_class"),
            "objectives": [],
            "toolkit_activations": [],
            "toolkit_links": [],
            "existing_reconstruction_indexes": legacy[quest_id],
            "missing": [],
        }
        profiles_for_quest = []
        for row, profile in profiles:
            for activation in profile.get("activations", ()):
                if activation.get("quest_id") == quest_id:
                    quest["toolkit_activations"].append(
                        {
                            "profile_id": row["id"],
                            "version": row["version"],
                            **activation,
                        }
                    )
            for link in profile.get("links", ()):
                if quest_id in (
                    link.get("parent_quest_id"),
                    link.get("child_quest_id"),
                ):
                    quest["toolkit_links"].append(
                        {"profile_id": row["id"], "version": row["version"], **link}
                    )
            profiles_for_quest.append((row, profile))
        for objective in definition.get("cjJ", ()):
            objective_id = objective["d"]
            bound = []
            for row, profile in profiles_for_quest:
                for binding in profile.get("bindings", ()):
                    if (binding.get("quest_id"), binding.get("objective_id")) == (
                        quest_id,
                        objective_id,
                    ):
                        bound.append(
                            {
                                "profile_id": row["id"],
                                "version": row["version"],
                                **binding,
                            }
                        )
            native_counters = [
                {
                    "variable_id": row[2],
                    "threshold": row[3],
                    "status": "native_counter_candidate_not_event_binding",
                }
                for values in counters.values()
                for row in values
                if row[:2] == (quest_id, objective_id)
            ]
            quest["objectives"].append(
                {
                    "objective_id": objective_id,
                    "native_class": objective.get("native_class"),
                    "native_counter_candidates": native_counters,
                    "event_bindings": bound,
                    "status": "bound" if bound else "needs_binding",
                }
            )
        has_conversation_activation = any(
            row["kind"] == "placement_activation"
            for row in legacy[quest_id]["conversation"]
        ) or any(
            row.get("start_quest") == quest_id for row in legacy[quest_id]["links"]
        )
        if (
            not quest["toolkit_activations"]
            and not has_conversation_activation
            and not legacy[quest_id]["combat"]
        ):
            quest["missing"].append("activation")
        if any(
            row["status"] == "needs_binding"
            and not any(
                binding.get("objective_id") == row["objective_id"]
                for binding in legacy[quest_id]["interactive"]
                + legacy[quest_id]["combat"]
                + [
                    {"objective_id": objective_id}
                    for binding in legacy[quest_id]["item_action"]
                    for objective_id in binding["objective_ids"]
                ]
                + legacy[quest_id]["conversation"]
            )
            for row in quest["objectives"]
        ):
            quest["missing"].append("objective_event_binding")
        report["quests"].append(quest)
    return report


def _emit(value, *, as_json):
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(value, list):
        if not value:
            print("No mission toolkit profiles are published.")
            return
        for row in value:
            print(
                f"{row['id']} v{row['version']} "
                f"{'active' if row['active'] else 'inactive'} "
                f"native={row['native_revision']} sha256={row['sha256']}"
            )
        return
    if isinstance(value, dict) and value.get("status") == "needs_binding":
        print(f"Scaffold status: {value['status']}")
        print(f"Native revision: {value['native_revision']}")
        if value.get("output"):
            print(f"Manifest: {value['output']}")
        for candidate in value["candidates"]:
            print(
                f"Quest {candidate['quest_id']} objective {candidate['objective_id']}: "
                f"{candidate['status']}"
                + (
                    f" (native variable {candidate['variable_id']}, "
                    f"threshold {candidate['native_threshold']})"
                    if "variable_id" in candidate
                    else ""
                )
            )
        print("Set producer events and evidence before validation.")
        return
    if isinstance(value, dict) and "valid" in value:
        print(
            f"Profile {value.get('id', '<unknown>')}: "
            f"{'VALID' if value['valid'] else 'INVALID'}"
        )
        if value.get("native_revision"):
            print(f"Native revision: {value['native_revision']}")
        for reason in value.get("diagnostics", ()):
            print(f"- {reason}")
        for warning in value.get("warnings", ()):
            print(f"Warning: {warning}")
        if value.get("applied") is False:
            print(value.get("message", "Dry run; no changes were applied."))
        elif value.get("applied") is True:
            print(
                f"Published {value['id']} v{value['version']} "
                f"({'active' if value['active'] else 'inactive'})."
            )
        return
    if isinstance(value, dict) and "quests" in value:
        print(f"Native metadata revision: {value['native_revision']}")
        print(f"Coverage scope: {value['coverage_scope']}")
        for producer in value.get("event_producers", ()):
            suffix = f" ({producer['producer']})" if producer.get("producer") else ""
            print(f"  producer {producer['kind']}: {producer['status']}{suffix}")
        for quest in value["quests"]:
            print(f"Quest {quest['quest_id']}: {quest.get('title') or '(untitled)'}")
            for objective in quest["objectives"]:
                candidate_text = (
                    ", ".join(
                        f"var {row['variable_id']} threshold {row['threshold']}"
                        for row in objective["native_counter_candidates"]
                    )
                    or "no supported counter candidate"
                )
                print(
                    f"  objective {objective['objective_id']}: {objective['status']}; {candidate_text}"
                )
            print("  missing:", ", ".join(quest["missing"]) or "none")
        return
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _load_manifest(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read profile manifest: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Profile manifest must be a JSON object")
    return value


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("list",):
        command = subparsers.add_parser(name)
        command.add_argument("--json", action="store_true")
    inspect_parser = subparsers.add_parser("inspect", aliases=["coverage"])
    inspect_parser.add_argument("quest_ids", nargs="+", type=int)
    inspect_parser.add_argument("--json", action="store_true")
    scaffold_parser = subparsers.add_parser("scaffold")
    scaffold_parser.add_argument("quest_ids", nargs="+", type=int)
    scaffold_parser.add_argument("--id", required=True, dest="profile_id")
    scaffold_parser.add_argument("--instance", action="append", type=int, default=[])
    scaffold_parser.add_argument("--output", type=Path)
    scaffold_parser.add_argument("--json", action="store_true")
    for name in ("validate", "install"):
        command = subparsers.add_parser(name)
        command.add_argument("manifest", type=Path)
        command.add_argument("--json", action="store_true")
        command.add_argument(
            "--require-complete",
            action="store_true",
            help="Require this profile to cover every objective and activation for each quest",
        )
        if name == "install":
            command.add_argument(
                "--apply",
                action="store_true",
                help="Install and activate this profile in the local database",
            )
    args = parser.parse_args(argv)

    database = _connection()
    try:
        with database.connection() as db:
            from wakfu_server.achievements import mission_toolkit

            if args.command == "list":
                _emit(mission_toolkit.installed(db), as_json=args.json)
                return 0
            if args.command in ("inspect", "coverage"):
                _emit(inspect_report(db, args.quest_ids), as_json=args.json)
                return 0
            if args.command == "scaffold":
                revision, definitions = native_definitions(db, args.quest_ids)
                profile, candidates = scaffold_profile(
                    args.profile_id,
                    args.quest_ids,
                    definitions,
                    instances=args.instance,
                )
                if args.output is not None:
                    if args.output.exists():
                        raise ValueError(f"Refusing to overwrite {args.output}")
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(
                        json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
                    )
                _emit(
                    {
                        "manifest": profile,
                        "native_revision": revision,
                        "candidates": candidates,
                        "status": "needs_binding",
                        "output": str(args.output) if args.output else None,
                    },
                    as_json=args.json,
                )
                return 0

            profile = _load_manifest(args.manifest)
            quest_ids = referenced_quest_ids(profile)
            revision, definitions = native_definitions(db, quest_ids)
            diagnostics = validation_diagnostics(profile, definitions)
            warnings = coverage_warnings(profile, definitions)
            if args.require_complete:
                producer = producer_warnings(profile)
                diagnostics.extend(item for item in warnings if item not in producer)
                diagnostics.extend(strict_producer_errors(profile))
            if diagnostics:
                _emit(
                    {
                        "valid": False,
                        "native_revision": revision,
                        "diagnostics": diagnostics,
                        "warnings": [] if args.require_complete else warnings,
                    },
                    as_json=args.json,
                )
                return 2
            validated = mission_toolkit_contract.validate(profile, definitions)
            if args.command == "validate":
                _emit(
                    {
                        "valid": True,
                        "id": profile["id"],
                        "native_revision": revision,
                        "quests": quest_ids,
                        "bindings": len(profile["bindings"]),
                        "activations": len(profile["activations"]),
                        "links": len(profile["links"]),
                        "warnings": warnings,
                    },
                    as_json=args.json,
                )
                return 0
            if not args.apply:
                _emit(
                    {
                        "valid": True,
                        "applied": False,
                        "id": profile["id"],
                        "native_revision": revision,
                        "warnings": warnings,
                        "message": "Dry run. Pass --apply to install and activate locally.",
                    },
                    as_json=args.json,
                )
                return 0
            with db.transaction():
                result = mission_toolkit.install(db, validated, activate=True)
            _emit({"applied": True, **result}, as_json=args.json)
            return 0
    finally:
        database.close()


def main():
    try:
        return run()
    except (OSError, ValueError, KeyError) as error:
        print(
            json.dumps({"error": str(error)}, ensure_ascii=False),
            file=__import__("sys").stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
