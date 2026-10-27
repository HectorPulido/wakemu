"""Production weapon entry ordering over a bounded catalog/factory fixture.

The observer records external event delivery; original listener execution has
its own native consumer qualification. No weapon damage arithmetic is stubbed
into an alleged paid-fight result here.
"""
from copy import deepcopy
from random import Random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_weapon as weapon
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_state import Actor, Fight


class PaidWeaponBoundaryTests(unittest.TestCase):
    def test_production_payment_precedes_event_then_roots_and_failure_is_private(self):
        caster = Actor(7, 0, (0, 0, 0), 100, 6, 3, 20, 20, owner_id=3, controlled=True)
        enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 10, 20)
        caster.effect_stats = {1: 100, 2: 6, 3: 3, 4: 6}
        fight = Fight(
            81,
            [caster, enemy],
            {caster.position, enemy.position},
            {0: {caster.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        self.assertIs(fight.current, caster)
        character = dict(
            id=7,
            level=20,
            builds={0: dict(equipment="")},
            inventory_items=[
                dict(uid=1000, reference=2027, character_id=7, quantity=1)
            ],
        )
        rule = dict(
            native_use_criteria="",
            item_level=20,
            ap_cost=2,
            mp_cost=1,
            wp_cost=1,
            native_cpF=1,
            native_cpG=1,
            native_gjn=False,
            native_gjj=False,
            native_gjl=False,
            native_gjk=False,
            roots=[
                dict(reference=11, variant=0, active=True, execution_mode=2),
                dict(reference=12, variant=0, active=True, execution_mode=2),
            ],
        )
        definitions = {str(ref): dict(effect_class=1, children=[]) for ref in (11, 12)}

        class Actors:
            def __call__(self, current, actor):
                return SimpleNamespace(is_carrying=False)

            def properties(self, current, actor):
                return frozenset()

        traces = []
        previews = []
        reject = [False]
        rng = Random(1018)

        class Factory:
            summon_authority = Actors()

            def __call__(self, preview, plan):
                previews.append(preview)
                packets = []
                clone_authority = object()

                def replay(event, *, authority):
                    if authority is not clone_authority:
                        raise ValueError("Foreign clone authority")
                    paid = preview.actors[7]
                    traces.append(
                        (
                            "event",
                            event.event_ids,
                            event.channel,
                            (paid.ap, paid.mp, paid.effect_stats[4]),
                        )
                    )
                    return ()

                def execute(invocation):
                    paid = preview.actors[7]
                    traces.append(
                        (
                            "root",
                            invocation.reference,
                            (paid.ap, paid.mp, paid.effect_stats[4]),
                        )
                    )
                    rng.random()
                    packets.append((12613, b"private observer packet"))
                    if reject[0] and invocation.reference == 12:
                        preview.actors[-7].hp = 1
                        raise ValueError("later native root rejected")
                    return True

                return (
                    SimpleNamespace(
                        native_retention=SimpleNamespace(
                            fight=preview, view=lambda: SimpleNamespace(entries=())
                        ),
                        native_clone_authority=clone_authority,
                        effects=definitions,
                        replay_event=replay,
                        execute=execute,
                    ),
                    packets,
                )

        factory = Factory()

        def prepare(uid=1000):
            return weapon.prepare_server_weapon(
                struct.pack(">qqbiih", 7, uid, 15, 1, 0, 0),
                character,
                {},
                fight,
                3,
                b"",
                action_id=1,
                line_of_sight=lambda *_: True,
                critical=False,
                rng=rng,
            )

        before = source_snapshot(fight)
        with patch.object(weapon, "catalog", return_value={2027: rule}), patch.object(
            weapon, "validate_sheet", return_value=[dict(uid=1000, slot=15)]
        ), patch.object(
            weapon,
            "weapon_runtime_catalog",
            return_value=SimpleNamespace(effects=definitions),
        ), patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(factory, None),
        ), patch(
            "wakfu_server.combat_cast_facing.begin_cast_facing", return_value=()
        ):
            transaction = prepare()
            self.assertEqual(source_snapshot(fight), before)
            self.assertIsNot(transaction.fight, fight)
            self.assertEqual(
                (
                    transaction.fight.actors[7].ap,
                    transaction.fight.actors[7].mp,
                    transaction.fight.actors[7].effect_stats[4],
                ),
                (4, 2, 5),
            )
            self.assertEqual(
                [row[:3] for row in traces],
                [
                    ("event", (1018,), 6),
                    ("event", (1018,), 60),
                    ("root", 11, (4, 2, 5)),
                    ("root", 12, (4, 2, 5)),
                ],
            )
            self.assertTrue(all(row[-1] == (4, 2, 5) for row in traces))
            self.assertEqual(transaction.plan["native_retained_container"]["type"], 12)
            traces.clear()
            with self.assertRaises(ValueError):
                prepare(uid=1001)
            self.assertEqual(traces, [])
            rule["ap_cost"] = -1
            with self.assertRaises(ValueError):
                prepare()
            self.assertEqual(traces, [])
            rule["ap_cost"] = 2
            reject[0] = True
            rng_before = rng.getstate()
            with self.assertRaisesRegex(ValueError, "later native root rejected"):
                prepare()
            self.assertEqual(rng.getstate(), rng_before)
            self.assertEqual(source_snapshot(fight), before)
            self.assertEqual(fight.actors[-7].hp, 100)
            self.assertIsNot(previews[-1], fight)
