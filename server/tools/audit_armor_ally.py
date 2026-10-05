"""Real common cast entry with an ordinary allied NPC and third opponent.

Test-only roster construction uses bootstrap-produced native snapshots/team
properties. This does not change the production runtime or native criteria.
"""
import copy
import json
from pathlib import Path
import audit_active_spells as audit
from wakfu_server.combat_state import Fight
from wakfu_server.combat_state_ledger import StateLedger


def run(spell_id, level, output, *, wound_target=False):
    original_fixture = audit.fixture
    original_authority = audit.OrdinaryActorAuthority
    original_runtime = audit.server_runtime
    opponents = {}
    original_initialize = audit.initialize_transaction
    original_prepare = audit.prepare_spell_transaction
    wounds, observations = [], []

    def initialize(*args, **kwargs):
        fight, packets = original_initialize(*args, **kwargs)
        if wound_target:
            target = fight.actors[-7]
            before = target.hp
            dealt = fight.apply_effect_damage(-8, -7, max(0, before - 1))
            wounds.append(dict(before=before, after=target.hp, dealt=dealt))
        return fight, packets

    def prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        observations.append(
            dict(events=list(result.events), target_hp=result.fight.actors[-7].hp)
        )
        return result

    def fixture(*args, **kwargs):
        character, creature, old = original_fixture(*args, **kwargs)
        player, ally = copy.deepcopy(old.actors[7]), copy.deepcopy(old.actors[-7])
        ally.team = 0
        enemy = copy.deepcopy(ally)
        enemy.id, enemy.team, enemy.state_ledger = -8, 1, StateLedger(-8)
        enemy.position = next(
            cell
            for cell in sorted(old.walkable)
            if cell not in (player.position, ally.position)
        )
        for actor in (player, ally, enemy):
            actor.turn_count = 0
        fight = Fight(
            old.id,
            (player, ally, enemy),
            old.walkable,
            {0: {player.position, ally.position}, 1: {enemy.position}},
            old.edges,
        )
        for key, value in vars(old).items():
            if key not in vars(fight):
                setattr(fight, key, copy.deepcopy(value))
        fight.native_effect_uid_next = 200
        fight.ready(3)
        opponents[-8] = dict(
            creature,
            id=-8,
            x=enemy.position[0],
            y=enemy.position[1],
            z=enemy.position[2],
        )
        return character, creature, fight

    def authority(**kwargs):
        kwargs["monsters"] = dict(kwargs["monsters"]) | opponents
        return original_authority(**kwargs)

    def runtime(character, monsters, *args, **kwargs):
        return original_runtime(character, dict(monsters) | opponents, *args, **kwargs)

    audit.server_runtime = runtime
    audit.fixture, audit.OrdinaryActorAuthority = fixture, authority
    audit.initialize_transaction, audit.prepare_spell_transaction = initialize, prepare
    try:
        report = audit.run(
            cases=[dict(spell_id=spell_id, level=level, variant="enemy")],
            output_name=output,
        )
    finally:
        audit.server_runtime = original_runtime
        audit.initialize_transaction, audit.prepare_spell_transaction = (
            original_initialize,
            original_prepare,
        )
        audit.fixture, audit.OrdinaryActorAuthority = (
            original_fixture,
            original_authority,
        )
    report[
        "scope"
    ] = "Actual common entry on ordinary ally; third ordinary opponent. No native criterion bypass."
    report["fixture_damage"] = wounds
    report["prepared_healing"] = observations
    for row in report["rows"]:
        row["target_relation"] = "ally"
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("spell_id", type=int)
    parser.add_argument("level", type=int)
    parser.add_argument("output")
    parser.add_argument("--wound-target", action="store_true")
    args = parser.parse_args()
    run(args.spell_id, args.level, args.output, wound_target=args.wound_target)
