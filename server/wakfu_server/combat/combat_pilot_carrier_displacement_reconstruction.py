"""Independent byte-derived displacement of an explicitly registered carry pair."""
from .combat_pilot_displacement_reconstruction import (
    _cell,
    modeled_displacement_positions,
)
from .combat_protocol_reconstruction import _field, decode_packet


def normalize_view(view):
    positions = {}
    relations = {}
    for raw_id, raw_cell in view["positions"].items():
        identity = int(raw_id)
        if (
            identity in positions
            or len(raw_cell) != 3
            or any(type(x) is not int for x in raw_cell)
        ):
            raise ValueError("Unique actor identity and explicit integer cell required")
        positions[identity] = tuple(raw_cell)
    for raw_id, relation in view["relations"].items():
        identity = int(raw_id)
        if identity in relations or set(relation) != {"carrier", "carried"}:
            raise ValueError("Unique explicit reciprocal relation required")
        if any(
            value is not None and type(value) is not int for value in relation.values()
        ):
            raise ValueError("Explicit integer partner identities required")
        relations[identity] = dict(relation)
    if positions.keys() != relations.keys():
        raise ValueError("Actor registration and relation identities differ")
    for identity, relation in relations.items():
        carrier, carried = relation["carrier"], relation["carried"]
        if carrier is not None and carried is not None:
            raise ValueError("Nested carrying outside pilot proof")
        for partner, reciprocal in ((carrier, "carried"), (carried, "carrier")):
            if partner is not None and (
                partner == identity
                or partner not in relations
                or relations[partner][reciprocal] != identity
                or positions[partner] != positions[identity]
            ):
                raise ValueError(
                    "Carry pair must be registered, reciprocal and colocated"
                )
    return positions, relations


def modeled_carrier_displacement(packet, before):
    positions, relations = normalize_view(before)
    decoded = decode_packet(*packet)
    if decoded.get("kind") == "effect" and decoded["effect"]["family"] == 302:
        if packet[0] != 12613 or decoded["immediate"] is not False:
            raise ValueError("One non-immediate native application required")
        effect = decoded["effect"]
        caster, target = effect["caster"], effect["target"]
        if caster not in positions or target != caster:
            raise ValueError("Caster teleport requires registered self identity")
        after = dict(positions)
        destination = _cell(_field(effect["additional"], 15, 2, required=True))
        if _field(effect["additional"], 33, 0, default=0) != 0:
            after[caster] = destination
    else:
        decoded, after = modeled_displacement_positions(packet, positions)
    # Original eGj position operations propagate to fry(), independent of a
    # second displacement packet. A directly displaced carried actor is not
    # qualified by this carrier-preservation slice.
    for identity, cell in tuple(after.items()):
        if cell != positions[identity]:
            if relations[identity]["carrier"] is not None:
                raise ValueError(
                    "Direct carried-actor displacement outside carrier pilot"
                )
            partner = relations[identity]["carried"]
            if partner is not None:
                after[partner] = cell
    return decoded, dict(
        positions={str(key): list(cell) for key, cell in after.items()},
        relations={str(key): value for key, value in relations.items()},
    )


def _recipient_label(value):
    if type(value) is str and value:
        return value
    if (
        type(value) is dict
        and set(value) == {"schema", "root", "nodes", "services"}
        and value["schema"] == "wakemu-combat-reproduction-state-v1"
        and type(value["root"]) is str
        and value["root"]
        and value["nodes"] == []
        and value["services"] == []
    ):
        return value["root"]
    raise ValueError("Explicit captured recipient label required")


def verify_native_carrier_displacement_case(
    *, packet, before, projection, recipient, proof_bytes, trusted_proof_sha256
):
    """Bind exact delivered bytes and captured actor graph to a pinned receipt.

    Recipient is the exact captured delivery label, not an invented live socket
    generation. Qualification covers the original logical callback only.
    """
    import hashlib
    import json

    base = dict(
        qualified=False,
        rendering_qualified=False,
        live_delivery_qualified=False,
        visual_script_qualified=False,
        reasons=[],
        scope="one native carrier displacement callback, explicit positions and reciprocal relations",
    )
    try:
        if (
            type(recipient) is not str
            or not recipient
            or type(proof_bytes) is not bytes
            or len(proof_bytes) > 4 * 1024 * 1024
        ):
            raise ValueError(
                "Explicit recipient label and bounded immutable proof required"
            )
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
        if not trusted_proof_sha256 or proof_hash != trusted_proof_sha256:
            raise ValueError(
                "Native carrier displacement proof is not independently pinned"
            )
        proof = json.loads(proof_bytes)
        if (
            proof.get("schema") != "wakemu-pilot-carrier-displacement-native-proof-v1"
            or proof.get("complete") is not True
            or proof.get("source_stable") is not True
            or type(proof.get("compile_returncode")) is not int
            or proof["compile_returncode"] != 0
            or proof.get("instrumentation") != "none"
            or "client/lib/wakfu-client.jar" not in proof.get("classpath", {})
            or not proof.get("bdata")
            or "sniffer/java/VerifyPilotCarrierDisplacementQueue.java"
            not in proof.get("source", {})
        ):
            raise ValueError(
                "Native carrier receipt incomplete or wrong original consumer"
            )
        positions, relations = normalize_view(before)
        if not any(row["carried"] is not None for row in relations.values()):
            raise ValueError("Explicit registered carrier pair required")
        initial = dict(
            positions={str(k): list(v) for k, v in positions.items()},
            relations={str(k): v for k, v in relations.items()},
        )
        decoded, modeled = modeled_carrier_displacement(packet, before)
        projected_positions, projected_relations = normalize_view(projection)
        projected = dict(
            positions={str(k): list(v) for k, v in projected_positions.items()},
            relations={str(k): v for k, v in projected_relations.items()},
        )
        payload_hash = hashlib.sha256(packet[1]).hexdigest()
        records = [
            row
            for row in proof.get("cases", ())
            if row.get("opcode") == packet[0]
            and row.get("payload_sha256") == payload_hash
            and row.get("initial") == initial
            and _recipient_label(row.get("recipient")) == recipient
        ]
        if not records:
            raise ValueError(
                "Exact displacement bytes, recipient and initial pair absent from native proof"
            )
        for record in records:
            native = record.get("native", {})
            if (
                record.get("complete") is not True
                or type(record.get("returncode")) is not int
                or record["returncode"] != 0
                or native.get("completed_normally") is not True
                or native.get("queue_drained") is not True
                or native.get("native_completed_action_ids") != [decoded["action"]]
                or native.get("action_id") != decoded["action"]
                or any(
                    native.get(key) != decoded["effect"][effect_key]
                    for key, effect_key in (
                        ("family", "family"),
                        ("generic_effect", "definition"),
                        ("uid", "uid"),
                        ("caster", "caster"),
                        ("target", "target"),
                    )
                )
            ):
                raise ValueError(
                    "Original callback/action/owner identity or queue completion differs"
                )
            if (
                native.get("before") != initial
                or native.get("after") != modeled
                or record.get("modeled") != modeled
                or record.get("expected") != modeled
            ):
                raise ValueError(
                    "Independent byte-derived pair differs from original native callback"
                )
        if projected != modeled:
            raise ValueError(
                "Requested position/relation projection differs from native callback"
            )
        return dict(
            base,
            qualified=True,
            recipient=recipient,
            native_proof_sha256=proof_hash,
            packet_sha256=payload_hash,
            native_cases=[row["id"] for row in records],
            before=initial,
            after=modeled,
            action_ids=(decoded["action"],),
            pending=False,
        )
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OverflowError,
        AttributeError,
    ) as error:
        return dict(base, reasons=[str(error)])
