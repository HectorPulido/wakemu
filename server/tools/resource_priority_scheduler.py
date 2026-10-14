"""Bounded search ordering only; all preparation and casting remain real calls."""
from collections import deque
from dataclasses import dataclass


@dataclass
class SceneWork:
    scene: tuple
    context: object = None
    targets: object = None
    target_counts: object = None

    @property
    def resumed(self):
        return self.targets is not None


class PreparationScheduler:
    def __init__(self, scenes):
        self.pending = deque(SceneWork(scene) for scene in scenes)
        self.discovered = []

    def __iter__(self):
        while self.pending:
            yield self.pending.popleft()

    def append(self, scene):
        if not any(work.scene == scene for work in self.pending):
            self.pending.append(SceneWork(scene))

    def prioritize_scenes(self, scenes):
        """Promote valid replacement placements without discarding resumptions."""
        selected = []
        for scene in scenes:
            if any(work.scene == scene for work in selected):
                continue
            existing = next(
                (work for work in self.pending if work.scene == scene), None
            )
            selected.append(existing if existing is not None else SceneWork(scene))
        self.pending = deque(
            work
            for work in self.pending
            if not any(chosen.scene == work.scene for chosen in selected)
        )
        self.pending.extendleft(reversed(selected))

    def prioritize(
        self,
        preparations,
        current,
        remaining,
        context,
        counts,
        *,
        attempts,
        attempt_cap,
        scenes,
        scene_cap
    ):
        """Preempt only when an actual new scene can still be attempted.

        Preserve the current scene's exact remaining target order and per-class
        counts. A resume reuses its verified unmutated context, not another
        scene's prepared actor state. Caps are enforced by the caller unchanged.
        """
        if attempt_cap is not None and attempts >= attempt_cap:
            return False
        if scene_cap is not None and scenes >= scene_cap:
            return False
        new = []
        for preparation in preparations:
            scene = (preparation, current.scene[1])
            if scene in self.discovered or scene == current.scene:
                continue
            self.discovered.append(scene)
            new.append(scene)
        if not new:
            return False
        self.pending = deque(work for work in self.pending if work.scene not in new)
        if remaining:
            self.pending.appendleft(
                SceneWork(current.scene, context, tuple(remaining), counts.copy())
            )
        for scene in reversed(new):
            self.pending.appendleft(SceneWork(scene))
        return True
