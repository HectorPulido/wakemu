#!/usr/bin/env python3
"""Public HTTP acceptance corpus using explicit synthetic native forecasts."""
import argparse
from copy import deepcopy
import json
import urllib.error
import urllib.request


def fixture():
    cells = [[x, 0, 0] for x in range(5)]
    actors = [
        dict(
            id=-2,
            team=1,
            controlled=False,
            position=[0, 0, 0],
            hp=30,
            max_hp=30,
            armor=0,
            ap=6,
            mp=3,
            wp=2,
        ),
        dict(
            id=1,
            team=0,
            controlled=True,
            position=[4, 0, 0],
            hp=10,
            max_hp=30,
            armor=0,
            ap=6,
            mp=3,
            wp=2,
        ),
    ]
    return dict(
        protocol=2,
        requestId="acceptance",
        stateKey="full-root-hash",
        fight_id=1,
        fightInstanceId="acceptance-instance",
        actor_id=-2,
        current_id=-2,
        turnId=1,
        stateRevision=1,
        catalogVersion="native-fixture-v1",
        policyVersion="fixture-v1",
        walkable=cells,
        edges=[[a, b] for a in cells for b in cells if abs(a[0] - b[0]) == 1],
        actors=actors,
        rootState="root",
        states=[dict(key="root", actors=deepcopy(actors), transitions=[], threat=0)],
    )


def successor(
    data,
    source,
    key,
    action,
    *,
    hp=None,
    position=None,
    ap=None,
    mp=None,
    threat=0,
    supported=True
):
    before = next(s for s in data["states"] if s["key"] == source)
    actors = deepcopy(before["actors"])
    if hp is not None:
        for actor in actors:
            if actor["id"] in hp:
                actor["hp"] = hp[actor["id"]]
    if position is not None:
        actors[0]["position"] = position
    if ap is not None:
        actors[0]["ap"] = ap
    if mp is not None:
        actors[0]["mp"] = mp
    before["transitions"].append(
        dict(id=key, supported=supported, action=action, nextState=key)
    )
    data["states"].append(dict(key=key, actors=actors, transitions=[], threat=threat))


def cast(target=1):
    return dict(
        type="cast",
        spellId=7962,
        level=10,
        targetId=target,
        target=[4, 0, 0] if target == 1 else [0, 0, 0],
    )


def scenarios():
    result = []
    combo = fixture()
    combo["states"][0]["threat"] = 8
    successor(
        combo,
        "root",
        "move",
        dict(type="move", path=[[1, 0, 0]]),
        position=[1, 0, 0],
        mp=2,
        threat=8,
    )
    successor(combo, "move", "cast", cast(), hp={1: 0}, ap=3, threat=8)
    successor(
        combo,
        "cast",
        "retreat",
        dict(type="move", path=[[0, 0, 0]]),
        position=[0, 0, 0],
        mp=1,
    )
    result.append(("move → finish → retreat", combo, ["move", "cast", "retreat"]))
    heal = fixture()
    heal["actors"][0]["hp"] = 5
    heal["states"][0]["actors"] = deepcopy(heal["actors"])
    successor(heal, "root", "heal", cast(-2), hp={-2: 30}, ap=3)
    successor(heal, "root", "damage", cast(), hp={1: 1}, ap=3)
    result.append(("useful healing outweighs attrition", heal, ["heal"]))
    fire = fixture()
    successor(fire, "root", "fire", cast(), hp={1: 1, -2: 1}, ap=3)
    result.append(("friendly fire outweighs benefit: end turn", fire, []))
    unknown = fixture()
    successor(unknown, "root", "unknown", cast(), hp={1: 0}, supported=False)
    result.append(("unsupported branch discarded", unknown, []))
    finish = fixture()
    successor(finish, "root", "kill", cast(), hp={1: 0}, ap=3)
    successor(finish, "root", "damage", cast(), hp={1: 1}, ap=3)
    result.append(("prefer finishing blow", finish, ["kill"]))
    risk = fixture()
    successor(
        risk,
        "root",
        "avoid-response",
        dict(type="move", path=[[1, 0, 0]]),
        position=[1, 0, 0],
        mp=2,
    )
    for state in risk["states"]:
        del state["threat"]
        plans = []
        for damage in (12, 8) if state["key"] == "root" else (6, 4):
            after = deepcopy(state["actors"])
            after[0]["hp"] -= damage
            after[1]["ap"] -= 3
            plans.append(
                dict(
                    id="response-" + str(damage),
                    supported=True,
                    steps=[
                        dict(
                            action=dict(
                                type="cast",
                                spellId=100,
                                level=1,
                                targetId=-2,
                                target=state["actors"][0]["position"],
                            ),
                            actors=after,
                        )
                    ],
                )
            )
        state["rivalForecasts"] = [dict(actorId=1, mode="native", plans=plans)]
    result.append(
        (
            "avoid the best rival response without adding alternatives",
            risk,
            ["avoid-response"],
        )
    )
    return result


def request(
    url,
    data,
    expected_status=200,
    *,
    raw=None,
    content_length=None,
    endpoint="/v2/decide"
):
    headers = {"Content-Type": "application/json"}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    call = urllib.request.Request(
        url + endpoint,
        data=raw if raw is not None else json.dumps(data, allow_nan=False).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(call, timeout=5) as reply:
            status, payload = reply.status, json.load(reply)
    except urllib.error.HTTPError as error:
        status, payload = error.code, json.load(error)
    if status != expected_status:
        raise AssertionError((status, expected_status, payload))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18091")
    args = parser.parse_args()
    for label, data, expected in scenarios():
        response = request(args.url, data)
        assert response["decision"]["transitionIds"] == expected, (label, response)
        assert response["stateRevision"] == data["stateRevision"]
        assert response["stateKey"] == data["stateKey"]
        print("OK:", label)
    old = fixture()
    old["teamContext"] = dict(
        fightInstanceId=old["fightInstanceId"], stateRevision=0, team=1
    )
    request(args.url, old, 400)
    root = fixture()
    root["actors"][0]["wp"] -= 1
    request(args.url, root, 400)
    ambiguous = fixture()
    ambiguous["states"][0]["rivalForecasts"] = []
    request(args.url, ambiguous, 400)
    request(args.url, None, 400, raw=b'{"protocol":2,"protocol":1}')
    request(args.url, None, 400, raw=b'{"protocol":NaN}')
    # Probe the early size check without streaming a multi-megabyte body that
    # the server correctly refuses before reading (which makes urllib hit a
    # BrokenPipe while it continues writing to the closed connection).
    request(args.url, {}, 413, content_length=4 * 1024 * 1024 + 1)
    legacy = fixture()
    legacy["protocol"] = 1
    response = request(args.url, legacy, endpoint="/v1/decide")
    assert response["decision"]["path"] == [[1, 0, 0], [2, 0, 0], [3, 0, 0]]
    assert response["decision"]["attack"] is None
    print("OK: revisions/context, JSON, HTTP size and protocol 1 compatibility")
    print("Full HTTP acceptance: OK")


if __name__ == "__main__":
    main()
