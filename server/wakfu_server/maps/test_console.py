"""Explicit local chat console; authoritative changes use existing owned APIs.

Caller flushes position write-behind before execution and handles world transition
bootstrap/broadcast. Commands are development privileges, not ordinary chat.
"""
import secrets
import os
import shlex
from .combat_terrain import map_geometry
from .combat_geometry import published_geometry
from .inventory_items import grant, insertion, equipment_inventory, _lease
from .inventory_move import STACKS
from .monsters import owned_instance, statistics, reference as monster_reference
from .combat_monster_world import spawn_group

HELP = "!help | !position | !astrub | !level level [target] | !teleport map x y z [target] | !item reference quantity [target] | !monster reference level quantity [target] | !kamas amount [target] | !buscar [item|mob] name [--pagina N] | !checkpoint [receipt] | !resultado receipt | !perfil [informe|estado|iniciar seconds|detener|reiniciar] | !equip uid slot | !unequip slot | !exitdungeon | !winfight | !losefight | !nuke | !nuke-all | !genesis | !genesis-all | !eco-status | !nuke-all-flora | !genesis-all-flora"

TARGET_ARITY = {"!nivel": 1, "!tp": 4, "!item": 2, "!mob": 3, "!kamas": 1}


def parse_target(text):
    """Extract an optional final player name without changing numeric arguments."""
    from .command_permissions import canonical_command

    try:
        fields = shlex.split(text)
    except ValueError:
        raise ValueError("Nombre entre comillas incompleto") from None
    if not fields:
        raise ValueError("Comando vacío")
    command = canonical_command(fields[0])
    arity = TARGET_ARITY.get(command)
    if arity is None:
        return text, None
    if len(fields) not in (arity + 1, arity + 2):
        raise ValueError(HELP)
    args = fields[1 : arity + 1]
    try:
        for value in args:
            int(value, 10)
    except ValueError:
        raise ValueError("Los argumentos deben ser números enteros") from None
    target = fields[-1].removeprefix("@") if len(fields) == arity + 2 else None
    if target is not None and not target.strip():
        raise ValueError("El nombre de destino está vacío")
    return " ".join([command, *args]), target


def execute(
    store,
    groups,
    account,
    generation,
    character,
    text,
    *,
    authorized_by=None,
    ecology_players=(),
    ecology_coordination=None,
    ecology_publish=None,
    private_scene=None,
    positions=None,
):
    if not isinstance(text, str) or not text.startswith("!"):
        return None
    from .command_permissions import authorize_command, canonical_command

    issuer = account if authorized_by is None else authorized_by
    authorize_command(store, issuer, text)
    if issuer != account:
        from .command_permissions import is_admin

        if not is_admin(store, issuer):
            raise PermissionError(
                "Solo un administrador puede modificar otro personaje"
            )
    fields = text.split()
    if not fields:
        raise ValueError("Comando vacío")
    command, args = canonical_command(fields[0]), fields[1:]
    expected = {
        "!ayuda": 0,
        "!pos": 0,
        "!nivel": 1,
        "!kamas": 1,
        "!tp": 4,
        "!astrub": 0,
        "!item": 2,
        "!mob": 3,
        "!equip": 2,
        "!unequip": 1,
        **{
            name: 0
            for name in (
                "!nuke",
                "!nuke-all",
                "!genesis",
                "!genesis-all",
                "!eco-status",
                "!nuke-all-flora",
                "!genesis-all-flora",
            )
        },
    }
    if command not in expected or len(args) != expected[command]:
        raise ValueError(HELP)
    try:
        values = [int(value, 10) for value in args]
    except ValueError:
        raise ValueError("Los argumentos deben ser números enteros") from None
    with store.connection() as db:
        _lease(store, db, account, generation, character["id"])
        current = store.character(account, character["id"], db)
        if command == "!mob" and private_scene is not None:
            from .haven_ranch import RanchSession

            if not isinstance(private_scene, RanchSession) or not private_scene.owns(
                character
            ):
                raise ValueError("Monster creation requires its live ranch session")
            private_scene.validate_lease(generation)
            current = private_scene.refresh(character, current)
        if command == "!mob" and current["instance_id"] != 0:
            run = db.execute(
                "SELECT 1 FROM dungeon_room_runs WHERE instance_id=%s AND status='active'",
                (current["instance_id"],),
            ).fetchone()
            if run is not None:
                raise ValueError(
                    "La mazmorra solo permite el grupo de su sala actual. "
                    "Usa !exitdungeon antes de crear monstruos de prueba."
                )
    result = dict(character=current, packets=[], action=command[1:])
    if command in (
        "!nuke",
        "!nuke-all",
        "!genesis",
        "!genesis-all",
        "!eco-status",
        "!nuke-all-flora",
        "!genesis-all-flora",
    ):
        if command.endswith("-flora"):
            from .ecology_flora_admin import execute as execute_ecology
        else:
            from .ecology_admin import execute as execute_ecology

        result.update(
            execute_ecology(
                store,
                groups,
                current,
                command,
                players=ecology_players,
                coordination=ecology_coordination,
                publish=ecology_publish,
            )
        )
    elif command == "!ayuda":
        result["message"] = HELP
    elif command == "!pos":
        result[
            "message"
        ] = "mapa={map_id} instancia={instance_id} x={x} y={y} z={z}".format(**current)
    elif command == "!nivel":
        from .progression import level_xp
        from . import health_store
        from .combat_lifecycle import outside_progression

        level = values[0]
        xp = level_xp(level)
        with store.connection() as db:
            _lease(store, db, account, generation, current["id"])
            latest = store.character(account, current["id"], db)
            if level < latest["level"]:
                raise ValueError("Este comando solo permite subir de nivel")
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s AND account_id=%s",
                (level, current["id"], account),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (max(xp, latest["xp"]), current["id"]),
            )
            updated = health_store.initialize(
                store, account, generation, current["id"], exploration=True, db=db
            )
            packet = outside_progression(
                updated,
                wp=(
                    int(os.environ["WAKFU_COMBAT_TEST_WP"])
                    if os.environ.get("WAKFU_COMBAT_TEST_WP", "").strip()
                    else None
                ),
            )
        result.update(
            character=updated,
            packets=[packet],
            message=f"Nivel {level} guardado; biblioteca y lista de personajes actualizadas",
        )
    elif command == "!kamas":
        from .wire import account_kamas_update

        amount = values[0]
        if not 1 <= amount <= (1 << 63) - 1:
            raise ValueError("La cantidad de kamas debe ser positiva")
        with store.connection() as db:
            _lease(store, db, account, generation, current["id"])
            row = db.execute(
                "UPDATE account_wallets SET kamas=kamas+%s "
                "WHERE account_id=%s AND kamas<=%s RETURNING kamas",
                (amount, account, (1 << 63) - 1 - amount),
            ).fetchone()
            if row is None:
                raise ValueError("El saldo de kamas excedería el máximo permitido")
            updated = store.character(account, current["id"], db)
        result.update(
            character=updated,
            packets=[(12753, account_kamas_update(row["kamas"]))],
            message=f"{amount} kamas añadidos; saldo={row['kamas']}",
        )
    elif command in ("!tp", "!astrub"):
        # Native central Astrub zaap 19249 arrival, independent of arbitrary !tp rights.
        map_id, x, y, z = (527, 0, 32, 0) if command == "!astrub" else values
        if (x, y, z) not in {tuple(cell) for cell in map_geometry(map_id)["cells"]}:
            raise ValueError(
                "La casilla de destino no es transitable en la geometría nativa"
            )
        destination = dict(map_id=map_id, instance_id=0, x=x, y=y, z=z)
        from .console_relocation import relocate

        result["character"] = relocate(
            store,
            account,
            generation,
            current["id"],
            current,
            destination,
            positions=positions,
        )
        result.update(
            action="tp",
            source=current,
            destination=destination,
            message="Teletransporte local realizado",
        )
    elif command == "!item":
        reference, quantity = values
        rule = STACKS.get(reference)
        if (
            rule is None
            or reference <= 0
            or not 1 <= quantity <= min(rule["maximum"], 32767)
        ):
            raise ValueError(
                "Referencia o cantidad fuera del catálogo nativo de objetos"
            )
        from wakfu_server.items import quest_inventory, account_quest_inventory

        if (
            reference in quest_inventory.REFERENCES
            or reference in account_quest_inventory.REFERENCES
        ):
            # Native quest inventories have no ordinary bag position or capacity.
            destination = (0, 0)
        else:
            occupied = {
                (item["container"], item["slot"]) for item in current["inventory_items"]
            }
            destination = next(
                (
                    (bag["uid"], slot)
                    for bag in current["inventory_containers"]
                    for slot in range(bag["capacity"])
                    if (bag["uid"], slot) not in occupied
                ),
                None,
            )
            if destination is None:
                raise ValueError("El inventario está lleno")
        item = grant(
            store,
            account,
            generation,
            current["id"],
            reference=reference,
            quantity=quantity,
            container=destination[0],
            slot=destination[1],
            allowed_references=STACKS,
        )
        updated = store.character(account, current["id"])
        result.update(
            character=updated,
            packets=[insertion(item), equipment_inventory(updated)],
            item=item,
            message=f"{rule.get('name') or f'Objeto {reference}'} ×{quantity} añadido; UID={item['uid']}",
        )
    elif command in ("!equip", "!unequip"):
        from . import builds
        from .equipment import validate_sheet
        from .wire import proto_field

        index = current.get("active_build_index", 0)
        saved = current.get("builds", {}).get(index, {})
        entries = validate_sheet(
            current, bytes.fromhex(saved.get("equipment", "")) or builds.EMPTY_EQUIPMENT
        )
        slot = values[-1]
        if not 0 <= slot <= 255:
            raise ValueError("Slot de equipo inválido")
        if command == "!unequip" and not any(item["slot"] == slot for item in entries):
            raise ValueError("El slot de equipo está vacío")
        uid = values[0] if command == "!equip" else None
        entries = [
            item for item in entries if item["slot"] != slot and item["uid"] != uid
        ]
        if uid is not None:
            entries.append(dict(uid=uid, slot=slot))
        equipment = builds.EMPTY_EQUIPMENT + b"".join(
            proto_field(10, proto_field(8, item["uid"]) + proto_field(16, item["slot"]))
            for item in entries
        )
        validate_sheet(current, equipment)
        sheet = bytes.fromhex(saved.get("sheet", "")) or b"".join(
            proto_field(t, v)
            for t, v in (
                (8, index),
                (18, b"Build por defecto"),
                (24, (1 << 64) - 1),
                (56, 1),
                (64, 1),
            )
        )
        blobs = {key: bytes.fromhex(saved.get(key, "")) for key in builds.KEYS}
        blobs.update(sheet=sheet, equipment=equipment)
        updated = store.save_build(account, generation, current["id"], index, blobs)
        result.update(
            character=updated,
            build_index=index,
            message="Equipo actualizado",
            packets=builds.response_messages(
                updated,
                index,
                wp=(
                    int(os.environ["WAKFU_COMBAT_TEST_WP"])
                    if os.environ.get("WAKFU_COMBAT_TEST_WP", "").strip()
                    else None
                ),
            ),
        )
    else:
        if groups is None:
            raise ValueError(
                "Los grupos de prueba no están habilitados en este servidor"
            )
        reference, level, quantity = values
        from .monster_minigame_policy import require_ordinary_spawn

        require_ordinary_spawn(reference)
        statistics(reference, level)
        if not 1 <= quantity <= 8:
            raise ValueError("El grupo local admite entre 1 y 8 monstruos")
        if current["map_id"] == 9 or (
            current["instance_id"] != 0 and private_scene is None
        ):
            raise ValueError(
                "La creación de monstruos requiere el mundo público o una sesión válida del merkalugar"
            )
        origin = (current["x"], current["y"], current["z"])
        geometry = published_geometry(current["map_id"])
        if origin not in geometry.cells:
            raise ValueError("Posición del personaje fuera de la geometría nativa")
        occupied = {
            tuple(m[k] for k in ("x", "y", "z"))
            for group in groups.available(current["map_id"], current["instance_id"])
            for m in group["members"]
        }
        seen, queue, cells = {origin}, [origin], []
        for cell in queue:
            for neighbor in geometry.outgoing.get(cell, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
                    if neighbor not in occupied:
                        cells.append(neighbor)
            if len(cells) >= quantity:
                break
        if len(cells) < quantity:
            raise ValueError("No hay suficientes casillas alcanzables libres")
        group_id = secrets.randbits(62) + 1
        from .npc_actor_identity import allocate_block

        with store.connection() as identity_db:
            actor_id_base = allocate_block(identity_db, quantity)
        members = [
            owned_instance(
                reference,
                level,
                -(actor_id_base + index),
                map_id=current["map_id"],
                x=cell[0],
                y=cell[1],
                z=cell[2],
                instance_id=current["instance_id"],
            )
            for index, cell in enumerate(cells[:quantity])
        ]
        packet = (12608, spawn_group(members, group_id=group_id))
        key = groups.register(
            current["map_id"], current["instance_id"], group_id, members
        )
        result.update(
            group_key=key,
            members=members,
            world_packets=[packet],
            message=f"{quantity} × {monster_reference(reference).get('name') or f'Monstruo {reference}'} creado; grupo={group_id}",
        )
    return result
