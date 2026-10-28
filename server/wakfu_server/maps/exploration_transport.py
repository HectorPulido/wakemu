"""Reviewed artifact travel gates and reusable original activation bindings."""
import struct

# Original S.I.D. travel: acquisition2000, explicit traversal objective7498.
SID_DEFINITIONS = frozenset((*range(2387, 2399), 2403, 2404, 2405, *range(2408, 2417)))
# Original Clepsidra travel: acquisition2457, explicit traversal objective7387.
CLOCK_DEFINITIONS = frozenset((2399, 2400))
MISSION_FREE_DEFINITIONS = SID_DEFINITIONS | CLOCK_DEFINITIONS
ACTION_IDS = (0, 31, 32, 33, 34, 35, 36, 37)


def recognizes(source):
    return (
        source is not None and source.get("definition_id") in MISSION_FREE_DEFINITIONS
    )


def projected_access(source, character):
    """Waive acquisition gates only for an owned projected artifact grant."""
    if not recognizes(source):
        return False
    from wakfu_server import exploration_secrets

    reference = 18591 if source["definition_id"] in SID_DEFINITIONS else 19113
    return exploration_secrets.projected_transport_access(character, reference, 1)


def native_binding(source, route_key):
    """Retain native destination order for the original bBH action positions."""
    destinations = tuple(source["destinations"])
    if not destinations or len(destinations) > len(ACTION_IDS):
        raise ValueError("Unsupported native exploration destination count")
    labels = ("desc.mru.entrer", "desc.mru.sortir")
    parameters = "".join(
        "{1;" + labels[min(index, 1)] + "}" for index in range(len(destinations))
    ).encode("utf-8")
    return dict(
        source=source,
        destination=destinations[0],
        destinations=destinations,
        activation_parameters=parameters,
        route_key=route_key,
    )


def binding(map_id, source_id):
    from wakfu_server import generic_transports

    source = generic_transports.source(map_id, source_id)
    return (
        native_binding(source, "exploration_artifact") if recognizes(source) else None
    )


def request(current, action):
    try:
        index = ACTION_IDS.index(action)
    except ValueError:
        raise ValueError("Invalid native exploration action") from None
    destinations = current["destinations"]
    if index >= len(destinations):
        raise ValueError("Absent native exploration destination")
    destination = destinations[index]
    return destination, struct.pack(
        ">qiBi", current["source"]["id"], destination["destination_id"], 0, 2
    )
