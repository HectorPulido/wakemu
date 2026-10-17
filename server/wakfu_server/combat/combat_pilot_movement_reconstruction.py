"""Exact native movement callback evidence for the independent pilot model."""
from dataclasses import asdict
import hashlib
import json

from .combat_protocol_reconstruction import (
    BlockCompletion,
    Recipient,
    compare_permitted_projection,
    decode_packet,
    reconstruct_packets,
)
from .combat_protocol_replay_verification import stream_digest
from .combat_pilot_protocol_comparison import _bounded_stream


def verify_native_movement_delivery(
    *, bootstrap, packets, recipient, projection, proof_bytes, trusted_proof_sha256
):
    """Use actual original timer callbacks, never dispatch/ACK, as witnesses.

    Supported delivery is explicit compact bootstrap/placement followed by one
    mode0 movement and native fences. The movement must have its own exact
    native proof case, including original actor position and executed endpoint.
    Renderer reset/duration fixtures remain disclosed in the native receipt.
    """
    result = dict(
        qualified=False,
        rendering_qualified=False,
        scope="partial-independent-recipient-model; headless native timer/FIFO",
        reasons=[],
    )
    try:
        if (
            type(proof_bytes) is not bytes
            or len(proof_bytes) > 4 * 1024 * 1024
            or not isinstance(recipient, Recipient)
        ):
            raise ValueError("Bounded native proof and explicit recipient required")
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
        if not trusted_proof_sha256 or proof_hash != trusted_proof_sha256:
            raise ValueError("Native movement proof is not independently pinned")
        proof = json.loads(proof_bytes)
        if (
            proof.get("schema") != "wakemu-pilot-movement-native-proof-v1"
            or proof.get("complete") is not True
            or proof.get("source_stable") is not True
            or type(proof.get("compile_returncode")) is not int
            or proof["compile_returncode"] != 0
            or proof.get("instrumentation") != "none"
            or "client/lib/wakfu-client.jar" not in proof.get("classpath", {})
            or "sniffer/java/VerifyPilotMovementQueue.java"
            not in proof.get("source", {})
        ):
            raise ValueError("Native movement proof incomplete or wrong boundary")
        initial, updates = _bounded_stream(bootstrap, packets)
        # Validate frame identities/types and the explicit bootstrap boundary.
        digest = stream_digest(initial, updates)
        base = reconstruct_packets(initial, (), recipient=recipient)
        if base.findings or not base.complete:
            raise ValueError("Initial recipient model is unresolved")
        positions = {
            actor: row["cell"] for actor, row in base.executed.positions.items()
        }
        contracts = proof.get("cases", ())
        actions, completions, selected = [], [], []
        for opcode, payload in updates:
            decoded = decode_packet(opcode, payload)
            if decoded["kind"] == "fence":
                if actions:
                    completions.append(
                        BlockCompletion(len(completions), tuple(actions), proof_hash)
                    )
                    actions = []
                continue
            if decoded["kind"] != "movement" or decoded["mode"] != 0:
                raise ValueError("Delivery outside native mode0 movement proof")
            candidates = [
                record
                for record in contracts
                if record.get("opcode") == opcode
                and record.get("payload_sha256") == hashlib.sha256(payload).hexdigest()
            ]
            record = next(
                (
                    record
                    for record in candidates
                    if tuple(record.get("initial_position", ()))
                    == positions.get(decoded["actor"])
                ),
                None,
            )
            if record is None:
                raise ValueError(
                    "Movement bytes/initial actor position absent from native proof"
                )
            native = record.get("native", {})
            if (
                record.get("complete") is not True
                or type(record.get("returncode")) is not int
                or record["returncode"] != 0
                or native.get("completed_normally") is not True
                or native.get("queue_drained") is not True
                or native.get("action_id") != decoded["action"]
                or native.get("actor_id") != decoded["actor"]
                or native.get("native_completed_action_ids") != [decoded["action"]]
                or native.get("native_path")
                != [list(point) for point in decoded["path"]]
                or tuple(native.get("executed_position", ()))
                != tuple(decoded["path"][-1])
            ):
                raise ValueError("Native movement identity/path/completion mismatch")
            actions.append(decoded["action"])
            positions[decoded["actor"]] = tuple(native["executed_position"])
            selected.append(record["id"])
        if len(selected) != 1:
            raise ValueError("Native proof covers one isolated movement queue per case")
        reconstruction = reconstruct_packets(
            initial, updates, recipient=recipient, completions=completions
        )
        compared = compare_permitted_projection(
            reconstruction, recipient=recipient, projection=projection
        )
        return dict(
            result,
            qualified=compared["matches"],
            stream_sha256=digest,
            native_proof_sha256=proof_hash,
            native_cases=selected,
            differences=list(compared["differences"]),
            pending=compared["pending"],
            findings=[asdict(item) for item in reconstruction.findings],
            reasons=[] if compared["matches"] else ["recipient_model_not_converged"],
        )
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        return dict(result, reasons=[str(error)])
