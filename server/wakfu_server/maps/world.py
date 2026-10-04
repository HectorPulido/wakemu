"""Live player membership, scoped by map and instance, separate from storage."""
import threading


class World:
    def __init__(self, spawn, remove, deliver):
        self.lock = threading.RLock()
        self.players = {}
        self.spawn = spawn
        self.remove = remove
        self.deliver = deliver

    @staticmethod
    def location(character):
        return character["map_id"], character["instance_id"]

    def snapshot(self):
        """Detached player data for proximity policies; no peers or tokens."""
        from copy import deepcopy

        with self.lock:
            return [deepcopy(character) for _, _, character in self.players.values()]

    def _send(self, peer, opcode, body):
        try:
            self.deliver(peer, opcode, body)
        except OSError:
            # Its connection worker owns lease cleanup and departure notification.
            try:
                peer.shutdown(2)
            except OSError:
                pass

    def join(self, generation, peer, character):
        with self.lock:
            existing = self.players.get(character["id"])
            if existing:
                self.leave(character["id"], existing[0])
            entry = (generation, peer, dict(character))
            for _, other_peer, other in self.players.values():
                if self.location(other) == self.location(character):
                    self._send(peer, 12608, self.spawn(other))
                    self._send(other_peer, 12608, self.spawn(character))
            self.players[character["id"]] = entry

    def leave(self, character_id, generation):
        with self.lock:
            existing = self.players.get(character_id)
            if not existing or existing[0] != generation:
                return False
            self.players.pop(character_id)
            for _, peer, other in self.players.values():
                if self.location(other) == self.location(existing[2]):
                    self._send(peer, 12304, self.remove(character_id))
            return True

    def update(self, generation, character, opcode, body, *, include_sender=True):
        with self.lock:
            existing = self.players.get(character["id"])
            if not existing or existing[0] != generation:
                raise ValueError("Character is no longer in this world session")
            if self.location(character) != self.location(existing[2]):
                raise ValueError("Map transition requires leave/join")
            self.players[character["id"]] = (generation, existing[1], dict(character))
            self.broadcast(
                generation, character["id"], opcode, body, include_sender=include_sender
            )

    def broadcast(self, generation, character_id, opcode, body, *, include_sender=True):
        with self.lock:
            existing = self.players.get(character_id)
            if not existing or existing[0] != generation:
                raise ValueError("Character is no longer in this world session")
            for _, peer, other in self.players.values():
                if (include_sender or other["id"] != character_id) and self.location(
                    other
                ) == self.location(existing[2]):
                    self._send(peer, opcode, body)

    def emit_location(
        self, map_id, instance_id, opcode, body, *, exclude_generation=None
    ):
        """Broadcast a location event without requiring a player sender."""
        with self.lock:
            for generation, peer, character in self.players.values():
                if generation != exclude_generation and self.location(character) == (
                    map_id,
                    instance_id,
                ):
                    self._send(peer, opcode, body)
