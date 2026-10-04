"""Validate replacement paths while the client animates an approved route."""


class Movement:
    def __init__(self, position):
        self.approved = {self.key(position)}

    @staticmethod
    def key(position):
        return tuple(position[k] for k in ("x", "y", "z"))

    def validate(self, request):
        point = dict(request["start_position"])
        if self.key(point) not in self.approved:
            raise ValueError("Route starts outside the previous approved path")
        points = {self.key(point)}
        for step in request["steps"]:
            for axis in ("x", "y", "z"):
                point[axis] += step["d" + axis]
            points.add(self.key(point))
        if point != request["end_position"]:
            raise ValueError("Route endpoint mismatch")
        return points

    def commit(self, points):
        self.approved = points
