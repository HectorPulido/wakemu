"""Pure native gift-list presentation of already-owned custom task snapshots."""
from dataclasses import dataclass
from html import escape
import re
import struct

MESSAGE_ID = 13369
MAX_BODY_BYTES = 60_000
MAX_PACKAGES = 256
MAX_CONTENTS = 256
TASK_CLAIM_NOTICE = "Progress only. No items to claim here; configured rewards are delivered automatically."


@dataclass(frozen=True)
class GiftItem:
    gift_id: str
    reference: int
    quantity: int


@dataclass(frozen=True)
class GiftPackage:
    title: str
    description: str
    contents: tuple = ()


def _text(value, *, allow_empty=False):
    if type(value) is not str or "\0" in value or (not value and not allow_empty):
        raise ValueError("Invalid gift text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Invalid gift UTF-8") from exc
    if len(encoded) > 65535:
        raise ValueError("Gift UTF-8 exceeds unsigned16 length")
    return struct.pack(">H", len(encoded)) + encoded


def _integer(value, maximum):
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError("Invalid gift integer")
    return value


def encode(packages, *, cap_reached=False):
    """Encode cwj/uD/uE/uC. No rewards or ownership authority are inferred."""
    if (
        type(packages) not in (list, tuple)
        or len(packages) > MAX_PACKAGES
        or type(cap_reached) is not bool
    ):
        raise ValueError("Invalid native gift package list")
    chunks = [struct.pack(">H", len(packages))]
    size = 3
    titles, gift_ids = set(), set()
    for package in packages:
        if (
            type(package) is not GiftPackage
            or type(package.contents) is not tuple
            or len(package.contents) > MAX_CONTENTS
        ):
            raise ValueError("Invalid native gift package")
        title = _text(package.title)
        if package.title in titles:
            raise ValueError("Duplicate native gift package title/guid")
        titles.add(package.title)
        row = [
            title,
            _text(package.description, allow_empty=True),
            struct.pack(">H", len(package.contents)),
        ]
        for item in package.contents:
            if type(item) is not GiftItem:
                raise ValueError("Invalid native gift item")
            identity = _text(item.gift_id)
            if item.gift_id in gift_ids:
                raise ValueError("Duplicate native gift claim identity")
            gift_ids.add(item.gift_id)
            reference = _integer(item.reference, 2**31 - 1)
            quantity = _integer(item.quantity, 2**15 - 1)
            row.append(identity + struct.pack(">ih", reference, quantity))
        encoded = b"".join(row)
        size += len(encoded)
        if size > MAX_BODY_BYTES:
            raise ValueError("Native gift publication exceeds practical packet bound")
        chunks.append(encoded)
    chunks.append(bytes([int(cap_reached)]))
    return b"".join(chunks)


def task_packages(snapshot):
    """Render service.snapshot rows as automatically active, read-only cards.

    Empty contents intentionally expose no item claim and invent no reward.
    The caller must obtain the snapshot under the real owned service contract.
    """
    if type(snapshot) is not list or len(snapshot) > MAX_PACKAGES:
        raise ValueError("Invalid custom task snapshot")
    packages, keys = [], set()
    for row in snapshot:
        if type(row) is not dict or set(row) != {
            "key",
            "title",
            "description",
            "count",
            "target",
            "completed",
        }:
            raise ValueError("Invalid custom task snapshot row")
        key = row["key"]
        if (
            type(key) is not str
            or not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", key)
            or key in keys
        ):
            raise ValueError("Invalid or duplicate custom task key")
        keys.add(key)
        _text(row["title"])
        _text(row["description"])
        target = _integer(row["target"], 2**31 - 1)
        count = row["count"]
        if (
            type(count) is not int
            or not 0 <= count <= target
            or type(row["completed"]) is not bool
            or row["completed"] != (count == target)
        ):
            raise ValueError("Invalid custom task progress")
        # Native title also acts as the presentation guid; backend keys stay private.
        title = f"Task: {escape(row['title'], quote=False)}"
        status = "Completed" if row["completed"] else "In progress"
        description = (
            f"{escape(row['description'], quote=False)}\n{status}: {count}/{target}\n"
            f"{TASK_CLAIM_NOTICE}"
        )
        packages.append(GiftPackage(title, description))
    if len({package.title for package in packages}) != len(packages):
        raise ValueError("Duplicate visible custom task title")
    return packages


def publication(snapshot, *, existing_packages=(), cap_reached=False):
    """Merge explicitly provided genuine gifts and custom cards; reject collisions."""
    if type(existing_packages) not in (list, tuple):
        raise ValueError("Existing native gift packages must be explicit")
    merged = list(existing_packages) + task_packages(snapshot)
    return MESSAGE_ID, encode(merged, cap_reached=cap_reached)
