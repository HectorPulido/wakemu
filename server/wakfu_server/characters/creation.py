"""Character creation for an authenticated world connection."""
from protocol_codec import decode_body


def create(store, account_id, generation, body):
    if not store.current_session(account_id, generation):
        raise ValueError("Authentication required")
    request = decode_body("out", 22296, body)
    if request["character_id"] != -1:
        return 101, None  # Existing-character modification is a separate flow.
    try:
        character = store.create_character(
            account_id,
            request["character_name"],
            breed=request["breed_id"],
            appearance=request["appearance"],
        )
    except ValueError as error:
        status = {
            "Ese nombre ya existe o la cuenta es inválida.": 102,
            "Nombre: 3–24 letras, espacios o guiones.": 103,
            "Máximo cinco personajes por cuenta.": 104,
        }.get(str(error), 101)
        return status, None
    return 0, character
