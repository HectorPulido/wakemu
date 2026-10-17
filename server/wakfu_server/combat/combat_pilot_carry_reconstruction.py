"""Independent modeled Pandawa owner relationships at native carry callbacks."""
import hashlib
import json
from itertools import islice

from .combat_protocol_reconstruction import Recipient, _field, decode_packet
from .combat_pilot_displacement_reconstruction import _cell


def verify_native_carry_lifecycle(
    *,
    packets,
    recipient,
    initial_projection,
    projection,
    proof_bytes,
    trusted_proof_sha256
):
    """Decode actual334→333 bytes; preserve nullable throw target and ownership.

    Explicit projections disclose positions and reciprocal carrier/carried IDs.
    Native cost/eligibility and resource comparisons remain the actual owned
    cast fixture's responsibility. No client rendering or visual parenting is
    inferred from the original logical eGj callback evidence.
    """
    base = dict(
        qualified=False,
        rendering_qualified=False,
        visual_parenting_qualified=False,
        live_delivery_qualified=False,
        scope="one owned native carry/throw logical callback sequence",
        reasons=[],
    )
    try:
        if (
            not isinstance(recipient, Recipient)
            or type(proof_bytes) is not bytes
            or len(proof_bytes) > 4 * 1024 * 1024
        ):
            raise ValueError(
                "Explicit recipient and bounded native carry proof required"
            )
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
        if not trusted_proof_sha256 or proof_hash != trusted_proof_sha256:
            raise ValueError("Native carry proof is not independently pinned")
        proof = json.loads(proof_bytes)
        if (
            proof.get("schema") != "wakemu-pilot-carry-native-proof-v1"
            or proof.get("complete") is not True
            or proof.get("source_stable") is not True
            or type(proof.get("compile_returncode")) is not int
            or proof["compile_returncode"] != 0
            or proof.get("instrumentation") != "none"
            or "client/lib/wakfu-client.jar" not in proof.get("classpath", {})
            or not proof.get("bdata")
            or "sniffer/java/VerifyPilotCarryQueue.java" not in proof.get("source", {})
        ):
            raise ValueError("Native carry proof incomplete or wrong consumer")
        packets = tuple(islice(iter(packets), 3))
        if len(packets) != 2:
            raise ValueError("Exact owned carry then throw packet sequence required")
        hashes = [hashlib.sha256(body).hexdigest() for _, body in packets]
        record = next(
            (
                row
                for row in proof.get("cases", ())
                if row.get("packets_sha256") == hashes
            ),
            None,
        )
        if (
            record is None
            or record.get("complete") is not True
            or type(record.get("returncode")) is not int
            or record["returncode"] != 0
            or record["native"].get("completed_normally") is not True
        ):
            raise ValueError(
                "Exact successful owned carry/throw frames absent from native proof"
            )
        if (
            not isinstance(initial_projection, dict)
            or set(initial_projection) != {"positions", "relations"}
            or not isinstance(projection, dict)
            or set(projection) != {"positions", "relations"}
        ):
            raise ValueError("Explicit same-scope public positions/relations required")
        positions = {
            str(actor): list(cell)
            for actor, cell in initial_projection["positions"].items()
        }
        relations = {
            str(actor): dict(row)
            for actor, row in initial_projection["relations"].items()
        }
        if set(positions) != set(relations):
            raise ValueError("Recipient actor registration/relations differ")
        stages = record["native"]["stages"]
        if len(stages) != 2:
            raise ValueError("Native original carry callbacks incomplete")
        fight, actions = None, []
        for index, ((opcode, body), native) in enumerate(zip(packets, stages)):
            decoded = decode_packet(opcode, body)
            if (
                opcode != 12613
                or decoded["kind"] != "effect"
                or decoded["immediate"] is not False
            ):
                raise ValueError(
                    "One non-immediate native application per carry stage required"
                )
            effect = decoded["effect"]
            if effect["family"] != (334 if index == 0 else 333):
                raise ValueError("Native carrying family order differs")
            if fight is None:
                fight = decoded["fight"]
            if fight != decoded["fight"]:
                raise ValueError("Carry lifecycle fight identity differs")
            if (
                native.get("family") != effect["family"]
                or native.get("uid") != effect["uid"]
                or native.get("generic_effect") != effect["definition"]
                or native.get("caster") != effect["caster"]
                or native.get("action_id") != decoded["action"]
                or native.get("queue_drained") is not True
                or native.get("native_completed_action_ids") != [decoded["action"]]
            ):
                raise ValueError(
                    "Native carrying runner/owner/action/completion identity differs"
                )
            if native["before"] != dict(positions=positions, relations=relations):
                raise ValueError(
                    "Explicit initial native owner/position relationships differ"
                )
            caster = str(effect["caster"])
            if caster not in positions:
                raise ValueError("Native carrying caster unregistered")
            if index == 0:
                target = str(effect["target"])
                if target not in positions or target == caster:
                    raise ValueError(
                        "Native carried actor identity unregistered or self-owned"
                    )
                if any(
                    relations[actor] != dict(carrier=None, carried=None)
                    for actor in (caster, target)
                ):
                    raise ValueError("Native carrying relationships already occupied")
                positions[target] = list(positions[caster])
                relations[caster]["carried"] = int(target)
                relations[target]["carrier"] = int(caster)
            else:
                target_id = relations[caster]["carried"]
                target = str(target_id)
                if (
                    target_id is None
                    or target not in relations
                    or relations[target]["carrier"] != int(caster)
                    or effect["target"] not in (None, target_id)
                ):
                    raise ValueError(
                        "Native nullable throw target does not match reciprocal carried actor"
                    )
                positions[target] = list(
                    _cell(_field(effect["additional"], 15, 2, required=True))
                )
                relations[caster]["carried"] = None
                relations[target]["carrier"] = None
            if native["after"] != dict(positions=positions, relations=relations):
                raise ValueError(
                    "Independent byte-derived carrying view differs from original native callback"
                )
            actions.append(decoded["action"])
        expected = dict(
            positions={
                str(actor): list(cell)
                for actor, cell in projection["positions"].items()
            },
            relations={
                str(actor): dict(row) for actor, row in projection["relations"].items()
            },
        )
        view = dict(positions=positions, relations=relations)
        matches = view == expected
        return dict(
            base,
            qualified=matches,
            native_case=record["id"],
            native_proof_sha256=proof_hash,
            recipient=dict(role=recipient.role, generation=recipient.generation),
            executed=view,
            action_ids=actions,
            pending=False,
            reasons=[] if matches else ["permitted_carry_projection_differs"],
        )
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        return dict(base, reasons=[str(error)])
