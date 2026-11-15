"""Python representation adapter for Rust-owned exploration route identity."""

import weakref


def _default_native():
    from wakfu_server.spatial_native import get_spatial

    return get_spatial()


def _release_native(spatial, operation, handle):
    try:
        spatial.call(operation, handle=handle)
    except Exception:
        # The process owner may already have closed the native engine.
        pass


def _position(position):
    return (
        tuple(position[axis] for axis in ("x", "y", "z"))
        if isinstance(position, dict)
        else position[:3]
    )


def _request(request):
    return {
        "start_position": _position(request["start_position"]),
        "end_position": _position(request["end_position"]),
        "steps": [
            {axis: step[axis] for axis in ("dx", "dy", "dz")}
            for step in request["steps"]
        ],
    }


class Movement:
    def __init__(self, position, *, native=None):
        self._spatial = _default_native() if native is None else native
        self._handle = self._spatial.call(
            "navigation.route_new", position=_position(position)
        )["handle"]
        self._finalizer = weakref.finalize(
            self, _release_native, self._spatial, "navigation.route_drop", self._handle
        )

    @staticmethod
    def key(position):
        return tuple(
            _default_native().call("navigation.route_key", position=_position(position))
        )

    @property
    def approved(self):
        return {
            tuple(row)
            for row in self._spatial.call(
                "navigation.route_points", handle=self._handle
            )
        }

    @approved.setter
    def approved(self, points):
        self.commit(points)

    def validate(self, request):
        return {
            tuple(row)
            for row in self._spatial.call(
                "navigation.route_validate",
                handle=self._handle,
                request=_request(request),
            )
        }

    def commit(self, points):
        self._spatial.call(
            "navigation.route_commit", handle=self._handle, points=list(points)
        )
