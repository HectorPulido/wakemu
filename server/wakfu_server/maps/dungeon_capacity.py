"""Dungeon roster bounds inherited from existing combat and party admission."""
# combat_placement_cells.generate limits total placement actor seeds to 127.
MAX_PLACEMENT_ACTORS = 127
# player_parties._policy validates configured party membership at at most six.
MAX_PARTY_PLAYERS = 6
MAX_DUNGEON_MONSTERS = MAX_PLACEMENT_ACTORS - MAX_PARTY_PLAYERS
# Reserve a full block for each monotonically allocated dungeon group identity.
DUNGEON_ACTOR_ID_STRIDE = 128
