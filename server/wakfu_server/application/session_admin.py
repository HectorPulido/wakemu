"""Admin operations for one lease-bound World session."""

from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class AdminSessionMixin:
    @PROFILER.profile("admin.command")
    def execute_test_command(self, text, *, authorized_by=None):
        from wakfu_server.test_console import execute, parse_target
        from wakfu_server.command_permissions import (
            authorize_command,
            canonical_command,
            is_admin,
        )

        failure = None
        try:
            issuer = self.state.account_id if authorized_by is None else authorized_by
            authorize_command(self.runtime.STORE, issuer, text)
            text, target = parse_target(text)
            command = canonical_command(text.split()[0])
            if (
                command == "!astrub"
                and target is None
                and issuer == self.state.account_id
            ):
                if len(text.split()) != 1:
                    raise ValueError("Uso: !astrub")
                self.emergency_exit_current_combat()
                if (
                    self.state.aborted_native_return is not None
                    and not self.state.aborted_native_return.world_returned
                ):
                    self.state.aborted_native_return.command = text
                    return {
                        "message": "El combate está cancelado; finalizando su salida."
                    }
            if (
                command in ("!astrub", "!tp")
                and target is None
                and issuer == self.state.account_id
                and self.deferred_native_combat_attachment() is not None
            ):
                fields = text.split()
                if len(fields) != (1 if command == "!astrub" else 5):
                    raise ValueError("Uso: !astrub | !tp mapa x y z")
                from wakfu_server.combat_terrain import map_geometry

                destination = (
                    (527, 0, 32, 0)
                    if command == "!astrub"
                    else tuple(int(value) for value in fields[1:])
                )
                if destination[1:] not in {
                    tuple(cell) for cell in map_geometry(destination[0])["cells"]
                }:
                    raise ValueError("La casilla de destino no es transitable")
                self.abort_waiting_publication_cohort()
                if (
                    self.state.aborted_native_return is not None
                    and not self.state.aborted_native_return.world_returned
                ):
                    self.state.aborted_native_return.command = text
                    return {
                        "message": "El combate está cancelado; finalizando su salida."
                    }
                if self.deferred_native_combat_attachment() is not None:
                    return {
                        "message": "El combate ya se abandonó; el regreso al mapa sigue pendiente. Repite el comando al terminar de cargar."
                    }
            if command == "!merkamundo":
                from wakfu_server.guild_haven_world import create_assignment
                from wakfu_server.haven_world_travel import travel

                words = text.split()
                if (
                    target is not None
                    or issuer != self.state.account_id
                    or len(words) > 2
                ):
                    raise ValueError(
                        "Uso: !merkamundo [asignar|salir] (solo el personaje propio)"
                    )
                if self.active_private_session() is not None:
                    raise ValueError(
                        "Sal del merkasaco o Rancho antes de cambiar de Merkamundo"
                    )
                action = words[1].lower() if len(words) == 2 else "entrar"
                if action == "asignar":
                    with self.runtime.STORE.connection() as db:
                        member = db.execute(
                            "SELECT guild_id FROM guild_members WHERE character_id=%s",
                            (self.state.character["id"],),
                        ).fetchone()
                    if member is None:
                        raise ValueError("El personaje debe pertenecer a un gremio")
                    binding = create_assignment(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        member["guild_id"],
                    )
                    answer = "Merkamundo asignado al gremio " + str(binding["guild_id"])
                elif action in ("entrar", "salir"):
                    outcome = travel(
                        self.runtime.STORE,
                        self.runtime.POSITIONS,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        leave=action == "salir",
                    )
                    self.publish_haven_world_travel(outcome)
                    answer = (
                        "Has salido del Merkamundo"
                        if action == "salir"
                        else "Has entrado al Merkamundo de tu gremio"
                    )
                else:
                    raise ValueError("Uso: !merkamundo [asignar|salir]")
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer}
            if command == "!chest":
                from wakfu_server.haven_chest import deposit_all
                from wakfu_server.haven_chest_wire import (
                    action_result as chest_action_result,
                    bootstrap as chest_bootstrap,
                )
                from wakfu_server.inventory_move import synchronization
                from wakfu_server.inventory_items import equipment_inventory

                if (
                    text.split() != ["!chest", "depositall"]
                    or target is not None
                    or issuer != self.state.account_id
                ):
                    raise ValueError(
                        "Uso: !chest depositall (solo el personaje propio)"
                    )
                if (
                    self.state.chest_opening is None
                    or self.state.fight is not None
                    or self.state.combat_session is not None
                ):
                    raise ValueError(
                        "Abre tu cofre fuera de combate antes de depositar"
                    )
                result = deposit_all(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    opening_token=self.state.chest_opening,
                    location=self.state.character,
                    ranch_session=self.state.ranch_session,
                )
                self.state.character = self.active_private_session().refresh(
                    self.state.character, result["character"]
                )
                for owner in result.get(
                    "inventory_characters", (self.state.character,)
                ):
                    for packet in (synchronization(owner), equipment_inventory(owner)):
                        self.runtime.send(
                            self.state.connection, self.state.service, *packet
                        )
                for packet in (chest_bootstrap(result["chest"]), chest_action_result()):
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
                self.runtime.record(
                    event="account_chest_deposited_all",
                    actor_id=self.state.character["id"],
                    applied=result["applied"],
                    revision=result["chest"]["revision"],
                )
                answer = "Depósito completado; los objetos equipados y de misión permanecen en el inventario"
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer}
            if command == "!foodclear":
                from wakfu_server.consumable_world_lifecycle import clear_for_test
                from wakfu_server.consumable_buff_wire import delta

                if (
                    len(text.split()) != 1
                    or target is not None
                    or issuer != self.state.account_id
                ):
                    raise ValueError("Uso: !foodclear (solo el personaje propio)")
                if (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                ):
                    raise ValueError(
                        "Sal del combate antes de retirar los efectos de comida"
                    )
                previous = self.state.character
                self.state.character = clear_for_test(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                )
                for packet in delta(
                    previous,
                    self.state.character,
                    allocate_action=lambda: next(self.runtime.LOCAL_WORLD_ACTIONS),
                ):
                    self.runtime.WORLD.broadcast(
                        self.state.generation, self.state.character["id"], *packet
                    )
                self.publish_consumable_character(self.state.character)
                answer = "Efectos de consumibles retirados; puedes iniciar la siguiente prueba"
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer}
            from wakfu_server.custom_tasks import external as objectives_mode

            if objectives_mode.enabled() and command in (
                "!astrub",
                "!tp",
                "!nivel",
                "!item",
                "!kamas",
                "!mob",
            ):
                from wakfu_server.objectives.challenges import mark_scene_test

                with self.runtime.STORE.connection() as challenge_db:
                    source = challenge_db.execute(
                        "SELECT c.instance_id,r.attempt_id FROM characters c "
                        "JOIN objectives_challenge_runs r ON r.instance_id=c.instance_id "
                        "AND r.map_id=c.map_id AND r.owner_account_id=c.account_id "
                        "AND r.returned_at IS NULL WHERE c.id=%s AND c.account_id=%s",
                        (self.state.character["id"], self.state.account_id),
                    ).fetchone()
                    if source is not None and command not in ("!astrub", "!tp"):
                        mark_scene_test(challenge_db, source["instance_id"])
                if source is not None:
                    if command == "!astrub":
                        from wakfu_server.objectives.challenges import (
                            return_from_challenge,
                        )

                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            with self.runtime.STORE.connection() as challenge_db:
                                moved_ids = tuple(
                                    row["character_id"]
                                    for row in challenge_db.execute(
                                        "SELECT character_id FROM objectives_challenge_members WHERE attempt_id=%s",
                                        (source["attempt_id"],),
                                    ).fetchall()
                                )
                                return_from_challenge(
                                    challenge_db,
                                    self.state.account_id,
                                    self.state.character["id"],
                                    abandon=True,
                                )
                                self.state.character = self.runtime.STORE.character(
                                    self.state.account_id,
                                    self.state.character["id"],
                                    challenge_db,
                                )
                            for member_id in moved_ids:
                                self.runtime.POSITIONS.release(
                                    self.state.account_id,
                                    self.state.generation,
                                    member_id,
                                )
                    elif command == "!tp":
                        raise ValueError(
                            "Use !challenge abandon before leaving the weekly challenge."
                        )
            if command in ("!winfight", "!losefight"):
                from wakfu_server.combat_test_commands import finish
                from wakfu_server.combat_command_recovery import (
                    apply_outcome,
                    bind_current_owners,
                    release_deferred_owners,
                )

                if len(text.split()) != 1 or target is not None:
                    raise ValueError("Uso: !winfight | !losefight")
                if issuer != self.state.account_id:
                    raise ValueError("El comando solo afecta al combate propio")
                command_from_world = (
                    self.state.fight is None and self.state.combat_session is None
                )
                if command_from_world:
                    self.attach_command_combat()
                if self.state.fight is None and self.state.combat_session is None:
                    answer = "No hay ningún combate pendiente."
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.information(answer),
                    )
                    return {"message": answer}
                from wakfu_server.custom_tasks import external as objectives_mode

                if objectives_mode.enabled() and self.state.fight is not None:
                    from wakfu_server.objectives.challenges import mark_test_fight

                    with self.runtime.STORE.connection() as challenge_db:
                        mark_test_fight(challenge_db, self.state.fight.id)
                if self.state.combat_session is not None:
                    bind_current_owners(
                        self.runtime.STORE,
                        self.runtime.COMBAT_SESSIONS.registry,
                        self.state.character["id"],
                        self.runtime.CHECKPOINT_WRITER,
                    )
                    shared_outcome = apply_outcome(
                        self.runtime.COMBAT_SESSIONS.registry,
                        self.state.combat_session,
                        win=command == "!winfight",
                    )
                    if shared_outcome is None:
                        self.emergency_exit_current_combat()
                        answer = "El combate ya está cerrado."
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.information(answer),
                        )
                        return {"message": answer}
                    self.refresh_shared_combat()
                else:
                    terminal = finish(
                        self.state.fight,
                        self.state.fight_messages,
                        account_id=self.state.account_id,
                        character_id=self.state.character["id"],
                        win=command == "!winfight",
                    )
                    self.state.fight, self.state.fight_messages = (
                        terminal.fight,
                        terminal.runtime,
                    )
                self.runtime.record(
                    event="test_console_combat_outcome",
                    command=command,
                    actor_id=self.state.character["id"],
                    account_id=self.state.account_id,
                    fight_id=self.state.fight.id,
                    winner=self.state.fight.winner,
                )
                outcome_actor = self.state.fight.actors.get(self.state.character["id"])
                outcome_won = (
                    self.state.fight.winner == outcome_actor.team
                    if outcome_actor is not None
                    and outcome_actor.controlled
                    and outcome_actor.owner_id == self.state.account_id
                    and self.state.fight.winner in (0, 1)
                    else None
                )
                self.complete_test_fight()
                self.checkpoint_fight("ended")
                if self.state.combat_session is not None:
                    completed_shared = self.runtime.COMBAT_SESSIONS.registry.lookup(
                        self.state.fight.id
                    )
                    release_deferred_owners(
                        self.runtime.STORE,
                        self.runtime.COMBAT_SESSIONS.registry,
                        completed_shared,
                    )
                if command_from_world:
                    self.emergency_exit_current_combat()
                    if (
                        self.state.aborted_native_return is None
                        or self.state.aborted_native_return.world_returned
                    ):
                        self.runtime.send_batch(
                            self.state.connection,
                            self.state.service,
                            self.combat_return_bootstrap(),
                        )
                        self.runtime.join_world(
                            self.state.generation,
                            self.state.connection,
                            self.state.character,
                        )
                        self.mark_static_sync_pending()
                answer = (
                    "El combate ya está cerrado."
                    if outcome_won is None
                    else "Combate ganado." if outcome_won else "Combate perdido."
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer}
            if command == "!perfil":
                from wakfu_server.performance_commands import execute_profile_command

                if not is_admin(self.runtime.STORE, issuer):
                    raise PermissionError(
                        "Solo un administrador puede consultar perfiles"
                    )
                answer = execute_profile_command(
                    PROFILER, text, self.runtime.RUNTIME / "logs/profiles"
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer}
            if command == "!checkpoint":
                from wakfu_server.manual_checkpoint import checkpoint_message

                args = text.split()[1:]
                if len(args) > 1:
                    raise ValueError("Uso: !checkpoint [recibo]")
                if args:
                    checkpoint_result = self.runtime.MANUAL_CHECKPOINT.status(args[0])
                else:
                    recipient = dict(self.state.character, name="Consola local")
                    recipient_id, recipient_generation = (
                        self.state.character["id"],
                        self.state.generation,
                    )
                    checkpoint_result = self.runtime.MANUAL_CHECKPOINT.request(
                        requester=(recipient_id, recipient_generation),
                        notify=lambda completed: self.runtime.WORLD.send_to(
                            recipient_id,
                            recipient_generation,
                            674,
                            self.runtime.wire.chat(
                                recipient, checkpoint_message(completed)
                            ),
                        ),
                    )
                answer = checkpoint_message(checkpoint_result)
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer, "checkpoint": checkpoint_result}
            if target is not None:
                if not is_admin(self.runtime.STORE, issuer):
                    raise PermissionError(
                        "Solo un administrador puede modificar otro personaje"
                    )
                identity = self.runtime.WORLD.live_identity(name=target)
                if identity is None:
                    raise ValueError("El personaje de destino debe estar conectado")
                target_generation, target_character = identity
                if target_character["id"] != self.state.character["id"]:
                    # The target's owner thread must execute with its own closure.
                    receipt = self.runtime.TEST_CONSOLE.submit(
                        target_character["id"],
                        text,
                        requester_account_id=issuer,
                        authorize=lambda: authorize_command(
                            self.runtime.STORE, issuer, text
                        ),
                        delegated_by=issuer,
                        expected_generation=target_generation,
                    )
                    answer = f"Comando enviado a {target_character['name']}; recibo {receipt['handle']}"
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        674,
                        self.runtime.wire.chat(
                            dict(self.state.character, name="Consola local"), answer
                        ),
                    )
                    return {"message": answer, "handle": receipt["handle"]}
            if command == "!resultado":
                args = text.split()[1:]
                if len(args) != 1:
                    raise ValueError("Uso: !resultado recibo")
                if args[0].startswith("eco-"):
                    receipt = self.runtime.ECOLOGY_ADMIN_JOBS.status(args[0])
                    if receipt.get("account_id") != issuer and not is_admin(
                        self.runtime.STORE, issuer
                    ):
                        raise PermissionError("El recibo pertenece a otra cuenta")

                    from wakfu_server.ecology_feedback import (
                        information as ecology_information,
                    )

                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *ecology_information(receipt["message"]),
                    )
                    return {"message": receipt["message"], "ecology_job": receipt}
                receipt = self.runtime.TEST_CONSOLE.poll(args[0])
                if receipt.get("requester_account_id") != issuer and not is_admin(
                    self.runtime.STORE, issuer
                ):
                    raise PermissionError("El recibo pertenece a otra cuenta")
                answer = str(
                    receipt.get("error")
                    or receipt.get("result", {}).get("message")
                    or receipt["status"]
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), answer
                    ),
                )
                return {"message": answer}
            if command in ("!buscar", "!search", "!ids"):
                import shlex
                from wakfu_server.command_search import search

                args = shlex.split(text)[1:]
                kind, page = "all", 1
                if args and args[0].lower() in ("item", "items", "mob", "mobs"):
                    kind = args.pop(0).lower()
                if "--pagina" in args:
                    index = args.index("--pagina")
                    if index != len(args) - 2:
                        raise ValueError("Uso: !buscar [item|mob] nombre [--pagina 2]")
                    page = int(args[index + 1])
                    args = args[:index]
                found = search(" ".join(args), kind=kind, page=page)
                for line in found["message"].splitlines():
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        674,
                        self.runtime.wire.chat(
                            dict(self.state.character, name="Consola local"), line
                        ),
                    )
                return {"message": found["message"]}
            ecology_submission = self.runtime.submit_ecology_admin_command(
                self.state.connection,
                self.state.service,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                command,
                text,
            )
            if ecology_submission is not None:
                return ecology_submission
            if command in (
                "!tp",
                "!astrub",
                "!mob",
                "!item",
                "!equip",
                "!unequip",
                "!nivel",
            ) and (
                self.state.fight is not None or self.state.combat_session is not None
            ):
                if (
                    self.state.fight is not None
                    and self.state.fight.phase == "finished"
                ):
                    raise ValueError(
                        "El combate terminó, pero su cierre sigue pendiente. Cierra la pantalla de resultados. "
                        "Si no responde, desconecta a todo el grupo y pide a un administrador "
                        "inspeccionar y cancelar la recuperación del combate "
                        + str(self.state.fight.id)
                        + "."
                    )
                raise ValueError(
                    "Termina el combate antes de modificar el mundo o el inventario."
                )
            if self.state.bag_session is not None and (
                command == "!tp"
                or (command == "!mob" and self.state.ranch_session is None)
            ):
                raise ValueError(
                    "Sal del combate o del merkasaco antes de usar este comando."
                )
            if command == "!astrub" and self.state.ranch_session is not None:
                self.validate_ranch_lease()
            self.runtime.flush_positions(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
            )
            from contextlib import contextmanager

            ecology_command = command in (
                "!nuke",
                "!nuke-all",
                "!genesis",
                "!genesis-all",
                "!eco-status",
                "!nuke-all-flora",
                "!genesis-all-flora",
            )

            ecology_coordination = self.runtime.ecology_admin_coordination

            def publish_ecology_admin(outcome):
                self.runtime.publish_ecology_admin_outcome(
                    dict(outcome, command=command)
                )

            result = execute(
                self.runtime.STORE,
                self.runtime.COMBAT_GROUPS if self.runtime.COMBAT_TEST else None,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                text,
                authorized_by=issuer,
                ecology_players=(
                    self.runtime.WORLD.ecology_snapshot if ecology_command else ()
                ),
                ecology_coordination=ecology_coordination if ecology_command else None,
                ecology_publish=publish_ecology_admin if ecology_command else None,
                private_scene=self.state.ranch_session,
                positions=self.runtime.POSITIONS,
                fighting=lambda identity: self.runtime.COMBAT_SESSIONS.lookup_character(
                    identity
                )
                is not None,
            )
            if result["action"] == "tp" and self.deliver_rift_transition():
                # Native departure already owns one complete scene bootstrap.
                pass
            elif result["action"] == "tp":
                leaving_ranch = (
                    command == "!astrub" and self.state.ranch_session is not None
                )
                leaving_private = (
                    command == "!astrub" and self.state.bag_session is not None
                )
                if command == "!astrub" and self.state.bag_session is not None:
                    self.runtime.PLANTINGS.cancel(
                        self.state.character["id"], self.state.generation
                    )
                    self.runtime.HARVESTS.cancel(
                        self.state.character["id"], generation=self.state.generation
                    )
                    self.cancel_flora()
                    exterior = self.runtime.HAVEN_BAG_EXTERIORS.discard(
                        self.state.generation, self.state.bag_session.exterior_actor_id
                    )
                    if exterior is not None:
                        outside, packet = exterior
                        self.runtime.WORLD.emit_location(
                            outside["map_id"], outside["instance_id"], *packet
                        )
                    if self.state.ranch_session is not None:
                        self.state.ranch_session.leave(self.state.character)
                    self.state.bag_session = None
                    self.state.ranch_session = None
                self.cancel_crafting()
                self.runtime.WORLD.leave(
                    self.state.character["id"], self.state.generation
                )
                self.state.character = result["character"]
                self.runtime.POSITIONS.attach(
                    self.state.account_id, self.state.generation, self.state.character
                )
                self.state.position = {
                    key: self.state.character[key] for key in ("x", "y", "z")
                }
                self.state.movement_state = self.runtime.Movement(self.state.position)
                transition_messages = (
                    self.runtime.owned_haven_leave(
                        self.runtime.fixture(13974), self.state.character
                    )
                    if leaving_private
                    else self.runtime.owned_native_bootstrap(self.state.character)
                )
                for message_id, message_body in transition_messages:
                    # Ranch entry already cleared the non-nullsafe bpq controller.
                    if leaving_ranch and message_id == 13019:
                        continue
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        message_id,
                        message_body,
                    )
                self.runtime.join_world(
                    self.state.generation, self.state.connection, self.state.character
                )
                self.mark_static_sync_pending()
            else:
                self.state.character = (
                    self.active_private_session().refresh(
                        self.state.character, result["character"]
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else result["character"]
                )
                for message_id, message_body in result["packets"]:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        message_id,
                        message_body,
                    )
                if result["action"] == "nivel":
                    from wakfu_server.level_publication import refresh

                    for message_id, message_body in refresh(
                        self.state.character,
                        self.runtime.STORE.characters(self.state.account_id),
                        entity_template=self.runtime.OWNED_HERO_TEMPLATE,
                        roster_template=self.runtime.CHARACTERS,
                        retained_state_packets=self.runtime.consumable_state_packets,
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            message_id,
                            message_body,
                        )
                    self.runtime.send_native_planting_bonus(
                        self.state.connection, self.state.character
                    )
                for message_id, message_body in result.get("world_packets", []):
                    self.runtime.WORLD.emit_location(
                        self.state.character["map_id"],
                        self.state.character["instance_id"],
                        message_id,
                        message_body,
                    )
            answer = result["message"]
            self.runtime.record(
                event="test_console_command",
                actor_id=self.state.character["id"],
                command=command,
                outcome="ok",
            )
        except (ValueError, PermissionError) as error:
            failure = error
            answer = str(error)
            self.runtime.record(
                event="test_console_command",
                actor_id=self.state.character["id"],
                command=text.split()[0],
                outcome="rejected",
                reason=answer,
            )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            674,
            self.runtime.wire.chat(
                dict(self.state.character, name="Consola local"), answer.splitlines()[0]
            ),
        )
        for line in answer.splitlines()[1:]:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"), line
                ),
            )
        if failure is not None:
            raise failure
        summary = {"message": answer}
        if "item" in result:
            summary["item"] = {
                key: result["item"][key]
                for key in ("uid", "reference", "quantity", "container", "slot")
                if key in result["item"]
            }
        if "group_key" in result:
            summary["group_key"] = list(result["group_key"])
            summary["actor_ids"] = [member["id"] for member in result["members"]]
        return summary
