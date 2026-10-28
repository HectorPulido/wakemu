"""Mission-free access to the original Bruma de travesía transport family."""
from .exploration_transport import ACTION_IDS, native_binding, request

# Original Spanish text table 89 names these flE definitions identically.
# Match native definitions, never map-specific scene UIDs or generic icons.
DEFINITION_IDS = frozenset(
    (
        1905,
        1906,
        1907,
        1908,
        2029,
        2030,
        2031,
        2032,
        2033,
        2034,
        2035,
        2036,
        2037,
        2038,
        2039,
        2040,
        2041,
        2351,
        2352,
    )
)


def recognizes(source):
    return source is not None and source.get("definition_id") in DEFINITION_IDS


def binding(map_id, source_id):
    from wakfu_server import generic_transports

    source = generic_transports.source(map_id, source_id)
    if not recognizes(source):
        return None
    return native_binding(source, "travel_mist")
