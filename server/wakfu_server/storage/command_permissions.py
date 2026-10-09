"""Current database-backed development-command authorization."""

PUBLIC_COMMANDS_SETTING = "player_allowed_commands"
DEFAULT_PLAYER_COMMANDS = ("!ayuda", "!pos")
COMMAND_ALIASES = {
    "!help": "!ayuda",
    "!position": "!pos",
    "!level": "!nivel",
    "!teleport": "!tp",
    "!monster": "!mob",
}


def canonical_command(command):
    return COMMAND_ALIASES.get(command.lower(), command.lower())


def is_admin(store, account_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s", (account_id,)
        ).fetchone()
    if row is None:
        raise PermissionError("Cuenta desconocida")
    return bool(row["is_admin"])


def authorize_command(store, account_id, text):
    if not isinstance(text, str) or not text.split() or not text.startswith("!"):
        raise ValueError("Comando inválido")
    command = canonical_command(text.split()[0])
    with store.connection() as db:
        row = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s", (account_id,)
        ).fetchone()
        setting = db.execute(
            "SELECT value FROM settings WHERE name=%s", (PUBLIC_COMMANDS_SETTING,)
        ).fetchone()
    if row is None:
        raise PermissionError("Cuenta desconocida")
    if row["is_admin"]:
        return
    allowed = setting["value"] if setting else []
    if not isinstance(allowed, list) or any(
        not isinstance(c, str) or not c.startswith("!") or len(c.split()) != 1
        for c in allowed
    ):
        raise PermissionError("Política de comandos inválida")
    if command not in {canonical_command(value) for value in allowed}:
        raise PermissionError("Comando no autorizado para esta cuenta")


def set_admin(store, account_id, enabled, *, operator, reason):
    """Offline operator action; never exposed through register/login or chat."""
    if (
        type(enabled) is not bool
        or not isinstance(operator, str)
        or not operator.strip()
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        raise ValueError("Operador y motivo requeridos")
    with store.connection() as db:
        if (
            db.execute(
                "UPDATE accounts SET is_admin=%s WHERE id=%s", (enabled, account_id)
            ).rowcount
            != 1
        ):
            raise ValueError("Cuenta desconocida")
        db.execute(
            "INSERT INTO admin_role_audit(account_id,is_admin,operator,reason,changed_at) VALUES(%s,%s,%s,%s,%s)",
            (account_id, enabled, operator, reason, store.now()),
        )
