"""Recognize an already selected owned character without replaying bootstrap."""


def already_selected_owned_character(store, account_id, generation, character, request):
    """Read the exact current selected lease; never select or grant anything."""
    if (
        type(account_id) is not int
        or account_id <= 0
        or not isinstance(generation, str)
        or not generation
        or not isinstance(character, dict)
        or not isinstance(request, dict)
        or type(character.get("id")) is not int
        or type(character.get("account_id")) is not int
        or type(request.get("character_id")) is not int
        or not isinstance(character.get("name"), str)
        or not isinstance(request.get("character_name"), str)
        or character["account_id"] != account_id
        or request["character_id"] != character["id"]
        or request["character_name"] != character["name"]
    ):
        return False
    return store.current_character_session(account_id, generation, character["id"])
