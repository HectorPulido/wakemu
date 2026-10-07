"""Post-commit publisher adapter for the native pet-feeding request.

The caller owns request routing and socket cleanup. A send failure happens
after the durable transaction has committed and must not be retried blindly;
the caller should close that connection so the next world bootstrap restores
the authoritative inventory snapshot.
"""
from . import mount_feeding


def prepare(store, account_id, generation, character_id, body, *, in_fight):
    """Commit the domain operation without sending packets.

    Keeping this separate lets a dispatcher catch validation errors without
    accidentally treating a post-commit publisher exception as a rejection.
    """
    return mount_feeding.feed(
        store,
        account_id,
        generation,
        character_id,
        body,
        in_fight=in_fight,
    )


def publish_result(result, callback):
    """Publish the already-committed ordered packet batch exactly once."""
    if not callable(callback):
        raise ValueError("Feeding packet publisher is required")
    packets = result["packets"]
    if packets:
        callback(packets)
    return result


def handle(store, account_id, generation, character_id, body, *, in_fight, publish):
    if not callable(publish):
        raise ValueError("Feeding packet publisher is required")
    result = prepare(
        store,
        account_id,
        generation,
        character_id,
        body,
        in_fight=in_fight,
    )
    return publish_result(result, publish)
