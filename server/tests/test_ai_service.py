import importlib.util
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

_DIRECTORY = Path(__file__).resolve().parents[1] / "ai-service"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = _load("wakfu_service_planner", _DIRECTORY / "planner.py")
previous = sys.modules.get("planner")
sys.modules["planner"] = planner
try:
    service = _load("wakfu_ai_service", _DIRECTORY / "server.py")
finally:
    if previous is None:
        sys.modules.pop("planner", None)
    else:
        sys.modules["planner"] = previous


def fixture():
    cells = [[x, 0, 0] for x in range(6)]
    edges = [
        [c, [c[0] + dx, 0, 0]] for c in cells for dx in (-1, 1) if 0 <= c[0] + dx < 6
    ]
    return dict(
        protocol=1,
        requestId="own-request",
        stateKey="own-state",
        fight_id=1,
        actor_id=-2,
        current_id=-2,
        walkable=cells,
        edges=edges,
        actors=[
            dict(
                id=-2, team=1, hp=12, controlled=False, position=[0, 0, 0], mp=3, ap=6
            ),
            dict(id=1, team=0, hp=60, controlled=True, position=[5, 0, 0], mp=3, ap=6),
        ],
    )


class ServicePlannerTests(unittest.TestCase):
    def test_existing_policy_mp_budget_and_enemy_cell_never_traversed(self):
        data = fixture()
        result = planner.decide(data)
        self.assertEqual(
            (result["requestId"], result["stateKey"]), ("own-request", "own-state")
        )
        self.assertEqual(result["decision"]["path"], [[1, 0, 0], [2, 0, 0], [3, 0, 0]])
        self.assertEqual(result["decision"]["target_id"], 1)
        self.assertIsNone(result["decision"]["attack"])
        data["actors"][0]["position"] = [4, 0, 0]
        self.assertEqual(planner.decide(data)["decision"]["path"], [])

    def test_verified_altitude_edge_works_missing_edge_does_not(self):
        data = fixture()
        data["walkable"][1][2] = 2
        for edge in data["edges"]:
            for cell in edge:
                if cell[0] == 1:
                    cell[2] = 2
        result = planner.decide(data)["decision"]
        self.assertEqual(result["path"][0], [1, 0, 2])
        data["edges"] = [
            edge for edge in data["edges"] if edge != [[0, 0, 0], [1, 0, 2]]
        ]
        self.assertEqual(planner.decide(data)["decision"]["path"], [])

    def test_controlled_dead_duplicate_actors_and_wrong_turn_rejected(self):
        for mutation in ("controlled", "dead", "duplicate", "current"):
            data = fixture()
            if mutation == "controlled":
                data["actors"][0]["controlled"] = True
            elif mutation == "dead":
                data["actors"][0]["hp"] = 0
            elif mutation == "duplicate":
                data["actors"].append(data["actors"][0])
            else:
                data["current_id"] = 1
            with self.assertRaises(ValueError):
                planner.decide(data)

    def test_non_cardinal_shortcut_is_not_a_legal_movement(self):
        data = fixture()
        data["edges"].append([[0, 0, 0], [4, 0, 0]])
        self.assertEqual(
            planner.decide(data)["decision"]["path"], [[1, 0, 0], [2, 0, 0], [3, 0, 0]]
        )


class ServiceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        cls.url = "http://127.0.0.1:" + str(cls.http.server_port)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(2)

    def test_health_and_real_decision_post(self):
        with urllib.request.urlopen(self.url + "/health") as reply:
            self.assertEqual(json.load(reply)["status"], "ok")
        request = urllib.request.Request(
            self.url + "/v1/decide",
            data=json.dumps(fixture()).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as reply:
            result = json.load(reply)
        self.assertEqual(result["decision"]["path"], [[1, 0, 0], [2, 0, 0], [3, 0, 0]])

    def test_bad_snapshot_gets_http400_without_decision(self):
        request = urllib.request.Request(
            self.url + "/v1/decide", data=b'{"protocol":2}'
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)
        self.assertNotIn("decision", json.load(caught.exception))
