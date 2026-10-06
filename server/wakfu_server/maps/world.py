"""Live player membership, scoped by map and instance, separate from storage."""
import threading


class World:
    def __init__(self, spawn, remove, deliver, *, delivery_failure=None):
        self.lock = threading.RLock()
        self.players = {}
        self.spawn = spawn
        self.remove = remove
        self.deliver = deliver
        self.delivery_failure = delivery_failure

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
            return True
        except OSError as error:
            if self.delivery_failure is not None:
                try:
                    self.delivery_failure(peer, opcode, error)
                except Exception:
                    pass  # Diagnostics must not prevent existing socket cleanup.
            # Its connection worker owns lease cleanup and departure notification.
            try:
                peer.shutdown(2)
            except OSError:
                pass
            return False

    def private_chat(
        self, generation, sender_id, account_id, recipient, text, *, valid_session
    ):
        """Route native720 to current loaded peers across maps; never broadcast."""
        from wakfu_server import wire

        if (
            not isinstance(recipient, str)
            or not 1 <= len(recipient.encode("utf-8")) <= 127
        ):
            raise ValueError("Invalid private chat recipient")
        with self.lock:
            sender = self.players.get(sender_id)
            target = next(
                (
                    entry
                    for entry in self.players.values()
                    if entry[2]["name"].casefold() == recipient.casefold()
                ),
                None,
            )
        if sender is None or sender[0] != generation:
            raise ValueError("Private chat sender session is stale")
        if sender[2]["account_id"] != account_id:
            raise ValueError("Private chat account identity disagrees")
        # PostgreSQL and socket latency must not hold the membership lock.
        if not valid_session(sender):
            raise ValueError("Private chat sender session is stale")
        target_valid = target is not None and valid_session(target)
        with self.lock:
            current_sender = self.players.get(sender_id)
            if (
                current_sender is None
                or current_sender[0] != sender[0]
                or current_sender[1] is not sender[1]
            ):
                raise ValueError("Private chat sender session is stale")
            if target_valid:
                current_target = self.players.get(target[2]["id"])
                target_valid = (
                    current_target is not None
                    and current_target[0] == target[0]
                    and current_target[1] is target[1]
                )
        if not target_valid:
            self._send(sender[1], 349, wire.private_chat_error(101, recipient))
            return False
        if target[2]["id"] == sender_id:
            self._send(sender[1], 349, wire.private_chat_error(104))
            return False
        payload = wire.private_chat(account_id, sender[2], target[2], text)
        if not self._send(target[1], 720, payload):
            self._send(sender[1], 349, wire.private_chat_error(140))
            return False
        # A captured peer can disconnect after validation; writes are not atomic
        # with lease changes. Never redirect this payload to a replacement peer.
        return self._send(sender[1], 720, payload)

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
