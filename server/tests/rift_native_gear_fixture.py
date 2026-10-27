"""Build actual owned native gear before fresh QA Actor construction."""
from copy import deepcopy


def equip_character(character, specification):
    from wakfu_server.wire import proto_field
    from wakfu_server.equipment import validate_sheet

    character = deepcopy(character)
    entries = specification["entries"]
    items, fields = [], []
    for entry in entries:
        uid = character["id"] * 100000 + entry["slot"] + 1
        items.append(
            dict(
                uid=uid,
                character_id=character["id"],
                reference=entry["reference"],
                quantity=1,
            )
        )
        fields.append(
            proto_field(10, proto_field(8, uid) + proto_field(16, entry["slot"]))
        )
    character["inventory_items"] = items
    index = character.get("active_build_index", 0)
    blob = b"".join(fields)
    character["builds"][index]["equipment"] = blob.hex()
    validate_sheet(character, blob)
    return character


def clone_equipment_owner(character, identity):
    from wakfu_server.wire import proto_fields, proto_field

    character = deepcopy(character)
    character["id"] = identity
    index = character.get("active_build_index", 0)
    fields, identities = [], {}
    for tag, value in proto_fields(
        bytes.fromhex(character["builds"][index].get("equipment", ""))
    ):
        if tag == 10:
            row = dict(proto_fields(value))
            uid = identity * 100000 + row[16] + 1
            identities[row[8]] = uid
            value = proto_field(8, uid) + proto_field(16, row[16])
        fields.append(proto_field(tag, value))
    for item in character.get("inventory_items", ()):
        item["character_id"] = identity
        item["uid"] = identities[item["uid"]]
    character["builds"][index]["equipment"] = b"".join(fields).hex()
    return character
