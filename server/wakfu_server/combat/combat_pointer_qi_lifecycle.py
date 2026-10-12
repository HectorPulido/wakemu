"""Private eYa lifecycle for exact sealed, indefinite eVy definitions.

This is a typed source closure, not a generic timer or a published live handler.
Qe side-effect callbacks are explicit dependencies supplied by the consumer.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from .combat_pointer_qi_actor import ActualRetained937
from .combat_pointer_qi_hashset import qf_clear_order

# The file is in the preceding sealed investigation, not this new model directory.
_SOURCE = Path(__file__).with_name("native-spatial937-source.json")
_SOURCE_SHA256 = "6da0b80e36744431d8418f4e683037954df8021a9e313e730c33ffda1cadad66"


@dataclass(frozen=True)
class NativePK937:
    reference: int
    level: int
    source_hash: str
    duration: int

    @classmethod
    def from_sealed(cls, reference, level, definition):
        if (
            type(reference) is not int
            or type(level) is not int
            or not 0 <= level <= 32767
        ):
            raise ValueError("Missing native PK reference/short effect level")
        raw = _SOURCE.read_bytes()
        if hashlib.sha256(raw).hexdigest() != _SOURCE_SHA256:
            raise ValueError("Sealed family937 PK source changed")
        expected = json.loads(raw).get(str(reference))
        if expected is None or json.dumps(definition, sort_keys=True) != json.dumps(
            expected, sort_keys=True
        ):
            raise ValueError("PK does not match the sealed native effect")
        fields = definition["native_timing_definition"]
        # Exact constant eVy.en(short) branch; no guessed duration or scheduler.
        if (
            definition["native_definition_class"] != "eVy"
            or definition["native_execution_mode"] != 2
            or fields["ryF"] != 0.0
            or fields["ryH"] != 0
            or fields["ryI"] != 0.0
        ):
            raise ValueError("Unqualified native eVy timing arithmetic")
        duration = fields["ryE"]
        # Both actual family937 definitions have duration -1 with no growth.
        if (
            definition["effect_class"] != 937
            or definition["native_effect_flags"] != [17]
            or duration != -1
        ):
            raise ValueError("Unqualified family937 retained timing domain")
        return cls(reference, level, _SOURCE_SHA256, duration)

    def validate(self):
        definition = json.loads(_SOURCE.read_bytes()).get(str(self.reference))
        if self != type(self).from_sealed(self.reference, self.level, definition):
            raise ValueError("Forged native PK authority")


class NativeRunner937:
    """Exact negative-Tt retention branch, with actual retained PV/PN operands."""

    def __init__(self, spatial, pk, hooks):
        if not isinstance(spatial, ActualRetained937) or not isinstance(
            pk, NativePK937
        ):
            raise ValueError("Missing actual spatial runner/native PK")
        pk.validate()
        if not all(
            callable(getattr(hooks, name, None))
            for name in (
                "publish_execution",
                "log_exception",
                "after_application",
                "before_dispose",
                "release",
            )
        ):
            raise ValueError("Missing Qe lifecycle callbacks")
        self.spatial, self.pk, self.hooks = spatial, pk, hooks
        self.disposed = False
        self.pooled = False
        self.manager = None

    def apply(self):
        if self.disposed or self.pooled:
            raise ValueError("Disposed or pooled runner cannot execute")
        self.pk.validate()
        rejected = not self.spatial.valid()
        moved = False
        try:
            moved = self.spatial.apply()
        except Exception as error:
            self.hooks.log_exception("c", error)
        # eZR.a sets rEj even when eYa.c calls fRS for invalid context.
        self.spatial.executed = True
        if not rejected:  # rIW is set by eYa.c only on fPL rejection.
            try:
                self.hooks.publish_execution(self)
            except Exception as error:
                self.hooks.log_exception("d", error)
        self.hooks.after_application(self)
        # eZR.bbX is true for native Tt.biT < 0, so Ty retains this branch.
        return moved

    def pool_without_removal(self):
        """Qe.bal -> aWr/bbo, independently of Qe.aW -> bbR.

        Only a proven null-Qf collection boundary may call this operation.
        Clearing represented Qe target/context/PK does not restore QI or emit
        running-effect removal; native pooling does neither operation.
        """
        if self.manager is not None or self.pooled:
            raise ValueError("Missing unregistered native pooling boundary")
        self.spatial.target = None
        self.spatial.context = None
        self.pk = None
        self.pooled = True

    def dispose(self):
        self.spatial.remove_runner()  # Qe.aW: bbR is before disposal hooks.
        self.hooks.before_dispose(self)
        self.disposed = True
        self.hooks.release(self)
        self.spatial.target = None
        self.spatial.context = None


class NativeQf937:
    """Actual LinkedHashMap membership and source-qualified UID snapshot order."""

    def __init__(self):
        self.runners = {}

    def add(self, runner):
        if (
            not isinstance(runner, NativeRunner937)
            or runner.disposed
            or runner.manager is not None
        ):
            raise ValueError("Invalid retained runner registration")
        uid = runner.spatial.uid
        if uid in self.runners:
            raise ValueError("Duplicate running UID")
        qf_clear_order((*self.runners, uid))
        self.runners[uid] = runner
        runner.manager = self

    def clear_native(self):
        """Exact Qf.clear snapshot, current-map relookup, catch and final clear.

        The separately exposed transactional clear() intentionally propagates
        callback failures to its caller's rollback. This entry point preserves
        the installed native manager's catch-and-continue boundary instead.
        """
        order = qf_clear_order(self.runners)
        population = tuple(self.runners.values())
        for uid in order:
            runner = self.runners.get(uid)
            if runner is None:
                continue
            try:
                runner.dispose()
            except Exception as error:
                runner.hooks.log_exception("Qf.clear", error)
        for runner in (*population, *self.runners.values()):
            if runner.manager is self:
                runner.manager = None
        self.runners.clear()

    def clear(self):
        # Validate complete population before any mutation; unknown tree bins reject.
        order = qf_clear_order(self.runners)
        for uid in order:
            self.runners[uid].dispose()
        for runner in self.runners.values():
            runner.manager = None
        self.runners.clear()


from contextlib import contextmanager
from .combat_pointer_qi_transaction import checkpoint, restore


@contextmanager
def retained_spatial_transaction(qi, manager, *, forecast=False):
    """Rollback actual QK/QL and retained-manager state as one private domain.

    External packet/resource/event hooks remain the whole-fight caller's job.
    """
    if not isinstance(manager, NativeQf937):
        raise ValueError("Missing actual retained manager")
    population = tuple(manager.runners.items())
    owned = [runner.spatial for _, runner in population]
    spatial = checkpoint(qi, owned)
    lifecycle = [(runner, runner.disposed, runner.manager) for _, runner in population]

    def rollback():
        for runner in manager.runners.values():
            if all(runner is not original for original, _, _ in lifecycle):
                runner.manager = None
        restore(qi, owned, spatial)
        manager.runners = dict(population)
        for runner, disposed, membership in lifecycle:
            runner.disposed, runner.manager = disposed, membership

    try:
        yield
    except BaseException:
        rollback()
        raise
    else:
        if forecast:
            rollback()
