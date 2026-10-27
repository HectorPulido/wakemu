"""Observed Jondo visibility reaches the existing native facing heuristic.

These are compact DTO and World function regressions, not a fight simulation
or a certified opponent damage forecast.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

import wakfu_ai.bridge

_STAGE = Path(__file__).resolve().parents[1] / "wakfu_ai" / "bridge"
if str(_STAGE) not in wakfu_ai.bridge.__path__:
    wakfu_ai.bridge.__path__.insert(0, str(_STAGE))
from wakfu_ai.bridge.jondo_facing import defensive_facing


class JondoFacingTests(unittest.TestCase):
    def request(self):
        return dict(
            source=dict(actorId=-7, turnId=4, stateRevision=8),
            board=dict(
                cells=[
                    dict(id=3, xyz=[0, 0, 0]),
                    dict(id=9, xyz=[2, 0, 0]),
                    dict(id=11, xyz=[-2, 0, 0]),
                ],
                actors=[
                    dict(id=-7, cell=3, hidden=False),
                    dict(id=12, cell=9, hidden=False),
                    dict(id=13, cell=11, hidden=True),
                ],
            ),
        )

    def test_source_bound_positions_exclude_hidden_actors_without_fake_forecasts(self):
        request = self.request()
        result = defensive_facing(request)
        self.assertEqual(
            (result["actorId"], result["turnId"], result["stateRevision"]), (-7, 4, 8)
        )
        self.assertEqual(result["visibleActorIds"], [-7, 12])
        self.assertEqual(
            result["actors"],
            [dict(id=-7, position=[0, 0, 0]), dict(id=12, position=[2, 0, 0])],
        )
        self.assertEqual(result["rivals"], [])
        result["actors"][0]["position"][0] = 99
        self.assertEqual(request["board"]["cells"][0]["xyz"], [0, 0, 0])

    def test_partial_or_ambiguous_snapshots_do_not_attest_visibility(self):
        invalid = [None, {}, dict(source={"nativeIdentity": "fixture"})]
        base = self.request()
        for mutate in (
            lambda r: r["source"].update(actorId=True),
            lambda r: r["source"].update(stateRevision=None),
            lambda r: r["board"]["cells"].append(dict(id=3, xyz=[9, 9, 0])),
            lambda r: r["board"]["actors"][0].update(cell=99),
            lambda r: r["board"]["actors"][0].update(hidden=True),
            lambda r: r["board"]["actors"][1].pop("hidden"),
        ):
            request = deepcopy(base)
            mutate(request)
            invalid.append(request)
        for request in invalid:
            with self.subTest(request=request):
                self.assertIsNone(defensive_facing(request))

    def test_visible_fresh_player_without_live_property_override_can_be_faced(self):
        from wakfu_server.combat_ai_facing import apply, choose

        def actor(identity, team, position, controlled):
            return SimpleNamespace(
                id=identity,
                team=team,
                position=position,
                hp=100,
                controlled=controlled,
                direction=3,
                ap=6,
                mp=3,
                max_ap=6,
                max_mp=3,
                effect_stats={
                    20: 100,
                    21: 100,
                    22: 0,
                    23: 0,
                    24: 0,
                    27: 0,
                    28: 0,
                    29: 0,
                    30: 0,
                    31: 0,
                    48: 0,
                    9: 0,
                    52: 0,
                },
                effect_maxima={2: 6, 3: 3},
            )

        npc = actor(-7, 1, (0, 0, 0), False)
        player = actor(12, 0, (2, 0, 0), True)
        fight = SimpleNamespace(
            id=42,
            actors={npc.id: npc, player.id: player},
            current=npc,
            events=[],
            native_carry_pairs={},
            native_global_pv_collections={},
            _in_play=lambda candidate: candidate.hp > 0,
        )
        fight._event = lambda kind, **fields: fight.events.append(
            dict(kind=kind, **fields)
        )
        runtime = SimpleNamespace(
            fight=fight, action_id=7, _flush=lambda: (13420, b"flush")
        )
        self.assertFalse(hasattr(player, "native_fight_properties"))
        self.assertIsNone(choose(fight, npc))
        evidence = defensive_facing(self.request())
        self.assertEqual(choose(fight, npc, evidence)["targetId"], player.id)
        packets = apply(runtime, npc, evidence)
        self.assertEqual(packets[0][0], 13494)
        self.assertEqual(npc.direction, 1)
        self.assertEqual(npc.position, (0, 0, 0))
        self.assertEqual((npc.ap, npc.mp), (6, 3))
        self.assertEqual(fight.events[-1]["kind"], "orientation")
        self.assertEqual(fight.events[-1]["defensive_facing"]["certifiedLoss"], 0)


if __name__ == "__main__":
    unittest.main()
