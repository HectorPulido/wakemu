#!/usr/bin/env python3
"""Report native SKIP_TURN subscriber evidence without changing activation."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def load(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as stream:
        return json.load(stream)


def trigger_role(monster, states, effects):
    """Traverse only initial-state child edges; masks are source IDs, not guesses."""
    raw = monster["initial_state_triples"]
    if len(raw) % 3:
        raise ValueError("Malformed native initial states")
    roots, missing_states = [], []
    for offset in range(0, len(raw), 3):
        state_id, level, _ = raw[offset : offset + 3]
        profile = states.get(str(state_id))
        if profile is None:
            missing_states.append(state_id)
            continue
        # These roots are structural unions only; execution must resolve the
        # native descriptor-dependent state level before using any effect.
        roots.extend((state_id, effect) for effect in profile.get("effect_ids", ()))
    pending = [(state, str(effect), []) for state, effect in roots]
    seen, rows, missing = set(), [], set()
    while pending:
        state, reference, subscriptions = pending.pop()
        key = (
            state,
            reference,
            tuple((s["effect_id"], s["mask_index"]) for s in subscriptions),
        )
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > 4096:
            raise ValueError("Native initial-state graph exceeds audit bound")
        effect = effects.get(reference)
        if effect is None:
            missing.add(reference)
            continue
        current = [
            dict(
                effect_id=int(reference),
                mask_index=index,
                event_bits=mask,
                criteria=effect.get("criteria", ""),
            )
            for index, mask in enumerate(effect.get("target_masks", ())[:6])
            if mask
        ]
        lineage = subscriptions + current
        family = effect.get("effect_class")
        if current or family == 426:
            rows.append(
                dict(
                    state_id=state,
                    effect_id=int(reference),
                    family=family,
                    criteria=effect.get("criteria", ""),
                    parameters=effect.get("parameters", []),
                    subscriptions=current,
                    inherited_subscriptions=subscriptions,
                )
            )
        pending.extend(
            (state, str(child), lineage) for child in effect.get("children", ())
        )
    owned = {ability["spell_id"] for ability in monster["native_abilities"]}

    def constant_owned_spell(row):
        parameters = row["parameters"]
        if row["family"] != 426 or len(parameters) < 2:
            return None
        reference, slope = parameters[:2]
        if (
            type(reference) not in (int, float)
            or not math.isfinite(reference)
            or not float(reference).is_integer()
            or reference <= 0
            or type(slope) not in (int, float)
            or not math.isfinite(slope)
            or slope != 0
            or int(reference) not in owned
        ):
            return None
        return int(reference)

    trigger_links, unconditional_links = [], []
    for row in rows:
        reference = constant_owned_spell(row)
        if reference is None:
            continue
        link = dict(row, spell_id=reference)
        if row["subscriptions"] or row["inherited_subscriptions"]:
            trigger_links.append(link)
        else:
            unconditional_links.append(link)

    return dict(
        reference=monster["ref"],
        native_levels=[monster["min_level"], monster["max_level"]],
        fight_properties=monster["fight_properties"],
        skip_turn=1 in monster["fight_properties"],
        native_owned_spells=sorted(owned),
        initial_state_triples=raw,
        subscriber_evidence=rows,
        owned_trigger_links=trigger_links,
        unsubscribed_owned_trigger_links=unconditional_links,
        missing_states=missing_states,
        missing_effects=sorted(missing),
        classification="skip_turn_with_owned_trigger_links"
        if trigger_links
        else "skip_turn_role_unproven",
        runtime_validated=False,
        excluded=False,
        resources_changed=False,
    )


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monsters", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--translations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope = load(args.scope)
    references = {
        int(row.get("ref", row.get("reference"))) for row in scope["monsters"]
    }
    states = load(args.states)
    translations = load(args.translations) if args.translations else {}
    rows = [
        trigger_role(monster, states["states"], states["effects"])
        for monster in load(args.monsters)["monsters"]
        if monster["ref"] in references and 1 in monster["fight_properties"]
    ]
    for row in rows:
        row["name"] = translations.get(f"content.7.{row['reference']}")
        row["owned_spell_names"] = {
            str(spell): translations.get(f"content.3.{spell}")
            for spell in row["native_owned_spells"]
        }
    paths = [args.monsters, args.states, args.scope] + (
        [args.translations] if args.translations else []
    )
    output = dict(
        schema="native-skip-turn-trigger-role-audit-v1",
        offline=True,
        source_sha256={str(path): sha256_file(path) for path in paths},
        rows=rows,
    )
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"Audited {len(rows)} native SKIP_TURN definitions; no activation changes")


if __name__ == "__main__":
    main()
