"""Preflight/commit transport retaining actual Actor/Qq objects at publication."""
from copy import deepcopy
from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
from .combat_pointer_qi_spatialowned import validate_spatial_record


class PointerCommitBinding:
    def __init__(self, candidate):
        checkpoint = getattr(candidate, "native_pointer_checkpoint", None)
        if not isinstance(checkpoint, NativePointerCheckpoint):
            raise ValueError("Typed native QI candidate required")
        qi = checkpoint.validate(candidate)
        collection = getattr(candidate, "native_owned_spatial_effects", {})
        for row in collection.values():
            validate_spatial_record(candidate, row)
        self.candidate = candidate
        self.checkpoint = checkpoint
        self.collection = collection
        self.actors = {identity: obj.actor for identity, obj in qi.objects.items()}
        self.areas = {identity: obj.row for identity, obj in qi.area_objects.items()}

    def stage(self, destination):
        """Complete every fallible copy before the caller mutates live actors."""
        self.checkpoint.validate(self.candidate)
        for row in self.collection.values():
            validate_spatial_record(self.candidate, row)
        memo = {id(self.candidate): destination}
        for identity, actor in self.actors.items():
            # Existing identities retain their actual live object. A newly
            # created summon is adopted as the original candidate object.
            actual = destination.actors.get(identity, actor)
            memo[id(actor)] = actual
        # Area-boundary adoption replaces the destination's area collections
        # with these exact candidate Qq rows, preserving their identity.
        for row in self.areas.values():
            memo[id(row)] = row
        checkpoint, collection = deepcopy((self.checkpoint, self.collection), memo)
        self.staged = (destination, checkpoint, collection)
        return self

    def publish(self):
        """Non-fallible publication following the existing actor commit."""
        destination, checkpoint, collection = self.staged
        destination.native_pointer_checkpoint = checkpoint
        destination.native_owned_spatial_effects = collection

    def adopt(self, destination):
        self.stage(destination)
        self.publish()


def prepare_pointer_commit(candidate):
    if not hasattr(candidate, "native_pointer_checkpoint"):
        return None
    return PointerCommitBinding(candidate)
