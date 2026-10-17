"""Independent old/new recipient observations for the displacement pilot.

Byte equality and modeled parity are regression observations, never native
execution evidence. No completion is synthesized from a fence, ACK or equality.
The optional native verifier separately qualifies each actual input stream.
"""
from dataclasses import asdict
from itertools import islice

from .combat_protocol_reconstruction import MAX_PACKETS, Recipient, reconstruct_packets
from .combat_protocol_replay_verification import stream_digest, verify_replay_projection


def _bounded_stream(bootstrap, packets):
    initial = tuple(islice(iter(bootstrap), MAX_PACKETS + 1))
    updates = tuple(islice(iter(packets), MAX_PACKETS + 1))
    if len(initial) + len(updates) > MAX_PACKETS:
        raise ValueError("Recipient delivery exceeds reconstruction bounds")
    return initial, updates


def decode_recipient_delivery(bootstrap, packets, *, recipient):
    """Decode one explicit recipient generation without inventing witnesses.

    The caller supplies opcode/payload pairs, not framed socket messages. Full
    native snapshots and unsupported movement/effect variants remain findings.
    Received and executed views remain separate even for identical streams.
    """
    initial, updates = _bounded_stream(bootstrap, packets)
    digest = stream_digest(initial, updates)
    reconstruction = reconstruct_packets(initial, updates, recipient=recipient)
    return dict(
        recipient=asdict(recipient),
        stream_sha256=digest,
        decoded=reconstruction.decoded,
        received=asdict(reconstruction.received),
        executed=asdict(reconstruction.executed),
        findings=tuple(asdict(item) for item in reconstruction.findings),
        queue=dict(
            pending_blocks=reconstruction.pending_blocks,
            open_actions=reconstruction.open_actions,
            pending_terminal=reconstruction.pending_terminal,
            deferred_removals=reconstruction.deferred_removals,
        ),
        execution_qualified=False,
    )


def compare_recipient_deliveries(
    *,
    recipient,
    old_bootstrap,
    old_packets,
    new_bootstrap,
    new_packets,
    old_projection,
    new_projection,
    old_native_evidence=None,
    new_native_evidence=None,
    trusted_native_proof_sha256=None
):
    """Compare two isolated outputs and independently verify each public view.

    Keep bootstrap boundaries, action/runner/area identities and packet order
    exact. This API deliberately offers no identity or ordering normalization.
    Explicit permitted projections are mandatory for native qualification.
    """
    if not isinstance(recipient, Recipient):
        raise ValueError("Explicit same-recipient generation required")
    streams = (
        _bounded_stream(old_bootstrap, old_packets),
        _bounded_stream(new_bootstrap, new_packets),
    )
    observations = tuple(
        decode_recipient_delivery(*stream, recipient=recipient) for stream in streams
    )
    differences = tuple(
        key
        for key in ("decoded", "received", "executed", "queue", "findings")
        if observations[0][key] != observations[1][key]
    )
    verifications = tuple(
        verify_replay_projection(
            bootstrap=stream[0],
            packets=stream[1],
            recipient=recipient,
            permitted_projection=projection,
            native_evidence=evidence,
            trusted_native_proof_sha256=trusted_native_proof_sha256,
        )
        for stream, projection, evidence in zip(
            streams,
            (old_projection, new_projection),
            (old_native_evidence, new_native_evidence),
        )
    )
    return dict(
        packet_bytes_equal=streams[0] == streams[1],
        modeled_observations_equal=not differences,
        differences=differences,
        old=observations[0],
        new=observations[1],
        old_native_verification=verifications[0],
        new_native_verification=verifications[1],
        execution_qualified=all(item["qualified"] for item in verifications),
        scope="partial-independent-recipient-model; no rendering qualification",
    )
