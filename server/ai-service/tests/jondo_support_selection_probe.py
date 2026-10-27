"""Actual Jondo TCP selection on explicit DTOs, not native healing proof."""
import time
import uuid


def run_support_selection(*, endpoint="tcp://ai-jondo:8091"):
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address

    cases = []
    channel = FramedClient(*tcp_address(endpoint), timeout=5)
    try:
        for hp in (10, 100):
            identity = "qa-native-shaped-heal-" + uuid.uuid4().hex
            request = dict(
                protocol=1,
                requestId=identity,
                source=dict(
                    actorId=1,
                    fightInstanceId=identity,
                    turnId=1,
                    catalogRevision="heal-dto-v1",
                ),
                board=dict(
                    cells=[dict(id=i, xyz=[i, 0, 0]) for i in range(5)],
                    edges=[
                        [a, b] for i in range(4) for a, b in ((i, i + 1), (i + 1, i))
                    ],
                    actors=[
                        dict(id=1, team=1, cell=0, hp=100, maxHp=100, ap=6, mp=0),
                        dict(id=2, team=1, cell=1, hp=hp, maxHp=100, ap=6, mp=0),
                        dict(id=3, team=0, cell=4, hp=100, maxHp=100, ap=6, mp=0),
                    ],
                    lineOfSight=[[a, b, True] for a in range(5) for b in range(5)],
                ),
                spells=[
                    dict(
                        id=70001,
                        grade=1,
                        cost=2,
                        nativeCosts=dict(ap=2, mp=0, wp=0),
                        minRange=1,
                        maxRange=3,
                        heal=40,
                        rows=[
                            dict(
                                kind="heal",
                                amount=40,
                                target="ally",
                                fixedCells=[[0, 0]],
                            )
                        ],
                    )
                ],
                native=dict(usage=[]),
                excludedActions=[],
                limits=dict(budgetMs=1000),
            )
            started = time.monotonic()
            status, reply = channel.request(
                "/jondo/decide", request, deadline=started + 5
            )
            action = reply.get("action", {})
            expected = (
                (
                    action.get("type") == "cast"
                    and action.get("spellId") == 70001
                    and action.get("targetId") == 2
                )
                if hp == 10
                else action.get("type") == "end_turn"
            )
            cases.append(
                dict(
                    allyHP=hp,
                    status=status,
                    action=action,
                    plannerElapsedMs=reply.get("elapsedMs"),
                    rpcWallMs=(time.monotonic() - started) * 1000,
                    passed=status == 200 and expected,
                )
            )
    finally:
        channel.close()
    return dict(
        scope="Actual Jondo Docker TCP on synthetic native-shaped DTO; no native heal committed",
        cases=cases,
        passed=all(row["passed"] for row in cases),
    )
