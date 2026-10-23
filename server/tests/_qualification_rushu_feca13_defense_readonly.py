"""Read the retained defense facts without evaluating or advancing an action."""
import json
from pathlib import Path
import sys
import unittest


class ReadFecaDefense(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        nr = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        rv, nv = (
            cp["authorized_service_transition_verifier"],
            nr["authorized_scoped_policy_transition_verifier"],
        )
        before = rv()
        nv(nr)
        rng = cp["rng"].getstate()
        fight = cp["runtime"].fight
        actor = fight.actors[1]

        def bounded(value):
            if isinstance(value, (list, tuple)):
                return value[-256:]
            if isinstance(value, dict):
                return dict(list(value.items())[-128:])
            return value

        facts = dict(
            verification_before=before,
            endpoint=dict(
                table=fight.native_table_turn,
                turn=fight.turn_id,
                current=fight.current.id,
            ),
            checkpoint_keys=sorted(cp),
            character_spell_fields={
                k: v
                for k, v in cp["characters"][1].items()
                if any(s in k.lower() for s in ("spell", "deck", "level", "passive"))
            },
            build_fields=[
                {
                    k: getattr(build, k, None)
                    for k in ("breed", "level", "active_spells", "passive_spells")
                }
                for build in cp.get("builds", ())
            ],
            resources=dict(
                hp=actor.hp,
                max_hp=actor.max_hp,
                ap=actor.ap,
                mp=actor.mp,
                stats=dict(actor.effect_stats),
                maxima=dict(actor.effect_maxima),
            ),
            states=[
                vars(e)
                if hasattr(e, "__dict__")
                else dict(
                    uid=e.uid,
                    reference=e.reference,
                    level=e.level,
                    caster_id=e.caster_id,
                )
                for e in actor.state_ledger.entries
            ],
            native_spell_usage=bounded(getattr(fight, "native_spell_usage", None)),
            events=list(getattr(fight, "events", ()))[-256:],
            trace_fields={
                k: bounded(v)
                for k, v in vars(fight).items()
                if any(s in k.lower() for s in ("damage", "runner", "trace"))
            },
            runtime_last_native_delivery=bounded(
                getattr(cp["runtime"], "last_native_delivery", None)
            ),
            actors={
                i: dict(
                    hp=a.hp,
                    team=a.team,
                    position=a.position,
                    properties=getattr(a, "native_fight_properties", None),
                    stats=dict(a.effect_stats),
                )
                for i, a in fight.actors.items()
            },
            area_rows=[
                {
                    k: row.get(k)
                    for k in (
                        "uid",
                        "reference",
                        "owner_id",
                        "cell",
                        "effect_reference",
                        "removed",
                    )
                }
                for row in getattr(fight, "native_effect_areas", {}).values()
            ],
        )
        self.assertEqual(cp["rng"].getstate(), rng)
        facts["verification_after"] = rv()
        nv(nr)
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-actual-feca13-defense-and-native-damage-readonly.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadFecaDefense()])
