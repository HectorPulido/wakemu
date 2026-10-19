"""Live player membership, scoped by map and instance, separate from storage."""
import threading


class World:
    def __init__(
        self,
        spawn,
        remove,
        deliver,
        *,
        deliver_batch=None,
        delivery_failure=None,
        state_packets=None,
    ):
        self.lock = threading.RLock()
        self.players = {}
        self._ecology_inactive = set()
        self._presence_generation = {}
        self._presence_sequence = 0
        self.spawn = spawn
        self.remove = remove
        self.deliver = deliver
        self.deliver_batch = deliver_batch
        self.delivery_failure = delivery_failure
        self.state_packets = state_packets or (lambda character: ())

    @staticmethod
    def location(character):
        return character["map_id"], character["instance_id"]

    def snapshot(self):
        """Detached player data for proximity policies; no peers or tokens."""
        from copy import deepcopy

        with self.lock:
            return [
                (
                    dict(deepcopy(character), _ecology_active=False)
                    if (character["id"], generation) in self._ecology_inactive
                    else deepcopy(character)
                )
                for generation, _, character in self.players.values()
            ]

    def update_territory_projection(self, generation, character, *, peer, bonuses):
        """Merge derived stats only while the exact owner/location lease is live."""
        with self.lock:
            entry = self.players.get(character["id"])
            if (
                entry is None
                or entry[0] != generation
                or entry[1] is not peer
                or any(
                    entry[2].get(key) != character.get(key)
                    for key in ("map_id", "instance_id", "x", "y", "z")
                )
            ):
                return False
            entry[2]["territory_stat_bonuses"] = dict(bonuses)
            entry[2]["_published_territory_stat_bonuses"] = dict(bonuses)
            return True

    def ecology_snapshot(self):
        """Copy only scalar occupancy authority, without inventory/build graphs."""
        keys = ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        with self.lock:
            return [
                dict(
                    {key: character[key] for key in keys},
                    presence_generation=self._presence_generation[
                        self.location(character)
                    ],
                )
                for generation, _, character in self.players.values()
                if (character["id"], generation) not in self._ecology_inactive
            ]

    def deactivate_ecology(self, character_id, generation):
        """Stop simulation authority immediately without disrupting combat cleanup."""
        with self.lock:
            entry = self.players.get(character_id)
            if entry is None or entry[0] != generation:
                return False
            self._ecology_inactive.add((character_id, generation))
            location = self.location(entry[2])
            if not any(
                self.location(other) == location
                and (other["id"], lease) not in self._ecology_inactive
                for lease, _, other in self.players.values()
            ):
                self._presence_generation.pop(location, None)
            return True

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

    def _send_batch(self, peer, packets):
        try:
            if self.deliver_batch is None:
                for opcode, body in packets:
                    self.deliver(peer, opcode, body)
            else:
                self.deliver_batch(peer, packets)
            return True
        except OSError as error:
            if self.delivery_failure is not None:
                try:
                    self.delivery_failure(
                        peer, packets[0][0] if packets else None, error
                    )
                except Exception:
                    pass
            try:
                peer.shutdown(2)
            except OSError:
                pass
            return False

    def live_identity(self, *, character_id=None, name=None):
        """Capture an identity and lease, without exposing its socket."""
        from copy import deepcopy

        with self.lock:
            entry = (
                self.players.get(character_id)
                if character_id is not None
                else next(
                    (
                        entry
                        for entry in self.players.values()
                        if entry[2]["name"].casefold() == name.casefold()
                    ),
                    None,
                )
            )
            return None if entry is None else (entry[0], deepcopy(entry[2]))

    def set_guild_projection(self, character_id, generation, model, factor):
        """Update social fields for future spawns without replacing combat data."""
        from copy import deepcopy

        with self.lock:
            entry = self.players.get(character_id)
            if entry is None or entry[0] != generation:
                return False
            character = dict(entry[2])
            character["guild_native"] = deepcopy(model)
            character["guild_moderation_factor"] = factor
            self.players[character_id] = (entry[0], entry[1], character)
            return True

    def guild_projection(self, character_id, generation):
        from copy import deepcopy

        with self.lock:
            entry = self.players.get(character_id)
            if entry is None or entry[0] != generation:
                return {}
            return {
                key: deepcopy(entry[2][key])
                for key in ("guild_native", "guild_moderation_factor")
                if key in entry[2]
            }

    def send_to(self, character_id, generation, opcode, body):
        """Send across maps to a captured lease; never redirect to its replacement.

        Socket writes happen outside the world membership lock. A disconnect
        after capture may fail delivery to the old peer, never the new one.
        """
        with self.lock:
            entry = self.players.get(character_id)
            if entry is None or entry[0] != generation:
                return False
            peer = entry[1]
        return self._send(peer, opcode, body)

    def send_batch_to(self, character_id, generation, packets):
        """Deliver a captured lease's ordered packet batch as one write."""
        with self.lock:
            entry = self.players.get(character_id)
            if entry is None or entry[0] != generation:
                return False
            peer = entry[1]
        return self._send_batch(peer, tuple(packets))

    def private_chat(
        self,
        generation,
        sender_id,
        account_id,
        recipient,
        text,
        *,
        valid_session,
        block_reason=None,
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
        # Social policy may query PostgreSQL. Keep it outside the membership
        # lock, and evaluate against the captured account identities only.
        if block_reason is not None:
            reason = block_reason(account_id, target[2]["account_id"])
            if reason is not None:
                self._send(sender[1], 349, wire.private_chat_error(reason, recipient))
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
            location = self.location(character)
            self._ecology_inactive.discard((character["id"], generation))
            if location not in self._presence_generation:
                self._presence_sequence += 1
                self._presence_generation[location] = self._presence_sequence
            entry = (generation, peer, dict(character))
            for _, other_peer, other in self.players.values():
                if self.location(other) == self.location(character):
                    self._send(peer, 12608, self.spawn(other))
                    for opcode, body in self.state_packets(other):
                        self._send(peer, opcode, body)
                    self._send(other_peer, 12608, self.spawn(character))
                    for opcode, body in self.state_packets(character):
                        self._send(other_peer, opcode, body)
            self.players[character["id"]] = entry
            for opcode, body in self.state_packets(character):
                self._send(peer, opcode, body)

    def resynchronize(self, generation, peer, character):
        """Restore this loaded client's current visible actors and retained state.

        Unlike `join`, this is directed only to the current peer: it must not
        announce a second player arrival to the other occupants of the map.
        The native client may clear its world view while leaving an external
        fight, so this rebuilds the same current snapshot that `join` sends to
        a newly loaded client.
        """
        from copy import deepcopy

        with self.lock:
            own = self.players.get(character["id"])
            if (
                own is None
                or own[0] != generation
                or own[1] is not peer
                or self.location(own[2]) != self.location(character)
            ):
                raise ValueError("World resynchronization session is stale")
            location = self.location(character)
            others = tuple(
                (other_peer, deepcopy(other))
                for _, other_peer, other in self.players.values()
                if other["id"] != character["id"] and self.location(other) == location
            )
            own_state = tuple(self.state_packets(character))

        for _, other in others:
            if not self._send(peer, 12608, self.spawn(other)):
                return False
            for opcode, body in self.state_packets(other):
                if not self._send(peer, opcode, body):
                    return False
        for opcode, body in own_state:
            if not self._send(peer, opcode, body):
                return False
        return True

    def leave(self, character_id, generation):
        with self.lock:
            existing = self.players.get(character_id)
            if not existing or existing[0] != generation:
                return False
            self.deactivate_ecology(character_id, generation)
            self.players.pop(character_id)
            self._ecology_inactive.discard((character_id, generation))
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

    def refresh_location(self, generation, character):
        """Publish canonical owner coordinates without sending a synthetic walk."""
        from .planting_location import _validate_location

        _validate_location(character)
        direction = character.get("direction")
        if type(direction) is not int or not 0 <= direction <= 7:
            raise ValueError("Invalid owned world direction")
        with self.lock:
            existing = self.players.get(character["id"])
            if (
                existing is None
                or existing[0] != generation
                or existing[2]["account_id"] != character["account_id"]
            ):
                raise ValueError("Character is no longer in this world session")
            if self.location(character) != self.location(existing[2]):
                raise ValueError("Map transition requires leave/join")
            updated = dict(existing[2])
            updated.update(
                {
                    key: character[key]
                    for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                }
            )
            self.players[character["id"]] = (generation, existing[1], updated)

    def publish_ecology(self, character):
        """Publish committed ecology to the current session, wherever it is.

        Preserve its current location and reject older revisions from delayed
        asynchronous world births. Offline characters restore on next join.
        """
        from wakfu_server.personal_ecology import packet

        payload = packet(character["id"], character["ecology_value"])
        revision = character["ecology_revision"]
        if type(revision) is not int or revision < 0:
            raise ValueError("Invalid ecology revision")
        with self.lock:
            current = self.players.get(character["id"])
            if current is None:
                return False
            if revision < current[2].get("ecology_revision", 0):
                return False
            updated = dict(
                current[2],
                ecology_value=character["ecology_value"],
                ecology_revision=revision,
            )
            self.players[character["id"]] = (current[0], current[1], updated)
            self.broadcast(current[0], character["id"], *payload)
            return True

    def information(self, character_id, text):
        """Private game-log feedback for the currently loaded actor."""
        from wakfu_server.ecology_feedback import information

        message = information(text)
        with self.lock:
            current = self.players.get(character_id)
            return False if current is None else self._send(current[1], *message)

    def information_all(self, text):
        """Deliver an informational game-log entry to a snapshot of all peers.

        Copy sockets while membership is locked, then write after releasing the
        lock so a slow connection cannot stall joins, leaves, or world updates.
        """
        from wakfu_server.ecology_feedback import information

        message = information(text)
        with self.lock:
            peers = [peer for _, peer, _ in self.players.values()]
        delivered = 0
        for peer in peers:
            if self._send(peer, *message):
                delivered += 1
        return delivered

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
        self,
        map_id,
        instance_id,
        opcode,
        body,
        *,
        exclude_generation=None,
        exclude_sessions=(),
    ):
        """Broadcast a location event without requiring a player sender."""
        exclude_sessions = frozenset(exclude_sessions)
        with self.lock:
            for generation, peer, character in self.players.values():
                if (
                    generation != exclude_generation
                    and (character["id"], generation) not in exclude_sessions
                    and self.location(character) == (map_id, instance_id)
                ):
                    self._send(peer, opcode, body)

    def emit_location_batch(
        self,
        map_id,
        instance_id,
        packets,
        *,
        exclude_generation=None,
        exclude_sessions=(),
        require_all=False,
    ):
        """Capture location peers, then deliver each ordered batch in one write.

        Identity/generation exclusions have the same meaning as emit_location.
        Captured sockets are never redirected to replacement leases. A failed
        peer cannot prevent delivery to the other captured recipients.
        Strict outbox callers raise after all sends if any recipient failed;
        they retain their durable publication retry rather than acknowledging it.
        """
        packets = tuple(packets)
        if not packets:
            return 0
        exclude_sessions = frozenset(exclude_sessions)
        with self.lock:
            peers = tuple(
                peer
                for generation, peer, character in self.players.values()
                if generation != exclude_generation
                and (character["id"], generation) not in exclude_sessions
                and self.location(character) == (map_id, instance_id)
            )
        delivered = sum(self._send_batch(peer, packets) for peer in peers)
        if require_all and delivered != len(peers):
            raise OSError("World location batch has unpublished recipients")
        return delivered
