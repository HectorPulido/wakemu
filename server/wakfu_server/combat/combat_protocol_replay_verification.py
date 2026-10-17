"""Optional independent reconstruction result attached to offline replay output.

The caller supplies the actual recipient stream, permitted domain projection,
and a separately trusted native proof receipt. Dispatch/socket/ACK observations
are deliberately not accepted as execution completion. No gameplay/replay CLI,
serializer, catalog, dynamic symbol or live connection is used here.
"""
from dataclasses import asdict
import hashlib
import json
import struct
from itertools import islice
from pathlib import Path

from .combat_protocol_reconstruction import (
    BlockCompletion,
    EffectContract,
    MAX_BODY,
    MAX_PACKETS,
    Recipient,
    compare_permitted_projection,
    reconstruct_packets,
)


SCHEMA = "wakemu-native-protocol-reconstruction-evidence-v1"
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024


def stream_digest(bootstrap, packets):
    """Bind ordered native bytes, including the declared bootstrap boundary."""
    initial = tuple(islice(iter(bootstrap), MAX_PACKETS + 1))
    updates = tuple(islice(iter(packets), MAX_PACKETS + 1))
    if len(initial) + len(updates) > MAX_PACKETS:
        raise ValueError("Reconstruction stream exceeds bounds")
    value = hashlib.sha256(b"wakemu-recipient-stream-v1\x00")
    value.update(struct.pack(">II", len(initial), len(updates)))
    for opcode, body in (*initial, *updates):
        if (
            type(opcode) is not int
            or not 0 < opcode < 65536
            or type(body) is not bytes
            or len(body) > MAX_BODY
        ):
            raise ValueError("Invalid immutable stream frame")
        value.update(struct.pack(">HI", opcode, len(body)))
        value.update(body)
    return value.hexdigest()


def _json_bytes(raw):
    if type(raw) is not bytes or len(raw) > MAX_EVIDENCE_BYTES:
        raise ValueError("Require bounded immutable evidence bytes")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Evidence must contain an object")
    return result


def load_native_reconstruction_sidecar(path):
    """Read a bounded descriptor plus its two fixed, same-directory receipts.

    No paths or dynamic symbols from the descriptor are imported/executed.
    Trust still requires the separately pinned proof digest at verification.
    """
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise ValueError("Unsafe or oversized native reconstruction sidecar")
    result = _json_bytes(path.read_bytes())
    if (
        result.get("schema") != SCHEMA
        or "proof_bytes" in result
        or "observations_bytes" in result
    ):
        raise ValueError("Unknown native reconstruction sidecar descriptor")
    for key, name in (
        ("proof_bytes", "server-native-proof.json"),
        ("observations_bytes", "server-native-observations.json"),
    ):
        companion = path.parent / name
        if companion.is_symlink() or companion.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("Unsafe or oversized native proof companion")
        result[key] = companion.read_bytes()
    return result


def verify_replay_projection(
    *,
    bootstrap,
    packets,
    recipient,
    permitted_projection,
    native_evidence=None,
    trusted_native_proof_sha256=None
):
    """Verify only independently covered bytes/components; otherwise unqualified.

    A native_evidence mapping contains schema, recipient, stream_sha256,
    proof_bytes, observations_bytes, effect_contracts and block_completions.
    The caller pins the receipt digest independently (for example a reviewed
    validation manifest); merely supplying a matching digest inside a sidecar
    does not establish trust. Native proof fixtures cover each exact payload,
    and every completion must occur in original-consumer callback observations.
    """
    base = dict(
        available=native_evidence is not None,
        qualified=False,
        scope="partial-independent-recipient-model",
        client_receipt_qualified=False,
        rendering_qualified=False,
        reasons=[],
    )
    if native_evidence is None:
        return dict(base, reasons=["native_reconstruction_evidence_missing"])
    try:
        if not isinstance(recipient, Recipient) or not isinstance(
            native_evidence, dict
        ):
            raise ValueError("Explicit recipient and evidence mapping required")
        if native_evidence.get("schema") != SCHEMA:
            raise ValueError("Unknown native reconstruction evidence schema")
        expected_recipient = dict(role=recipient.role, generation=recipient.generation)
        if native_evidence.get("recipient") != expected_recipient:
            raise ValueError("Native evidence recipient role/generation differs")
        initial = tuple(islice(iter(bootstrap), MAX_PACKETS + 1))
        updates = tuple(islice(iter(packets), MAX_PACKETS + 1))
        digest = stream_digest(initial, updates)
        if native_evidence.get("stream_sha256") != digest:
            raise ValueError("Native evidence ordered packet stream differs")
        raw = native_evidence.get("proof_bytes")
        proof = _json_bytes(raw)
        proof_digest = hashlib.sha256(raw).hexdigest()
        if (
            not trusted_native_proof_sha256
            or trusted_native_proof_sha256 != proof_digest
        ):
            raise ValueError("Native proof receipt is not independently pinned")
        if (
            proof.get("schema") != "wakemu-independent-server-protocol-proof-v1"
            or proof.get("complete") is not True
            or proof.get("returncode") != 0
            or proof.get("compile_returncode") != 0
            or proof.get("source_stable") is not True
            or proof.get("instrumentation") != "none"
            or not isinstance(proof.get("classpath"), dict)
            or "client/lib/wakfu-client.jar" not in proof["classpath"]
            or "sniffer/java/VerifyServerCombatReconstructionPilot.java"
            not in proof.get("source", {})
        ):
            raise ValueError(
                "Native proof is incomplete or not the independent server-byte boundary"
            )
        observations_raw = native_evidence.get("observations_bytes")
        observations = _json_bytes(observations_raw)
        if hashlib.sha256(observations_raw).hexdigest() != proof.get(
            "observations_sha256"
        ):
            raise ValueError("Native callback observations differ from proof")
        if observations.get("completed_normally") is not True:
            raise ValueError("Native consumer did not complete normally")
        supported_hashes = set(proof.get("fixtures", {}).values())
        if any(
            hashlib.sha256(body).hexdigest() not in supported_hashes
            for _, body in (*initial, *updates)
        ):
            raise ValueError("Packet bytes were not consumed by this native proof")
        # Known opcode-body pairs also bind packet identity; a matching blob
        # reused under another opcode is not a covered native frame.
        fixture_pairs = {
            (int(name.split("-", 1)[0].split(".", 1)[0]), value)
            for name, value in proof.get("fixtures", {}).items()
        }
        if any(
            (opcode, hashlib.sha256(body).hexdigest()) not in fixture_pairs
            for opcode, body in (*initial, *updates)
        ):
            raise ValueError("Packet opcode differs from independent native input")
        contracts = {}
        for item in native_evidence.get("effect_contracts", ()):
            if not isinstance(item, dict):
                raise ValueError("Invalid independent effect contract fact")
            family = item.get("family")
            native = observations.get("state310" if family == 310 else "area315", {})
            facts = native.get("native_contract", {})
            if (
                family not in (310, 315)
                or facts.get("family") != family
                or facts.get("generic_effect") != item.get("definition")
                or facts.get("retained_before_application") is not item.get("retained")
                or facts.get("observation_registers")
                is not item.get("observation_registers")
                or facts.get("manager_registered_after_application") is not True
            ):
                raise ValueError(
                    "Effect contract was not established by original native consumer"
                )
            key = (item["definition"], family)
            if key in contracts:
                raise ValueError("Duplicate independent native effect contract")
            contracts[key] = EffectContract(
                family, item["retained"], item["observation_registers"], proof_digest
            )
        completed = observations.get("native_completed_action_ids", ())
        if not isinstance(completed, list) or not all(
            type(action) is int for action in completed
        ):
            raise ValueError("Missing actual original-consumer completion identities")
        requested = []
        witnesses = []
        for item in native_evidence.get("block_completions", ()):
            if (
                not isinstance(item, dict)
                or item.get("source") != "original-native-queue-callback"
            ):
                raise ValueError("Dispatch or ACK is not native execution completion")
            actions = tuple(item.get("action_ids", ()))
            requested.extend(actions)
            witnesses.append(
                BlockCompletion(item["block_index"], actions, proof_digest)
            )
        # The proof may cover several independent case queues. This sidecar
        # must select an ordered subsequence of observed callbacks, without
        # inventing repetitions or movement completion absent from that trace.
        cursor = 0
        for action in requested:
            while cursor < len(completed) and completed[cursor] != action:
                cursor += 1
            if cursor == len(completed):
                raise ValueError(
                    "Completion identity absent from original native callbacks"
                )
            cursor += 1
        reconstruction = reconstruct_packets(
            initial,
            updates,
            recipient=recipient,
            effect_contracts=contracts,
            completions=witnesses,
        )
        comparison = compare_permitted_projection(
            reconstruction, recipient=recipient, projection=permitted_projection
        )
        return dict(
            base,
            qualified=comparison["matches"],
            matches=comparison["matches"],
            reasons=[]
            if comparison["matches"]
            else ["modeled_projection_not_converged"],
            native_proof_sha256=proof_digest,
            stream_sha256=digest,
            differences=list(comparison["differences"]),
            pending=comparison["pending"],
            findings=[asdict(item) for item in comparison["findings"]],
        )
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        return dict(base, reasons=[str(error)])


def attach_replay_reconstruction(replay_output, **arguments):
    """Add optional verification without changing the existing replay outcome."""
    if not isinstance(replay_output, dict):
        raise ValueError("Existing replay result must be a mapping")
    return dict(
        replay_output, protocol_reconstruction=verify_replay_projection(**arguments)
    )
