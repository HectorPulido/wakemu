"""Compile separate native non-challenge archmonster world-birth rules.

No standard mission profile, objective progress, scenario reward or activation
is generated. Original ten-second duration is announcement duration only.
"""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

SOURCE = "installed-environmental-source-v1"
POLICY = "wakemu.native-count-archmonster-world-birth-v1"
CONTRACT = "wakemu.native-count-archmonster-world-birth.v1"
FALLBACK_MS = 14_400_000


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def criterion(raw):
    predicates = []
    blocked = False
    for ordinal, clause in enumerate(re.split(r"\band\b", raw)):
        clause = clause.strip()
        if clause == "False":
            blocked = True
            continue
        matched = re.fullmatch(
            r"(GetMonsterCountInZone|GetNbMonstersInZone|GetResourceCountInZone)\((\d+)\)\s*(<|>)\s*(\d+)",
            clause,
        )
        if matched is None:
            raise ValueError("Unsupported original archmonster membership criterion")
        function, reference, comparison, threshold = matched.groups()
        predicates.append(
            dict(
                ordinal=ordinal,
                function_name=function,
                reference=int(reference),
                comparison=comparison,
                threshold=int(threshold),
            )
        )
    if not predicates:
        raise ValueError(
            "Archmonster birth requires its actual original count predicates"
        )
    return blocked, predicates


def _name(value):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", value.replace("’", "'").casefold())
            if not unicodedata.combining(c)
        ).split()
    )


def compile_sources(
    specs, locations, monsters, *, catalog_revision, monsters_sha256, cadences
):
    actors = {row["ref"]: row for row in monsters["monsters"]}
    overrides = {row["scenario_id"]: row for row in cadences["rows"]}
    if len(overrides) != len(cadences["rows"]):
        raise ValueError("Duplicate source-specific archmonster cadence")
    sources = []
    memberships = []
    predicates = []
    scopes = []
    cadence_rows = []
    seen = set()
    for original in specs["rows"]:
        scenario = original["scenario_id"]
        actor = original["native_monster"]
        reference = original["explicit_count_predicate_breed"]
        if scenario in seen:
            raise ValueError("Duplicate native archmonster scenario")
        seen.add(scenario)
        actual = actors[reference]
        if any(actual.get(key) != value for key, value in actor.items()):
            raise ValueError("Native archmonster source record changed")
        configuration = {
            key.lower(): value for key, value in original["configuration"].items()
        }
        if (
            original["native_type"] != 4
            or original["native_mode_name"] != "NONE"
            or original["text1"] != "False"
            or original["original_scenario_rewards"]
            or configuration.get("challengeduration") != "10"
            or configuration.get("usergroupquantitytospawn") != "1"
            or actor["ref"] != reference
            or actor["min_level"] <= 0
            or actor["max_level"] < actor["min_level"]
            or actor["statistics"]["HP"]["base"] <= 0
        ):
            raise ValueError("Native non-challenge archmonster source contract changed")
        if (
            sha256(original["original_script"].encode()).hexdigest()
            != original["script_sha256"]
        ):
            raise ValueError("Original archmonster scenario script digest changed")
        base = dict(source_key=SOURCE, scenario_id=scenario)
        blocked_states = []
        membership_by_group = {}
        for membership in original["group_memberships"]:
            group = membership["group_id"]
            if group in membership_by_group:
                raise ValueError("Duplicate original archmonster group membership")
            membership_by_group[group] = membership
            blocked, typed = criterion(membership["criteria"])
            blocked_states.append(blocked)
            if not blocked and {
                (p["function_name"], p["reference"], p["comparison"], p["threshold"])
                for p in typed
            } != {
                ("GetMonsterCountInZone", reference, "<", 4),
                ("GetNbMonstersInZone", reference, "<", 4),
            }:
                raise ValueError(
                    "Positive archmonster rule is not the exact original breed-count guard"
                )
            memberships.append(
                dict(
                    base,
                    group_id=group,
                    original_criterion=membership["criteria"],
                    literal_false=blocked,
                )
            )
            predicates.extend(dict(base, group_id=group, **p) for p in typed)
        if not blocked_states or len(set(blocked_states)) != 1:
            raise ValueError("Mixed/absent archmonster membership activation authority")
        blocked = blocked_states[0]
        if blocked != (original["classification"] == "ORIGINAL_FALSE_MEMBERSHIP_GUARD"):
            raise ValueError("Original literal False membership classification changed")
        provenance = dict(
            original=original,
            text1_original_consumer=specs["text1_original_consumer"],
            reconstruction="Wakemu exact native breed world birth; one member per original group; original server spawn producer unrecovered",
            cardinality_authority="User-authorized one native exact-breed member, no invented companions",
            announcement_duration_is_not_monster_ttl=True,
            scenario_reward_policy="none; preserve native combat drops",
        )
        sources.append(
            dict(
                base,
                template_reference=int(configuration["usergrouptemplateid"]),
                monster_reference=reference,
                native_min_level=actor["min_level"],
                native_max_level=actor["max_level"],
                requested_group_count=1,
                announcement_duration_ms=10_000,
                participation_criterion=original["text1"],
                blocked_by_membership=blocked,
                catalog_revision=catalog_revision,
                monsters_sha256=monsters_sha256,
                source_sha256=digest(provenance),
                provenance=provenance,
            )
        )
        grouped = {}
        for location in locations:
            if int(location["scenario_id"]) != scenario:
                continue
            group = int(location["group_id"])
            if (
                not location["map_id"]
                or not location["region_id"]
                or location["native_cells_present"] != "True"
                or group not in membership_by_group
                or location["native_criteria"] != membership_by_group[group]["criteria"]
            ):
                raise ValueError(
                    "Archmonster source requires an exact located original membership"
                )
            key = (int(location["map_id"]), int(location["region_id"]))
            grouped.setdefault(key, []).append(location)
        if not grouped:
            raise ValueError(
                "Archmonster source has no positive native location binding"
            )
        scopes.extend(
            dict(base, map_id=key[0], region_id=key[1], original_locations=value)
            for key, value in sorted(grouped.items())
        )
        if blocked:
            if scenario in overrides:
                raise ValueError(
                    "Literal False archmonster source cannot receive a public cadence"
                )
            continue
        public = overrides.get(scenario)
        if public is not None:
            proof = public["provenance"]
            guide = proof["guide_row"]
            timer = re.fullmatch(r"(\d+)H(?:(\d+))?", guide["timer"])
            if (
                public["native_breed"] != reference
                or public["native_min_level"] != actor["min_level"]
                or _name(public["native_name_fr"])
                != _name(original["native_monster_names"]["fr"])
                or _name(guide["name_fr"])
                != _name(original["native_monster_names"]["fr"])
                or timer is None
                or int(timer[1]) * 3_600_000 + int(timer[2] or 0) * 60_000
                != public["cooldown_ms"]
                or proof["clock_anchor"] != "last successful spawn"
            ):
                raise ValueError(
                    "Source-specific cadence is not an exact named public row"
                )
            cadence_rows.append(
                dict(
                    base,
                    policy_version=POLICY,
                    cooldown_ms=public["cooldown_ms"],
                    authority_kind="SOURCE_DERIVED_PUBLIC",
                    provenance=public,
                )
            )
        else:
            cadence_rows.append(
                dict(
                    base,
                    policy_version=POLICY,
                    cooldown_ms=FALLBACK_MS,
                    authority_kind="DECLARED_WAKEMU",
                    provenance=dict(
                        authority="Explicit Wakemu conservative four-hour fallback; original cadence unrecovered",
                        clock_anchor="last successful spawn",
                        native_breed=reference,
                    ),
                )
            )
    if set(overrides) - seen:
        raise ValueError(
            "Public cadence points outside the original archmonster cohort"
        )
    return dict(
        sources=sources,
        memberships=memberships,
        predicates=predicates,
        scopes=scopes,
        cadences=cadence_rows,
    )


def literal(value):
    if isinstance(value, (dict, list)):
        return (
            literal(
                json.dumps(
                    value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
            )
            + "::jsonb"
        )
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def inserts(table, rows):
    if not rows:
        return ""
    columns = tuple(rows[0])
    if any(tuple(row) != columns for row in rows):
        raise ValueError("Inconsistent normalized source row schema")
    return (
        "\n".join(
            "INSERT INTO "
            + table
            + " ("
            + ",".join(columns)
            + ") VALUES("
            + ",".join(literal(row[key]) for key in columns)
            + ");"
            for row in rows
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "specs",
        "locations",
        "monsters",
        "catalog_metadata",
        "cadences",
        "schema",
        "output",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    specs = json.loads(args.specs.read_text())
    for path, expected in specs["source_sha256"].items():
        if sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("Original archmonster source SHA changed: " + path)
    monster_sha = sha256(args.monsters.read_bytes()).hexdigest()
    metadata = json.loads(args.catalog_metadata.read_text())
    if {row["path"]: row["sha256"] for row in metadata["documents"]}[
        "monsters.json"
    ] != monster_sha:
        raise ValueError(
            "Native archmonster document differs from actual catalog release"
        )
    public = json.loads(args.cadences.read_text())
    if (
        sha256((args.cadences.parent / public["source"]).read_bytes()).hexdigest()
        != public["source_sha256"]
    ):
        raise ValueError("Public named cadence table SHA changed")
    with args.locations.open() as stream:
        locations = list(csv.DictReader(stream))
    rows = compile_sources(
        specs,
        locations,
        json.loads(args.monsters.read_text()),
        catalog_revision=metadata["revision"],
        monsters_sha256=monster_sha,
        cadences=public,
    )
    policy = dict(
        policy_version=POLICY,
        policy_contract=CONTRACT,
        cooldown_ms=FALLBACK_MS,
        member_count=1,
        authority="Explicit Wakemu world-birth reconstruction: native breed/count predicates, one member, last-spawn cooldown; default disabled",
        source_sha256=digest(
            dict(fallback_ms=FALLBACK_MS, member_count=1, contract=CONTRACT)
        ),
    )
    text = (
        args.schema.read_text()
        + "\n"
        + inserts("archmonster_spawn_policy_versions", [policy])
    )
    text += inserts(
        "archmonster_spawn_active",
        [dict(singleton=True, policy_version=POLICY, enabled=False)],
    )
    for key, table in (
        ("sources", "archmonster_spawn_sources"),
        ("memberships", "archmonster_spawn_memberships"),
        ("predicates", "archmonster_spawn_predicates"),
        ("scopes", "archmonster_spawn_scopes"),
        ("cadences", "archmonster_spawn_cadences"),
    ):
        text += inserts(table, rows[key])
    args.output.write_text(text)
    manifest = dict(
        policy_version=POLICY,
        counts={key: len(value) for key, value in rows.items()},
        blocked=sum(row["blocked_by_membership"] for row in rows["sources"]),
        rows=rows,
    )
    args.output.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
