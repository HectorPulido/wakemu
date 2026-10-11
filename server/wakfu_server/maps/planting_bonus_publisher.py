"""Connection-owned native profession modifier delivery without repeat stacking."""
import threading
import weakref

from wakfu_server.planting_bonus_wire import publication


class Publisher:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.baselines = weakref.WeakKeyDictionary()
        # Separate namespaces from combat runner IDs and script action IDs.
        self.uid = 0x504C000000000000
        self.action = 0x50000000

    def _uid(self):
        self.uid += 1
        if self.uid >= (1 << 63):
            raise ValueError("Planting native effect identities exhausted")
        return self.uid

    def _action(self):
        self.action += 1
        if self.action >= (1 << 31):
            raise ValueError("Planting native action identities exhausted")
        return self.action

    def reset(self, connection, actor_id):
        """Call only after a verified native actor modifier reset/recreation."""
        with self.lock:
            self.baselines.get(connection, {}).pop(actor_id, None)

    def deliver(self, connection, packets, write):
        """Fence successful reset-frame delivery against concurrent publication."""
        resets = [
            actor_id
            for opcode, body in packets
            for actor_id in reset_actors(opcode, body)
        ]
        if not resets:
            write()
            return
        with self.lock:
            write()
            for actor_id in resets:
                self.reset(connection, actor_id)

    def publish(self, connection, character, deliver):
        """Serialize comparison, delivery and marker commit as one publication.

        A failed write terminates that connection; its marker remains unchanged.
        ``deliver`` must send the entire ordered packet batch or raise.
        """
        with self.lock:
            actors = self.baselines.setdefault(connection, {})
            result = publication(
                self.store,
                character,
                actors.get(character["id"], {}),
                allocate_uid=self._uid,
                allocate_action=self._action,
            )
            if result["packets"]:
                deliver(result["packets"])
            actors[character["id"]] = result["bonuses"]
            return result["bonuses"]


def reset_actor(opcode, body):
    """Identify only verified owned actor reconstruction/runner-clear carriers.

    Account13873, map13974, guild format22 and bags format35 do not clear
    profession modifiers. Combat snapshot envelopes are decoded separately by reset_actors.
    """
    import struct

    if opcode == 12666:
        if len(body) < 2:
            raise ValueError("Truncated native actor initialization")
        count = struct.unpack_from(">H", body)[0]
        offset = 2 + 8 * count
        if len(body) < offset + 4:
            raise ValueError("Truncated native actor initialization block")
        size = struct.unpack_from(">I", body, offset)[0]
        entity = body[offset + 4 : offset + 4 + size]
        if len(entity) != size or size < 9 or entity[0] != 10:
            raise ValueError("Invalid native owned actor initialization")
        return struct.unpack_from(">q", entity, 1)[0]
    if opcode not in (13713, 15548):
        return None
    offset = 8 if opcode == 13713 else 10
    if len(body) <= offset:
        raise ValueError("Truncated native owned actor refresh")
    if opcode == 15548 and struct.unpack_from(">H", body, 8)[0] != len(body) - 10:
        raise ValueError("Invalid native local actor refresh length")
    if body[offset] in (10, 11):
        return struct.unpack_from(">q", body)[0]
    return None


def reset_actors(opcode, body):
    """Combat retains the same native world actor; effect snapshots clear it."""
    if opcode == 13912:
        from wakfu_server.combat_wire import decode_actor_state

        return (decode_actor_state(opcode, body)["actor_id"],)
    if opcode == 12847:
        from wakfu_server.combat_wire import decode_bootstrap

        value = decode_bootstrap(body)
        # Compact participant lists carry no evaluated running-effect snapshot.
        return (
            ()
            if value["compact"]
            else tuple(actor["actor_id"] for actor in value["participants"])
        )
    actor_id = reset_actor(opcode, body)
    return () if actor_id is None else (actor_id,)
