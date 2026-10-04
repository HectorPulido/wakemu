"""Clock23354 carries Unix epoch milliseconds; date drives client daylight.

An offset permits a local chosen time of day at real-time speed. Accelerated
clock rates need frequent resync because the client advances at real time.
"""
import struct
import time


def packet(now_ms=None, offset_ms=0):
    if now_ms is None:
        now_ms = time.time_ns() // 1000000
    if type(now_ms) is not int or type(offset_ms) is not int:
        raise ValueError("Clock values must be integer milliseconds")
    return struct.pack(">q", now_ms + offset_ms)


DAY_SECONDS = 7200


def daytime(epoch_ms):
    """Match TX.bjX: daylight for the middle half of a two-hour cycle."""
    if type(epoch_ms) is not int or epoch_ms < 0:
        raise ValueError("Clock must be nonnegative integer milliseconds")
    phase = (epoch_ms // 1000) % DAY_SECONDS
    return DAY_SECONDS // 4 <= phase < 3 * DAY_SECONDS // 4
