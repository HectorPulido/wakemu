"""Wakemu policy for the native effect-completion PR boundary.

The client PR implementation dispatches OY presentation callbacks. Wakemu
records the completed running UID and the server's parent UID, then invokes
only explicitly registered, typed Wakemu observers. This is a server policy;
it does not claim to reproduce client OY rendering.
"""
from dataclasses import dataclass


FRESH_POLICY_SOURCE = "wakemu.fresh.pr_notification_policy"


@dataclass(frozen=True)
class PRCompletionNotice:
    running_uid: int
    parent_uid: int | None
    effect_reference: int
    effect_class: int
    caster_id: int
    target_id: int
    native_parent_index: int | None = None


@dataclass(frozen=True)
class PRCompletionWatcher:
    """Typed Wakemu observer, kept in OY registration order.

    Native eVn.i/eVn.j select two independent callback slots per OY; Wakemu
    observers state explicitly which slots they implement.
    """

    on_i: object = None
    on_j: object = None

    def __post_init__(self):
        if self.on_i is None and self.on_j is None:
            raise ValueError("PR completion watcher needs a typed callback")
        if (self.on_i is not None and not callable(self.on_i)) or (
            self.on_j is not None and not callable(self.on_j)
        ):
            raise ValueError("PR completion watcher callbacks must be callable")


def fresh_pr_completion_authority():
    """Create the explicit no-client-watcher policy for a fresh Wakemu fight."""
    return {
        "source": FRESH_POLICY_SOURCE,
        "watchers": [],
        "completed": [],
    }


class WakemuPRCompletionPolicy:
    """Dispatch a typed completion notice through available Wakemu watchers."""

    def __init__(self, authority):
        if (
            not isinstance(authority, dict)
            or authority.get("source") != FRESH_POLICY_SOURCE
            or not isinstance(authority.get("watchers"), list)
            or not isinstance(authority.get("completed"), list)
        ):
            raise ValueError("Unknown Wakemu PR notification policy")
        self.authority = authority

    def notify(self, notice):
        if (
            not isinstance(notice, PRCompletionNotice)
            or type(notice.running_uid) is not int
            or notice.running_uid <= 0
            or (notice.parent_uid is not None and type(notice.parent_uid) is not int)
        ):
            raise ValueError("Invalid typed PR completion notice")
        records = self.authority["completed"]
        if any(record.get("running_uid") == notice.running_uid for record in records):
            return False
        watchers = tuple(self.authority["watchers"])
        if any(not isinstance(watcher, PRCompletionWatcher) for watcher in watchers):
            raise ValueError("Unknown Wakemu PR watcher record")
        # Native bfb.c invokes registered observers in source-list order, then
        # records the runner UID. Keep that failure boundary in this policy.
        for watcher in watchers:
            if watcher.on_i is not None:
                watcher.on_i(notice)
            if watcher.on_j is not None:
                watcher.on_j(notice)
        records.append(
            {
                "running_uid": notice.running_uid,
                "parent_uid": notice.parent_uid,
                "effect_reference": notice.effect_reference,
                "effect_class": notice.effect_class,
                "caster_id": notice.caster_id,
                "target_id": notice.target_id,
                "native_parent_index": notice.native_parent_index,
            }
        )
        return True
