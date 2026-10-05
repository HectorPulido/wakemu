"""Common self-cast audit with three nearby ordinary NPCs, no effect overrides."""
import copy
import json
from pathlib import Path
import audit_active_spells as audit
import audit_native_start_casts as start
from wakfu_server.combat_state import Fight
from wakfu_server.combat_state_ledger import StateLedger


def verify_adjacent_damage(report):
    """Require actual damage events on each verified adjacent NPC, per case."""
    observations = report["nearby_target_observations"]
    if len(observations) != len(report["rows"]):
        raise AssertionError("Some cast cases did not complete")
    verified = []
    for observation in observations:
        damage = {
            actor: sum(
                event["amount"]
                for event in observation["events"]
                if event["kind"] == "damage" and event["target_id"] == actor
            )
            for actor in (-7, -8, -9)
        }
        if not all(amount > 0 for amount in damage.values()):
            raise AssertionError(f"Missing damage on adjacent NPCs: {damage}")
        verified.append(damage)
    return verified


def run(spell_id, levels, output, *, require_adjacent_damage=False):
    original_fixture, original_runtime = audit.fixture, audit.server_runtime
    original_prepare = audit.prepare_spell_transaction
    extra, observations = {}, []

    def fixture(breed, level, enemy_cell, terrain, origin, **kwargs):
        cells = [
            cell
            for cell in sorted(terrain["cells"])
            if cell[2] == origin[2]
            and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) == 1
        ]
        if len(cells) < 3:
            raise ValueError("Fixture requires three verified adjacent terrain cells")
        character, creature, old = original_fixture(
            breed, level, cells[0], terrain, origin, **kwargs
        )
        actors = [copy.deepcopy(old.actors[7]), copy.deepcopy(old.actors[-7])]
        extra.clear()
        for identity, cell in zip((-8, -9), cells[1:3]):
            actor = copy.deepcopy(old.actors[-7])
            actor.id, actor.position, actor.state_ledger = (
                identity,
                cell,
                StateLedger(identity),
            )
            actors.append(actor)
            extra[identity] = dict(
                creature, id=identity, x=cell[0], y=cell[1], z=cell[2]
            )
        for actor in actors:
            actor.turn_count = 0
        fight = Fight(
            old.id, actors, old.walkable, {0: {origin}, 1: set(cells[:3])}, old.edges
        )
        for key, value in vars(old).items():
            if key not in vars(fight):
                setattr(fight, key, copy.deepcopy(value))
        fight.native_effect_uid_next = 200
        fight.ready(3)
        return character, creature, fight

    def runtime(character, monsters, *args, **kwargs):
        return original_runtime(character, dict(monsters) | extra, *args, **kwargs)

    def prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        observations.append(
            dict(
                events=list(result.events),
                actors={
                    str(key): dict(hp=actor.hp, position=actor.position)
                    for key, actor in result.fight.actors.items()
                },
            )
        )
        return result

    audit.fixture, audit.server_runtime, audit.prepare_spell_transaction = (
        fixture,
        runtime,
        prepare,
    )
    try:
        report = start.run(
            cases=[
                dict(spell_id=spell_id, level=level, variant="self") for level in levels
            ],
            output=output,
        )
    finally:
        audit.fixture, audit.server_runtime, audit.prepare_spell_transaction = (
            original_fixture,
            original_runtime,
            original_prepare,
        )
    report["nearby_target_observations"] = observations
    if require_adjacent_damage:
        report["verified_adjacent_damage"] = verify_adjacent_damage(report)
    report[
        "scope"
    ] = "Common native-start self-cast with three ordinary NPCs on verified adjacent terrain; real effect areas and criteria."
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("spell_id", type=int)
    parser.add_argument("levels", nargs="+", type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-adjacent-damage", action="store_true")
    args = parser.parse_args()
    report = run(
        args.spell_id,
        args.levels,
        args.output,
        require_adjacent_damage=args.require_adjacent_damage,
    )
    print(
        json.dumps(
            dict(
                rows=report["rows"], observations=report["nearby_target_observations"]
            ),
            ensure_ascii=False,
        )
    )
