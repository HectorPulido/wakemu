"""Restore professions without opening learning UI over the intro scene."""


def packets(map_id, source):
    return [packet for packet in source if map_id != 1465 or packet[0] != 12675]
