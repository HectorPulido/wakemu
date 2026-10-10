"""One capacity policy for native roster decoding, creation and selection UI."""
import os
import struct

# cEk.dp reads the roster length with ByteBuffer.get(), a signed byte.
NATIVE_MAX_CHARACTERS = 127
# bkg.b adds cEl's signed extra-slot byte to eEL.oZT's native base of five.
NATIVE_BASE_CHARACTERS = 5
DEFAULT_MAX_CHARACTERS = 18


def configured_capacity(override=None):
    if override is None:
        raw = os.environ.get("WAKFU_MAX_CHARACTERS", str(DEFAULT_MAX_CHARACTERS))
        try:
            capacity = int(raw)
        except (TypeError, ValueError):
            raise ValueError("Invalid character selection capacity") from None
    else:
        capacity = override
    if type(capacity) is not int or not 1 <= capacity <= NATIVE_MAX_CHARACTERS:
        raise ValueError("Invalid character selection capacity")
    return capacity


def packet(capacity):
    """23992/cEl is a signed adjustment, not the absolute slot total."""
    capacity = configured_capacity(capacity)
    return 23992, struct.pack(">b", capacity - NATIVE_BASE_CHARACTERS)
