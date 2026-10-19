"""All-year access for explicitly reviewed native event calendar windows.

The map binding and both literal boundaries are required. This policy never
waives item, level, mission, state, mode or historical release requirements.
Internal doors and combat conditions keep their original date evaluation.
"""

EVENT_WINDOWS = {
    443: ("IsAfter(16,10,2026,10,00,00) and IsBefore(03,11,2026,10,00,00)"),
    1075: ("IsAfter(27,07,2027,10,00,00) and IsBefore(31,08,2027,10,00,00)"),
    146: (
        "(GetDate() >= GetDate(07,07,2026,09,00,00)) and "
        "(GetDate() <= GetDate(08,09,2026,08,59,59))"
    ),
}


def open_event_calendar(criterion, *, destination_map_id=None):
    """Replace one reviewed calendar conjunct in its bound exterior entry.

    A missing or mismatched binding leaves the complete original expression
    intact. Unknown or changed native windows require a new catalog review.
    The caller still evaluates the resulting full criterion normally.
    """
    if not isinstance(criterion, str) or len(criterion) > 32768:
        raise ValueError("Malformed seasonal entry criterion")
    if destination_map_id is None:
        return criterion
    if type(destination_map_id) is not int or destination_map_id <= 0:
        raise ValueError("Invalid seasonal entry destination")
    window = EVENT_WINDOWS.get(destination_map_id)
    if window is None or criterion.count(window) != 1:
        return criterion
    return criterion.replace(window, "true", 1)
