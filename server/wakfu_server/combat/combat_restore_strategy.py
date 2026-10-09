"""eXO.fPz -> eGj.lD -> eGz.pHO; independent of death/population."""


def initialize_restore_strategy(actor):
    # eGz has no constructor write to pHO: the fresh JVM boolean is false.
    actor.native_restore_strategy = dict(source="fresh.eGz.pHO", restored=False)


def triggered_restore_requested(trigger):
    if trigger is None:
        return False
    if not isinstance(trigger, dict):
        raise ValueError("Missing actual eXO source runner")
    bits = trigger.get("event_ids")
    if (
        trigger.get("native_events_verified") is not True
        or not isinstance(bits, (tuple, list))
        or any(type(bit) is not int or bit < 0 for bit in bits)
    ):
        raise ValueError("Missing actual eXO source Qe.oz event set")
    return 1010 in bits


def mark_restored_strategy(actor):
    snapshot = getattr(actor, "native_restore_strategy", None)
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("source") != "fresh.eGz.pHO"
        or type(snapshot.get("restored")) is not bool
    ):
        raise ValueError("Missing actual eGz restore strategy component")
    # Native lD(true) only sets pHO. It neither clears dsA nor changes fdy/QI.
    snapshot["restored"] = True
