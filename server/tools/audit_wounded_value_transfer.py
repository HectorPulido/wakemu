"""Audit legal common casts after ordinary fixture damage; no predicate forcing."""
import json
from pathlib import Path
import audit_native_start_casts as start
import audit_active_spells as audit


def run(*, spell_id, levels, output):
    initialize = audit.initialize_transaction
    prepare = audit.prepare_spell_transaction
    observations = []
    wounds = []

    def wounded(*args, **kwargs):
        fight, packets = initialize(*args, **kwargs)
        caster = fight.actors[7]
        attacker = next(actor.id for actor in fight.actors.values() if actor.id != 7)
        amount = min(100, caster.hp - 1)
        before = caster.hp
        dealt = fight.apply_effect_damage(attacker, caster.id, amount)
        wounds.append(
            dict(
                before=before,
                dealt=dealt,
                after=caster.hp,
                current_hp_stat=caster.effect_stats[1],
            )
        )
        return fight, packets

    def observed(*args, **kwargs):
        source = args[2]
        before = {key: actor.hp for key, actor in source.actors.items()}
        result = prepare(*args, **kwargs)
        observations.append(
            dict(
                before_hp=before,
                after_hp={key: actor.hp for key, actor in result.fight.actors.items()},
                events=list(result.events),
            )
        )
        return result

    audit.initialize_transaction = wounded
    audit.prepare_spell_transaction = observed
    try:
        report = start.run(
            cases=[
                dict(spell_id=spell_id, level=level, variant="enemy")
                for level in levels
            ],
            output=output,
        )
    finally:
        audit.initialize_transaction = initialize
        audit.prepare_spell_transaction = prepare
    report["fixture_damage"] = wounds
    report["prepared_actor_health"] = observations
    report[
        "fixture_policy"
    ] = "Ordinary Fight.apply_effect_damage wounds caster before cast; real roots, targeting, criteria, callbacks and transaction remain unchanged."
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("spell_id", type=int)
    parser.add_argument("levels", nargs="+", type=int)
    parser.add_argument("--output", required=True)
    options = parser.parse_args()
    report = run(
        spell_id=options.spell_id, levels=options.levels, output=options.output
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "rows",
                    "fixture_damage",
                    "prepared_actor_health",
                    "sources_stable",
                )
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
