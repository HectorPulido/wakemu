"""Ordered native routing; conditions deliberately preserve state precedence."""

import struct
from wakfu_server.rii_zaap_scene import handles_activation as rii_zaap_activation
from wakfu_server.astrub_house_exit import (
    handles_activation as astrub_house_exit_activation,
)

from .dispatch_result import DispatchResult


class SessionDispatchMixin:
    def dispatch_request(self):
        if self.state.opcode == 574:
            return self.handle_handshake()
        elif self.state.service == "dispatcher":
            return self.handle_dispatcher()
        elif self.state.opcode == 426:
            return self.handle_realm_ticket()
        elif self.state.opcode == 22954:
            return self.handle_character_list()
        elif self.state.opcode == 13488:
            return self.handle_character_selection_prepare()
        elif self.state.opcode == 22296:
            return self.handle_character_create()
        elif self.state.opcode == 22870:
            return self.handle_created_character_select()
        elif self.state.opcode == 23664:
            return self.handle_character_select()
        elif self.state.opcode == 13932 and self.state.loaded:
            return self.handle_position_save()
        elif self.state.opcode == 12239 and self.state.loaded:
            return self.handle_position_checkpoint()
        elif self.state.opcode == 12767 and self.state.loaded:
            return self.handle_inventory_move()
        elif self.state.opcode in (12634, 13928) and self.state.loaded:
            return self.handle_mount_state()
        elif self.state.opcode in (12231, 13382) and self.state.loaded:
            return self.handle_craft()
        elif (
            self.state.opcode == 13429
            and self.state.loaded
            and len(self.state.body) == 3
            and struct.unpack(">h", self.state.body[1:])[0] == 8
        ):
            return self.handle_craft_station()
        elif self.state.opcode == 12995 and self.state.loaded:
            return self.handle_resource_collect()
        elif (
            self.state.opcode == 13429
            and self.state.loaded
            and len(self.state.body) == 3
            and struct.unpack(">Bh", self.state.body)[1] == 3
        ):
            return self.handle_resource_complete()
        elif self.state.opcode == 13284 and self.state.loaded:
            return self.handle_appearance_fusion()
        elif self.state.opcode == 12851:
            return self.handle_inventory_journal()
        elif self.state.opcode == 13220 and self.state.loaded:
            return self.handle_item_action()
        elif (
            self.state.opcode == 13481
            and self.state.loaded
            and self.runtime.COMBAT_TEST
        ):
            return self.handle_monster_collect()
        elif (
            self.state.opcode == 13429
            and self.state.loaded
            and self.runtime.COMBAT_TEST
            and len(self.state.body) == 3
            and struct.unpack(">Bh", self.state.body)[0] in (2, 3)
            and struct.unpack(">h", self.state.body[1:])[0] in (2, 6)
        ):
            return self.handle_harvest_complete()
        elif self.state.opcode == 12117 and self.state.loaded:
            return self.handle_duel_invite()
        elif self.state.opcode == 13520 and self.state.loaded:
            return self.handle_duel_accept()
        elif (
            self.state.opcode == 13241
            and self.state.loaded
            and self.runtime.COMBAT_TEST
        ):
            return self.handle_fight_join()
        elif (
            self.state.opcode == 13413
            and self.state.loaded
            and self.runtime.COMBAT_TEST
        ):
            return self.handle_spectator_join()
        elif (
            self.state.opcode == 12154
            and self.state.loaded
            and self.runtime.COMBAT_TEST
        ):
            return self.handle_spectator_leave()
        elif (
            self.state.loaded
            and self.runtime.COMBAT_TEST
            and (
                self.state.opcode == 13130
                or (
                    self.state.opcode == 13222
                    and (
                        self.bind_input(
                            "encounter_world_action",
                            self.prepare_native_encounter_world_action(self.state.body),
                        )
                    )
                    is not None
                )
                or (
                    self.state.opcode == 12870
                    and (
                        self.bind_input(
                            "rift_start_run", self.prepare_rift_start(self.state.body)
                        )
                    )
                    is not None
                )
            )
        ):
            return self.handle_encounter_start()
        elif self.state.opcode in (12543, 12519, 12597) and self.state.loaded:
            return self.handle_fight_roster()
        elif self.state.opcode == 12806 and self.state.fight is not None:
            return self.handle_fight_placement()
        elif self.state.opcode == 12523 and self.state.fight is not None:
            return self.handle_fight_placement_validate()
        elif self.state.opcode == 13260 and self.state.fight_messages is not None:
            return self.handle_spell_cast()
        elif self.state.opcode == 12889 and self.state.fight_messages is not None:
            return self.handle_weapon_cast()
        elif self.state.opcode == 13952 and self.state.loaded:
            return self.handle_fight_abandon()
        elif self.state.opcode == 12921 and self.state.loaded:
            return self.handle_world_loaded()
        elif (
            self.state.opcode == 12925 and self.state.aborted_native_return is not None
        ):
            return self.handle_aborted_return_ack()
        elif (
            self.state.opcode == 12925 and self.state.pve_withdrawal_pending is not None
        ):
            return self.handle_withdrawal_ack()
        elif (
            self.state.opcode == 12925
            and self.state.loaded
            and self.state.spectator_terminal_pending is not None
        ):
            return self.handle_spectator_return_ack()
        elif self.state.opcode == 12925 and self.state.fight_messages is not None:
            return self.handle_combat_return_ack()
        elif self.state.opcode == 12593:
            return self.handle_world_orientation()
        elif (
            self.state.opcode == 13655
            and self.state.fight is None
            and self.state.loaded
        ):
            return self.handle_world_direction()
        elif self.state.opcode == 13655 and self.state.fight is not None:
            return self.handle_fight_direction()
        elif self.state.opcode == 12161 and self.state.fight_messages is not None:
            return self.handle_fight_movement()
        elif self.state.opcode == 12403 and self.state.fight_messages is not None:
            return self.handle_fight_turn_end()
        elif self.state.opcode == 13332 and self.state.fight_messages is not None:
            return self.handle_fight_ack()
        elif self.state.opcode == 13510 and self.state.fight_messages is not None:
            return self.handle_fight_ack_followup()
        elif self.state.opcode in (12014, 13068) and self.state.loaded:
            return self.handle_captured_roster()
        elif self.state.opcode == 13571 and self.state.loaded:
            return self.handle_captured_selection()
        elif self.state.opcode == 14689 and self.state.loaded:
            return self.handle_captured_view()
        elif self.state.opcode == 13787 and self.state.loaded:
            return self.handle_shard_identify()
        elif self.state.opcode == 12487 and self.state.loaded:
            return self.handle_element_select()
        elif (
            self.state.opcode in (12365, 13257, 12221, 12364, 13269)
            and self.state.loaded
        ):
            return self.handle_socket_enchant()
        elif self.state.opcode == 13589 and self.state.loaded:
            return self.handle_inventory_uid()
        elif self.state.opcode in (12656, 13673) and self.state.loaded:
            return self.handle_inventory_bag()
        elif self.state.opcode == 12659 and self.state.loaded:
            return self.handle_consumable()
        elif self.state.opcode in (13993, 12294) and self.state.loaded:
            return self.handle_item_unpack()
        elif self.state.opcode == 12561 and self.state.loaded:
            return self.handle_item_inspect()
        elif self.state.opcode == 13447 and self.state.loaded:
            return self.handle_recycle_preview()
        elif self.state.opcode == 12787 and self.state.loaded:
            return self.handle_recycle()
        elif self.state.opcode == 13057 and self.state.loaded:
            return self.handle_item_upgrade()
        elif self.state.opcode == 12490 and self.state.loaded:
            return self.handle_inventory_action()
        elif self.state.opcode == 12804 and self.state.loaded:
            return self.handle_equipment_action()
        elif self.state.opcode == 13686 and self.state.loaded:
            return self.handle_storage_travel()
        elif self.state.opcode == 12463 and self.state.loaded:
            return self.handle_transport_list()
        elif self.state.opcode == 12223 and self.state.loaded:
            return self.handle_transport_select()
        elif self.state.loaded and (
            self.state.opcode == 12296 or self.state.artifact_action_request
        ):
            return self.handle_transport_travel()
        elif self.state.opcode == 12962 and self.state.generation:
            return self.handle_tutorial()
        elif self.state.opcode == 12091 and self.state.loaded:
            return self.handle_build_view()
        elif self.state.opcode == 13169 and self.state.loaded:
            return self.handle_build_select()
        elif self.state.opcode == 13776 and self.state.loaded:
            return self.handle_build_reset()
        elif self.state.opcode == 12772 and self.state.loaded:
            return self.handle_build_save()
        elif self.state.opcode == 13578 and self.state.loaded:
            return self.handle_haven_bag_enter()
        elif (
            self.state.opcode in (12844, 12004, 14616, 12531, 13994)
            and self.state.loaded
        ):
            return self.handle_haven_furniture()
        elif self.state.opcode in (12038, 12529, 12551, 13050) and self.state.loaded:
            return self.handle_haven_chest()
        elif self.state.opcode == 12686 and self.state.loaded:
            return self.handle_haven_permissions()
        elif self.state.loaded and (
            self.state.opcode in (12380, 13982)
            or (
                self.state.opcode == 12870
                and len(self.state.body) == 12
                and (
                    struct.unpack_from(">q", self.state.body)[0] == 36028
                    or (
                        self.state.ranch_session is not None
                        and struct.unpack_from(">H", self.state.body, 8)[0] == 18
                    )
                )
            )
        ):
            return self.handle_ranch_travel()
        elif (
            self.state.loaded
            and self.state.ranch_session is not None
            and self.state.opcode == 12870
            and (
                len(self.state.body) == 12
                and struct.unpack_from(">q", self.state.body)[0] in (36068, 36069)
            )
        ):
            return self.handle_ranch_bridge()
        elif self.state.loaded and self.state.opcode in (12068, 12320):
            return self.handle_ranch_building()
        elif self.state.loaded and self.state.opcode in (13541, 12617, 13017, 13961):
            return self.handle_ranch_construction()
        elif (
            self.state.loaded
            and self.state.ranch_session is not None
            and self.state.opcode in (12671, 12662, 13480)
        ):
            return self.handle_ranch_production()
        elif (
            self.state.loaded
            and self.state.ranch_session is not None
            and (
                self.state.opcode == 12766
                or self.state.opcode == 12363
                or (
                    self.state.opcode == 12870
                    and len(self.state.body) == 12
                    and struct.unpack_from(">H", self.state.body, 8)[0] in (23, 29)
                )
            )
        ):
            return self.handle_ranch_interaction()
        elif (
            self.state.opcode == 12870
            and self.state.loaded
            and rii_zaap_activation(self.state.character, self.state.body)
        ):
            return self.handle_rii_zaap_scene()
        elif (
            self.state.opcode == 12870
            and self.state.loaded
            and astrub_house_exit_activation(self.state.character, self.state.body)
        ):
            return self.handle_astrub_house_exit()
        elif self.state.opcode in (12870, 12363) and self.state.loaded:
            return self.handle_world_interaction()
        elif self.state.opcode == 13826 and self.state.loaded:
            return self.handle_haven_furniture_move()
        elif self.state.opcode == 12580 and self.state.loaded:
            return self.handle_haven_bag_settings()
        elif self.state.opcode in (12177, 13090) and self.state.loaded:
            return self.handle_haven_bag_transfer()
        elif self.state.opcode == 13210 and self.state.loaded:
            return self.handle_haven_bag_permission()
        elif self.state.opcode == 13434 and self.state.loaded:
            return self.handle_haven_bag_access()
        elif self.state.opcode == 12247 and self.state.loaded:
            return self.handle_haven_bag_leave()
        elif self.state.opcode in (13191, 13345, 12019) and self.state.loaded:
            return self.handle_companion_equipment()
        elif self.state.opcode == 12555 and self.state.loaded:
            return self.handle_companion_action()
        elif self.state.opcode == 12219 and self.state.loaded:
            return self.handle_companion_view()
        elif self.state.opcode == 12006 and self.state.loaded:
            return self.handle_hero_switch()
        elif self.state.opcode == 12054 and self.state.loaded:
            return self.handle_hero_roster()
        elif self.state.opcode == 13498 and self.state.loaded:
            return self.handle_emote()
        elif self.state.opcode == 13331 and self.state.loaded:
            return self.handle_world_movement()
        elif (
            self.state.opcode == 13222
            and self.state.loaded
            and self.try_native_monster_destroy(self.state.body)
        ):
            return self.handle_monster_destroy()
        elif self.state.opcode in (13222, 12058, 12535) and self.state.loaded:
            return self.handle_world_dialogue()
        elif self.state.opcode == 13397 and self.state.loaded:
            return self.handle_guild_daily_quest()
        elif (
            self.state.opcode in self.runtime.GUILD_REQUEST_OPCODES
            and self.state.loaded
        ):
            return self.handle_guild_request()
        elif (
            self.state.opcode in (13074, 13224, 13188, 13831, 12116, 13702, 12387)
            and self.state.loaded
        ):
            return self.handle_chat_channel()
        elif self.state.opcode in (784, 657, 672, 799, 12449) and self.state.loaded:
            return self.handle_social_contact()
        elif (
            self.state.opcode
            in (13140, 12997, 13037, 12510, 12203, 12781, 13406, 12027, 13113)
            and self.state.loaded
        ):
            return self.handle_exchange()
        elif self.state.opcode in (1156, 1031, 1074, 1066) and self.state.loaded:
            return self.handle_party()
        elif self.state.opcode in (12455, 13765) and self.state.loaded:
            return self.handle_cosmetic()
        elif self.state.opcode == 13917 and self.state.loaded:
            return self.handle_private_chat()
        elif self.state.opcode == 12366 and self.state.loaded:
            return self.handle_local_chat()
        else:
            self.runtime.record(
                event="request_rejected",
                opcode=self.state.opcode,
                reason="No handler for this opcode in the current session state",
                loaded=self.state.loaded,
                authenticated=self.state.account_id is not None,
            )
        return DispatchResult.FALLTHROUGH
