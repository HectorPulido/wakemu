"""Installed bcW/fbb SIMPLE areas inherit faV without HP or obstacles.

fbb.e accepts only its owner; fbb.c always returns null, so activation has
no effect coordinates. fbb.n supplies the actual exit target. The subtype
serializes no extra mutable bytes (fTl) and has no additional parameters.
"""

SOURCE = "bcW.fbb.Qr.constructor.type6"


def simple_area_constructor(definition):
    """Verify subtype authority without specializing individual prototypes."""
    if (
        definition.get("type") != "SIMPLE"
        or definition.get("native_class") != "bcW"
        or definition.get("native_type_id") != 6
        or definition.get("native_container_type") != 3
    ):
        raise ValueError("Missing native fbb SIMPLE constructor authority")
    return dict(
        source=SOURCE,
        owner_activation=True,
        other_activation=False,
        activation_coordinates=None,
        obstacle=False,
        movement_blocking=False,
        bcK_value=6,
    )


def verified_simple_area(row, definition):
    constructor = simple_area_constructor(definition)
    if (
        row.get("native_area_contract") != "fbb"
        or row.get("native_type_id") != 6
        or row.get("native_simple_constructor") != constructor
    ):
        raise ValueError("Missing registered native fbb SIMPLE provenance")
    return constructor
