"""Server-owned exploration walking before an actor interaction."""

import time

from .dispatch_result import DispatchResult


class ActorApproachMixin:
    def approach_actor(
        self, accepts, *, blocked=(), geometry=None, allow_unreachable=False
    ):
        from wakfu_server.actor_approach import (
            ApproachUnavailable,
            approach_path,
            movement_request,
        )
        from wakfu_server.combat_geometry import prepare_geometry
        from wakfu_server.combat_terrain import map_geometry

        character = self.state.character
        start = tuple(character[axis] for axis in ("x", "y", "z"))
        if start not in blocked and accepts(start):
            return False
        try:
            path = approach_path(
                geometry or prepare_geometry(map_geometry(character["map_id"])),
                start,
                accepts,
                blocked=blocked,
            )
        except ApproachUnavailable:
            if allow_unreachable:
                return False
            raise
        if len(path) == 1:
            return False
        opcode, body = self.state.opcode, self.state.body
        request = movement_request(path)
        try:
            self.state.opcode, self.state.body = 13331, request
            result = self.handle_world_movement()
        finally:
            self.state.opcode, self.state.body = opcode, body
        # Movement's existing gate validators may reject a route before commit.
        if result == DispatchResult.CONTINUE:
            return True
        self.runtime.send(
            self.state.connection,
            self.state.service,
            13852,
            self.runtime.wire.movement_path(character["id"], request),
        )
        self.state.pending_actor_approach = dict(
            generation=self.state.generation,
            identity=tuple(character[key] for key in ("id", "map_id", "instance_id")),
            position=path[-1],
            opcode=opcode,
            body=body,
            due=time.monotonic() + (len(path) - 1) * 0.5 + 0.1,
        )
        return True

    def resume_actor_approach(self):
        pending = getattr(self.state, "pending_actor_approach", None)
        if pending is None or time.monotonic() < pending["due"]:
            return
        self.state.pending_actor_approach = None
        character = self.state.character
        if (
            not self.state.loaded
            or character is None
            or self.state.generation != pending["generation"]
            or self.state.fight is not None
            or self.state.spectator_session is not None
            or tuple(character[key] for key in ("id", "map_id", "instance_id"))
            != pending["identity"]
            or tuple(character[key] for key in ("x", "y", "z")) != pending["position"]
        ):
            return
        opcode, body = self.state.opcode, self.state.body
        try:
            self.state.opcode, self.state.body = pending["opcode"], pending["body"]
            if self.prepare_request() != DispatchResult.CONTINUE:
                self.dispatch_request()
        finally:
            self.state.opcode, self.state.body = opcode, body
