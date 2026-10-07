"""Offline body decoders for verified layouts from the installed Wakfu JAR."""
import base64, struct, zlib

DIRECTIONS = {
    0: ("EAST", 1, -1),
    1: ("SOUTH_EAST", 1, 0),
    2: ("SOUTH", 1, 1),
    3: ("SOUTH_WEST", 0, 1),
    4: ("WEST", -1, 1),
    5: ("NORTH_WEST", -1, 0),
    6: ("NORTH", -1, -1),
    7: ("NORTH_EAST", 0, -1),
}
MOVEMENT_MODES = {
    0: "WALK",
    1: "RUN",
    2: "SLIDE",
    3: "SWIM",
    4: "WALK_CARRY",
    5: "THROW",
    6: "CUSTOM_WALK",
    7: "TRAJECTORY",
    8: "NONE",
    9: "WALK_SPELL",
    10: "RUN_IN_FIGHT",
    11: "MOUNT",
    12: "MOUNT_WALK",
    13: "WALK_WEAPON",
    14: "RUN_CARRY",
    -1: "UNKNOWN",
}
APPEARANCE_FIELDS = (
    "skinColor",
    "hairColor",
    "pupilColor",
    "costumeColor1",
    "costumeColor2",
    "costumeColor3",
    "costumeColor4",
    "costumeColor5",
    "costumeColor6",
    "clothIndex",
    "faceIndex",
    "sex",
    "currentTitle",
    "headRefId",
    "shouldersRefId",
    "chestRefId",
)
NATION_UPDATE_TYPES = {
    0: "FOR_WORLD_TO_GLOBAL",
    1: "FOR_GLOBAL_TO_WORLD",
    2: "ID_ONLY",
    3: "SERVER_CANDIDATES",
    4: "LAWS",
    5: "SURVEY",
    6: "DIPLOMACY",
    7: "GOVERNMENT",
    8: "ECONOMY",
    9: "PROTECTORS",
    10: "TRAVELLING_NATION_CHANGE",
    11: "FORBIDDEN_CANDIDATES",
    12: "GLOBAL_TO_GAME_INITIALISATION",
    13: "GLOBAL_TO_GAME_VOTE_STATUS",
    14: "GLOBAL_TO_GAME_VOTE_UPDATE",
    15: "GLOBAL_TO_GAME_PROTECTOR_BUFFS",
    16: "GAME_TO_LOCAL_FOR_CHARACTER_NATION_INITIALIZATION",
    17: "GLOBAL_TO_LOCAL_FOR_CHARACTER_NATION_INITIALIZATION",
}
CREATION_RESULTS = {
    0: "success",
    102: "existing_name",
    103: "invalid_name",
    104: "too_many_characters",
    105: "pending_migration_request",
    106: "character_class_disabled",
}


def decode_integer_proto(body, fields):
    """Verified protobuf messages containing only signed int32/int64 fields."""
    r = Reader(body)
    result = {}

    def varint():
        value = 0
        for shift in range(0, 70, 7):
            byte = r.number("B")
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("Invalid protobuf varint")

    while r.pos < len(body):
        tag = varint()
        number = tag >> 3
        if tag & 7 or number not in fields:
            raise ValueError("Unsupported integer protobuf field")
        name, bits = fields[number]
        value = varint() & ((1 << bits) - 1)
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        result[name] = value
    return result


def decode_appearance(body):
    """appearance.proto/dS: sixteen int32 fields, including signed sentinels."""
    r = Reader(body)

    def varint():
        value = 0
        for shift in range(0, 70, 7):
            byte = r.number("B")
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("Invalid appearance varint")

    result = {}
    while r.pos < len(body):
        tag = varint()
        number = tag >> 3
        if tag & 7 or not 1 <= number <= len(APPEARANCE_FIELDS):
            raise ValueError("Unsupported appearance field")
        value = varint() & 0xFFFFFFFF
        if value & 0x80000000:
            value -= 1 << 32
        result[APPEARANCE_FIELDS[number - 1]] = value
    return result


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("Truncated or invalid length")
        result = self.data[self.pos : self.pos + n]
        self.pos += n
        return result

    def number(self, fmt):
        return struct.unpack(">" + fmt, self.take(struct.calcsize(">" + fmt)))[0]

    def text(self, width="I"):
        return self.take(self.number(width)).decode("utf-8")

    def finish(self):
        if self.pos != len(self.data):
            raise ValueError(f"{len(self.data)-self.pos} undecoded bytes")


def decode_body(direction, opcode, body):
    r = Reader(body)
    fields = None
    if direction == "out":
        if opcode in (574, 402, 1026, 14689, 300):
            fields = {}
        elif opcode == 13130:
            fields = {
                "target_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
                "auto_lock": bool(r.number("B")),
            }
        elif opcode == 13220:
            fields = {
                "item_action_id": r.number("i"),
                "item_uid": r.number("q"),
                "action_binary_hex": r.take(len(body) - 12).hex(),
            }
        elif opcode == 13222:
            fields = {
                "npc_id": r.number("q"),
                "action_id": r.number("q"),
                "action_binary_hex": r.take(len(body) - 16).hex(),
            }
        elif opcode == 13498:
            fields = {"emote_id": r.number("i"), "target_id": r.number("q")}
        elif opcode == 33:
            fields = {"version_bytes_hex": r.take(len(body)).hex()}
        elif opcode == 584:
            n = r.number("I")
            fields = {
                "encrypted_authentication_bytes": n,
                "encrypted_authentication_base64": base64.b64encode(r.take(n)).decode(),
            }
        elif opcode == 575:
            fields = {"server_id": r.number("i")}
            has = r.number("B")
            fields["optional_id"] = r.number("q") if has else None
        elif opcode == 426:
            fields = {"ticket": r.text(), "machine_identifier": r.text()}
        elif opcode == 22954:
            fields = {"language": r.text()}
        elif opcode == 23664:
            fields = {"character_id": r.number("q"), "character_name": r.text()}
        elif opcode == 22870:
            fields = {"character_id": r.number("q")}
            if fields["character_id"] <= 0:
                raise ValueError("Invalid character deletion identity")
        elif opcode == 22296:
            fields = {
                "character_id": r.number("q"),
                "breed_id": r.number("h"),
                "character_name": r.text("B"),
                "creation_flag": bool(r.number("B")),
            }
            appearance = r.take(r.number("H"))
            fields["appearance"] = decode_appearance(appearance)
        elif opcode == 12231:
            fields = {
                "craft_station_id": r.number("q"),
                "recipe_id": r.number("i"),
                "quantity": r.number("i"),
            }
        elif opcode == 363:
            fields = {
                "service_route": r.number("B"),
                "ping_id": r.number("i"),
                "sent_nanoseconds": r.number("q"),
            }
        elif opcode == 12058:
            fields = {"dialogue_id": r.number("i"), "choice_id": r.number("i")}
        elif opcode == 12296:
            fields = {
                "interactive_element_id": r.number("q"),
                "destination_id": r.number("i"),
                "flag": bool(r.number("B")),
                "iTS": r.number("i"),
            }
        elif opcode == 12656:
            fields = {
                "bfx": r.number("q"),
                "mss": r.number("q"),
                "kfj": r.number("q"),
                "msq": r.number("b"),
            }
        elif opcode == 12659:
            fields = {"item_id": r.number("q"), "has_position": bool(r.number("B"))}
            if fields["has_position"]:
                fields["position"] = {
                    "x": r.number("i"),
                    "y": r.number("i"),
                    "z": r.number("h"),
                }
        elif opcode == 12870:
            # cpF allocates 12 bytes but writes only i64+i16; two trailing
            # zero bytes are part of the actual Java wire layout.
            fields = {
                "interactive_element_id": r.number("q"),
                "action_id": r.number("h"),
                "padding_hex": r.take(2).hex(),
            }
        elif opcode == 12921:
            fields = {"server_event_id": r.number("i")}
        elif opcode == 12925:
            fields = {"fight_id": r.number("i"), "flag": bool(r.number("B"))}
        elif opcode == 12962:
            flag = bool(r.number("B"))
            count = r.number("i")
            if not 0 <= count <= (len(body) - r.pos) // 4:
                raise ValueError("Invalid cnG entry count")
            fields = {"flag": flag, "ids": [r.number("i") for _ in range(count)]}
        elif opcode == 12995:
            # Current callers use dynamic cmC + zg protobuf, replacing the
            # still-present cnj legacy fixed-width serializer.
            fields = decode_integer_proto(
                r.take(len(body)), {1: ("action_id", 32), 2: ("x", 32), 3: ("y", 32)}
            )
        elif opcode == 13130:
            fields = {
                "bgA": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
                "mri": bool(r.number("B")),
            }
        elif opcode == 13260:
            fields = {
                "actor_id": r.number("q"),
                "mrK": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
            }
        elif opcode == 13429:
            fields = {"result": r.number("b"), "occupation_type": r.number("h")}
        elif opcode == 13481:
            fields = decode_integer_proto(
                r.take(len(body)), {1: ("action_id", 32), 2: ("monster_id", 64)}
            )
        elif opcode == 13130:
            fields = {
                "target_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
                "auto_lock": bool(r.number("B")),
            }
        elif opcode == 13220:
            fields = {
                "item_action_id": r.number("i"),
                "item_uid": r.number("q"),
                "action_binary_hex": r.take(len(body) - 12).hex(),
            }
        elif opcode == 13222:
            fields = {
                "npc_id": r.number("q"),
                "action_id": r.number("q"),
                "action_binary_hex": r.take(len(body) - 16).hex(),
            }
        elif opcode == 13498:
            fields = {"ezG": r.number("i"), "bgA": r.number("q")}
        elif opcode == 13510:
            fields = {"turn_id": r.number("i")}
        elif opcode == 15494:
            fields = {
                "query_type": r.number("b"),
                "eiR": r.number("i"),
                "lXi": r.number("i"),
            }
        elif opcode == 23481:
            fields = {}
        elif opcode == 649:
            fields = {"request_type": r.number("i"), "meaning": "unresolved"}
        elif opcode in (12225, 12851):
            fields = {"character_id": r.number("q")}
        elif opcode == 13003:
            fields = {"language": r.take(len(body)).decode("utf-8")}
        elif opcode == 12010:
            fields = {"language_mask": r.number("B"), "language_id": r.number("B")}
        elif opcode == 13331:
            mode = r.number("i")
            x, y, z, n = r.number("i"), r.number("i"), r.number("h"), r.number("B")
            steps = []
            for _ in range(n):
                b = r.number("B")
                d = b >> 5
                dz = b & 31
                dz = dz - 32 if dz & 16 else dz
                name, dx, dy = DIRECTIONS[d]
                steps.append(
                    {
                        "direction": d,
                        "name": name,
                        "dx": dx,
                        "dy": dy,
                        "dz": dz,
                        "encoded_byte": b,
                    }
                )
            fields = {
                "mode_id": mode,
                "mode": MOVEMENT_MODES.get(mode),
                "start_position": {"x": x, "y": y, "z": z},
                "end_position": {
                    "x": x + sum(s["dx"] for s in steps),
                    "y": y + sum(s["dy"] for s in steps),
                    "z": z + sum(s["dz"] for s in steps),
                },
                "step_count": n,
                "steps": steps,
            }
        elif opcode == 12161:
            actor = r.number("q")
            points = []
            if (len(body) - 8) % 10:
                raise ValueError("Invalid fight path length")
            while r.pos < len(body):
                points.append(
                    {"x": r.number("i"), "y": r.number("i"), "z": r.number("h")}
                )
            fields = {"actor_id": actor, "points": points}
        elif opcode == 12889:
            fields = {
                "actor_id": r.number("q"),
                "spell_instance_id": r.number("q"),
                "mode": r.number("B"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
            }
        elif opcode == 12543:
            fields = {"x": r.number("i"), "y": r.number("i"), "z": r.number("h")}
        elif opcode == 12806:
            fields = {
                "actor_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
            }
        elif opcode == 13655:
            fields = {"actor_id": r.number("q"), "direction": r.number("B")}
        elif opcode == 12403:
            fields = {"actor_id": r.number("q"), "turn_id": r.number("h")}
        elif opcode == 13110:
            fields = {"request_help": bool(r.number("B"))}
        elif opcode == 12523:
            fields = {"ready": bool(r.number("B"))}
        elif opcode in (12366, 13074, 13744, 13702):
            fields = {"text": r.text("H")}
        elif opcode in (13188, 13831):
            fields = {"language_id": r.number("B"), "text": r.text("H")}
        elif opcode == 13224:
            fields = {"group_id": r.number("q"), "text": r.text("H")}
        elif opcode == 13917:
            fields = {"recipient": r.text("B"), "text": r.text("H")}
    else:
        if opcode in (13726, 13337, 13482, 12502, 13494, 12727, 13970):
            fields = {
                "fight_id": r.number("i"),
                "action_id": r.number("i"),
                "mzn": r.number("i"),
                "actor_id": r.number("q"),
            }
            if opcode in (13337, 13482):
                fields["turn_delay"] = r.number("q")
            elif opcode == 12502:
                fields.update(huU=r.number("i"), huV=r.number("i"))
            elif opcode == 13494:
                fields["direction"] = r.number("b")
            elif opcode == 12727:
                fields["vital_state"] = r.number("b")
            elif opcode == 13970:
                fields.update(mzI=r.number("i"), huT=r.number("B") == 1)
        elif opcode == 13420:
            fields = {"fight_id": r.number("i")}
        elif opcode == 13684:
            fields = {"fight_id": r.number("i"), "placement_duration": r.number("i")}
        elif opcode == 13887:
            fields = {
                "fight_id": r.number("i"),
                "actor_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
            }
        elif opcode in (13205, 13312, 13832):
            fields = {
                "actor_id": r.number("q"),
                "achievement_id" if opcode != 13832 else "objective_id": r.number("i"),
            }
        elif opcode == 13371:
            fields = {
                "actor_id": r.number("q"),
                "achievement_id": r.number("i"),
                "tracked": bool(r.number("B")),
            }
        elif opcode == 13422:
            fields = {
                "actor_id": r.number("q"),
                "achievement_id": r.number("i"),
                "completion_time": r.number("q"),
            }
        elif opcode == 13295:
            fields = {
                "actor_id": r.number("q"),
                "variable_id": r.number("i"),
                "value": r.number("q"),
            }
        elif opcode == 13256:
            fields = {}
        elif opcode == 13462:
            fields = {
                "item_id": r.number("q"),
                "item_reference": r.number("i"),
                "quantity": r.number("h"),
                "notification": bool(r.number("B")),
                "actor_id": r.number("q"),
            }
        elif opcode == 13411:
            fields = {
                "mEC": r.number("B") == 1,
                "atv": r.number("i"),
                "atu": r.number("i"),
            }
            count = r.number("b")
            if count < 0:
                raise ValueError("Invalid objective actor count")
            fields["actors"] = [r.number("q") for _ in range(count)]
        elif opcode == 12782:
            fields = {
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
                "resource_state": r.number("h"),
                "kEB": r.number("q"),
                "kEC": r.number("i"),
            }
        elif opcode == 12634:
            fields = {"actor_id": r.number("q"), "result_id": r.number("i")}
        elif opcode == 13928:
            fields = {"actor_id": r.number("q")}
        elif opcode == 13421:
            fields = {
                "actor_id": r.number("q"),
                "resource_action_id": r.number("i"),
                "enabled": bool(r.number("B")),
            }
        elif opcode == 13948:
            fields = {"mwN": r.number("q"), "mwO": r.number("b")}
            for name in ("bJZ", "mwP", "mwQ", "mwR", "mwS", "mwT"):
                fields[name] = r.number("f")
            fields["weather_id"] = r.number("i")
        elif opcode == 314:
            fields = {
                "service": r.number("b"),
                "ping_id": r.number("i"),
                "client_nanotime": r.number("q"),
                "server_receive_nanotime": r.number("q"),
                "server_send_nanotime": r.number("q"),
            }
        elif opcode == 23354:
            fields = {"server_time": r.number("q")}
        elif opcode == 23597:
            count = r.number("b")
            if count < 0:
                raise ValueError("Invalid suggested name count")
            fields = {"suggested_names": [r.text("b") for _ in range(count)]}
        elif opcode == 22025:
            status = r.number("b")
            fields = {"status": status, "success": status == 0}
            fields["reason"] = CREATION_RESULTS.get(status, "unspecified_error")
        elif opcode == 12470:
            fields = {
                "item_id": r.number("q"),
                "quantity": r.number("h"),
                "padding_hex": r.take(2).hex(),
            }
        elif opcode == 13652:
            fight = r.number("i")
            count = r.number("h")
            if count < 0:
                raise ValueError("Invalid relocation actor count")
            actors = [
                {
                    "actor_id": r.number("q"),
                    "x": r.number("i"),
                    "y": r.number("i"),
                    "z": r.number("h"),
                }
                for _ in range(count)
            ]
            fields = {
                "fight_id": fight,
                "actors": actors,
                "force_immediate": bool(r.number("B")),
            }
            if len(body) - r.pos == 4:
                fields["padding_hex"] = r.take(4).hex()
        elif opcode == 12705:
            fields = {
                "dIy": r.number("i"),
                "mzn": r.number("i"),
                "mEW": bool(r.number("B")),
                "mzM": bool(r.number("B")),
                "effect_id": r.number("i"),
            }
            fields["effect_binary_hex"] = r.take(r.number("h")).hex()
            if (len(body) - r.pos) % 16:
                raise ValueError("Invalid effect triplet records")
            fields["triplets"] = [
                {
                    "first": r.number("i"),
                    "second": r.number("i"),
                    "third": r.number("q"),
                }
                for _ in range((len(body) - r.pos) // 16)
            ]
        elif opcode == 12954:
            fields = {
                "mEI": r.number("q"),
                "eiT": r.number("i"),
                "success": bool(r.number("B")),
            }
        elif opcode == 13778:
            reset = r.number("b")
            count = r.number("b")
            if count < 0:
                raise ValueError("Invalid reserved UID count")
            fields = {
                "clear_reserve": reset == 0,
                "reserved_uids": [r.number("q") for _ in range(count)],
            }
        elif opcode == 12877:
            fields = {"enabled": bool(r.number("B")), "world_context_id": r.number("q")}
        elif opcode == 13026:
            fields = {"fight_id": r.number("i")}
        elif opcode == 15548:
            fields = {
                "character_id": r.number("q"),
                "entity_binary_hex": r.take(r.number("h")).hex(),
            }
        elif opcode == 15529:
            actor = r.number("q")
            count = r.number("h")
            if count < 0:
                raise ValueError("Invalid monthly dungeon count")
            fields = {
                "actor_id": actor,
                "monthly_completed_dungeons": [r.number("i") for _ in range(count)],
            }
        elif opcode == 14303:
            decompressor = zlib.decompressobj()
            plain = decompressor.decompress(body, 16 * 1024 * 1024 + 1)
            if (
                len(plain) > 16 * 1024 * 1024
                or decompressor.unconsumed_tail
                or not decompressor.eof
                or decompressor.unused_data
            ):
                raise ValueError("Invalid or oversized market price compression")
            r.pos = len(body)
            p = Reader(plain)
            fields = {"market_prices": []}
            while p.pos < len(plain):
                ref = p.number("i")
                mask = p.number("B")
                if mask & ~31:
                    raise ValueError("Unsupported market price mask")
                prices = [
                    p.number("q") if mask & (1 << index) else -1 for index in range(5)
                ]
                fields["market_prices"].append(
                    {"item_reference": ref, "prices_by_variant_index": prices}
                )
        elif opcode == 15984:
            fields = {"nations": []}
            while r.pos < len(body):
                nation_id = r.number("i")
                size = r.number("i")
                blob = r.take(size)
                subtype = blob[0] if blob else None
                fields["nations"].append(
                    {
                        "nation_id": nation_id,
                        "update_type": NATION_UPDATE_TYPES.get(subtype),
                        "nested_binary_hex": blob.hex(),
                    }
                )
        elif opcode == 13735:
            fields = {
                "actor_id": r.number("q"),
                "animation_definition_id": r.number("i"),
                "ending": bool(r.number("B")),
            }
            if len(body) - r.pos == 4:
                fields["padding_hex"] = r.take(4).hex()
        elif opcode == 23992:
            fields = {"additional_character_slots": r.number("b")}
        elif opcode == 13574:
            fields = {"actor_id": r.number("q"), "gauge_value": r.number("i")}
        elif opcode == 12916:
            fields = {"profession_id": r.number("i"), "xp_gain": r.number("q")}
        elif opcode == 13479:
            fields = {
                "result_id": r.number("b"),
                "mxQ": r.number("i"),
                "quantity": r.number("h"),
            }
        elif opcode == 12471:
            fields = {
                "container_id": r.number("q"),
                "destination_position": r.number("h"),
            }
            size = r.number("i")
            if size < 0:
                raise ValueError("Invalid inventory object length")
            fields["item_binary_hex"] = r.take(size).hex()
            fields["mAB"] = bool(r.number("B"))
        elif opcode == 12401:
            fields = {"actor_id": r.number("q"), "direction": r.number("b")}
        elif opcode == 12447:
            fields = {
                "actor_id": r.number("q"),
                "property_family": r.number("b"),
                "property_id": r.number("b"),
                "operation": r.number("b"),
            }
        elif opcode == 12503:
            fields = {"actor_id": r.number("q"), "spells": []}
            if (len(body) - r.pos) % 14:
                raise ValueError("Invalid learned spell records")
            while r.pos < len(body):
                fields["spells"].append(
                    {
                        "reference_id": r.number("i"),
                        "uid": r.number("q"),
                        "level": r.number("h"),
                    }
                )
        elif opcode == 13249:
            fields = {
                "actor_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
            }
        elif opcode == 13259:
            fields = {
                "actor_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
                "mxm": bool(r.number("B")),
                "mxn": bool(r.number("B")),
            }
        elif opcode == 12436:
            fields = {
                "actor_id": r.number("q"),
                "health": r.number("i"),
                "regeneration_coefficient": r.number("i"),
            }
        elif opcode == 12318:
            fields = {"world_x": r.number("i"), "world_y": r.number("i")}
        elif opcode == 13060:
            actor = r.number("q")
            count = r.number("b")
            if count < 0:
                raise ValueError("Invalid actor attribute count")
            fields = {
                "actor_id": actor,
                "attributes": [
                    {
                        "id": r.number("b"),
                        "first_value": r.number("i"),
                        "second_value": r.number("i"),
                    }
                    for _ in range(count)
                ],
            }
        elif opcode == 12218:
            fields = {"dialogue_id": r.number("i")}
        elif opcode == 12969:
            fields = {
                "dialogue_id": r.number("i"),
                "result": r.number("b"),
                "actor_id": r.number("q"),
            }
        elif opcode == 13417:
            fields = {
                "actor_id": r.number("q"),
                "item_reference": r.number("i"),
                "quantity": r.number("i"),
            }
        elif opcode == 13021:
            fields = {"kamas": r.number("q")}
        elif opcode == 13852:
            actor = r.number("q")
            path = decode_body(
                "out", 13331, struct.pack(">i", -1) + r.take(len(body) - 8)
            )
            fields = {
                "actor_id": actor,
                **{
                    key: value
                    for key, value in path.items()
                    if key not in ("mode_id", "mode")
                },
            }
        elif opcode == 13530:
            fields = {
                "actor_id": r.number("q"),
                "x": r.number("i"),
                "y": r.number("i"),
                "z": r.number("h"),
                "direction": r.number("B"),
                "mode_id": r.number("i"),
            }
            fields["mode"] = MOVEMENT_MODES.get(fields["mode_id"])
        elif opcode == 13046:
            fields = {"actor_id": r.number("q")}
            n = r.number("h")
            fields["entity_state_base64"] = base64.b64encode(r.take(n)).decode()
        elif opcode == 12728:
            n = r.number("B")
            fields = {"payload_base64": base64.b64encode(r.take(n)).decode()}
        elif opcode == 400:
            fields = {
                "challenge": r.number("q"),
                "public_key_base64": base64.b64encode(r.take(len(body) - 8)).decode(),
            }
        elif opcode == 309:
            fields = {"seed_hex": r.take(4).hex()}
        elif opcode == 23:
            fields = {
                "version_accepted": bool(r.number("B")),
                "version_bytes_hex": r.take(len(body) - 1).hex(),
            }
        elif opcode == 762:
            fields = {
                "channel_id": r.number("i"),
                "sender": r.text("B"),
                "language_mask": r.number("B"),
                "language_id": r.number("B"),
                "sender_id": r.number("q"),
                "flag": bool(r.number("B")),
                "text": r.text("H"),
            }
    if fields is not None:
        r.finish()
    return fields
