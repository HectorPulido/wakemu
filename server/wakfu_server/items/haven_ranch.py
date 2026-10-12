"""Session-owned empty ranch projection; native installed geometry is injected.

This module never writes exterior positions, creates animals or grants bag rights.
"""
import struct

POSITION = ("map_id", "instance_id", "x", "y", "z")
ACTIONS = {0: 2, 31: 3, 32: 4, 33: 5, 34: 6, 35: 1}
MAPS = {2: 1466, 3: 1467, 4: 1468, 5: 1469, 6: 1470, 1: 1440}
# Qualified by the original native VB/Vy topology reader; other installed
# references have no standalone assets and remain blocked until resolved.
QUALIFIED_DESTINATIONS = {1: {"map_id": 1440, "x": 28, "y": 6, "z": 4}}


def destination(action, installed=None):
    """Require an installed destination including a geometry-qualified height."""
    installed = QUALIFIED_DESTINATIONS if installed is None else installed
    biome = ACTIONS.get(action)
    if biome is None or biome not in installed:
        raise ValueError("Unsupported installed ranch choice")
    result = dict(installed[biome])
    if result.get("map_id") != MAPS[biome] or any(
        k not in result for k in ("x", "y", "z")
    ):
        raise ValueError("Unqualified native ranch destination")
    return {**result, "biome_id": biome}


class RanchSession:
    """A child private scene with a separate, strictly map9 parent capability."""

    def __init__(self, bag, character, target, *, lease, now_ms):
        if not bag.owns(character):
            raise ValueError("Ranch entry requires the live host bag")
        if lease is None or now_ms <= 0:
            raise ValueError("Ranch entry requires a live actor lease and clock")
        biome = target.get("biome_id")
        if MAPS.get(biome) != target.get("map_id") or any(
            k not in target for k in ("x", "y", "z")
        ):
            raise ValueError("Unqualified native ranch destination")
        self.parent = bag
        self.return_point = dict(character)
        self.lease = lease
        self.snapshot_ms = int(now_ms)
        self.biome_id = biome
        self.closed = False
        # Private world IDs already use owner-character identity for bag scenes;
        # map identity distinguishes the child scene, without a new ID namespace.
        self.inside = {
            **character,
            **{k: target[k] for k in ("map_id", "x", "y", "z")},
            "instance_id": bag.bag_instance_id,
            "haven_ranch_session": True,
        }

    def owns(self, character):
        return (
            not self.closed
            and self.parent.owns(self.return_point)
            and all(
                character.get(k) == self.inside[k]
                for k in ("id", "account_id", "map_id", "instance_id")
            )
        )

    def validate_lease(self, lease):
        if not self.owns(self.inside) or lease != self.lease:
            raise ValueError("Expired ranch actor lease")

    def move(self, character, end):
        if not self.owns(character) or any(
            k in end for k in ("map_id", "instance_id", "id", "account_id")
        ):
            raise ValueError("Invalid private ranch movement")
        self.inside = {**character, **end}
        return dict(self.inside)

    def rebind(self, character, saved):
        """Change selected hero while retaining the host ranch and parent bag."""
        if not self.owns(character):
            raise ValueError("Character is outside its ranch")
        returned = self.parent.rebind(self.return_point, saved)
        inside = {
            **returned,
            **{key: character[key] for key in POSITION},
            "haven_ranch_session": True,
        }
        self.return_point = returned
        self.inside = inside
        return dict(inside)

    def refresh(self, character, saved):
        if (
            not self.owns(character)
            or saved.get("id") != character["id"]
            or saved.get("account_id") != character["account_id"]
        ):
            raise ValueError("Invalid private ranch refresh")
        # Let the parent update its authoritative exterior metadata while
        # retaining the immediate bag return location and visitor policy.
        self.return_point = self.parent.refresh(self.return_point, saved)
        self.inside = {
            **self.return_point,
            **{k: character[k] for k in POSITION},
            "haven_ranch_session": True,
        }
        return dict(self.inside)

    def leave(self, character):
        if not self.owns(character):
            raise ValueError("Character is outside its ranch")
        self.closed = True
        return dict(self.return_point)

    def context(self):
        if self.closed:
            raise ValueError("Closed ranch session")
        return struct.pack(
            ">qqBiiiq",
            self.parent.owner["account_id"],
            self.inside["map_id"],
            1,
            0,
            0,
            0,
            self.snapshot_ms,
        )

    def entry_messages(self, template, character, *, clear_bag_role=True):
        from wakfu_server.haven_bag import map_transition

        if not self.owns(character):
            raise ValueError("Character is outside its ranch")
        # cyV requires an active bag model. Ranch-to-Ranch transitions already
        # cleared it and must not invoke that consumer a second time.
        role_cleanup = [(13019, b"")] if clear_bag_role else []
        return role_cleanup + [
            (13256, b""),
            (13864, self.context()),
            (13974, map_transition(template, character, character["map_id"])),
            (12318, struct.pack(">ii", character["x"], character["y"])),
        ]


def leave_messages(template, character, bag):
    from wakfu_server.haven_bag import map_transition, entry_result

    if not bag.owns(character):
        raise ValueError("Ranch return requires its parent bag")
    # 13256 clears ceK; sending an empty13864 would reinstall a ranch model.
    return [
        (13256, b""),
        (
            13307,
            entry_result(
                success=True,
                own=bag.is_owner,
                owner=None if bag.is_owner else bag.owner,
            ),
        ),
        (13974, map_transition(template, character, 9)),
        (12318, struct.pack(">ii", character["x"], character["y"])),
    ]
