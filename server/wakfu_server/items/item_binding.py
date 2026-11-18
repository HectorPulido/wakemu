"""Publish durable native binding state through both owned item encodings."""


def _template(reference):
    from wakfu_server.combat_drop_delivery import _template_binding

    return _template_binding(reference)


def hydrate(db, items):
    if not items:
        return items
    references = {item["uid"]: item["reference"] for item in items}
    bindings, overrides = {}, {}
    for row in db.execute(
        "SELECT uid,bound,template_reference,binding_type FROM inventory_item_bindings WHERE uid=ANY(%s)",
        (list(references),),
    ):
        if type(row["bound"]) is not bool or row[
            "template_reference"
        ] != references.get(row["uid"]):
            raise ValueError("Invalid persisted item binding")
        bindings[row["uid"]] = row["bound"]
        if row.get("binding_type") is not None:
            overrides[row["uid"]] = row["binding_type"]
    for item in items:
        enum, binding_type, default = _template(item["reference"])
        if item["uid"] in overrides:
            binding_type = overrides[item["uid"]]
            validate_override(binding_type)
            item["binding_type"] = binding_type
            item["bound"] = bindings.get(item["uid"], False)
            continue
        if enum != "NOT_BOUND":
            item["binding_type"] = binding_type
            item["bound"] = bindings.get(item["uid"], False) or default
        elif bindings.get(item["uid"], False):
            # Preserve explicit persisted state; do not reinterpret its scope.
            item["binding_type"] = binding_type
            item["bound"] = True
    return items


def validate_override(binding_type):
    """foS IDs0–8 are recovered from the installed client's native enum."""
    if type(binding_type) is not int or not 0 <= binding_type <= 8:
        raise ValueError("Invalid native reward binding override")
    return binding_type


def save_override(db, uid, reference, binding_type):
    binding_type = validate_override(binding_type)
    bound = binding_type in (2, 4, 6, 8)
    db.execute(
        "INSERT INTO inventory_item_bindings(uid,bound,template_reference,binding_type) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT(uid) DO UPDATE SET "
        "bound=EXCLUDED.bound,template_reference=EXCLUDED.template_reference,"
        "binding_type=EXCLUDED.binding_type",
        (uid, bound, reference, binding_type),
    )
    return binding_type, bound


def effective_template(reference, persisted):
    """Use a per-unit reward's scope before the ordinary template fallback."""
    value = persisted.get("binding_type")
    if value is None:
        return _template(reference)
    value = validate_override(value)
    names = (
        "NOT_BOUND",
        "BOUND_ON_EQUIP_TO_CHARACTER",
        "BOUND_ON_PICKUP_TO_CHARACTER",
        "BOUND_ON_EQUIP_TO_ACCOUNT",
        "BOUND_ON_PICKUP_TO_ACCOUNT",
        "BOUND_ON_EQUIP_TO_CHARACTER",
        "BOUND_ON_PICKUP_TO_CHARACTER",
        "BOUND_ON_EQUIP_TO_ACCOUNT",
        "BOUND_ON_PICKUP_TO_ACCOUNT",
    )
    return names[value], value, value in (2, 4, 6, 8)


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
    if row.get("binding_type") is not None:
        binding_type = validate_override(row["binding_type"])
        return dict(item, binding_type=binding_type, bound=row["bound"])
    if enum == "NOT_BOUND" and not row["bound"]:
        return item
    return dict(item, binding_type=binding_type, bound=row["bound"] or default)
