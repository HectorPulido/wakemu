"""Original building child-definition preflight, separate from Ranch paddocks.

An empty aMX.epT is a complete zero-child producer. Nonempty aMZ/fBH rows
require their persistent fBM instance authority before ownership can change.
"""
from wakfu_server.haven_ranch_building_catalog import definition, view


def validate_building_children(building, mode_id, view_kind, view_value):
    """Return the complete qualified child tuple or reject before mutation.

    The definition must be the pinned original row. Never infer empty children
    from an absent field, an unsupported view, or missing native data.
    """
    if not isinstance(building, dict) or building != definition(building.get("p")):
        raise ValueError("Building children require the original pinned definition")
    selected = view(building, mode_id, view_kind, view_value)
    children = selected.get("epT")
    if not isinstance(children, list):
        raise ValueError("Native building child definitions are missing")
    if children:
        raise ValueError(
            "Native building attached scene-object producer is not qualified"
        )
    return ()
