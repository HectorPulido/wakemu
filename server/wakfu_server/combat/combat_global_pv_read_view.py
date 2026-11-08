"""One trusted read-only operation's lazily validated native fighter map.

The visibility operation creates and discards this view. It is never attached
to a fight, checkpoint, global registry or cache. Native slot/order/history is
retained; this only shares constructor validation across its pure readers.
"""
from .combat_global_pv_collections import _collections
from .combat_trove_long_map import NativeTroveLongMap


def in_play_actors(fight):
    """Read one stable population without revalidating its map per actor.

    Return a materialized population so the view never survives a callback or
    mutation. Custom participation hooks retain their original semantics.
    """
    from .combat_state import Fight

    if (
        hasattr(fight, "native_global_pv_collections")
        and type(fight) is Fight
        and "_in_play" not in fight.__dict__
        and getattr(fight._in_play, "__func__", None) is Fight._in_play
    ):
        view = NativeGlobalPVReadView(fight)
        return tuple(
            actor
            for actor in fight.actors.values()
            if view.participates(fight, actor.id)
        )
    return tuple(actor for actor in fight.actors.values() if fight._in_play(actor))


class NativeGlobalPVReadView:
    def __init__(self, fight):
        self.fight = fight
        self._fighters = None
        self._token = None
        self._death_index = None
        self._death_token = None

    def _state(self, fight):
        if fight is not self.fight:
            raise ValueError("Native fighter read view belongs to another fight")
        state = _collections(fight)
        raw = state["fighters"]
        # These are only producer invalidation hints. A fresh view always uses
        # the unchanged complete native constructor before serving any lookup.
        token = (
            (
                id(raw),
                id(raw.get("keys")),
                id(raw.get("states")),
                raw.get("size"),
                raw.get("free"),
                raw.get("compact_removes"),
            )
            if isinstance(raw, dict)
            else None
        )
        if self._fighters is None or token != self._token:
            self._fighters = NativeTroveLongMap(raw)
            self._token = token
        return state, self._fighters

    def guards(self, fight, identity):
        state, fighters = self._state(fight)
        if not fighters.contains(identity):
            raise ValueError("Actual native fdy registration required")
        status = state["fighter_status"].get(str(identity))
        if status not in ("IN_PLAY", "OFF_PLAY", "OUT_OF_PLAY"):
            raise ValueError("Missing actual native fighter status")
        return dict(
            baF=status == "IN_PLAY",
            baG=status == "OFF_PLAY",
            baK=status == "OUT_OF_PLAY",
        )

    def registered(self, fight, identity):
        state, fighters = self._state(fight)
        registered = fighters.contains(identity)
        if registered:
            if identity in state["retired_fighters"]:
                raise ValueError("Native fighter is both registered and retired")
            self.guards(fight, identity)
            return True
        if (
            identity in state["retired_fighters"]
            and str(identity) not in state["fighter_status"]
        ):
            return False
        raise ValueError("Missing actual native fighter registration authority")

    def participates(self, fight, identity):
        state, fighters = self._state(fight)
        registered = fighters.contains(identity)
        retired = identity in state["retired_fighters"]
        if not registered:
            if retired and str(identity) not in state["fighter_status"]:
                return False
            raise ValueError("Missing actual native fighter participation authority")
        if retired:
            raise ValueError("Native fighter is both registered and retired")
        return self.guards(fight, identity)["baF"]

    def death_indices(self, fight, actor_id):
        """Select original reverse-scan candidates, never cache proof validity.

        Opaque records remain candidates at their exact original positions so
        unsupported types and malformed events raise only if the original scan
        would reach them. Every selected death still uses the original causal
        previous-event, sequence and owner-transition validation body.
        """
        if fight is not self.fight:
            raise ValueError("Native fighter read view belongs to another fight")
        events = getattr(fight, "events", None)
        if not isinstance(events, list):
            raise ValueError("Missing owned ordinary death registration")
        if type(events) is not list or type(actor_id) not in (
            int,
            float,
            bool,
            str,
            type(None),
        ):
            return None  # Preserve legacy/custom sequence access exactly.
        token = (id(events), len(events))
        if self._death_index is None or token != self._death_token:
            deaths, opaque = {}, []
            for index, event in enumerate(events):
                if type(event) is not dict or type(event.get("kind")) is not str:
                    opaque.append(index)
                elif event["kind"] == "death":
                    identity = event.get("actor_id")
                    if type(identity) in (int, float, bool, str, type(None)):
                        deaths.setdefault(identity, []).append(index)
                    else:
                        opaque.append(index)
            self._death_index = (deaths, opaque)
            self._death_token = token
        deaths, opaque = self._death_index
        return tuple(sorted((*deaths.get(actor_id, ()), *opaque), reverse=True))
