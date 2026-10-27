"""Scale earned ordinary bundles without adding probability/quantity draws."""
from dataclasses import asdict, replace


class ReceiptIdentities:
    """Allocate unused native receipt coordinates, never another loot roll."""

    def __init__(self, decisions):
        self.used = {
            (d.defeated_actor_id, d.drop_row_index, d.attempt_index) for d in decisions
        }
        self.next, self.first_row = {}, {}
        for actor, row, attempt in self.used:
            self.first_row[actor] = max(self.first_row.get(actor, 0), row + 1)

    def take(self, actor, *, attempt_base=0):
        # Native owner and companion report lines occupy separate1000-attempt
        # bands. Quantity segments stay on their actual originating line.
        if type(attempt_base) is not int or not 0 <= attempt_base <= 31000:
            raise ValueError("Invalid Rift delivery attempt band")
        identity = actor, attempt_base
        start = self.next.get(identity, self.first_row.get(actor, 0) * 1000)
        for offset in range(len(self.used) + 1):
            position = (start + offset) % (32768 * 1000)
            row, within = divmod(position, 1000)
            attempt = attempt_base + within
            key = (actor, row, attempt)
            if key not in self.used:
                self.used.add(key)
                self.next[identity] = position + 1
                return row, attempt
        raise ValueError("Rift delivery receipt namespace exhausted")


def scale_ordinary(decisions, multiplier):
    """Preserve accepted native rolls and split large quantities into wire stacks."""
    if type(multiplier) is not int or not 1 <= multiplier <= 100000:
        raise ValueError("Invalid earned Rift quantity multiplier")
    decisions = tuple(decisions)
    identities = ReceiptIdentities(decisions)
    output, ledger = [], []
    for decision in decisions:
        if not decision.success:
            output.append(decision)
            continue
        if type(decision.quantity) is not int or not 1 <= decision.quantity <= 32767:
            raise ValueError("Invalid original Rift common drop quantity")
        remaining, segments = decision.quantity * multiplier, []
        first = True
        while remaining:
            quantity = min(32767, remaining)
            row, attempt = (
                (decision.drop_row_index, decision.attempt_index)
                if first
                else identities.take(
                    decision.defeated_actor_id,
                    attempt_base=(decision.attempt_index // 1000) * 1000,
                )
            )
            output.append(
                replace(
                    decision,
                    drop_row_index=row,
                    attempt_index=attempt,
                    quantity=quantity,
                    quantity_min=quantity,
                    quantity_max=quantity,
                    quantity_draw_numerator=0,
                )
            )
            segments.append(
                dict(drop_row_index=row, attempt_index=attempt, quantity=quantity)
            )
            remaining -= quantity
            first = False
        original = asdict(decision)
        for field in ("base_probability", "raw_probability", "effective_probability"):
            original[field] = str(original[field])
        ledger.append(dict(original=original, multiplier=multiplier, segments=segments))
    return tuple(output), ledger
