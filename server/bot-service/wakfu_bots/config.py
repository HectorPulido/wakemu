"""Validated, atomically persisted behavior profiles, separate from World bindings."""
import copy
import json
import os
import re
import threading
from pathlib import Path


BOT_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")


def validate_profile(value):
    if not isinstance(value, dict) or set(value) - {
        "bot_id",
        "character",
        "enabled",
        "capabilities",
        "behaviors",
    }:
        raise ValueError("Invalid bot profile fields")
    bot_id = value.get("bot_id")
    if not isinstance(bot_id, str) or not BOT_ID.fullmatch(bot_id):
        raise ValueError("Invalid bot ID")
    if type(value.get("enabled")) is not bool:
        raise ValueError("Bot enabled must be boolean")
    character = value.get("character")
    if (
        not isinstance(character, dict)
        or set(character) - {"name", "breed", "sex", "initial_kamas", "location"}
        or not {"name", "breed", "sex"} <= set(character)
    ):
        raise ValueError("Character name, breed and sex are required")
    if (
        not isinstance(character["name"], str)
        or not character["name"].strip()
        or len(character["name"]) > 25
    ):
        raise ValueError("Invalid character name")
    if type(character["breed"]) is not int or not 1 <= character["breed"] <= 20:
        raise ValueError("Invalid character breed")
    if type(character["sex"]) is not int or character["sex"] not in (0, 1):
        raise ValueError("Invalid character sex")
    kamas = character.get("initial_kamas", 0)
    if type(kamas) is not int or not 0 <= kamas <= 10**9:
        raise ValueError("Invalid initial bot budget")
    if "location" in character:
        location = character["location"]
        if not isinstance(location, dict) or set(location) != {
            "map_id",
            "instance_id",
            "x",
            "y",
            "z",
        }:
            raise ValueError("Invalid initial bot location")
        if (
            any(type(value) is not int for value in location.values())
            or location["instance_id"] != 0
        ):
            raise ValueError("Bots require integer coordinates in a public instance")
    capabilities = value.get("capabilities", [])
    if (
        not isinstance(capabilities, list)
        or any(
            not isinstance(item, str) or item not in {"shop", "llm"}
            for item in capabilities
        )
        or len(set(capabilities)) != len(capabilities)
    ):
        raise ValueError("Invalid optional bot capabilities")
    behaviors = value.get("behaviors", {})
    if (
        not isinstance(behaviors, dict)
        or not behaviors
        or any(
            not isinstance(key, str) or not isinstance(settings, dict)
            for key, settings in behaviors.items()
        )
    ):
        raise ValueError("At least one behavior configuration is required")
    if "buyer" in behaviors:
        buyer = behaviors["buyer"]
        if set(buyer) - {"purchase_percent"} or "shop" not in capabilities:
            raise ValueError("Buyer requires the shop capability")
        percent = buyer.get("purchase_percent", 80)
        if type(percent) is not int or not 1 <= percent <= 100:
            raise ValueError("Invalid purchase percentage")
    if "llm" in behaviors:
        llm = behaviors["llm"]
        if set(llm) - {"personality"} or "llm" not in capabilities:
            raise ValueError("Conversation requires the explicit llm capability")
        if (
            not isinstance(llm.get("personality", ""), str)
            or len(llm.get("personality", "")) > 4096
        ):
            raise ValueError("Invalid bot personality")
    if "announcer" in behaviors:
        announcer = behaviors["announcer"]
        if set(announcer) != {"interval_seconds", "text"}:
            raise ValueError("Invalid announcer settings")
        interval, message = announcer["interval_seconds"], announcer["text"]
        if type(interval) is not int or not 10 <= interval <= 86400:
            raise ValueError("Invalid announcement interval")
        if (
            not isinstance(message, str)
            or not message.strip()
            or len(message.encode()) > 1024
            or "\x00" in message
        ):
            raise ValueError("Invalid announcement text")
    return copy.deepcopy(dict(value, capabilities=capabilities, behaviors=behaviors))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        os.chmod(temporary, 0o600)
        json.dump(value, output, ensure_ascii=False, separators=(",", ":"))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


class Profiles:
    def __init__(self, path, *, behavior_names=("buyer", "llm", "announcer")):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.behavior_names = frozenset(behavior_names)
        self.values = {}
        if self.path.exists():
            loaded = json.loads(self.path.read_text())
            if (
                not isinstance(loaded, dict)
                or set(loaded) != {"bots"}
                or not isinstance(loaded["bots"], list)
            ):
                raise ValueError("Invalid bot profile document")
            for entry in loaded["bots"]:
                profile = self.validate(entry)
                if profile["bot_id"] in self.values:
                    raise ValueError("Duplicate bot profile")
                self.values[profile["bot_id"]] = profile

    def validate(self, value):
        profile = validate_profile(value)
        if set(profile["behaviors"]) - self.behavior_names:
            raise ValueError("Unknown bot behavior")
        return profile

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.values)

    def put(self, bot_id, value):
        profile = self.validate(value)
        if profile["bot_id"] != bot_id:
            raise ValueError("Bot ID does not match resource")
        with self.lock:
            updated = dict(self.values, **{bot_id: profile})
            atomic_json(self.path, {"bots": list(updated.values())})
            self.values = updated
        return profile

    def remove(self, bot_id):
        with self.lock:
            if bot_id not in self.values:
                raise KeyError(bot_id)
            updated = {
                key: value for key, value in self.values.items() if key != bot_id
            }
            atomic_json(self.path, {"bots": list(updated.values())})
            self.values = updated
