"""Compile explicit public target proofs into disabled native action3 sources.

This does not reconstruct unnamed species, create profiles or activate events.
Original user-group counts remain distinct from drawn creature counts.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

POLICY = "wakemu.explicit-public-target-native-destroy-v1"
SOURCE = "installed-environmental-source-v1"


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compile_sources(specs, inventory, actions, catalog, native_world_actions):
    if specs.get("schema") != "wakemu.destroy-explicit-public-target-candidate-v1":
        raise ValueError("Unknown external destruction proof schema")
    if native_world_actions["revision"] != catalog["revision"]:
        raise ValueError("Native actor and action catalog releases differ")
    current_actions = {
        (row["reference"], action["d"]): action
        for row in native_world_actions["records"]
        for action in row["actions"]
    }
    original = {row["id"]: row for row in inventory["scenarios"]}
    if len(original) != len(inventory["scenarios"]):
        raise ValueError("Duplicate original scenario")
    descriptors = {}
    for action in actions["actions"]:
        key = (action["reference_id"], action["action_id"])
        if key in descriptors:
            raise ValueError("Ambiguous original world action")
        descriptors[key] = action
    native = {
        int(row["record_key"]): row["payload"]
        for row in catalog["records"]
        if row["path"] == "monsters.json"
    }
    rows = []
    seen = set()
    for template in specs["templates"]:
        if (
            template["original_template_membership_recovered"] is not False
            or template["per_group_member_count_source"] is not None
            or template["random_composition_authority"]
            != "USER_AUTHORIZED_EXACT_KNOWN_SPECIES_ONLY"
            or template["proof"]["kind"]
            != "EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN"
            or not template["proof"]["url"].startswith("https://")
        ):
            raise ValueError(
                "External target proof must retain its reconstruction boundary"
            )
        for case in template["scenario_cases"]:
            source = original[case["scenario_id"]]
            if (
                case["scenario_id"] in seen
                or source["type"] != 5
                or case["native_type"] != 5
                or source["configuration"] != case["configuration"]
                or source["native_subtype_name"] != case["native_mode"]
                or source["duration_raw"] != case["duration_seconds"]
            ):
                raise ValueError("Interaction scenario source changed")
            seen.add(case["scenario_id"])
            configuration = source["configuration"]
            expected = dict(
                usergrouptemplateid=template["template_reference"],
                usergroupquantitytospawn=case["requested_group_quantity"],
                nbmobforreward=case["mob_target"],
                nbgroupforreward=case["group_target"],
                monsteractiontypeid=3,
                challengeduration=case["duration_seconds"],
                challengelevelmin=case["challenge_level_min"],
                challengelevelmax=case["challenge_level_max"],
            )
            if any(
                str(value) != configuration.get(key) for key, value in expected.items()
            ):
                raise ValueError(
                    "Native group count/action/reward/level configuration changed"
                )
            for species in template["known_species"]:
                key = (species["reference"], species["world_action_id"])
                action = descriptors[key]
                actor = native[species["reference"]]
                if (
                    action["action_type"] != 3
                    or species["world_action_type"] != 3
                    or (actor["min_level"], actor["max_level"])
                    != (species["native_min_level"], species["native_max_level"])
                    or action["criteria"] != ""
                    or action["duration"] != 0
                    or action["native_cbH"] != 0
                    or action["native_csI"] is not False
                    or action["native_csJ"] is not True
                    or action["native_csK"] is not False
                ):
                    raise ValueError(
                        "Target lacks the exact supported native action3 context"
                    )
                descriptor = dict(
                    native_class="aMg",
                    d=action["action_id"],
                    aGJ=3,
                    clT=action["criteria"],
                    getDuration=action["duration"],
                    cbH=action["native_cbH"],
                    clx=action["native_clx"],
                    csI=action["native_csI"],
                    csJ=action["native_csJ"],
                    csK=action["native_csK"],
                )
                if descriptor != current_actions.get(key):
                    raise ValueError(
                        "Derived action descriptor differs from actual installed scalar record"
                    )
                rows.append(
                    dict(
                        source_key=SOURCE,
                        scenario_id=case["scenario_id"],
                        policy_version=POLICY,
                        template_reference=template["template_reference"],
                        monster_reference=species["reference"],
                        action_id=action["action_id"],
                        action_descriptor=descriptor,
                        descriptor_sha256=digest(descriptor),
                        catalog_revision=catalog["revision"],
                        public_proof=template["proof"],
                        source_sha256=digest(
                            dict(
                                template=template,
                                original=source,
                                native_action=action,
                                native_actor=actor,
                                revision=catalog["revision"],
                            )
                        ),
                    )
                )
    return sorted(
        rows,
        key=lambda row: (
            row["scenario_id"],
            row["monster_reference"],
            row["action_id"],
        ),
    )


def sql(rows):
    columns = (
        "source_key",
        "scenario_id",
        "policy_version",
        "template_reference",
        "monster_reference",
        "action_id",
        "action_descriptor",
        "descriptor_sha256",
        "catalog_revision",
        "public_proof",
        "source_sha256",
    )

    def literal(value):
        if isinstance(value, dict):
            return (
                literal(json.dumps(value, sort_keys=True, separators=(",", ":")))
                + "::jsonb"
            )
        if type(value) is int:
            return str(value)
        return "'" + value.replace("'", "''") + "'"

    return (
        "\n".join(
            "INSERT INTO environmental_destroy_sources ("
            + ",".join(columns)
            + ") VALUES("
            + ",".join(literal(row[column]) for column in columns)
            + ");"
            for row in rows
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "specs",
        "inventory",
        "actions",
        "catalog",
        "native_world_actions",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    options = parser.parse_args()
    rows = compile_sources(
        *(
            json.loads(getattr(options, name).read_text())
            for name in (
                "specs",
                "inventory",
                "actions",
                "catalog",
                "native_world_actions",
            )
        )
    )
    options.output.write_text(sql(rows))
    print(
        json.dumps(
            dict(
                scenarios=len({row["scenario_id"] for row in rows}),
                targets=len({row["monster_reference"] for row in rows}),
                rows=len(rows),
            )
        )
    )


if __name__ == "__main__":
    main()


NAMED_POLICY = "wakemu.original-body-namedtype-compatible-variant-v1"


def compile_named_sources(
    specs, inventory, monsters, native_world_actions, *, excluded_ids=()
):
    """Compile declared named-type variants, preserving every original operand.

    Variant selection is an explicit Wakemu policy. A positive native-HP actor
    with its own genuine action3 is required; no statistics are manufactured.
    Prefer direct named/type candidates, then exact original sprite bridges,
    breaking ties by native reference. Unselected candidates remain provenance.
    """
    original = {row["id"]: row for row in inventory["scenarios"]}
    actors = {row["ref"]: row for row in monsters["monsters"]}
    if len(original) != len(inventory["scenarios"]) or len(actors) != len(
        monsters["monsters"]
    ):
        raise ValueError("Duplicate original scenario or native actor reference")
    actions = {}
    for row in native_world_actions["records"]:
        if row["reference"] in actions or len(row["actions"]) != 1:
            raise ValueError("Ambiguous actual native destruction descriptor")
        actions[row["reference"]] = row["actions"][0]
    excluded_ids = set(excluded_ids)
    rows, selections = [], []
    seen = set()
    for cohort in specs["rows"]:
        compatible = cohort["compatible_native_action_prototypes"]
        if not compatible:
            continue
        if (
            cohort["classification"] != "NAMED_TYPE_RECONSTRUCTED_VARIANTS"
            or cohort["original_template_membership_recovered"] is not False
            or not cohort["candidates"]
        ):
            raise ValueError(
                "Missing explicit reconstructed named-type source boundary"
            )
        candidates = {
            candidate["reference"]: candidate for candidate in cohort["candidates"]
        }
        qualified = []
        for reference in compatible:
            actor = actors[reference]
            descriptor = actions[reference]
            if (
                descriptor.get("native_class") != "aMg"
                or descriptor.get("aGJ") != 3
                or descriptor.get("clT") != ""
                or descriptor.get("getDuration") != 0
                or descriptor.get("cbH") != 0
                or descriptor.get("csI") is not False
                or descriptor.get("csJ") is not True
                or descriptor.get("csK") is not False
            ):
                raise ValueError("Unsupported native named-type destruction action")
            matching = []
            for candidate in candidates.values():
                source_actor = actors[candidate["reference"]]
                if (
                    source_actor["sprite_id"] != candidate["sprite_id"]
                    or source_actor["family_id"] != candidate["family_id"]
                    or source_actor["min_level"] != candidate["native_min_level"]
                    or source_actor["max_level"] != candidate["native_max_level"]
                    or source_actor["statistics"] != candidate["native_statistics"]
                    or source_actor.get("raw_visual_arrays")
                    != candidate["raw_visual_arrays"]
                ):
                    raise ValueError("Named-type original candidate record changed")
                direct = (
                    candidate["reference"] == reference
                    and candidate["native_destroy_action"] is not None
                )
                bridges = [
                    bridge
                    for bridge in candidate["same_native_model_destroy_variants"]
                    if bridge["reference"] == reference
                ]
                if direct or bridges:
                    if source_actor["sprite_id"] != actor["sprite_id"] or (
                        not direct and actor["sprite_id"] <= 0
                    ):
                        raise ValueError(
                            "Named-type variant is not the identical original native sprite"
                        )
                    source_action = (
                        candidate["native_destroy_action"]
                        if direct
                        else bridges[0]["action"]
                    )
                    if int(source_action["action_id"]) != descriptor["d"]:
                        raise ValueError(
                            "Named-type action identity differs from its current native record"
                        )
                    if (
                        not candidate["source_name_literal_match"]
                        and candidate["family_id"] not in cohort["taxonomy_family_ids"]
                        and "Original named-type candidate"
                        not in candidate["variant_authority"]
                    ):
                        raise ValueError(
                            "Missing named-type candidate adjudication authority"
                        )
                    matching.append(candidate)
            if not matching:
                raise ValueError(
                    "Selected native action has no original candidate/sprite bridge"
                )
            hp = actor["statistics"].get("HP", {}).get("base", 0)
            if hp <= 0:
                continue
            if any(
                actor["statistics"].get(key, {}).get("base", -1) < 0
                for key in ("AP", "MP", "WP")
            ):
                raise ValueError(
                    "Native named-type world actor has invalid original resources"
                )
            qualified.append(
                (
                    0
                    if reference in candidates
                    and candidates[reference]["native_destroy_action"]
                    else 1,
                    reference,
                    actor,
                    descriptor,
                    matching,
                )
            )
        if not qualified:
            raise ValueError(
                "Named-type cohort has no naturally living native action actor"
            )
        _, reference, actor, descriptor, matching = min(
            qualified, key=lambda row: row[:2]
        )
        original_sources = {
            row["scenario_id"]: row for row in cohort["original_sources"]
        }
        selections.append(
            dict(
                template_reference=cohort["template_id"],
                monster_reference=reference,
                action_id=descriptor["d"],
                compatible_native_action_prototypes=compatible,
                excluded_nonpositive_hp=[
                    ref
                    for ref in compatible
                    if actors[ref]["statistics"].get("HP", {}).get("base", 0) <= 0
                ],
            )
        )
        for scenario_id in cohort["scenario_ids"]:
            if scenario_id in excluded_ids:
                continue
            if scenario_id in seen:
                raise ValueError("Duplicate named-type scenario")
            seen.add(scenario_id)
            source = original[scenario_id]
            configuration = {
                key.lower(): value for key, value in source["configuration"].items()
            }
            if len(configuration) != len(source["configuration"]):
                raise ValueError("Ambiguous native configuration key casing")
            if (
                source["type"] != 5
                or configuration.get("usergrouptemplateid")
                != str(cohort["template_id"])
                or configuration.get("monsteractiontypeid") != "3"
                or int(configuration["usergroupquantitytospawn"]) <= 0
                or int(configuration["nbmobforreward"]) <= 0
                or int(configuration["nbgroupforreward"]) != 0
            ):
                raise ValueError(
                    "Named-type source population/action/minimum configuration changed"
                )
            localization = original_sources[scenario_id]["localizations"]
            if set(localization) != {"en", "fr", "es"} or any(
                not values.get("26") for values in localization.values()
            ):
                raise ValueError(
                    "Named-type source must retain all three original title/body languages"
                )
            proof = dict(
                kind="ORIGINAL_BODY_NAMEDTYPE_COMPATIBLE_VARIANT",
                reconstruction="User-authorized named-type native variant, not original template membership",
                variant_selection="positive-native-HP; direct candidate before identical sprite bridge; minimum native reference",
                original_sources=original_sources[scenario_id],
                taxonomy_proof=specs["taxonomy_proof"],
                taxonomy_family_ids=cohort["taxonomy_family_ids"],
                selected_species=actor,
                matching_original_candidates=matching,
                compatible_native_action_prototypes=compatible,
                original_template_membership_recovered=False,
                native_action=descriptor,
            )
            rows.append(
                dict(
                    source_key=SOURCE,
                    scenario_id=scenario_id,
                    policy_version=NAMED_POLICY,
                    template_reference=cohort["template_id"],
                    monster_reference=reference,
                    action_id=descriptor["d"],
                    action_descriptor=descriptor,
                    descriptor_sha256=digest(descriptor),
                    catalog_revision=native_world_actions["revision"],
                    public_proof=proof,
                    source_sha256=digest(
                        dict(
                            original=source,
                            proof=proof,
                            source_hashes=specs["source_sha256"],
                        )
                    ),
                )
            )
    return sorted(rows, key=lambda row: row["scenario_id"]), selections


def qualify_named_sources(rows, audit):
    """Require explicit lexical/taxonomy annotations for each original scenario.

    Only accent/case/CamelCase normalization and enumerated grammatical plural
    suffixes are used. Taxonomy and sprite identities were validated upstream.
    """
    import re
    import unicodedata

    def canon(text):
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
        return "".join(
            c
            for c in unicodedata.normalize("NFKD", text.casefold())
            if not unicodedata.combining(c)
        )

    def has(text, token, *, plural=False):
        suffix = r"(?:s|es|x)?" if plural else ""
        return bool(
            re.search(
                r"(?<!\w)" + re.escape(canon(token)) + suffix + r"(?!\w)", canon(text)
            )
        )

    def inflection(source, native):
        source, native = canon(source), canon(native)
        return (
            source == native
            or source in (native + "s", native + "es", native + "x")
            or (native.endswith("y") and source == native[:-1] + "ies")
            or (source.endswith("y") and native == source[:-1] + "ies")
        )

    decisions = {row["template_reference"]: row for row in audit["template_decisions"]}
    checks = {row["scenario_id"]: row for row in audit["per_scenario_checks"]}
    if (
        len(decisions) != len(audit["template_decisions"])
        or len(checks) != len(audit["per_scenario_checks"])
        or set(checks) != {row["scenario_id"] for row in rows}
        or set(decisions) != {row["template_reference"] for row in rows}
    ):
        raise ValueError("Named-type annotation does not cover the exact source cohort")
    entries = {}
    for entry in audit["entries"]:
        key = (entry["template_reference"], entry["candidate_reference"])
        if key in entries:
            raise ValueError("Duplicate deterministic named-type annotation")
        entries[key] = entry
    result, pending = [], []
    for row in rows:
        template = row["template_reference"]
        decision, check = decisions[template], checks[row["scenario_id"]]
        if (
            decision["selected_reference"] != row["monster_reference"]
            or check["template_reference"] != template
            or set(decision["scenario_ids"])
            != {r["scenario_id"] for r in rows if r["template_reference"] == template}
        ):
            raise ValueError("Named-type annotation selected another source/variant")
        proof = row["public_proof"]
        sources = proof["original_sources"]["localizations"]
        positive = []
        for candidate in proof["matching_original_candidates"]:
            annotation = entries[(template, candidate["reference"])]
            if annotation["status"] != "ACCEPTED":
                continue
            if (
                annotation["selected_reference"] != row["monster_reference"]
                or annotation["candidate_sprite_id"] != candidate["sprite_id"]
                or annotation["selected_sprite_id"]
                != proof["selected_species"]["sprite_id"]
                or annotation["candidate_sprite_id"] != annotation["selected_sprite_id"]
            ):
                raise ValueError(
                    "Named-type annotation has a different native model identity"
                )
            kind = annotation["proof_kind"]
            hits = []
            if kind == "ORIGINAL_MULTILINGUAL_FULL_NAME":
                if annotation["literal"]["names"] != candidate["names"]:
                    raise ValueError("Original multilingual candidate name changed")
                hits = [
                    dict(language=language, field=field, token=name)
                    for language, name in candidate["names"].items()
                    if name
                    for field in ("24", "26")
                    if has(sources[language][field], name, plural=True)
                ]
            elif kind == "EXPLICIT_NAMED_TYPE_TOKEN":
                language = annotation["language"]
                source_token, native_token = (
                    annotation["source_token"],
                    annotation["native_name_token"],
                )
                if (
                    not inflection(source_token, native_token)
                    or not has(candidate["names"][language], native_token)
                    or candidate["names"][language] != annotation["native_name"]
                ):
                    raise ValueError(
                        "Named-type token lacks an exact native genus/inflection proof"
                    )
                hits = [
                    dict(language=language, field=field, token=source_token)
                    for field in ("24", "26")
                    if has(sources[language][field], source_token)
                ]
            elif kind == "NATIVE_CQM_CONTENT38":
                if (
                    annotation["family_id"] != candidate["family_id"]
                    or candidate["family_id"] not in proof["taxonomy_family_ids"]
                ):
                    raise ValueError("Named-type taxonomy membership changed")
                for match in annotation["source_matches"]:
                    language, token = match["language"], match["token"]
                    if not inflection(token, candidate["family_names"][language]):
                        raise ValueError("Original named taxonomy label changed")
                    hits.extend(
                        dict(language=language, field=field, token=token)
                        for field in ("24", "26")
                        if has(sources[language][field], token)
                    )
            else:
                raise ValueError("Unknown deterministic named-type proof grammar")
            if hits:
                positive.append(
                    dict(
                        candidate_reference=candidate["reference"],
                        annotation=annotation,
                        source_matches=hits,
                    )
                )
        qualified = bool(positive)
        if qualified != (check["status"] == "ACCEPTED") or qualified != (
            decision["status"] == "ACCEPTED"
        ):
            raise ValueError(
                "Deterministic named-type source qualification disagrees with annotation"
            )
        if not qualified:
            pending.append(
                dict(
                    scenario_id=row["scenario_id"],
                    template_reference=template,
                    reason="No exact lexical/taxonomy proof for the selected native variant",
                )
            )
            continue
        annotated = dict(proof, deterministic_named_type_proofs=positive)
        result.append(
            dict(
                row,
                public_proof=annotated,
                source_sha256=digest(
                    dict(original_source_sha256=row["source_sha256"], proof=annotated)
                ),
            )
        )
    return result, pending
