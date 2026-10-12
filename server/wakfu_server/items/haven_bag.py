"""Owned empty haven-bag data and verified entry-result encodings.

The interior map transition is separate from these messages; callers must not
report entry complete merely because the entry-result decoder accepts bytes.
"""
import struct


def own_bag(character):
    """pC/tR: a local owner, one commerce room, no furniture or inherited IDs.

    tT/xL uses a byte room index, u16 furniture count and uB discriminator 0.
    uB carries fixed-primary/ref/uid/ref/uid. Reference 4262 is the starting commerce
    gem in the fresh-character capture. tR's model 408 is the standard bag.
    """
    name = character["name"].encode("utf-8")
    if len(name) > 65535:
        raise ValueError("Haven-bag owner name is too long")
    owner, account = character["id"], character["account_id"]
    from wakfu_server.haven_bag_store import initial_layout

    config = character.get("haven_bag") or {
        "appearance_id": 408,
        "rooms": initial_layout(owner),
        "locked": False,
        "access": public_access(),
    }
    from wakfu_server.haven_bag_furniture import encode_vf

    rooms = config["rooms"]
    header = (
        struct.pack(">qqH", account, owner, len(name))
        + name
        + struct.pack(">qhqB", 0, 0, 0, len(rooms))
    )
    room_data = b""
    for room in rooms:
        objects = [
            item
            for item in config.get("furniture", [])
            if item["deployed"] and item["room"] == room["index"]
        ]
        room_data += struct.pack(">BH", room["index"], len(objects))
        for item in objects:
            room_data += encode_vf(
                **{
                    key: value
                    for key, value in item.items()
                    if key not in ("deployed", "room")
                }
            )
        room_data += struct.pack(
            ">BBiqiq",
            0,
            # uB.adK is fvw.tky, the non-removable primary flag, rather
            # than floor occupancy. Setting it for occupied rooms prevents
            # the native client from even sending a gem recovery request.
            room["index"] == 0,
            room["primary_ref"],
            room["primary_uid"] if room["primary_ref"] != -1 else -1,
            room["secondary_ref"],
            room["secondary_uid"] if room["secondary_ref"] != -1 else -1,
        )
    tail = (
        struct.pack(">iB", config["appearance_id"], 0)
        + visit_permission_payload(config)
        + b"\x00"
    )
    return header + room_data + tail


def leave_result():
    # cyU.dp reads byte[0]; the success status is zero. An empty body
    # causes a decoder exception. Separate cyV13019 triggers UI cleanup.
    return b"\x00"


def validate_leave_request(body):
    # crx.aWH() explicitly sends one zero byte; accepting empty supports old
    # test clients without accepting arbitrary trailing data.
    if body not in (b"", b"\x00"):
        raise ValueError("Invalid haven bag leave request")


def entry_result(*, success, own=True, owner=None):
    result = struct.pack(">BBi", bool(success), bool(own), 0)
    if success:
        if not own:
            if owner is None:
                raise ValueError("Foreign bag entry requires a serialized owner")
            return result + own_bag(owner)
        # own bags reuse biB.drc(), allow entry and mark the bag unlocked.
        result += bytes((0, 1))
    return result


def map_transition(template, character, map_id):
    """csW (13974), changing the format-28 POSITION world ID explicitly."""
    from protocol_codec import Reader
    from wakfu_server.wire import identity

    r = Reader(template)
    blocks = [r.take(r.number("H")) for _ in range(4)]
    r.finish()
    block = blocks[0]
    if len(block) != 56 or block[0] != 28:
        raise ValueError("Unexpected map-transition entity layout")
    # eHf format28: ID1:9, IDENTITY9:18, POSITION18:56.
    blocks[0] = (
        block[:18]
        + struct.pack(">iihq", character["x"], character["y"], character["z"], map_id)
        + block[36:]
    )
    # Fight entities/context from the captured exterior do not belong to the
    # destination. csW parses each list as a u16 count.
    from wakfu_server.maps.protector_ecosystem import message_records

    records = message_records(map_id)
    blocks[1] = struct.pack(">H", len(records)) + b"".join(
        struct.pack(">H", len(record)) + record for record in records
    )
    blocks[2] = b"\x00\x00"
    blocks = [identity(block, character["account_id"], character) for block in blocks]
    return b"".join(struct.pack(">H", len(block)) + block for block in blocks)


def entry_messages(template, character, *, owner=None):
    from wakfu_server.haven_bag_store import instance_id

    if character["map_id"] != 9 or character["instance_id"] != instance_id(character):
        raise ValueError("Own bag entry requires its private interior")
    return [
        # ctB invokes ciu.eDl() to remove actors from the previous world.
        # csW alone changes our map without clearing the old mob registry.
        (13256, b""),
        (13307, entry_result(success=True, own=owner is None, owner=owner)),
        (13974, map_transition(template, character, 9)),
        (12318, struct.pack(">ii", character["x"], character["y"])),
    ]


def leave_messages(template, character):
    if character["map_id"] == 9:
        raise ValueError("Own bag exit requires its exterior return point")
    # Status and leave notification have different roles. cyU13959 does not
    # clear the active bag; ciu consumes cyV13019 to clear its flags and UI.
    return [
        (13959, leave_result()),
        (13019, b""),
        (13256, b""),
        (13974, map_transition(template, character, character["map_id"])),
        (12318, struct.pack(">ii", character["x"], character["y"])),
    ]


class HavenBagSession:
    """Interior location stays in memory; PostgreSQL retains the exterior return point."""

    def __init__(self, outside, *, owner=None):
        from wakfu_server.haven_bag_store import instance_id

        self.owner = dict(owner or outside)
        self.bag_instance_id = instance_id(self.owner)
        self.is_owner = self.owner["account_id"] == outside["account_id"]
        self.outside = dict(outside)
        self.character_id = outside["id"]
        self.inside = {
            **outside,
            "map_id": 9,
            "instance_id": self.bag_instance_id,
            "haven_bag": self.owner.get("haven_bag", outside.get("haven_bag")),
            "haven_bag_visitor": not self.is_owner,
            "x": 3,
            "y": 3,
            "z": 0,
        }

    @property
    def exterior_actor_id(self):
        """Stable published owner's registry key; guests own no exterior entry."""
        return self.owner["id"] if self.is_owner else None

    def owns(self, character):
        return (
            character["id"] == self.character_id
            and character["account_id"] == self.outside["account_id"]
            and character["map_id"] == 9
            and character["instance_id"] == self.bag_instance_id
        )

    def rebind(self, character, saved):
        """Select an owned hero without leaving the current private interior.

        The caller validates the selected session and attaches position buffering
        to saved exterior storage, never to this transient map9 projection.
        Per-actor chest/occupation tokens must be cleared by the dispatcher.
        """
        from wakfu_server.haven_bag_store import instance_id

        if (
            not self.owns(character)
            or type(saved.get("id")) is not int
            or saved["id"] <= 0
            or saved.get("account_id") != self.outside["account_id"]
            or any(
                type(saved.get(key)) is not int
                for key in ("map_id", "instance_id", "x", "y", "z")
            )
            or saved["map_id"] == 9
            or (self.is_owner and instance_id(saved) != self.bag_instance_id)
        ):
            raise ValueError("Hero cannot adopt this haven bag session")
        inside = {
            **saved,
            **{key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")},
            "haven_bag": character.get(
                "haven_bag", self.owner.get("haven_bag", saved.get("haven_bag"))
            ),
            "haven_bag_visitor": not self.is_owner,
        }
        self.character_id = saved["id"]
        self.outside = dict(saved)
        self.inside = inside
        return dict(inside)

    def move(self, character, end):
        if not self.owns(character):
            raise ValueError("Character is outside its own haven bag")
        # Map9 also contains the lobby and exit at(-4,2,0), outside
        # the 6x6 commerce room. Movement.validate owns route validation.
        self.inside = {**character, **end}
        return dict(self.inside)

    def leave(self, character):
        if not self.owns(character):
            raise ValueError("Character is outside its own haven bag")
        return dict(self.outside)

    def refresh(self, character, saved):
        """Apply a persisted build without moving the active interior session."""
        if not self.owns(character) or saved["id"] != self.character_id:
            raise ValueError("Character is outside its own haven bag")
        self.outside = dict(saved)
        self.inside = {
            **saved,
            **{key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")},
            "haven_bag_visitor": not self.is_owner,
            **({"haven_bag": self.owner["haven_bag"]} if not self.is_owner else {}),
        }
        return dict(self.inside)


def public_access():
    """Native room-type bits allow public visits, never item management."""
    return {"groups": [{"group": 0, "rights": 255}], "characters": []}


def visit_permission_payload(config):
    """Publish the effective public room policy without rewriting owner data."""
    return permission_payload({**config, "locked": False, "access": public_access()})


def permission_payload(config):
    """uh: lock, ALL/GUILD room-right masks, individual character rights."""
    access = config.get("access", {})
    groups, characters = access.get("groups", []), access.get("characters", [])
    data = struct.pack(">BH", bool(config["locked"]), len(groups))
    data += b"".join(
        struct.pack(">BB", item["group"], item["rights"]) for item in groups
    )
    data += struct.pack(">H", len(characters))
    for item in characters:
        name = item["name"].encode("utf-8")
        data += (
            struct.pack(">qH", item["id"], len(name)) + name + bytes((item["rights"],))
        )
    return data


def decode_permissions(body):
    from protocol_codec import Reader

    r = Reader(body)
    payload = r.take(r.number("I"))
    r.finish()
    r = Reader(payload)
    locked = r.number("B")
    if locked not in (0, 1):
        raise ValueError("Invalid haven-bag lock flag")
    count = r.number("H")
    if count > 2:
        raise ValueError("Invalid haven-bag permission groups")
    groups = [dict(group=r.number("B"), rights=r.number("B")) for _ in range(count)]
    if (
        any(item["group"] not in (0, 1) for item in groups)
        or len({item["group"] for item in groups}) != count
    ):
        raise ValueError("Invalid haven-bag permission groups")
    count = r.number("H")
    if count > 100:
        raise ValueError("Too many haven-bag character permissions")
    characters = [
        dict(id=r.number("q"), name=r.text("H"), rights=r.number("B"))
        for _ in range(count)
    ]
    if (
        any(item["id"] <= 0 or not item["name"] for item in characters)
        or len({item["id"] for item in characters}) != count
    ):
        raise ValueError("Invalid haven-bag character permissions")
    r.finish()
    return bool(locked), dict(groups=groups, characters=characters)
