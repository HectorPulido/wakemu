"""Identify inert owned state representations already listed in native cle.

This is an offline qualification hint, never permission to skip initialization,
spell effect coverage, AI checks or native casting guards.
"""
import argparse
import gzip
import json
import math
from pathlib import Path


def constructor_spell_representations(monster, spells, effects, casting):
    raw = monster["initial_state_triples"]
    if len(raw) % 3:
        raise ValueError("Malformed native initial-state triples")
    initial = set(raw[::3])
    records, other = [], []
    for ability in monster["native_abilities"]:
        reference = str(ability["spell_id"])
        spell = spells.get(reference)
        native_casting = casting.get(reference)
        if spell is None or native_casting is None:
            other.append(int(reference))
            continue
        roots = {str(root) for level in spell.get("levels", ()) for root in level[2]}
        roots.update(map(str, spell.get("level_zero_roots", ())))
        states, witnesses = set(), []
        for root in sorted(roots):
            effect = effects.get(root, {})
            parameters = effect.get("parameters", ())
            if (
                effect.get("effect_class") != 304
                or effect.get("variant") != 0
                or effect.get("criteria", "").strip() != "False"
                or effect.get("children")
                or len(parameters) < 2
                or type(parameters[0]) not in (int, float)
                or not math.isfinite(parameters[0])
                or not float(parameters[0]).is_integer()
                or parameters[0] <= 0
                or type(parameters[1]) not in (int, float)
                or parameters[1] != 0
                or int(parameters[0]) not in initial
            ):
                break
            states.add(int(parameters[0]))
            witnesses.append(
                dict(
                    effect_id=int(root),
                    initial_state_id=int(parameters[0]),
                    native_root_criterion="False",
                )
            )
        else:
            if roots:
                records.append(
                    dict(
                        spell_id=int(reference),
                        casting_literal_false=native_casting.get(
                            "cast_criterion_raw", ""
                        ).strip()
                        == "False",
                        root_literal_false=True,
                        constructor_state_ids=sorted(states),
                        root_witnesses=witnesses,
                        level_equivalence_qualified=False,
                        constructor_execution_qualified=False,
                    )
                )
                continue
        other.append(int(reference))
    return dict(
        reference=monster["ref"],
        constructor_representations=records,
        other_owned_spell_ids=other,
        owned_book_role="only_inert_constructor_representations"
        if records and not other
        else "mixed_constructor_representations_and_other_spells"
        if records
        else "no_constructor_representation_proven",
        activated=False,
        qualification_changed=False,
    )


def load(path):
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope = json.loads(args.scope.read_text())["monsters"]
    references = {row["ref"] for row in scope}
    monsters = load(args.bundle / "monsters.json.gz")["monsters"]
    trees = load(args.bundle / "trees.json.gz")
    casting = load(args.bundle / "casting.json.gz")["spells"]
    translations = load(args.bundle / "translations.json.gz")
    rows = []
    for monster in monsters:
        if monster["ref"] not in references:
            continue
        row = constructor_spell_representations(
            monster, trees["spells"], trees["effects"], casting
        )
        if not row["constructor_representations"]:
            continue
        row["name"] = translations.get(f"content.7.{monster['ref']}")
        row["native_initial_state_triples"] = monster["initial_state_triples"]
        for spell in row["constructor_representations"]:
            spell["name_key"] = f"content.3.{spell['spell_id']}"
            spell["name"] = translations.get(spell["name_key"])
            spell["description_key"] = f"content.4.{spell['spell_id']}"
            spell["description"] = translations.get(spell["description_key"])
        rows.append(row)
    args.output.write_text(
        json.dumps(
            dict(
                schema="native-constructor-spell-representations-v1",
                offline=True,
                rows=rows,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(
                references=len(rows),
                only_inert=sum(not row["other_owned_spell_ids"] for row in rows),
            )
        )
    )


if __name__ == "__main__":
    main()
