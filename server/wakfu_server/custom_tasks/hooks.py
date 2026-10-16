"""Connection-local, post-commit publication policy for native task cards."""
from . import application


class SelectedTaskCards:
    """Never publish credited offscreen heroes into the client's global gift list.

    One instance belongs to one live connection. Its caller serializes calls on
    that connection's dispatcher, invokes after commits, and supplies genuine
    current gift packages explicitly. World delivery fences the captured lease.
    """

    def __init__(self):
        self._published = None
        self._dirty = True
        self.section = "overview"
        self.page = 1

    def select_view(self, section, page):
        from .sections import SECTIONS

        if section not in SECTIONS or type(page) is not int or page < 1:
            raise ValueError("Invalid objective section or page")
        self.section, self.page = section, page
        self._dirty = True

    def needs_refresh(self, account_id, generation, selected_character_id):
        identity = (account_id, generation, selected_character_id)
        return self._dirty or self._published is None or self._published[0] != identity

    def changed(self, selected_character_id, changed_character_ids):
        if selected_character_id in changed_character_ids:
            self._dirty = True

    def refresh(
        self,
        store,
        world,
        account_id,
        generation,
        selected_character_id,
        *,
        ready,
        existing_packages,
        cap_reached,
        definitions=None
    ):
        """Refresh after initial join/reconnect/switch or selected progress change.

        ready must be false during fights, scene loading or a pending hero swap.
        The application returns only after its owned snapshot transaction exits.
        No publication occurs inside a gameplay settlement transaction.
        """
        if type(ready) is not bool:
            raise ValueError("Explicit scene readiness required")
        if not ready:
            return False
        identity = (account_id, generation, selected_character_id)
        if (
            not self._dirty
            and self._published is not None
            and self._published[0] == identity
        ):
            return False
        from . import external

        view = (
            {"section": self.section, "page": self.page} if external.enabled() else {}
        )
        packet = application.publication(
            store,
            account_id,
            generation,
            selected_character_id,
            existing_packages=existing_packages,
            cap_reached=cap_reached,
            definitions=definitions,
            **view,
        )
        if self._published == (identity, packet):
            self._dirty = False
            return False
        # Session selection is rechecked after the snapshot commit, immediately
        # before the existing World generation-fenced network delivery.
        if not store.current_character_session(
            account_id, generation, selected_character_id
        ):
            raise ValueError("Custom task publication belongs to a replaced selection")
        if not world.send_batch_to(selected_character_id, generation, (packet,)):
            return False
        self._published = (identity, packet)
        self._dirty = False
        return True
