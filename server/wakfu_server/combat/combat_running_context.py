"""Qe owner fields9/10 and eZR/eVt field13, distinct from iR field12."""
from .combat_effects import _integer, _varint


def running_context_payload(
    *, container_type=None, container_id=None, context_payload=None
):
    if container_type is None and container_id is None:
        payload = b""
    elif (
        type(container_type) is not int
        or type(container_id) is not int
        or not -(1 << 31) <= container_type < (1 << 31)
        or not -(1 << 63) <= container_id < (1 << 63)
    ):
        raise ValueError("Missing paired native owner-container kind/identity")
    else:
        payload = _integer(9, container_type) + _integer(10, container_id)
    if context_payload is not None:
        if not isinstance(context_payload, bytes):
            raise ValueError("Native eVt context must be serialized ir bytes")
        # iP.d(ir)/iN.QM is13. iP.a(iR) is12 and carries additional data,
        # including the307 summoned creature UID; never reuse that namespace.
        payload += b"\x6a" + _varint(len(context_payload)) + context_payload
    return payload
