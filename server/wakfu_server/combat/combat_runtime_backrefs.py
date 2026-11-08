"""Non-owning edges inside a factory-owned synchronous effect runtime."""
from copy import deepcopy
from weakref import ref


class FactoryOwnerReference:
    def __init__(self, owner):
        self._reference = ref(owner)
        self._escaped_owner = None

    def get(self):
        owner = self._reference()
        if owner is None:
            raise RuntimeError("Native runtime owner has expired")
        return owner

    def __deepcopy__(self, memo):
        owner = self._reference()
        clone = type(self).__new__(type(self))
        memo[id(self)] = clone
        if owner is None:
            # Retained spatial disposal keeps its handler after the synchronous
            # dispatcher is gone; copying that handler must not resurrect it.
            clone._reference = self._reference
            clone._escaped_owner = None
            return clone
        if id(owner) in memo:
            target = memo[id(owner)]
            clone._escaped_owner = None
        else:
            # Copying a component independently is an explicit ownership
            # escape. Preserve its actual copied runtime, not the old owner.
            target = deepcopy(owner, memo)
            clone._escaped_owner = target
        clone._reference = ref(target)
        return clone


class FactoryMethod:
    def __init__(self, method):
        self.owner = FactoryOwnerReference(method.__self__)
        self.function = method.__func__

    def __call__(self, *args, **kwargs):
        return self.function(self.owner.get(), *args, **kwargs)


def resolved_owner(value):
    return value.get() if type(value) is FactoryOwnerReference else value


class FactoryCallback:
    """Copyable callback arguments; unlike closures, owner handles follow memo."""

    def __init__(self, function, *arguments):
        self.function = function
        self.arguments = arguments

    def __call__(self, *args, **kwargs):
        arguments = tuple(resolved_owner(value) for value in self.arguments)
        return self.function(*arguments, *args, **kwargs)
