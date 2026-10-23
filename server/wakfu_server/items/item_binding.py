"""Publish durable native binding state through both owned item encodings."""


def _template(reference):
    from wakfu_server.combat_drop_delivery import _template_binding

    return _template_binding(reference)


def hydrate(db, items):
    if not items:
        return items
    from wakfu_server.combat_drop_delivery import _binding_rows

    bindings = _binding_rows(db, items)
    for item in items:
        enum, binding_type, default = _template(item["reference"])
        if enum != "NOT_BOUND":
            item["binding_type"] = binding_type
            item["bound"] = bindings.get(item["uid"], False) or default
        elif bindings.get(item["uid"], False):
            # Preserve explicit persisted state; do not reinterpret its scope.
            item["binding_type"] = binding_type
            item["bound"] = True
    return items


def state(item):
    if "bound" not in item and "binding_type" not in item:
        return None
    bound = item.get("bound", False)
    if type(bound) is not bool:
        raise ValueError("Invalid native item binding flag")
    binding_type = item.get("binding_type")
    if binding_type is None:
        enum, binding_type, default = _template(item["reference"])
        bound = bound or default
        if enum == "NOT_BOUND" and not bound:
            return None
    if type(binding_type) is not int or not 0 <= binding_type <= 127:
        raise ValueError("Invalid native item binding type")
    return binding_type, bound


def proto(item):
    """kX field55 is la {int32 type=1; bool applied=2}, never a bool."""
    binding = state(item)
    if binding is None:
        return b""
    from wakfu_server.wire import proto_field

    binding_type, bound = binding
    return proto_field(442, proto_field(8, binding_type) + proto_field(16, int(bound)))


def binary_option(item):
    """vj.afx/vk wraps vP: presence byte, bind-type byte, applied byte."""
    binding = state(item)
    return b"\x00" if binding is None else bytes((1, binding[0], int(binding[1])))


def from_custody(item, metadata):
    """Project older stored chest binding sidecars without rewriting custody."""
    row = metadata.get("inventory_item_bindings")
    if row is None:
        return item
    if (
        row.get("uid") != item["uid"]
        or row.get("template_reference") != item["reference"]
        or type(row.get("bound")) is not bool
    ):
        raise ValueError("Invalid stored item binding metadata")
    enum, binding_type, default = _template(item["reference"])
    if enum == "NOT_BOUND" and not row["bound"]:
        return item
    return dict(item, binding_type=binding_type, bound=row["bound"] or default)
