"""Original bcC/faM constructor and callback authority, without a pickup policy.

faM.c(amP) supplies the actual target point and e(amP) is always true.
faM.d(amP) supplies no exit recipients. Its extra serialization is empty;
neither the type nor area property3 creates fighter PA resources.
"""


def validate_artifact_definition(definition):
    """Require the actual factory subtype before admitting a faM Qq."""
    if (
        definition.get("type") != "ARTIFACT"
        or definition.get("native_class") != "bcC"
        or type(definition.get("native_type_id")) is not int
        or definition["native_type_id"] != 20
        or type(definition.get("native_container_type")) is not int
        or definition["native_container_type"] != 3
        or definition.get("native_shape_class") != "anD"
        or definition.get("native_shape_description") != "point"
        or definition.get("shape_parameters") not in ([], ())
    ):
        raise ValueError("Missing native bcC/faM artifact constructor authority")


def verify_artifact_area(row, definition):
    validate_artifact_definition(definition)
    if (
        row.get("native_area_contract") != "faM"
        or type(row.get("native_type_id")) is not int
        or row["native_type_id"] != 20
    ):
        raise ValueError("Missing registered native faM artifact authority")
