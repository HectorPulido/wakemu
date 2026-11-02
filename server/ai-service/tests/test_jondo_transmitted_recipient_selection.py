"""Actual native support projection through Jondo TCP; no combat mutation."""
import os
import time
import unittest
import uuid
from types import SimpleNamespace


@unittest.skipUnless(
    os.environ.get("WAKFU_JONDO_RECIPIENT_SELECTION") == "1", "explicit TCP probe"
)
class TransmittedRecipientSelectionTests(unittest.TestCase):
    def test_original_7603_keeps_front_recipient_but_has_no_empty_fallback(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_ai.bridge.jondo_capabilities import project_support
        from wakfu_ai.transport.framed import FramedClient
        from wakfu_ai.transport.endpoint import tcp_address

        points = [(x, 0, 0) for x in range(6)]
        indices = {point: index for index, point in enumerate(points)}
        actor = SimpleNamespace(
            id=1, team=0, effective_level=58, direction=1, position=points[0]
        )
        actors = [
            dict(
                id=identity,
                team=team,
                cell=cell,
                hp=100,
                maxHp=100,
                ap=9,
                mp=0,
                nativeDirection=1,
                states=[],
            )
            for identity, team, cell in ((1, 0, 0), (2, 1, 4), (3, 1, 5))
        ]
        fight = SimpleNamespace(
            actors={1: actor},
            edges=[
                (points[a], points[b])
                for x in range(5)
                for a, b in ((x, x + 1), (x + 1, x))
            ],
        )
        table, index = native_casting_table(7603, 58)
        level, _, roots = table["levels"][index][:3]
        support = project_support(
            npc_runtime_catalog(imported=True),
            roots,
            level,
            fight=fight,
            actor=actor,
            rule=dict(minimum=1, maximum=30, allow_self=False, free_cell=False),
            indices=indices,
            actors=actors,
        )
        endpoint = os.environ.get("WAKFU_JONDO_ENDPOINT", "tcp://ai-jondo:8091")
        channel = FramedClient(*tcp_address(endpoint), timeout=5)
        try:
            for reject_front in (False, True):
                with self.subTest(reject_front=reject_front):
                    identity = "qa-native-transmitted-recipient-" + uuid.uuid4().hex
                    rejected = (
                        [
                            dict(
                                type="cast",
                                spellId=7603,
                                level=level,
                                target=list(points[row["cell"]]),
                                targetId=row["id"],
                            )
                            for row in actors[1:]
                        ]
                        if reject_front
                        else []
                    )
                    request = dict(
                        protocol=1,
                        requestId=identity,
                        source=dict(
                            actorId=1,
                            fightInstanceId=identity,
                            turnId=1,
                            catalogRevision="native-7603-recipient-projection",
                        ),
                        board=dict(
                            cells=[
                                dict(id=i, xyz=list(p)) for i, p in enumerate(points)
                            ],
                            edges=[
                                [a, b]
                                for x in range(5)
                                for a, b in ((x, x + 1), (x + 1, x))
                            ],
                            actors=actors,
                            round=1,
                            lineOfSight=[
                                [a, b, True] for a in range(6) for b in range(6)
                            ],
                        ),
                        spells=[
                            dict(
                                id=7603,
                                grade=level,
                                cost=3,
                                nativeCosts=dict(ap=3, mp=0, wp=0),
                                minRange=1,
                                maxRange=30,
                                needsLineOfSight=True,
                                needsFreeCell=False,
                                rows=[],
                                nativeSupport=support,
                            )
                        ],
                        native=dict(usage=[], turnActions=[]),
                        excludedActions=rejected,
                        limits=dict(budgetMs=1000),
                    )
                    status, reply = channel.request(
                        "/jondo/decide", request, deadline=time.monotonic() + 5
                    )
                    self.assertEqual(status, 200)
                    action = reply.get("action", {})
                    if reject_front:
                        self.assertEqual(action.get("type"), "end_turn", reply)
                    else:
                        self.assertEqual(action.get("type"), "cast", reply)
                        self.assertIn(action.get("targetId"), (2, 3), reply)
                        self.assertEqual(
                            action.get("target"),
                            list(points[4 if action["targetId"] == 2 else 5]),
                        )
        finally:
            channel.close()
