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


def run(spell_id, level, output):
    original_fixture = audit.fixture
    original_authority = audit.OrdinaryActorAuthority
    opponents = {}

    def fixture(*args, **kwargs):
        character, creature, old = original_fixture(*args, **kwargs)
        player, ally = copy.deepcopy(old.actors[7]), copy.deepcopy(old.actors[-7])
        ally.team = 0
        enemy = copy.deepcopy(ally)
        enemy.id, enemy.team, enemy.state_ledger = -8, 1, StateLedger(-8)
        enemy.position = next(cell for cell in sorted(old.walkable)
                              if cell not in (player.position, ally.position))
        for actor in (player, ally, enemy):
            actor.turn_count = 0
        fight = Fight(old.id, (player, ally, enemy), old.walkable,
                      {0: {player.position, ally.position}, 1: {enemy.position}}, old.edges)
        for key, value in vars(old).items():
            if key not in vars(fight):
                setattr(fight, key, copy.deepcopy(value))
        fight.native_effect_uid_next = 200
        fight.ready(3)
        opponents[-8] = dict(creature, id=-8, x=enemy.position[0],
                             y=enemy.position[1], z=enemy.position[2])
        return character, creature, fight

    def authority(**kwargs):
        kwargs["monsters"] = dict(kwargs["monsters"]) | opponents
        return original_authority(**kwargs)

    audit.fixture, audit.OrdinaryActorAuthority = fixture, authority
    try:
        report = audit.run(cases=[dict(spell_id=spell_id, level=level, variant="enemy")],
                           output_name=output)
    finally:
        audit.fixture, audit.OrdinaryActorAuthority = original_fixture, original_authority
    report["scope"] = "Actual common entry on ordinary ally; third ordinary opponent. No native criterion bypass."
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
    args = parser.parse_args()
    run(args.spell_id, args.level, args.output)
