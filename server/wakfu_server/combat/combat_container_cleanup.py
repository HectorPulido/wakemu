"""Installed eXY1031/1033: force-unapply equipment PL12 or aptitude PL36.

This is the original Qf container operation, not an allocation reset or a
Spirit-specific exemption. All removals reuse central native family callbacks.
"""
from .combat_state_cleanup import RetainedCleanupAuthority, NativeStateCleanupHandler

CONTAINER_FAMILIES = {1031: 12, 1033: 36}


class ContainerTypeCleanupAuthority(RetainedCleanupAuthority):
    def __init__(self, retention, target_id, container_type):
        super().__init__(retention, target_id)
        if (
            type(container_type) is not int
            or container_type not in CONTAINER_FAMILIES.values()
        ):
            raise ValueError(
                "Only installed eXY1031/1033 container contracts are qualified"
            )
        self.container_type = container_type

    def preflight(self):
        from .combat_state_managers import state_manager
        from .combat_periodic_aptitude import removed_container_recipes

        if state_manager(self.fight, self.target_id) is None:
            raise ValueError("Container cleanup lacks the actual target Qf manager")
        entries = self._entries()
        containers = tuple(
            dict.fromkeys(
                key
                for entry in entries
                if (key := self.container(entry)) is not None
                and key.kind == self.container_type
            )
        )
        selected = [
            entry.uid for entry in entries if self.container(entry) in containers
        ]
        view = self.retention.view()
        removal = self.retention.removal(view)
        if removal.view is not view:
            raise ValueError("Container cleanup removal/view ownership changed")
        removal.plan(selected)
        recipes = removed_container_recipes(self.fight, self.target_id, containers)
        return containers, recipes

    def execute(self):
        from .combat_periodic_aptitude import cancel_removed_container_recipes

        containers, recipes = self.preflight()
        # eZV.b(type,true,true) snapshots distinct PLs in Qf iteration order;
        # each PL then removes ordinary runners before its carrier list.
        for key in containers:
            states = []
            for entry in tuple(
                entry for entry in self._entries() if self.container(entry) == key
            ):
                self._set_forced(entry)
                if entry.effect_class == 310:
                    states.append(entry)
                else:
                    self._remove_exact(entry)
            for entry in states:
                self._remove_state(entry, forced=True)
        cancel_removed_container_recipes(self.fight, self.target_id, recipes)


class NativeContainerCleanupHandler(NativeStateCleanupHandler):
    def __init__(self, retention, *, family=1033, **kwargs):
        if type(family) is not int or family not in CONTAINER_FAMILIES:
            raise ValueError("Unknown installed eXY cleanup family")
        self.family = family
        super().__init__(retention, **kwargs)

    def _validate(self, effect, values):
        if effect["effect_class"] != self.family or values["parameters"]:
            raise ValueError("Installed eXY cleanup has no parameters")
        if self.event_lifecycle is None:
            raise ValueError("Container cleanup requires the actual Qe lifecycle")
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Container cleanup lacks original produced event masks")

    def _authority(self, target_id):
        return ContainerTypeCleanupAuthority(
            self.retention, target_id, CONTAINER_FAMILIES[self.family]
        )
