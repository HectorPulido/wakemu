"""Explicit owned sources for native timed-effect expiration."""

from copy import deepcopy


class OwnedExpirationFactory:
    """Create the ordinary native factory without a selected-session closure."""

    def __init__(
        self,
        *,
        characters,
        monsters,
        decks,
        actor_id,
        fight_start=True,
        area_callbacks=False,
    ):
        if (
            type(actor_id) is not int
            or actor_id not in characters
            or characters[actor_id].get("id") != actor_id
            or set(characters) != set(decks)
        ):
            raise ValueError("Missing owned expiration character/deck authority")
        self.characters, self.monsters, self.decks = deepcopy(
            (characters, monsters, decks)
        )
        self.actor_id = actor_id
        self.fight_start = fight_start
        self.area_callbacks = area_callbacks

    def turn_start(self, preview, **boundary):
        from .combat_server_spell import prepare_server_turn_start

        actor_id = boundary["actor_id"]
        source = self.characters.get(actor_id, self.characters[self.actor_id])
        deck = self.decks.get(actor_id, self.decks[self.actor_id])
        return prepare_server_turn_start(
            source,
            self.monsters,
            preview,
            deck,
            native_events=self.fight_start,
            area_callbacks=self.area_callbacks,
            player_characters=self.characters,
            deck_blobs=self.decks,
            **boundary,
        )

    def turn_end(self, preview, *, actor_id, action_id):
        from .combat_server_spell import prepare_server_turn_end

        actor = preview.actors[actor_id]
        source = self.characters.get(actor_id, self.characters[self.actor_id])
        deck = self.decks.get(actor_id, self.decks[self.actor_id])
        return prepare_server_turn_end(
            source,
            self.monsters,
            preview,
            deck,
            actor_id=actor_id,
            action_id=action_id,
            player_characters=self.characters,
            deck_blobs=self.decks,
        )

    def __call__(self, *, action_id):
        from .combat_server_spell import server_runtime

        return server_runtime(
            self.characters[self.actor_id],
            self.monsters,
            self.decks[self.actor_id],
            action_id=action_id,
            critical=False,
            player_characters=self.characters,
            deck_blobs=self.decks,
        )[0]
