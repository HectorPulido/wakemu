"""Render deployed haven-bag furniture through native dynamic scene entities.

12187 describes the bag layout/content model. cwG13664 separately creates
rendered interactives, using instance identity, template identity and byZ
part 3 with the owning character identity.
"""
import struct

from .haven_bag_furniture_catalog import resolve_item


def _record(owner_id, item, *, ranch=False):
    definition = resolve_item(item["item_ref"])
    if definition is None or definition["template_id"] != item["template_id"]:
        raise ValueError("Unknown native furniture mapping")
    kind = definition["kind"]
    if kind not in {
        "Decoration",
        "FxDecoration",
        "DimensionalBagBackgroundDisplay",
        "PortableCraftTable",
    }:
        raise ValueError("Unsupported furniture dynamic subtype")
    if (
        type(owner_id) is not int
        or owner_id <= 0
        or type(item["item_uid"]) is not int
        or item["item_uid"] <= 0
        or not 0 <= item["direction"] <= 7
        or not (-131071 <= item["x"] <= 131072 if ranch else 0 <= item["x"] < 18)
        or not (-131071 <= item["y"] <= 131072 if ranch else 0 <= item["y"] < 18)
        or not -511 <= item["z"] <= 512
    ):
        raise ValueError("Invalid native furniture scene identity or position")
    payload = struct.pack(
        ">iihBq?",
        item["x"],
        item["y"],
        item["z"],
        item["direction"],
        owner_id,
        item.get("virtual", False),
    )
    if kind != "PortableCraftTable":
        payload += struct.pack(">i", item["item_ref"])
    # fg: one part, index 3, absolute part offset 6; one version byte.
    dynamic = struct.pack(">BBIB", 1, 3, 6, 0) + payload
    position = (item["x"] + 131071) << 28 | (item["y"] + 131071) << 10 | item["z"] + 511
    return (
        struct.pack(">qqH", item["item_uid"], item["template_id"], len(dynamic))
        + dynamic
        + struct.pack(">q", position)
    )


def upsert(character, item):
    """Return one cwG creation for a deployed physical or virtual furniture unit."""
    if not item.get("deployed"):
        raise ValueError("Cannot render packed furniture")
    return 13664, struct.pack(">h", 1) + _record(character["id"], item)


def packets(character):
    """Render all deployed units after the haven-bag layout has loaded."""
    rows = (character.get("haven_bag") or {}).get("furniture", [])
    return [upsert(character, item) for item in rows if item.get("deployed")]


def remove(item):
    """cwH13082 removes the rendered instance, never its reusable template."""
    identity = item["item_uid"] if isinstance(item, dict) else item
    if type(identity) is not int or identity <= 0:
        raise ValueError("Invalid furniture instance identity")
    return 13082, struct.pack(">hq", 1, identity)


def ranch_upsert(owner_character_id, item):
    """Render a separately authorized Ranch fBM; never broaden bag geometry."""
    if not item.get("deployed") or not item.get("virtual"):
        raise ValueError("Ranch scene requires an installed learned decoration")
    return 13664, struct.pack(">h", 1) + _record(owner_character_id, item, ranch=True)
