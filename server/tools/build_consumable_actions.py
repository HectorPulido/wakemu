"""Build bounded native consumable descriptors and migration from offline exports.

Inputs are produced by ExportConsumableDescriptors and the targeted catalog
query in the item readiness report. This tool never connects to a game server.
"""
import argparse
import hashlib
import json
from pathlib import Path


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def build(
    items,
    native,
    closure,
    raw_states,
    counter_contracts,
    *,
    include_transformations=False,
    expected_count=239,
):
    raw_states = {int(row["p"]): row for row in raw_states}
    result = []
    for item in items:
        if (item["type_id"] == 738 and not include_transformations) or item[
            "status"
        ] == "implemented_healing":
            continue
        reference = item["reference"]
        source = native["items"][str(reference)]
        reasons = []
        plan = dict(
            criterion=source.get("use_criteria", {}).get("USE", ""),
            native_item_criteria=source.get("use_criteria", {}),
            states=[],
            emotes=[],
            heal=None,
            remove_states=[],
            emitted_events=[],
            emitted_event_details=[],
            native_item_effects={},
        )
        if source["use_action_present"]:
            reasons.append("native_action_or_criterion_requires_separate_dispatch")
        if not source["effects"]:
            reasons.append("no_native_action_or_effect")
        for identity in source["effects"]:
            node = native["effects"][f'{identity}:{source["level"]}']
            plan["native_item_effects"][str(identity)] = node
            generic, values = node["generic"], node["values"]
            if node["criteria"] or node["subscription"]:
                reasons.append("conditional_or_subscribed_direct_item_effect")
            if generic == 550 and len(values) == 1 and values[0] > 0:
                plan["emotes"].append(
                    dict(emote_id=values[0], effect_id=identity, forced=True)
                )
            elif generic == 321 and values:
                plan["remove_states"].append(values[0])
            elif generic == 25:
                plan["heal"] = dict(
                    effect_id=identity, values=values, params=node["params"]
                )
            elif generic == 400:
                masks = node["native_metadata"]["target_masks"]
                plan["emitted_events"].extend(masks[6] or [])
                plan["emitted_event_details"].extend(
                    dict(event_id=event, effect_id=identity)
                    for event in (masks[6] or [])
                )
                if node["children"]:
                    reasons.append("direct_item_group_children_require_execution")
            elif generic == 304:
                state_id, level, _ = values
                definition = closure["states"][str(state_id)]
                raw = raw_states[state_id]
                maximum = definition["maximum_level"]
                selected_level = min(maximum, level)
                duration = (
                    definition["realtime_duration_base"]
                    + definition["realtime_duration_per_level"] * selected_level
                )
                pending = list(definition["effect_ids"])
                effects = {}
                while pending:
                    effect_id = pending.pop(0)
                    if str(effect_id) in effects:
                        continue
                    effect = native["effects"].get(f"{effect_id}:{level}")
                    if effect is None:
                        reasons.append("native_state_effect_level_missing")
                        continue
                    effects[str(effect_id)] = effect
                    pending.extend(effect["children"])
                state = dict(
                    state_id=state_id,
                    level=selected_level,
                    maximum_level=maximum,
                    duration_ms=duration,
                    clock="online" if duration > 0 else None,
                    replace=definition["replace"],
                    additive=definition["additive"],
                    refresh=definition["refresh"],
                    stacking="replace"
                    if definition["replace"]
                    else "additive"
                    if definition["additive"]
                    else "native_reject_duplicate",
                    effect_ids=definition["effect_ids"],
                    removes=[],
                    metadata=dict(
                        native_effects=effects,
                        removal_event_ids=raw["esp"],
                        clock_contract="eZU.remaining/eZV.restore_remaining;fyW.cxn=false",
                        native_duration_base=definition["duration_base"],
                        native_realtime_duration_base=definition[
                            "realtime_duration_base"
                        ],
                        native_realtime_duration_per_level=definition[
                            "realtime_duration_per_level"
                        ],
                        skip_turn_timer=definition["skip_turn_timer"],
                        native_state_flags={
                            key: value
                            for key, value in raw.items()
                            if key.startswith("es")
                        },
                    ),
                )
                # Timed state roots may emit a native cancellation event that
                # existing states subscribe to; retain this separately from
                # explicit 321 direct removals.
                application_controls = set()
                for root_id in definition["effect_ids"]:
                    root = effects.get(str(root_id), {})
                    if (
                        root.get("generic") == 321
                        and not root.get("subscription")
                        and not root.get("criteria")
                        and len(root.get("values", [])) == 1
                        and root.get("timing", {}).get("delay", [0])[0] == 0
                    ):
                        state["removes"].append(root["values"][0])
                        application_controls.add(root_id)
                for effect in effects.values():
                    children = [effects[str(child)] for child in effect["children"]]
                    if (
                        effect["generic"] == 330
                        and not effect["criteria"]
                        and not effect["subscription"]
                        and children
                        and all(
                            child["generic"] == 321
                            and not child["criteria"]
                            and not child["subscription"]
                            and len(child["values"]) == 1
                            and child.get("timing", {}).get("delay", [0])[0] == 0
                            for child in children
                        )
                    ):
                        application_controls.add(effect["id"])
                        application_controls.update(child["id"] for child in children)
                        state["removes"].extend(
                            child["values"][0] for child in children
                        )
                state["metadata"]["application_control_effect_ids"] = sorted(
                    application_controls
                )
                combat_reactive_roots = set()
                combat_reactive_closure = set()
                for root_id in definition["effect_ids"]:
                    root = effects.get(str(root_id), {})
                    children = [
                        effects[str(child)] for child in root.get("children", [])
                    ]
                    masks = root.get("native_metadata", {}).get(
                        "target_masks", [None] * 7
                    )
                    first_aid = (
                        root.get("generic") == 330
                        and root.get("subscription")
                        and not root.get("criteria")
                        and masks[5] == [1001]
                        and children
                        and all(
                            child["generic"] == 25
                            and not child["criteria"]
                            and not child["subscription"]
                            and len(child["values"]) == 3
                            and child["values"][1:] == [2, 4]
                            for child in children
                        )
                    )
                    lifesteal = (
                        root.get("generic") == 1020
                        and root.get("subscription")
                        and masks[3] == [2]
                        and root.get("criteria")
                        == 'GetTeamId("triggeringTarget") != GetTeamId("caster")'
                        and children
                        and all(
                            child["generic"] == 25
                            and not child["criteria"]
                            and not child["subscription"]
                            and len(child["values"]) == 2
                            and child["values"][1] == 2
                            for child in children
                        )
                    )
                    solo_modifier = (
                        root.get("generic") == 330
                        and root.get("subscription")
                        and not root.get("criteria")
                        and masks[0] == [2]
                        and any(child["generic"] == 1093 for child in children)
                        and all(
                            child["generic"] in (1093, 400)
                            and not child["subscription"]
                            and (
                                child["generic"] != 1093
                                or child["criteria"]
                                == 'GetEnnemyCountInRange(1, 3, "target") == 0 and not HasState(6500)'
                            )
                            for child in children
                        )
                    )
                    if first_aid or lifesteal or solo_modifier:
                        combat_reactive_roots.add(root_id)
                        combat_reactive_closure.add(root_id)
                        combat_reactive_closure.update(
                            child["id"] for child in children
                        )
                state["metadata"]["combat_only_effect_ids"] = sorted(
                    combat_reactive_roots
                )
                expiry_events = set(raw["esp"])
                for effect in effects.values():
                    selector = (
                        effect["native_metadata"].get("native_target_selector") or {}
                    )
                    if (
                        effect["generic"] == 321
                        and effect["subscription"]
                        and effect["values"] == [state_id]
                        and not effect["criteria"]
                        and selector.get("class") == "fcE"
                        and selector.get("mask") in (0, 1, 2, 3)
                    ):
                        expiry_events.update(
                            effect["native_metadata"]["target_masks"][3] or []
                        )
                        expiry_events.update(
                            effect["native_metadata"]["target_masks"][5] or []
                        )
                counter = counter_contracts.get(str(state_id))
                simple_counter = bool(
                    counter
                    and counter["decrements"]
                    and all(
                        row["event_ids"] == [1030] and row["criterion"] == ""
                        for row in counter["decrements"]
                    )
                )
                event_state = (
                    duration <= 0
                    and definition["duration_base"] < 0
                    and definition["skip_turn_timer"]
                    and not definition["additive"]
                    and bool(expiry_events)
                    and expiry_events.issubset(
                        {1010, 1030, 1043, 2162, 2164, 2165, 2166}
                    )
                    and all(
                        effect["stat_id"] is not None
                        or effect["generic"] == 400
                        or effect["id"] in combat_reactive_closure
                        or (
                            effect["generic"] == 321
                            and effect["values"] == [state_id]
                            and not effect["criteria"]
                            and (
                                effect["subscription"]
                                or effect.get("timing", {}).get("delay", [0])[0] > 0
                            )
                        )
                        for effect in effects.values()
                    )
                )
                if simple_counter:
                    state["clock"] = "event"
                    state["duration_ms"] = 0
                    state["metadata"]["counter"] = dict(
                        decrement_event_ids=[1030], decrement=1, maximum_level=maximum
                    )
                    state["metadata"]["native_counter_contract"] = counter
                    state["metadata"]["removal_event_rules"] = [
                        dict(
                            event_id=event,
                            excluded_effect_ids=[row["exclude_triggering_effect_id"]],
                        )
                        for row in counter["cross_state_removals"]
                        for event in row["event_ids"]
                    ]
                    state["metadata"]["removal_event_ids"] = sorted(
                        set(raw["esp"])
                        | {
                            row["event_id"]
                            for row in state["metadata"]["removal_event_rules"]
                        }
                    )
                    state["metadata"]["counter_control_effect_ids"] = sorted(
                        {
                            effect_id
                            for row in counter["decrements"]
                            + counter["cross_state_removals"]
                            for effect_id in (
                                row["trigger_effect"],
                                row["decurse_effect"],
                            )
                        }
                    )
                elif event_state:
                    state["clock"] = "event"
                    state["duration_ms"] = 0
                for effect in effects.values():
                    if (
                        effect["generic"] == 321
                        and effect["subscription"]
                        and effect["values"] == [state_id]
                        and not effect["criteria"]
                        and effect["native_metadata"]["native_target_selector"].get(
                            "class"
                        )
                        == "fcE"
                        and effect["native_metadata"]["native_target_selector"].get(
                            "mask"
                        )
                        in (0, 1, 2, 3)
                    ):
                        state["metadata"]["removal_event_ids"] = sorted(
                            set(
                                state["metadata"]["removal_event_ids"]
                                + (effect["native_metadata"]["target_masks"][3] or [])
                                + (effect["native_metadata"]["target_masks"][5] or [])
                            )
                        )
                    if effect["generic"] == 400 and not effect["subscription"]:
                        events = effect["native_metadata"]["target_masks"][6] or []
                        plan["emitted_events"].extend(events)
                        plan["emitted_event_details"].extend(
                            dict(event_id=event, effect_id=effect["id"])
                            for event in events
                        )
                    if (
                        effect["generic"]
                        not in (400, 321, 2001, 2002, 2003, 2004, 2006, 2008)
                        and effect["stat_id"] is None
                        and effect["id"]
                        not in state["metadata"].get("counter_control_effect_ids", [])
                        and effect["id"] not in application_controls
                        and effect["id"] not in combat_reactive_closure
                        and not (
                            effect["generic"] == 39
                            and effect["runner"] == "eWQ"
                            and len(effect["values"]) == 3
                            and effect["values"][2] in (118, 119)
                        )
                    ):
                        reasons.append("native_state_runner_requires_execution")
                if duration <= 0 and not (simple_counter or event_state):
                    reasons.append("instant_or_event_counted_state_requires_execution")
                if (
                    (not definition["replace"] or definition["additive"])
                    and not simple_counter
                    and not (
                        duration > 0
                        and not definition["replace"]
                        and not definition["additive"]
                        and not definition["refresh"]
                    )
                ):
                    reasons.append("native_nonreplacement_stacking_requires_execution")
                plan["states"].append(state)
            else:
                reasons.append("native_direct_effect_requires_execution")
        plan["emitted_events"] = sorted(set(plan["emitted_events"]))
        reasons = sorted(set(reasons))
        result.append(
            dict(
                item_ref=reference,
                native_type=item["type_id"],
                name=item["name"],
                available=not reasons,
                unsupported_reason=";".join(reasons),
                plan=plan,
            )
        )
    assert len(result) == expected_count
    assert len({row["item_ref"] for row in result}) == expected_count
    return sorted(result, key=lambda row: row["item_ref"])


def write_migration(rows, source_sha, path):
    def literal(value):
        return "'" + value.replace("'", "''") + "'"

    lines = [
        "-- Generated by server/tools/build_consumable_actions.py from original native effects.",
        "CREATE TABLE native_consumable_actions (",
        " item_ref integer PRIMARY KEY CHECK(item_ref>0),",
        " available boolean NOT NULL, unsupported_reason text NOT NULL,",
        " plan jsonb NOT NULL CHECK(jsonb_typeof(plan)='object'),",
        " source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),",
        " CHECK((available AND unsupported_reason='') OR (NOT available AND unsupported_reason<>''))",
        ");",
        "INSERT INTO native_consumable_actions(item_ref,available,unsupported_reason,plan,source_sha256) VALUES",
    ]
    lines.append(
        ",\n".join(
            "("
            + ",".join(
                (
                    str(row["item_ref"]),
                    "true" if row["available"] else "false",
                    literal(row["unsupported_reason"]),
                    literal(encoded(row["plan"])),
                    literal(source_sha),
                )
            )
            + ")"
            for row in rows
        )
        + ";"
    )
    path.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()
    names = [
        "items-expanded.json",
        "native-descriptors.json",
        "state-closure.json",
        "raw-state-metadata.json",
        "counter-contracts.json",
    ]
    raw = {name: (args.input / name).read_bytes() for name in names}
    source_sha = hashlib.sha256(
        encoded(
            {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
        ).encode()
    ).hexdigest()
    rows = build(*(json.loads(raw[name]) for name in names))
    args.output.write_text(encoded(dict(source_sha256=source_sha, items=rows)) + "\n")
    write_migration(rows, source_sha, args.migration)
    print(
        encoded(
            dict(
                items=len(rows),
                available=sum(row["available"] for row in rows),
                source_sha256=source_sha,
            )
        )
    )


if __name__ == "__main__":
    main()
