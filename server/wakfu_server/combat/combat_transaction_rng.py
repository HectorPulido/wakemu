"""Explicit transaction-owned Random checkpoint; no callback introspection."""
from functools import wraps
from random import Random


def transactional_spell_rng(function):
    @wraps(function)
    def execute(*args, **kwargs):
        factory = kwargs.get("runtime_factory")
        owner = getattr(factory, "transaction_rng", None)
        if owner is not None and not isinstance(owner, Random):
            raise ValueError("Unknown spell-transaction RNG owner")
        state = None if owner is None else owner.getstate()
        try:
            return function(*args, **kwargs)
        except BaseException:
            if owner is not None:
                owner.setstate(state)
            raise

    return execute
