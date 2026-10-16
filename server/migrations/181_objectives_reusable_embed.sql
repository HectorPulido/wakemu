-- Reusable player links survive reconnects; game actions still require World.
ALTER TABLE objectives_player_tokens DROP CONSTRAINT objectives_player_tokens_kind_check;
ALTER TABLE objectives_player_tokens ADD CONSTRAINT objectives_player_tokens_kind_check CHECK(kind IN ('launch','session','embed'));
