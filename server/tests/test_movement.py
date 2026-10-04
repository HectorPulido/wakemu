import unittest
from wakfu_server.movement import Movement


def request(start, steps):
    end = dict(start)
    for step in steps:
        for axis in ("x", "y", "z"):
            end[axis] += step["d" + axis]
    return {"start_position": start, "end_position": end, "steps": steps}


class MovementTests(unittest.TestCase):
    def test_replacement_from_intermediate_cell_and_height(self):
        route = Movement(dict(x=-12, y=-8, z=-1))
        first = request(dict(x=-12, y=-8, z=-1), [dict(dx=-1, dy=0, dz=0)] * 5)
        route.commit(route.validate(first))
        redirect = request(dict(x=-14, y=-8, z=-1), [dict(dx=0, dy=-1, dz=1)] * 2)
        route.commit(route.validate(redirect))
        route.validate(request(redirect["end_position"], [dict(dx=1, dy=0, dz=0)]))
        with self.assertRaises(ValueError):
            route.validate(first)  # Abandoned path is no longer approved.

    def test_unvisited_origin_does_not_change_route(self):
        route = Movement(dict(x=-12, y=-8, z=-1))
        before = set(route.approved)
        with self.assertRaises(ValueError):
            route.validate(request(dict(x=0, y=0, z=-1), [dict(dx=1, dy=0, dz=0)]))
        self.assertEqual(route.approved, before)

    def test_route_crosses_former_test_boundary_and_checks_endpoint(self):
        route = Movement(dict(x=8, y=32, z=-1))
        path = request(dict(x=8, y=32, z=-1), [dict(dx=0, dy=1, dz=1)] * 6)
        route.commit(route.validate(path))
        self.assertIn((8, 38, 5), route.approved)
        path["end_position"]["z"] = 0
        with self.assertRaises(ValueError):
            route.validate(path)
