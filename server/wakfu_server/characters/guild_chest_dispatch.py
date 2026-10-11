"""Explicit world access validation for native guild shared storage.

Guild membership alone never grants a remote storage session. Installed guild
storage objects and configured actions must match the current world location.
Haven World storage remains outside this integration.
"""
import struct
import hashlib
import uuid
import time
import threading
import weakref

from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout


_SESSIONS = weakref.WeakSet()
_REGISTRY_LOCK = threading.RLock()
_GUILD_LOCKS = [threading.RLock() for _ in range(256)]


STORAGE_OPCODES = frozenset((12844, 12004, 14616, 12531))


def access_policy(store):
    """Disabled installations do not query unapplied guild chest tables."""
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='guild_policy'"
        ).fetchone()
    policy = row["value"] if row else {}
    chest = policy.get("chest", {})
    if (
        policy.get("enabled") is not True
        or policy.get("native_sync_enabled") is not True
        or chest.get("enabled") is not True
    ):
        raise ValueError("Guild chest is disabled")
    return chest


def validate_access(character, body, objects, access_points, *, blocked=False):
    """Return a detached authorized context, without trusting client position."""
    if blocked or character.get("instance_id", 0) != 0:
        raise ValueError("Guild chest is unavailable in the current activity")
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid guild chest interaction")
    identity, action, parameter = struct.unpack(">qHH", body)
    row = next((row for row in objects if row["id"] == identity), None)
    if row is None or row.get("type") != "GuildStorageBox":
        raise ValueError("Unknown installed guild storage object")
    matches = [
        point
        for point in access_points
        if (
            point.get("map_id") == character["map_id"]
            and point.get("object_id") == identity
            and point.get("action_id") == action
            and point.get("parameter") == parameter
        )
    ]
    if len(matches) != 1:
        raise ValueError("Guild chest access point is not configured")
    point = matches[0]
    distance = point.get("max_distance", 3)
    height = point.get("max_z_distance", 2)
    compartments = point.get("compartment_ids")
    if (
        type(distance) is not int
        or not 0 <= distance <= 3
        or type(height) is not int
        or not 0 <= height <= 2
        or not isinstance(compartments, list)
        or not compartments
        or any(type(value) is not int or not 0 <= value <= 3 for value in compartments)
        or len(set(compartments)) != len(compartments)
    ):
        raise ValueError("Invalid guild chest access configuration")
    if row.get("map_id") != character["map_id"] or (
        max(abs(character["x"] - row["x"]), abs(character["y"] - row["y"])) > distance
        or abs(character["z"] - row["z"]) > height
    ):
        raise ValueError("Guild chest is too far away")
    return dict(
        map_id=character["map_id"],
        object_id=identity,
        action_id=action,
        parameter=parameter,
        compartment_ids=tuple(compartments),
    )


class GuildChestSession:
    """One connection's open context; each request revalidates world access."""

    def __init__(
        self,
        store,
        account,
        generation,
        character,
        body,
        objects,
        *,
        blocked=False,
        world=None,
        objects_for=None,
        blocked_now=None
    ):
        from . import guild_chest

        self.store, self.account, self.generation = store, account, generation
        self.character_id = character["id"]
        self.world, self.objects_for = world, objects_for
        self.blocked_now = blocked_now or (lambda: False)
        self.closed = False
        self.money = 0
        self.money_retry = None
        policy = access_policy(store)
        self.context = validate_access(
            character, body, objects, policy.get("access_points", []), blocked=blocked
        )
        self.body = body
        self.token = uuid.uuid4()
        self.revisions = {}
        self.chests = []
        self.retry = None
        self.move_retry = None
        self.cell_retry = None
        self.refresh()
        self.guild_id = self.chests[0]["guild_id"]
        if world is not None:
            if objects_for is None:
                raise ValueError("Missing authoritative guild chest object resolver")
            with _REGISTRY_LOCK:
                _SESSIONS.add(self)

    def refresh(self):
        from . import guild_chest

        view = guild_chest.snapshot(
            self.store,
            self.account,
            self.generation,
            self.character_id,
            self.context["compartment_ids"],
            expected_guild_id=getattr(self, "guild_id", None),
        )
        if hasattr(self, "guild_id") and view["guild_id"] != self.guild_id:
            raise ValueError("Guild chest membership changed")
        self.chests, self.money = view["chests"], view["money"]
        self.revisions = {chest["id"]: chest["revision"] for chest in self.chests}

    def close(self, *, clear=False):
        with _GUILD_LOCKS[self.guild_id % len(_GUILD_LOCKS)]:
            self._close(clear=clear)

    def _close(self, *, clear=False):
        self.closed = True
        with _REGISTRY_LOCK:
            _SESSIONS.discard(self)
        if clear and self.world is not None:
            from . import guild_chest_wire

            empty = [
                dict(id=chest["id"], capacity=40, enabled=False, items=[])
                for chest in self.chests
            ]
            for packet in (
                guild_chest_wire.bootstrap(empty),
                guild_chest_wire.contents(empty),
            ):
                self.world.send_to(self.character_id, self.generation, *packet)
        self.retry = self.move_retry = self.cell_retry = self.money_retry = None

    @classmethod
    def refresh_guild(cls, guild_id):
        """Publish current views only to still-authorized captured sessions."""
        with _GUILD_LOCKS[guild_id % len(_GUILD_LOCKS)]:
            with _REGISTRY_LOCK:
                viewers = [
                    session for session in _SESSIONS if session.guild_id == guild_id
                ]
            for session in viewers:
                try:
                    live = session.world.live_identity(
                        character_id=session.character_id
                    )
                    if live is None or live[0] != session.generation:
                        session.close()
                        continue
                    character = live[1]
                    session.validate(
                        character,
                        session.objects_for(character["map_id"]),
                        blocked=session.blocked_now(),
                    )
                    session.refresh()
                    for packet in session.packets():
                        if not session.world.send_to(
                            session.character_id, session.generation, *packet
                        ):
                            session.close()
                            break
                except (ValueError, KeyError):
                    session.close(clear=True)
                except (DatabaseError, PoolTimeout):
                    # A failed publication never undoes committed custody. The
                    # next request/open retries a fresh authoritative snapshot.
                    session.close()

    def publish_current(self):
        if self.world is None:
            return self.packets()
        self.refresh_guild(self.guild_id)
        return ()

    def validate(self, character, objects, *, blocked=False):
        if self.closed:
            raise ValueError("Guild chest session is closed")
        if character["id"] != self.character_id:
            raise ValueError("Guild chest actor changed")
        policy = access_policy(self.store)
        current = validate_access(
            character,
            self.body,
            objects,
            policy.get("access_points", []),
            blocked=blocked,
        )
        if current != self.context:
            raise ValueError("Guild chest access changed")

    def packets(self):
        from . import guild_chest_wire

        return (
            guild_chest_wire.bootstrap(self.chests, self.money),
            *(guild_chest_wire.contents([chest]) for chest in self.chests),
            guild_chest_wire.money_packet(self.money),
        )

    def handle(self, opcode, body, character, objects, *, blocked=False):
        with _GUILD_LOCKS[self.guild_id % len(_GUILD_LOCKS)]:
            return self._handle(opcode, body, character, objects, blocked=blocked)

    def _handle(self, opcode, body, character, objects, *, blocked=False):
        from . import guild_chest, guild_wire

        self.validate(character, objects, blocked=blocked)
        request = guild_wire.decode_storage_request(opcode, body)
        compartments = self.context["compartment_ids"]
        requested = (
            (request["source_compartment_id"], request["destination_compartment_id"])
            if opcode == 14616
            else (request["compartment_id"],)
        )
        if any(value not in compartments for value in requested):
            raise ValueError("Guild compartment is outside the open chest")
        digest = hashlib.sha256(struct.pack(">H", opcode) + body).hexdigest()
        retry = (
            self.retry
            if self.retry
            and self.retry[0] == digest
            and time.monotonic() - self.retry[1] <= 3
            else None
        )
        key = (
            retry[2]
            if retry
            else "guild-chest:" + str(self.token) + ":" + str(uuid.uuid4())
        )
        common = (self.store, self.account, self.generation, self.character_id)
        if opcode in (12844, 12004):
            result = {
                "chest": guild_chest.load(
                    *common, request["compartment_id"], expected_guild_id=self.guild_id
                ),
                "applied": False,
            }
        elif opcode == 14616:
            previous = self.move_retry
            if (
                previous
                and previous[0] == digest
                and time.monotonic() - previous[1] <= 3
            ):
                key, revisions = previous[2:]
            else:
                revisions = {value: self.revisions[value] for value in requested}
            self.move_retry = (digest, time.monotonic(), key, revisions)
            result = guild_chest.move(
                *common,
                requested[0],
                request["source_slot"],
                requested[1],
                request["destination_slot"],
                operation_key=key,
                expected_revisions=revisions,
                expected_guild_id=self.guild_id
            )
        elif request.get("operation") in (3, 4):
            previous = self.money_retry
            if (
                previous
                and previous[0] == digest
                and time.monotonic() - previous[1] <= 3
            ):
                key = previous[2]
            self.money_retry = (digest, time.monotonic(), key)
            result = guild_chest.transfer_money(
                *common,
                request["compartment_id"],
                request["amount"],
                withdraw=request["operation"] == 4,
                operation_key=key,
                expected_guild_id=self.guild_id
            )
        elif request.get("operation") == 2:
            previous = self.cell_retry
            compartment = request["compartment_id"]
            if (
                previous
                and previous[0] == digest
                and time.monotonic() - previous[1] <= 3
            ):
                key, source_slot, revisions = previous[2:]
            else:
                source = next(
                    (
                        entry
                        for chest in self.chests
                        if chest["id"] == compartment
                        for entry in chest["items"]
                        if entry["item"]["uid"] == request["item_id"]
                    ),
                    None,
                )
                if source is None:
                    raise ValueError("Guild chest move source changed")
                source_slot = source["slot"]
                revisions = {compartment: self.revisions[compartment]}
            self.cell_retry = (digest, time.monotonic(), key, source_slot, revisions)
            result = guild_chest.move(
                *common,
                compartment,
                source_slot,
                compartment,
                request["slot"],
                operation_key=key,
                expected_revisions=revisions,
                expected_guild_id=self.guild_id
            )
        elif retry is not None:
            planned, deposit, revision = retry[3:]
            result = guild_chest.transfer(
                *common,
                request["compartment_id"],
                [planned],
                deposit=deposit,
                operation_key=key,
                expected_revision=revision,
                expected_guild_id=self.guild_id
            )
        elif request["operation"] in (0, 1):
            deposit = request["operation"] == 0
            planned = dict(
                compartment=request["compartment_id"],
                uid=request["item_id"],
                reference=request["reference"],
                quantity=request["quantity"],
            )
            if deposit:
                planned.update(slot=request["slot"])
            else:
                source = next(
                    (
                        entry
                        for chest in self.chests
                        if chest["id"] == request["compartment_id"]
                        for entry in chest["items"]
                        if entry["item"]["uid"] == request["item_id"]
                    ),
                    None,
                )
                if source is None:
                    raise ValueError("Guild chest withdrawal source changed")
                planned.update(
                    reference=request["reference"],
                    slot=source["slot"],
                    container=request["additional_item_id"],
                    destination=request["slot"],
                )
            revision = self.revisions[request["compartment_id"]]
            self.retry = (digest, time.monotonic(), key, planned, deposit, revision)
            result = guild_chest.transfer(
                *common,
                request["compartment_id"],
                [planned],
                deposit=deposit,
                operation_key=key,
                expected_revision=revision,
                expected_guild_id=self.guild_id
            )
        else:
            raise ValueError("Guild chest operation is not supported")
        # Read one coherent view after commit; watchers receive it under the
        # same per-guild publication lock as subsequent native operations.
        self.refresh()
        if self.world is not None:
            self.refresh_guild(self.guild_id)
            return result, ()
        return result, self.packets()
