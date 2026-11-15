"""Socket and character projections for the native Rust world authority."""

from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from copy import deepcopy
import threading
from weakref import WeakValueDictionary

from wakfu_server.spatial_native import NativeSpatial

_SPATIAL_FIELDS = ("map_id", "instance_id", "x", "y", "z", "direction")


class WorldBatchDeliveryDeferred(OSError):
    """A captured broadcast was partial; its durable publisher must retry."""

    def __init__(self, *, delivered, expected):
        self.delivered = delivered
        self.expected = expected
        super().__init__("World location batch has unpublished recipients")


class _Players(Mapping):
    """Read projections of native membership; never a Python membership store."""

    def __init__(self, world):
        self.world = world

    def __getitem__(self, character_id):
        with self.world.lock:
            row = self.world.native.call("world.get", id=character_id)
            if row is None:
                raise KeyError(character_id)
            return self.world._entry(row)

    def __iter__(self):
        with self.world.lock:
            return iter(
                tuple(
                    row["character_id"] for row in self.world.native.call("world.list")
                )
            )

    def __len__(self):
        return len(self.world.native.call("world.list"))

    def values(self):
        return self.world.captured_players()

    def items(self):
        return tuple((entry[2]["id"], entry) for entry in self.values())


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
        own_state_packets=None,
        refresh_state_packets=None,
        native=None,
    ):
        self.native = native if native is not None else NativeSpatial()
        # This lock protects only Python bindings and projection replacement.
        # Native scope reservations are acquired before it; socket writes and
        # database work never run inside this lock in the adapter.
        self.lock = threading.RLock()
        self.players = _Players(self)
        self._peers = {}
        self._peer_bindings = {}
        self._pending_output = {}
        self._write_gates = WeakValueDictionary()
        self._draining = set()
        self._lifecycle_locks = WeakValueDictionary()
        self.spawn = spawn
        self.remove = remove
        self.deliver = deliver
        self.deliver_batch = deliver_batch
        self.delivery_failure = delivery_failure
        self.state_packets = state_packets or (lambda character: ())
        self.own_state_packets = own_state_packets or self.state_packets
        self.refresh_state_packets = refresh_state_packets

    @staticmethod
    def location(character):
        return character["map_id"], character["instance_id"]

    @staticmethod
    def _owner(row):
        return row["account_id"], row["generation"], row["character_id"]

    @staticmethod
    def _scalars(character):
        return {key: character[key] for key in ("id", "account_id", *_SPATIAL_FIELDS)}

    def _character(self, row):
        character = dict(self.native.character(self._owner(row), domain="world"))
        character.update(
            id=row["character_id"],
            account_id=row["account_id"],
            **{key: row[key] for key in _SPATIAL_FIELDS},
        )
        return character

    def _entry(self, row):
        return row["generation"], self._peers[row["binding_id"]], self._character(row)

    def _entries(self, rows):
        return tuple(self._entry(row) for row in rows)

    def _actor_lock(self, character_id):
        with self.lock:
            lock = self._lifecycle_locks.get(character_id)
            if lock is None:
                lock = threading.RLock()
                self._lifecycle_locks[character_id] = lock
            return lock

    @contextmanager
    def scope_barrier(self, map_id, instance_id):
        reservation = self.native.call(
            "world.scope_acquire", map_id=map_id, instance_id=instance_id
        )
        try:
            yield
        finally:
            self.native.call("world.scope_release", token=reservation["token"])

    @contextmanager
    def _actor_scopes(self, character_id, character=None):
        row = self.native.call("world.get", id=character_id)
        scopes = set()
        if row is not None:
            scopes.add((row["map_id"], row["instance_id"]))
        if character is not None:
            scopes.add(self.location(character))
        reservations = []
        try:
            for map_id, instance_id in sorted(scopes):
                reservations.append(
                    self.native.call(
                        "world.scope_acquire", map_id=map_id, instance_id=instance_id
                    )["token"]
                )
            yield
        finally:
            for token in reversed(reservations):
                self.native.call("world.scope_release", token=token)

    def captured_players(self):
        with self.lock:
            return self._entries(self.native.call("world.list"))

    def snapshot(self):
        """Detached character-domain projections with native spatial fields."""
        with self.lock:
            result = []
            for row in self.native.call("world.list"):
                character = deepcopy(self._character(row))
                if not row["ecology_active"]:
                    character["_ecology_active"] = False
                result.append(character)
            return result

    def owned_location(self, character_id, generation=None, *, ecology_active=False):
        request = dict(id=character_id, generation=generation)
        if ecology_active:
            request["ecology_active"] = True
        row = self.native.call("world.get", **request)
        if row is None:
            return None
        return dict(
            id=row["character_id"],
            account_id=row["account_id"],
            generation=row["generation"],
            **{key: row[key] for key in _SPATIAL_FIELDS},
        )

    def ecology_snapshot(self, map_id=None, instance_id=None):
        return self.native.call(
            "world.ecology_snapshot", map_id=map_id, instance_id=instance_id
        )

    def registered_scope_snapshot(self, map_id, instance_id):
        return self.native.call(
            "world.registered_scope_snapshot", map_id=map_id, instance_id=instance_id
        )

    def scope_presence(self, map_id, instance_id):
        return self.native.call(
            "world.scope_presence", map_id=map_id, instance_id=instance_id
        )

    def try_scope_positions(self, map_id, instance_id, presence_generation):
        result = self.native.call(
            "world.try_scope_positions",
            map_id=map_id,
            instance_id=instance_id,
            presence_generation=presence_generation,
        )
        return None if result is None else tuple(tuple(point) for point in result)

    def empty_scope_generation(self, map_id, instance_id):
        return self.native.call(
            "world.empty_scope_generation", map_id=map_id, instance_id=instance_id
        )

    def empty_scope_snapshot(self):
        return self.native.call("world.empty_scope_snapshot")

    def deactivate_ecology(self, character_id, generation):
        with self._actor_lock(character_id), self._actor_scopes(character_id):
            return self.native.call(
                "world.deactivate_ecology", id=character_id, generation=generation
            )

    def _capture(self, map_id, instance_id, **filters):
        # Callers hold the metadata lock only for capture/materialization.
        return self._entries(
            self.native.call(
                "world.capture", map_id=map_id, instance_id=instance_id, **filters
            )
        )

    def _get(self, character_id, generation=None, peer=None):
        request = dict(id=character_id, generation=generation)
        if peer is not None:
            request["peer_id"] = id(peer)
        row = self.native.call("world.get", **request)
        return None if row is None else (row, self._entry(row))

    def _write_gate(self, peer, *, routing=False):
        gate = getattr(peer, "write_lock", None)
        if gate is not None:
            return gate
        with self.lock:
            if (
                routing
                and id(peer) not in self._draining
                and not any(
                    binding in self._pending_output
                    for binding in self._peer_bindings.get(id(peer), ())
                )
            ):
                return nullcontext()
            gate = self._write_gates.get(id(peer))
            if gate is None:
                gate = threading.RLock()
                self._write_gates[id(peer)] = gate
            return gate

    def _bind_peer(self, row, peer):
        binding = row["binding_id"]
        self._peers[binding] = peer
        self._peer_bindings.setdefault(id(peer), set()).add(binding)
        self._pending_output[binding] = [[], 0, False]

    def _unbind_peer(self, row):
        binding = row["binding_id"]
        peer = self._peers.pop(binding, None)
        self._pending_output.pop(binding, None)
        if peer is not None:
            bindings = self._peer_bindings[id(peer)]
            bindings.discard(binding)
            if not bindings:
                del self._peer_bindings[id(peer)]

    def _write_batch(self, peer, packets, *, single=False):
        """Write with the caller's socket gate held and no world lock."""
        try:
            if single or self.deliver_batch is None:
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

    def _route_batch(self, peer, packets, *, queued_is_success=False, single=False):
        # The native phase is checked inside the same socket gate used by
        # commit/drain. A capture made before commit cannot overtake its replay.
        with self._write_gate(peer, routing=True):
            with self.lock:
                for binding in tuple(self._peer_bindings.get(id(peer), ())):
                    row = self.native.call("world.delivery_state", binding_id=binding)
                    if row is None or not row["pending"]:
                        continue
                    queue = self._pending_output[binding]
                    size = sum(len(body) for _, body in packets)
                    if queue[2] or len(queue[0]) >= 4096 or queue[1] + size > 4194304:
                        queue[0].clear()
                        queue[1] = 0
                        queue[2] = True
                        return False
                    queue[0].append((packets, single))
                    queue[1] += size
                    # Durable publishers must not acknowledge queued packets.
                    return queued_is_success
            return self._write_batch(peer, packets, single=single)

    def _send(self, peer, opcode, body):
        return self._route_batch(
            peer, ((opcode, body),), queued_is_success=True, single=True
        )

    def _send_batch(self, peer, packets):
        return self._route_batch(peer, tuple(packets))

    def _send_direct(self, peer, opcode, body):
        with self._write_gate(peer):
            return self._write_batch(peer, ((opcode, body),), single=True)

    def live_identity(self, *, character_id=None, name=None):
        with self.lock:
            if character_id is not None:
                found = self._get(character_id)
                entry = None if found is None else found[1]
            else:
                entry = next(
                    (
                        entry
                        for entry in self.captured_players()
                        if entry[2]["name"].casefold() == name.casefold()
                    ),
                    None,
                )
            return None if entry is None else (entry[0], deepcopy(entry[2]))

    def refresh_projection(self, generation, character, *, peer=None):
        """Replace only character-domain metadata for an exact native owner."""
        with self.lock:
            request = dict(
                id=character["id"],
                generation=generation,
                account_id=character["account_id"],
                position={key: character[key] for key in _SPATIAL_FIELDS},
            )
            if peer is not None:
                request["peer_id"] = id(peer)
            if not self.native.call("world.matches", **request):
                return False
            row = self.native.call("world.get", id=character["id"])
            self.native.bind_character(self._owner(row), character, domain="world")
            return True

    def update_territory_projection(
        self, generation, character, *, peer, bonuses, regional_state_id=None
    ):
        if regional_state_id is not None and (
            type(regional_state_id) is not int
            or regional_state_id not in (1915, 1916, 1917)
        ):
            raise ValueError("Invalid native regional state projection")
        with self.lock:
            if not self.native.call(
                "world.matches",
                id=character["id"],
                generation=generation,
                peer_id=id(peer),
                position={key: character.get(key) for key in _SPATIAL_FIELDS[:-1]},
            ):
                return False
            row = self.native.call("world.get", id=character["id"])
            projection = self.native.character(self._owner(row), domain="world")
            projection["territory_stat_bonuses"] = dict(bonuses)
            projection["_published_territory_stat_bonuses"] = dict(bonuses)
            projection["territory_state_id"] = regional_state_id
            projection["_published_territory_state_id"] = regional_state_id
            for key in (
                "hp",
                "max_hp",
                "hp_damage",
                "health_dead",
                "hp_zero_valid",
                "territory_health_projection",
                "equipment_hp_projection",
            ):
                if key in character:
                    projection[key] = character[key]
            return True

    def set_guild_projection(
        self, character_id, generation, model, factor, *, member_bonus_records=None
    ):
        with self.lock:
            found = self._get(character_id, generation)
            if found is None:
                return False
            projection = self.native.character(self._owner(found[0]), domain="world")
            projection["guild_native"] = deepcopy(model)
            projection["guild_moderation_factor"] = factor
            projection["guild_member_bonus_records"] = deepcopy(
                {} if member_bonus_records is None else member_bonus_records
            )
            return True

    def guild_projection(self, character_id, generation):
        with self.lock:
            found = self._get(character_id, generation)
            if found is None:
                return {}
            return {
                key: deepcopy(found[1][2][key])
                for key in (
                    "guild_native",
                    "guild_moderation_factor",
                    "guild_member_bonus_records",
                )
                if key in found[1][2]
            }

    def send_to(self, character_id, generation, opcode, body):
        with self.lock:
            found = self._get(character_id, generation)
            peer = None if found is None else found[1][1]
        return False if found is None else self._send(peer, opcode, body)

    def send_batch_to(self, character_id, generation, packets):
        with self.lock:
            found = self._get(character_id, generation)
            peer = None if found is None else found[1][1]
        return False if found is None else self._send_batch(peer, tuple(packets))

    def send_to_if_location(
        self, character_id, generation, expected_location, opcode, body, *, peer=None
    ):
        return self.send_batch_to_if_location(
            character_id, generation, expected_location, ((opcode, body),), peer=peer
        )

    def send_batch_to_if_location(
        self, character_id, generation, expected_location, packets, *, peer=None
    ):
        with self.lock:
            found = self._get(character_id, generation, peer)
            if found is None:
                return False
            captured = found[1][1]
        with getattr(captured, "write_lock", nullcontext()):
            if not self.native.call(
                "world.matches",
                id=character_id,
                generation=generation,
                peer_id=id(captured),
                position=dict(expected_location),
            ):
                return False
            return self._send_batch(captured, tuple(packets))

    def request_ranch_scene_refresh(
        self, map_id, instance_id, *, exclude_generation=None
    ):
        with self.scope_barrier(map_id, instance_id), self.lock:
            plans = self.native.call(
                "world.ranch_refresh",
                map_id=map_id,
                instance_id=instance_id,
                exclude_generation=exclude_generation,
            )
            captured = tuple((self._entry(plan["row"])[1], plan) for plan in plans)
        queued = 0
        for peer, plan in captured:
            row = plan["row"]
            try:
                peer.ranch_scene_refresh = (
                    row["character_id"],
                    row["generation"],
                    row["map_id"],
                    row["instance_id"],
                    plan["nonce"],
                )
            except (AttributeError, TypeError):
                continue
            queued += 1
        return queued

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
                    for entry in self.captured_players()
                    if entry[2]["name"].casefold() == recipient.casefold()
                ),
                None,
            )
        if sender is None or sender[0] != generation:
            raise ValueError("Private chat sender session is stale")
        if sender[2]["account_id"] != account_id:
            raise ValueError("Private chat account identity disagrees")
        if not valid_session(sender):
            raise ValueError("Private chat sender session is stale")
        target_valid = target is not None and valid_session(target)
        with self.lock:
            if not self.native.call(
                "world.matches",
                id=sender_id,
                generation=sender[0],
                peer_id=id(sender[1]),
            ):
                raise ValueError("Private chat sender session is stale")
            if target_valid:
                target_valid = self.native.call(
                    "world.matches",
                    id=target[2]["id"],
                    generation=target[0],
                    peer_id=id(target[1]),
                )
        if not target_valid:
            self._send(sender[1], 349, wire.private_chat_error(101, recipient))
            return False
        if target[2]["id"] == sender_id:
            self._send(sender[1], 349, wire.private_chat_error(104))
            return False
        if block_reason is not None:
            reason = block_reason(account_id, target[2]["account_id"])
            if reason is not None:
                self._send(sender[1], 349, wire.private_chat_error(reason, recipient))
                return False
        payload = wire.private_chat(account_id, sender[2], target[2], text)
        if not self._send(target[1], 720, payload):
            self._send(sender[1], 349, wire.private_chat_error(140))
            return False
        return self._send(sender[1], 720, payload)

    def join(self, generation, peer, character):
        identity = character["id"]
        with self._actor_lock(identity):
            with self._actor_scopes(identity, character), self.lock:
                prepared = self.native.call(
                    "world.join_prepare",
                    generation=generation,
                    peer_id=id(peer),
                    character=self._scalars(character),
                )
                previous = prepared.get("previous")
                previous_entry = None if previous is None else self._entry(previous)
                departed = self._entries(prepared.get("leave_recipients", ()))
                row = prepared["row"]
                self.native.bind_character(self._owner(row), character, domain="world")
                self._bind_peer(row, peer)
                if previous is not None:
                    self._unbind_peer(previous)
                    if self._owner(previous) != self._owner(row):
                        self.native.release_character(self._owner(previous), "world")
                ready = self.native.call("world.join_ready", token=prepared["token"])
                others = self._entries(ready["others"])
            try:
                if previous_entry is not None:
                    for _, old_peer, _ in departed:
                        self._send(old_peer, 12304, self.remove(identity))
                for _, other_peer, other in others:
                    if not self._send_direct(peer, 12608, self.spawn(other)):
                        raise OSError("World bootstrap delivery failed")
                    for opcode, body in self.state_packets(other):
                        if not self._send_direct(peer, opcode, body):
                            raise OSError("World bootstrap delivery failed")
                    self._send(other_peer, 12608, self.spawn(character))
                    for opcode, body in self.state_packets(character):
                        self._send(other_peer, opcode, body)
                with self._write_gate(peer):
                    with self._actor_scopes(identity, character), self.lock:
                        queue = self._pending_output[row["binding_id"]]
                        if queue[2]:
                            raise OSError("World bootstrap replay exceeded its buffer")
                        self._draining.add(id(peer))
                        self.native.call("world.join_commit", token=prepared["token"])
                        batches = self._pending_output.pop(row["binding_id"])[0]
                    try:
                        for packets, single in batches:
                            if not self._write_batch(peer, packets, single=single):
                                raise OSError("World bootstrap replay delivery failed")
                        for opcode, body in self.own_state_packets(character):
                            if not self._write_batch(
                                peer, ((opcode, body),), single=True
                            ):
                                raise OSError("World own-state delivery failed")
                    finally:
                        with self.lock:
                            self._draining.discard(id(peer))
            except BaseException:
                with self._actor_scopes(identity, character), self.lock:
                    aborted = self.native.call(
                        "world.join_abort", token=prepared["token"]
                    )
                    removed = aborted.get("removed")
                    recipients = self._entries(aborted.get("recipients", ()))
                    if removed is None:
                        # A socket failure after commit still withdraws the actor.
                        aborted = self.native.call(
                            "world.leave", id=identity, generation=generation
                        )
                        removed = aborted["removed"]
                        recipients = self._entries(aborted["recipients"])
                    self._unbind_peer(row)
                    self.native.release_character(self._owner(row), "world")
                if removed is not None:
                    for _, other_peer, _ in recipients:
                        self._send(other_peer, 12304, self.remove(identity))
                raise

    def resynchronize(self, generation, peer, character):
        with self.lock:
            if not self.native.call(
                "world.matches",
                id=character["id"],
                generation=generation,
                peer_id=id(peer),
                position={key: character[key] for key in ("map_id", "instance_id")},
            ):
                raise ValueError("World resynchronization session is stale")
            others = tuple(
                deepcopy(entry[2])
                for entry in self._capture(
                    *self.location(character), exclude_character_id=character["id"]
                )
            )
        own_state = tuple(self.own_state_packets(character))
        for other in others:
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
        with self._actor_lock(character_id), self._actor_scopes(
            character_id
        ), self.lock:
            result = self.native.call(
                "world.leave", id=character_id, generation=generation
            )
            row = result["removed"]
            if row is None:
                return False
            recipients = self._entries(result["recipients"])
            self._unbind_peer(row)
            self.native.release_character(self._owner(row), "world")
        for _, peer, _ in recipients:
            self._send(peer, 12304, self.remove(character_id))
        return True

    def update(self, generation, character, opcode, body, *, include_sender=True):
        refresh_states = ()
        if self.refresh_state_packets is not None and opcode in (15548, 13713):
            from .planting_bonus_publisher import reset_actor

            if reset_actor(opcode, body) == character["id"]:
                refresh_states = tuple(self.refresh_state_packets(character))
        with self._actor_lock(character["id"]), self._actor_scopes(
            character["id"], character
        ), self.lock:
            row = self.native.call(
                "world.update",
                id=character["id"],
                generation=generation,
                character=self._scalars(character),
            )
            self.native.bind_character(self._owner(row), character, domain="world")
            recipients = self._capture(
                *self.location(character),
                exclude_character_id=None if include_sender else character["id"],
            )
        if refresh_states:
            packets = ((opcode, body), *refresh_states)
            for _, peer, _ in recipients:
                self._send_batch(peer, packets)
        else:
            for _, peer, _ in recipients:
                self._send(peer, opcode, body)

    def refresh_location(self, generation, character):
        with self._actor_lock(character["id"]), self._actor_scopes(
            character["id"], character
        ), self.lock:
            self.native.call(
                "world.update",
                id=character["id"],
                generation=generation,
                account_id=character["account_id"],
                character=self._scalars(character),
            )
            # Location refresh deliberately preserves all nonspatial projections.
            return None

    def publish_ecology(self, character):
        from wakfu_server.personal_ecology import packet

        payload = packet(character["id"], character["ecology_value"])
        revision = character["ecology_revision"]
        if type(revision) is not int or revision < 0:
            raise ValueError("Invalid ecology revision")
        with self.lock:
            current = self._get(character["id"])
            if current is None or revision < current[1][2].get("ecology_revision", 0):
                return False
            projection = self.native.character(self._owner(current[0]), domain="world")
            projection["ecology_value"] = character["ecology_value"]
            projection["ecology_revision"] = revision
            recipients = self._capture(current[0]["map_id"], current[0]["instance_id"])
        for _, peer, _ in recipients:
            self._send(peer, *payload)
        return True

    def information(self, character_id, text):
        from wakfu_server.ecology_feedback import information

        message = information(text)
        with self.lock:
            current = self._get(character_id)
            peer = None if current is None else current[1][1]
        return False if current is None else self._send(peer, *message)

    def information_all(self, text):
        from wakfu_server.ecology_feedback import information

        message = information(text)
        with self.lock:
            peers = tuple(entry[1] for entry in self.captured_players())
        return sum(self._send(peer, *message) for peer in peers)

    def broadcast(self, generation, character_id, opcode, body, *, include_sender=True):
        with self.lock:
            current = self._get(character_id, generation)
            if current is None:
                raise ValueError("Character is no longer in this world session")
            peers = tuple(
                entry[1]
                for entry in self._capture(
                    current[0]["map_id"],
                    current[0]["instance_id"],
                    exclude_character_id=None if include_sender else character_id,
                )
            )
        for peer in peers:
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
        only_character_id=None,
    ):
        with self.lock:
            peers = tuple(
                entry[1]
                for entry in self._capture(
                    map_id,
                    instance_id,
                    exclude_generation=exclude_generation,
                    exclude_sessions=list(exclude_sessions),
                    only_character_id=only_character_id,
                )
            )
        for peer in peers:
            self._send(peer, opcode, body)

    def emit_location_batch(
        self,
        map_id,
        instance_id,
        packets,
        *,
        exclude_generation=None,
        exclude_sessions=(),
        exclude_character_id=None,
        require_all=False,
    ):
        packets = tuple(packets)
        if not packets:
            return 0
        with self.lock:
            peers = tuple(
                entry[1]
                for entry in self._capture(
                    map_id,
                    instance_id,
                    exclude_generation=exclude_generation,
                    exclude_sessions=list(exclude_sessions),
                    exclude_character_id=exclude_character_id,
                )
            )
        delivered = sum(self._send_batch(peer, packets) for peer in peers)
        if require_all and delivered != len(peers):
            raise WorldBatchDeliveryDeferred(delivered=delivered, expected=len(peers))
        return delivered
