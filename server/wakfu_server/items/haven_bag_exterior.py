"""Native bAT/cwG exterior bags and lease-scoped visitor discovery.

bAU section 3 stores world/position then ua owner identity; ama.L packs position.
These layouts are verified against the shipped client and reference cwG capture.
"""
from copy import deepcopy
import struct
import threading

from .haven_bag_store import instance_id


def entity_id(character):
    return -(1 << 60) - instance_id(character)


def spawn(character):
    name = character["name"].encode("utf-8")
    if len(name) > 255:
        raise ValueError("Haven Bag owner name is too long")
    x, y, z = (character[k] for k in ("x", "y", "z"))
    if not (-131072 <= x <= 131071 and -131072 <= y <= 131071 and -512 <= z <= 511):
        raise ValueError("Haven Bag exterior position is out of range")
    config = character.get("haven_bag") or {}
    # ua account, actor, name, guild, appearance, empty display lists.
    owner = (
        struct.pack(">qqB", character["account_id"], character["id"], len(name)) + name
    )
    owner += struct.pack(
        ">qiBB",
        (character.get("guild_native") or {}).get("guildId", 0),
        config.get("appearance_id", 408),
        0,
        0,
    )
    common = bytes.fromhex("02000301010000000000000000")
    specific = (
        b"\x03" + struct.pack(">qiihBB", character["map_id"], x, y, z, 0, 0) + owner
    )
    blob = struct.pack(">BBiBi", 2, 2, 11, 3, 11 + len(common)) + common + specific
    packed = (
        ((x + 131071) & 262143) << 28
        | ((y + 131071) & 262143) << 10
        | ((z + 511) & 1023)
    )
    body = (
        struct.pack(">HqqH", 1, entity_id(character), 3700, len(blob))
        + blob
        + struct.pack(">q", packed)
    )
    return 13664, body


def remove(character):
    return 13082, struct.pack(">Hq", 1, entity_id(character))


def can_visit(visitor, owner):
    """All players may visit; discovery still checks live map and distance.

    Room masks grant traversal/use only. Inventory, room configuration and
    furniture mutations retain their separate account ownership checks.
    """
    return True


class ExteriorBags:
    """Bags exist while their owner's current connection occupies its interior."""

    def __init__(self):
        self.lock = threading.RLock()
        self.entries = {}

    def publish(self, generation, character):
        with self.lock:
            self.entries[character["id"]] = generation, deepcopy(character)
        return spawn(character)

    def discard(self, generation, character_id):
        with self.lock:
            entry = self.entries.get(character_id)
            if entry is None or entry[0] != generation:
                return None
            del self.entries[character_id]
        return entry[1], remove(entry[1])

    def snapshots(self, character):
        with self.lock:
            return [
                spawn(owner)
                for _, owner in self.entries.values()
                if (owner["map_id"], owner["instance_id"])
                == (character["map_id"], character["instance_id"])
            ]

    def resolve(self, visitor, target_id):
        with self.lock:
            entry = self.entries.get(target_id)
            if entry is None:
                raise ValueError("Haven Bag owner is unavailable")
            owner = deepcopy(entry[1])
        if (owner["map_id"], owner["instance_id"]) != (
            visitor["map_id"],
            visitor["instance_id"],
        ):
            raise ValueError("Haven Bag is in another world")
        if (
            abs(owner["x"] - visitor["x"]) + abs(owner["y"] - visitor["y"]) > 6
            or owner["z"] != visitor["z"]
        ):
            raise ValueError("Move closer to the Haven Bag")
        return owner
