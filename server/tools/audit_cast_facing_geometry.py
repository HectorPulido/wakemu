"""Common Desplume regression: actual13655 requests, native terrain, private cast.

No manual facing override. Multiple enemy cells and two legal levels share one
catalog load. This is offline delivery evidence, not GUI verification.
"""
import json
import struct
from pathlib import Path
import audit_active_spells as audit
from wakfu_server.combat_displacement import cardinal_vector
from wakfu_server.combat_orientation import apply
from wakfu_server.combat_runtime_messages import RuntimeMessages


def run():
    original_fixture = audit.fixture
    original_targets = audit.target_candidates
    original_prepare = audit.prepare_spell_transaction
    starts = {}
    observations = []

    def candidates(definition, level, terrain, origin, **kw):
        minimum, maximum, _ = definition["levels"][level - 1]
        choices = {}
        for cell in sorted(terrain["cells"]):
            dx, dy = cell[0] - origin[0], cell[1] - origin[1]
            if not minimum <= abs(dx) + abs(dy) <= maximum or not (dx == 0 or dy == 0):
                continue
            if cell == origin:
                continue
            try:
                if definition["line_of_sight"] and not audit.static_visible(
                    1134, origin, cell
                ):
                    continue
            except ValueError:
                continue
            direction = {(1, 0): 1, (0, 1): 3, (-1, 0): 5, (0, -1): 7}[
                cardinal_vector(dx, dy)
            ]
            choices.setdefault(direction, cell)
        if len(choices) < 3:
            raise AssertionError("Insufficient native cardinal target geometry")
        result = []
        for direction, cell in sorted(choices.items())[:3]:
            starts[cell] = (direction + 4) % 8
            result.append(("enemy", cell))
        return result

    def fixture(*args, **kw):
        character, creature, fight = original_fixture(*args, **kw)
        while fight.current.id != 7:
            fight.end_server_turn(fight.current.id, fight.turn_id)
        direction = starts[creature["x"], creature["y"], creature["z"]]
        apply(RuntimeMessages(fight), 3, struct.pack(">qB", 7, direction))
        return character, creature, fight

    def prepare(body, character, source, *args, **kw):
        before = audit.snapshot(source)
        result = original_prepare(body, character, source, *args, **kw)
        caster, target = result.fight.actors[7], result.fight.actors[-7]
        vector = cardinal_vector(
            target.position[0] - caster.position[0],
            target.position[1] - caster.position[1],
        )
        expected = {(1, 0): 1, (0, 1): 3, (-1, 0): 5, (0, -1): 7}[vector]
        assert caster.direction == expected and target.direction == expected
        assert audit.snapshot(source) == before
        assert any(op == 12613 for op, _ in result.packets[2:])
        observations.append(
            dict(
                level=character["level"],
                caster_start=source.actors[7].direction,
                caster_final=caster.direction,
                target_final=target.direction,
                caster_cell=caster.position,
                target_cell=target.position,
                expected_back_direction=expected,
                hp_before=source.actors[-7].hp,
                hp_after=target.hp,
                rollback_preserved=True,
                geometry_verified=True,
            )
        )
        return result

    audit.fixture, audit.target_candidates, audit.prepare_spell_transaction = (
        fixture,
        candidates,
        prepare,
    )
    try:
        report = audit.run(
            cases=[
                dict(spell_id=7318, level=level, variant="enemy") for level in (20, 200)
            ],
            output_name="docs/reports/combat-inventory/orientation303-desplume-geometry-runtime-audit.json",
        )
        report["geometry_observations"] = observations
        assert len(observations) == 6
        assert report["sources_stable"]
        return report
    finally:
        audit.fixture, audit.target_candidates, audit.prepare_spell_transaction = (
            original_fixture,
            original_targets,
            original_prepare,
        )


if __name__ == "__main__":
    path = Path(
        "docs/reports/combat-inventory/orientation303-desplume-geometry-runtime-audit.json"
    )
    path.write_text(json.dumps(run(), indent=2) + "\n")
    print(path)
