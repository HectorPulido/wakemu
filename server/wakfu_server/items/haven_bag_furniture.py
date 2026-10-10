"""Own furniture forms: exact current vf/vj/wI minimal wire variant.

Rich item options and specific data types are rejected, never discarded.
"""
import struct

_PREFIX = struct.Struct(">qiihBB")
_ITEM = struct.Struct(">qih")


def encode_furniture(
    *,
    template_id,
    item_uid,
    item_ref,
    x,
    y,
    z=0,
    direction=0,
    virtual=False,
    quantity=1
):
    if item_uid <= 0 or item_ref <= 0 or not 1 <= quantity <= 32767:
        raise ValueError("own item UID/reference/quantity must be positive")
    if not 0 <= direction <= 7 or type(virtual) is not bool:
        raise ValueError("invalid furniture direction or virtual flag")
    return (
        _PREFIX.pack(template_id, x, y, z, direction, int(virtual))
        + _ITEM.pack(item_uid, item_ref, quantity)
        + bytes(9)
    )


def decode_furniture(blob):
    if len(blob) != 43:
        raise ValueError("only exact 43-byte minimal vf supported")
    template_id, x, y, z, direction, virtual = _PREFIX.unpack_from(blob)
    uid, ref, quantity = _ITEM.unpack_from(blob, _PREFIX.size)
    if blob[34:42] != bytes(8) or blob[42] != 0:
        raise ValueError("rich itemForm or specificData unsupported")
    if virtual not in (0, 1):
        raise ValueError("invalid virtual boolean")
    result = dict(
        template_id=template_id,
        item_uid=uid,
        item_ref=ref,
        quantity=quantity,
        x=x,
        y=y,
        z=z,
        direction=direction,
        virtual=bool(virtual),
    )
    encode_furniture(**result)
    return result


encode_vf = encode_furniture
decode_vf = decode_furniture


def decode_deploy_request(blob):
    """Decode crM; second long is a template ID in cKB/cKC, UID in older UI.

    The historical item_uid key is retained for callers; ownership must be
    resolved against native template metadata and the owner's inventory.
    """
    if len(blob) != 26:
        raise ValueError("13826 requires exactly 26 bytes")
    ref, uid, x, y, z, direction = struct.unpack(">iqiihi", blob)
    if ref <= 0 or uid <= 0 or not 0 <= direction <= 7:
        raise ValueError("invalid deployment item or direction")
    return dict(item_ref=ref, item_uid=uid, x=x, y=y, z=z, direction=direction)
