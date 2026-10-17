"""Independent native displacement endpoint model at an observed callback.

This slice models one logical action callback in a detached native queue. It
does not qualify the skipped visual script, socket dispatch, or live admission.
"""
import hashlib
import json

from .combat_protocol_reconstruction import (
    Recipient,
    _field,
    _protobuf,
    _signed,
    decode_packet,
    reconstruct_packets,
)


def _cell(raw):
    fields = _protobuf(raw)
    return tuple(
        _signed(_field(fields, index, 0, default=0), bits)
        for index, bits in ((1, 32), (2, 32), (3, 16))
    )


def modeled_displacement_positions(packet, initial_positions):
    """Interpret native additional operands; never call a server serializer."""
    opcode, payload = packet
    decoded = decode_packet(opcode, payload)
    if (
        decoded["kind"] != "effect"
        or opcode != 12613
        or decoded["immediate"] is not False
    ):
        raise ValueError("One non-immediate native application required")
    effect = decoded["effect"]
    family, caster, target = effect["family"], effect["caster"], effect["target"]
    positions = {actor: tuple(cell) for actor, cell in initial_positions.items()}
    if caster not in positions or target not in positions:
        raise ValueError("Displacement references unregistered recipient actor")
    additional = effect["additional"]
    if family in (300, 301):
        raw = _field(additional, 70, 2)
        if raw is not None:
            path_fields = _protobuf(raw)
            entries = path_fields.get(1, ())
            if any(wire != 2 for wire, _ in entries):
                raise ValueError("Wrong native displacement path point type")
            path = [_cell(point) for _, point in entries]
            if path:
                positions[target] = path[-1]
    elif family == 340:
        destination = _cell(_field(additional, 15, 2, required=True))
        if _field(additional, 33, 0, default=0) != 0:
            positions[target] = destination
    elif family == 422:
        old_target = _cell(_field(additional, 15, 2, required=True))
        old_caster = _cell(_field(additional, 23, 2, required=True))
        if positions[target] != old_target or positions[caster] != old_caster:
            raise ValueError("Swap origin identity relationships differ")
        positions[caster], positions[target] = old_target, old_caster
    else:
        raise ValueError(
            "Native displacement family outside independently modeled pilot"
        )
    return decoded, positions


def verify_native_displacement_case(
    *, bootstrap, packet, recipient, projection, proof_bytes, trusted_proof_sha256
):
    """Qualify exact logical positions against an independently pinned receipt.

    Projection is explicitly ``{actor_id: (x,y,z)}``, without orientation,
    graphics, or hidden Fight fields. The modeled completion boundary is the
    actual original aVo.cbj observed in the native receipt, not a forged fence.
    """
    base = dict(
        qualified=False,
        rendering_qualified=False,
        visual_script_qualified=False,
        live_delivery_qualified=False,
        scope="one native logical displacement callback and recipient positions",
        reasons=[],
    )
    try:
        if (
            not isinstance(recipient, Recipient)
            or type(proof_bytes) is not bytes
            or len(proof_bytes) > 4 * 1024 * 1024
            or not isinstance(projection, dict)
        ):
            raise ValueError(
                "Explicit recipient, position projection and bounded native proof required"
            )
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
        if not trusted_proof_sha256 or proof_hash != trusted_proof_sha256:
            raise ValueError("Native displacement proof is not independently pinned")
        proof = json.loads(proof_bytes)
        if (
            proof.get("schema") != "wakemu-pilot-displacement-native-proof-v1"
            or proof.get("complete") is not True
            or proof.get("source_stable") is not True
            or type(proof.get("compile_returncode")) is not int
            or proof["compile_returncode"] != 0
            or proof.get("instrumentation") != "none"
            or "client/lib/wakfu-client.jar" not in proof.get("classpath", {})
            or not proof.get("bdata")
            or "sniffer/java/VerifyPilotDisplacementQueue.java"
            not in proof.get("source", {})
        ):
            raise ValueError("Native displacement receipt incomplete or wrong consumer")
        initial = reconstruct_packets(bootstrap, (), recipient=recipient)
        if initial.findings or not initial.complete:
            raise ValueError("Initial recipient registration/position model unresolved")
        positions = {
            actor: row["cell"] for actor, row in initial.executed.positions.items()
        }
        decoded, expected = modeled_displacement_positions(packet, positions)
        effect = decoded["effect"]
        if decoded["fight"] != initial.fight_id:
            raise ValueError(
                "Displacement fight identity differs from recipient bootstrap"
            )
        actor_ids = (effect["caster"], effect["target"])
        origins = {str(actor): list(positions[actor]) for actor in actor_ids}
        payload_hash = hashlib.sha256(packet[1]).hexdigest()
        record = next(
            (
                row
                for row in proof.get("cases", ())
                if row.get("opcode") == packet[0]
                and row.get("payload_sha256") == payload_hash
                and row.get("initial_positions") == origins
            ),
            None,
        )
        if record is None:
            raise ValueError(
                "Exact displacement bytes/origin identities absent from native proof"
            )
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
                native.get(key) != effect[effect_key]
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
                "Native displacement effect/action/owner/completion identity differs"
            )
        native_positions = {
            int(actor): tuple(cell)
            for actor, cell in native.get("executed_positions", {}).items()
        }
        if native_positions != {actor: expected[actor] for actor in actor_ids}:
            raise ValueError(
                "Independent byte-derived endpoint differs from original native callback"
            )
        projection = {actor: tuple(cell) for actor, cell in projection.items()}
        matches = expected == projection
        return dict(
            base,
            qualified=matches,
            native_case=record["id"],
            recipient=dict(role=recipient.role, generation=recipient.generation),
            native_proof_sha256=proof_hash,
            packet_sha256=payload_hash,
            received_positions=positions,
            executed_positions=expected,
            action_ids=(decoded["action"],),
            pending=False,
            reasons=[] if matches else ["permitted_position_projection_differs"],
        )
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        return dict(base, reasons=[str(error)])
