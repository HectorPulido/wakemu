"""Save both authentic endpoints and already-cached source context evidence."""
import dataclasses
import json
from pathlib import Path
import sys
import unittest


def field(value, key, default=None):
    return (
        value.get(key, default)
        if isinstance(value, dict)
        else getattr(value, key, default)
    )


def invocation_values(value):
    if isinstance(value, dict):
        return dict(value)
    if dataclasses.is_dataclass(value):
        return {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
    return vars(value) if hasattr(value, "__dict__") else value


class PreserveEndpoints(unittest.TestCase):
    def runTest(self):
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        nv = lambda: nox.verify_retained_component(nr)
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        rv = cp["authorized_service_transition_verifier"]
        nb = nv()
        rb = rv()
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.maps.boss_score_runtime import staged_score

        c = nr["case"]
        f = c.fight
        result = dict(
            table=f.native_table_turn,
            turn=f.turn_id,
            current=f.current.id,
            phase=f.phase,
            score=staged_score(f),
            snapshot=snapshot(f, runtime=c.runtime),
            rng_state=c.rng.getstate(),
            players={
                str(i): dict(
                    hp=f.actors[i].hp,
                    ap=f.actors[i].ap,
                    mp=f.actors[i].mp,
                    wp=f.actors[i].effect_stats[4],
                    position=f.actors[i].position,
                    marks9050=[
                        (e.uid, e.level, getattr(e, "caster_id", None))
                        for e in f.actors[i].state_ledger.entries
                        if e.reference == 9050
                    ],
                )
                for i in c.characters
            },
            faille_operations=nr["receipt"].get("native_faille_operations"),
            verification_before=nb,
            verification_after=nv(),
            no_actions=True,
        )
        Path(
            ".runtime/parallel-readiness-20261021/nox-v5-t9-101-paid-three-million-support-path-retained-endpoint.json"
        ).write_text(json.dumps(result, indent=2, default=str) + "\n")
        rf = cp["runtime"].fight
        rng = cp["rng"].getstate()
        a = rf.actors[2]
        states = [
            dict(
                uid=e.uid,
                reference=e.reference,
                level=e.level,
                caster=getattr(e, "caster_id", None),
                effect_ids=getattr(e, "effect_ids", None),
            )
            for e in a.state_ledger.entries
            if e.reference in (7013, 6999)
        ]
        uids = {e["uid"] for e in states}
        selected = []
        for uid, row in getattr(rf, "native_owned_group_effects", {}).items():
            inv = field(row, "invocation", {})
            container = field(inv, "native_retained_container")
            ref = field(inv, "reference", field(row, "generic_effect"))
            if (
                field(row, "container_id") == 4881
                or field(container, "id") == 4881
                or field(inv, "state_uid") in uids
                or ref == 318946
            ):
                values = dict(row) if isinstance(row, dict) else invocation_values(row)
                if isinstance(values, dict):
                    values["invocation"] = invocation_values(inv)
                selected.append(dict(uid=uid, row=values))
        area = sys.modules["wakfu_server.combat_effect_area"]
        cache = area.native_effect_areas.cache_info()
        definition = area.native_effect_areas().get("1654") if cache.currsize else None
        facts = dict(
            table=rf.native_table_turn,
            turn=rf.turn_id,
            current=rf.current.id,
            cached_definition1654=definition,
            cache_was_populated=bool(cache.currsize),
            states=states,
            selected_owned_groups=selected,
            retained_records={
                str(i): getattr(rf, "native_retained_records", {}).get(i)
                for i in (10072, 10078)
            },
            verification_before=rb,
            verification_after=rv(),
            no_actions=True,
        )
        self.assertEqual(cp["rng"].getstate(), rng)
        facts["rng_unchanged"] = True
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-returned-qq-complete-retained-invocation-source-facts.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([PreserveEndpoints()])
