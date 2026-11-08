"""Incremental primitive root graph; payload authority remains with consumers.

Every input is supplied by a mutation gateway, not discovered by a query-time
population scan. Unknown root tokens disable collection until repaired.
"""
from collections import Counter
from .combat_retired_area_frontier import retired_area_frontier


class RetiredAreaIndex:
    def __init__(self):
        self.owners = {}
        self.inbound = {}
        self.roots = Counter()
        self.active = set()
        self.protected = set()
        self.retired_order = {}
        self.next_order = 0
        self.dirty = set()
        self.tokens = {}
        self.opaque = set()

    def root(self, token, values):
        """Replace one producer's root multiset; None means unverified input."""
        previous = self.tokens.pop(token, Counter())
        self.opaque.discard(token)
        if values is None:
            self.opaque.add(token)
            current = Counter()
        else:
            current = Counter(values)
            if any(
                type(identity) is not int or type(count) is not int or count < 0
                for identity, count in current.items()
            ):
                raise ValueError("Root gateways require exact identity counts")
            if current:
                self.tokens[token] = current
        for identity in previous.keys() | current.keys():
            old = self.roots.get(identity, 0)
            new = old - previous.get(identity, 0) + current.get(identity, 0)
            if new:
                self.roots[identity] = new
            else:
                self.roots.pop(identity, None)
            if bool(old) != bool(new):
                self.dirty.add(identity)

    def area(self, identity, owner, *, active, retired, protected, verified=True):
        """Publish current actual map membership/edge/lease for one area UID."""
        if type(identity) is not int:
            raise ValueError("Area gateways require exact integer identity")
        token = ("area", identity)
        self.opaque.discard(token)
        if (
            not verified
            or (owner is not None and type(owner) is not int)
            or active
            and retired
        ):
            self.opaque.add(token)
            return
        old_owner = self.owners.get(identity)
        existed = identity in self.owners
        if existed and old_owner is not None:
            children = self.inbound.get(old_owner)
            if children is not None:
                children.discard(identity)
                if not children:
                    del self.inbound[old_owner]
        self.dirty.add(identity)
        if old_owner is not None:
            self.dirty.add(old_owner)
        self.dirty.update(self.inbound.get(identity, ()))
        if not active and not retired:
            self.owners.pop(identity, None)
            self.active.discard(identity)
            self.protected.discard(identity)
            self.retired_order.pop(identity, None)
            return
        self.owners[identity] = owner
        if owner is not None:
            self.inbound.setdefault(owner, set()).add(identity)
            self.dirty.add(owner)
        if active:
            self.active.add(identity)
        else:
            self.active.discard(identity)
        if protected:
            self.protected.add(identity)
        else:
            self.protected.discard(identity)
        if retired:
            if identity not in self.retired_order:
                self.retired_order[identity] = self.next_order
                self.next_order += 1
        else:
            self.retired_order.pop(identity, None)

    def plan(self):
        """Return ordered retired deletions, or None if any producer is opaque."""
        if self.opaque:
            return None
        prunable, examined = retired_area_frontier(
            owners=self.owners,
            inbound=self.inbound,
            roots=self.roots,
            active=self.active,
            protected=self.protected,
            dirty=self.dirty,
        )
        self.dirty.difference_update(examined)
        # Non-area roots have no reachable outgoing Qq edge. Do not retain an
        # ever-growing journal of historical fighter IDs.
        for identity in tuple(self.dirty):
            if identity not in self.owners:
                self.dirty.discard(identity)
        return tuple(
            sorted(
                (identity for identity in prunable if identity in self.retired_order),
                key=self.retired_order.__getitem__,
            )
        )
