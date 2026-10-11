"""Validated PostgreSQL settings and versioned reward/dungeon policy editing."""
from contextlib import nullcontext
from decimal import Decimal
import importlib
import json
import math
import re
from psycopg.types.json import Jsonb
from wakfu_server.reward_rates import MAX_REWARD_MULTIPLIER, REWARD_RATE_SCALE


_COMBAT_MULTIPLIERS = {
    "combat_xp_multiplier": ("combat_reward_policy", "xp_rate_bp"),
    "combat_kamas_multiplier": ("combat_reward_policy", "kamas_rate_bp"),
    "combat_drop_multiplier": ("combat_drop_policy", "drop_rate_bp"),
}

_COMBAT_EDITOR_ROWS = """
    SELECT 'combat_xp_multiplier',to_jsonb(trim_scale(v.xp_rate_bp::numeric/10000))
    FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v USING(version)
    WHERE a.singleton=true
    UNION ALL
    SELECT 'combat_kamas_multiplier',to_jsonb(trim_scale(v.kamas_rate_bp::numeric/10000))
    FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v USING(version)
    WHERE a.singleton=true
    UNION ALL
    SELECT 'combat_drop_multiplier',to_jsonb(trim_scale(v.drop_rate_bp::numeric/10000))
    FROM combat_drop_policy_active a JOIN combat_drop_policy_versions v USING(version)
    WHERE a.singleton=true
"""

# Legacy editor names are API aliases only; dungeon documents live in dedicated tables.
_VIRTUAL_SETTINGS = (
    """(
    SELECT name,value FROM settings
    WHERE name NOT IN ('combat_xp_multiplier','combat_kamas_multiplier','combat_drop_multiplier')
      AND NOT starts_with(name, 'dungeon_runtime_config:')
      AND NOT starts_with(name, 'dungeon_runtime_active:')
    UNION ALL
    SELECT 'dungeon_runtime_config:' || route_key || ':v' || policy_version::text,
           configuration AS value FROM dungeon_runtime_configurations
    UNION ALL
    SELECT 'dungeon_runtime_active:' || route_key,
           jsonb_build_object('version',policy_version,'key',
             'dungeon_runtime_config:' || route_key || ':v' || policy_version::text)
    FROM dungeon_runtime_active_configurations
    UNION ALL
"""
    + _COMBAT_EDITOR_ROWS
    + """
) AS editor_settings"""
)


def _settings_query(db):
    # Support the deployed schema while the independent dungeon migration is pending.
    migrated = db.execute(
        "SELECT to_regclass('dungeon_runtime_configurations') AS versions, "
        "to_regclass('dungeon_runtime_active_configurations') AS active"
    ).fetchone()
    if migrated["versions"] and migrated["active"]:
        return _VIRTUAL_SETTINGS
    return (
        "(SELECT name,value FROM settings WHERE name NOT IN "
        "('combat_xp_multiplier','combat_kamas_multiplier','combat_drop_multiplier') "
        "UNION ALL " + _COMBAT_EDITOR_ROWS + ") AS editor_settings"
    )


def _editor_row(db, name, *, lock=False):
    if name in _COMBAT_MULTIPLIERS:
        policy, column = _COMBAT_MULTIPLIERS[name]
        if lock:
            db.execute(
                "SELECT version FROM "
                + policy
                + "_active WHERE singleton=true FOR UPDATE"
            ).fetchone()
        return db.execute(
            "SELECT value,md5(value::text) revision FROM ("
            "SELECT to_jsonb(trim_scale(v."
            + column
            + "::numeric/10000)) value FROM "
            + policy
            + "_active a "
            "JOIN "
            + policy
            + "_versions v USING(version) WHERE a.singleton=true) selected"
        ).fetchone()
    config = re.fullmatch(r"dungeon_runtime_config:(.+):v([1-9][0-9]*)", name)
    if config:
        route, version = config.groups()
        return db.execute(
            "SELECT configuration AS value,md5(configuration::text) revision "
            "FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s"
            + (" FOR UPDATE" if lock else ""),
            (route, int(version)),
        ).fetchone()
    if name.startswith("dungeon_runtime_active:"):
        route = name.split(":", 1)[1]
        return db.execute(
            "SELECT value,md5(value::text) revision FROM ("
            "SELECT jsonb_build_object('version',policy_version,'key',"
            "'dungeon_runtime_config:' || route_key || ':v' || policy_version::text) value "
            "FROM dungeon_runtime_active_configurations WHERE route_key=%s"
            + (" FOR UPDATE" if lock else "")
            + ") selected",
            (route,),
        ).fetchone()
    if name.startswith("dungeon_runtime_config:"):
        raise ValueError("Invalid dungeon configuration editor name")
    return db.execute(
        "SELECT value,md5(value::text) revision FROM settings WHERE name=%s"
        + (" FOR UPDATE" if lock else ""),
        (name,),
    ).fetchone()


class SettingsConflict(ValueError):
    """The submitted editor revision is stale."""


def _shape(before, value, path="value", depth=0):
    if depth > 40:
        raise ValueError("Setting exceeds the maximum JSON nesting depth")
    if type(before) in (int, float) and type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 2147483647:
            raise ValueError(f"{path} must be a finite bounded number")
        if type(before) is int and type(value) is not int:
            raise ValueError(f"{path} must remain an integer")
        if before >= 0 and value < 0:
            raise ValueError(f"{path} cannot be negative")
    elif type(value) is not type(before):
        raise ValueError(f"{path} must retain its JSON type")
    elif isinstance(value, dict):
        if set(before) != set(value):
            raise ValueError(f"{path} must retain its configured fields")
        for key in before:
            _shape(before[key], value[key], path + "." + key, depth + 1)
    elif isinstance(value, list):
        if len(value) > 100000:
            raise ValueError(f"{path} contains too many elements")
        if before:
            structured = any(isinstance(item, (dict, list)) for item in before)
            if structured and len(value) != len(before):
                raise ValueError(f"{path} must retain its structural entries")
            for index, item in enumerate(value):
                if not structured and isinstance(before[0], str):
                    if item not in before:
                        raise ValueError(
                            f"{path} contains an unsupported configured value"
                        )
                else:
                    _shape(
                        before[index] if structured else before[0],
                        item,
                        f"{path}[{index}]",
                        depth + 1,
                    )
        elif value:
            raise ValueError(
                f"{path} has no configured element schema; populate it through its reviewed installer"
            )
    elif isinstance(value, str):
        if len(value) > 100000:
            raise ValueError(f"{path} is too long")
        # Policy source/version strings are consumer discriminators, not free text.
        if value != before and path.rsplit(".", 1)[-1] not in {
            "provenance",
            "name",
            "description",
            "notes",
        }:
            raise ValueError(f"{path} is a fixed policy discriminator")
    if (
        path.rsplit(".", 1)[-1] in {"version", "schema_version", "policy_version"}
        and before != value
    ):
        raise ValueError(
            f"{path} identifies the supported schema and cannot be changed directly"
        )


def _range(value, low, high, field):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{field} must be between {low} and {high}")


class AdminSettings:
    @staticmethod
    def _setting_name(name):
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z0-9_:.\-]{1,240}", name
        ):
            raise ValueError("Invalid setting name")
        return name

    @staticmethod
    def _setting_metadata(name, value):
        dungeon = name.startswith("dungeon_runtime_")
        restart = name == "dungeon_runtime_routes"
        mode = "restart" if restart else "new_actions"
        reason = (
            "World loads the route registry at startup; restart world after saving."
            if restart
            else "Read from PostgreSQL on the next applicable action or scheduled cycle. Existing fights, invitations and dungeon/rift runs retain their frozen configuration."
        )
        if name == "server_name":
            mode = "next_load"
            reason = "Shown when the client requests the world list again. Return to server selection or reconnect; no service restart is required."
        if name in _COMBAT_MULTIPLIERS:
            reason = (
                "Multiplier: 1 = normal, 2 = double, 0 = disabled. Range 0–9999999.9999, "
                "up to four decimal places. Applies when new combat rewards are calculated; "
                "previously recorded rewards are unchanged. No restart required."
            )
        category = (
            "Dungeons"
            if dungeon or name.startswith("dungeon_")
            else "Combat"
            if name.startswith(("combat_", "fight_", "friendly_"))
            else "Ecology"
            if name.startswith(
                (
                    "monster_",
                    "personal_ecology",
                    "weather_",
                    "planting_",
                    "open_planting",
                    "resource_",
                    "fishing_",
                    "mining_",
                )
            )
            else "Items and economy"
            if name.startswith(
                (
                    "socket_",
                    "mount",
                    "pet_",
                    "recycling",
                    "profession_",
                    "player_exchange",
                )
            )
            else "Social and access"
            if name.startswith(("guild_", "chat_", "player_", "emote_", "exploration_"))
            else "General"
        )
        edit_mode = (
            "new_version"
            if name.startswith("dungeon_runtime_config:")
            else "select_version"
            if name.startswith("dungeon_runtime_active:")
            else "json"
        )
        summary = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return dict(
            category=category,
            summary=summary[:220] + ("…" if len(summary) > 220 else ""),
            apply_mode=mode,
            apply_reason=reason,
            edit_mode=edit_mode,
            editable=True,
        )

    def settings(self, q="", limit=50, offset=0):
        with self.store.connection() as db:
            result = self._list(
                db,
                "SELECT name,md5(value::text) revision,jsonb_typeof(value) value_type,octet_length(value::text) bytes,left(value::text,220) preview FROM "
                + _settings_query(db)
                + " WHERE NOT starts_with(name, 'dungeon_runtime_config:') AND NOT starts_with(name, 'dungeon_runtime_active:') AND name ILIKE %s ORDER BY name",
                ("%" + str(q)[:100] + "%",),
                limit,
                offset,
            )
        items = []
        for row in result["items"]:
            metadata = self._setting_metadata(row["name"], None)
            metadata["summary"] = row["preview"] + (
                "…" if row["bytes"] > len(row["preview"].encode()) else ""
            )
            items.append(dict(row, **metadata))
        result["items"] = items
        return result

    def setting(self, name):
        name = self._setting_name(name)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT name,value,md5(value::text) revision,jsonb_typeof(value) value_type,octet_length(value::text) bytes,left(value::text,220) preview FROM "
                + _settings_query(db)
                + " WHERE name=%s",
                (name,),
            ).fetchone()
            if row is None:
                raise LookupError("Setting not found")
            result = dict(row, **self._setting_metadata(name, row["value"]))
            if name.startswith("dungeon_runtime_active:"):
                route_key = name.split(":", 1)[1]
                result["versions"] = [
                    dict(r)
                    for r in db.execute(
                        "SELECT 'dungeon_runtime_config:' || route_key || ':v' || policy_version::text name,policy_version version,md5(configuration::text) revision FROM dungeon_runtime_configurations WHERE route_key=%s ORDER BY policy_version",
                        (route_key,),
                    )
                ]
        result[
            "validation"
        ] = "Preserve configured fields and JSON types. Numeric ranges, supported consumer policies and immutable dungeon versions are checked before commit."
        if name == "server_name":
            result[
                "validation"
            ] = "Use 1–80 characters, at most 255 UTF-8 bytes, without control characters or surrounding whitespace."
        return result

    @staticmethod
    def _validate_policy(db, name, before, value):
        if name == "server_name":
            from wakfu_server.server_identity import validate_server_name

            validate_server_name(value)
            return
        if name == "player_allowed_commands":
            if (
                not isinstance(value, list)
                or len(value) > 1000
                or any(not isinstance(item, str) for item in value)
            ):
                raise ValueError("Allowed commands must be a bounded array of strings")
        elif name == "recycling_policy":
            if not isinstance(value, dict) or not isinstance(
                value.get("disabled_item_refs"), list
            ):
                raise ValueError("Invalid recycling policy")
            _shape(
                dict(before, disabled_item_refs=[]), dict(value, disabled_item_refs=[])
            )
        else:
            _shape(before, value)
        scalars = {
            "combat_placement_duration_ms": (1000, 300000),
            "planting_duration_ms": (1, 300000),
            "mount_toggle_cooldown_ms": (0, 300000),
            "non_permanent_build_limit": (1, 24),
            "open_planting_probability": (0, 1),
        }
        if name in scalars:
            _range(value, *scalars[name], name)
        validators = {
            "monster_reproduction": (
                "monster_reproduction",
                "validate_policy",
                "value",
            ),
            "monster_maturation": ("monster_maturation", "validate_policy", "value"),
            "fight_placement_policy": ("combat_placement_policy", "_policy", "value"),
            "rift_policy": ("rift_policy", "validate", "value"),
            "rift_reward_policy": ("rift_rewards", "validate_policy", "value"),
            "player_party_policy": ("player_parties", "_policy", "db"),
            "player_exchange_policy": ("player_exchanges", "_policy", "db"),
            "friendly_duel_policy": ("friendly_duels", "_invitation_policy", "db"),
            "socket_enchantment_policy": ("socket_enchantment", "_policy", "db"),
            "socket_identification_policy": ("shard_identification", "_policy", "db"),
            "recycling_policy": ("recycling", "_policy", "db"),
            "monster_harvest": ("monster_collect", "policy", "db"),
            "monster_corpse_policy": ("monster_corpses", "lifetime_seconds", "db"),
            "profession_action_rewards": ("profession_rewards", "base_xp", "rewards"),
        }
        if name in validators:
            module, function, argument = validators[name]
            validator = getattr(
                importlib.import_module("wakfu_server." + module), function
            )
            if argument == "rewards":
                validator(db, "harvest")
            else:
                validator(value if argument == "value" else db)
        if name == "monster_wander":
            from wakfu_server.monster_wander import policy

            class BorrowedStore:
                def connection(self):
                    return nullcontext(db)

            policy(BorrowedStore())
        if name in ("fishing_spot_policy", "mining_vein_policy"):
            _range(value["respawn_seconds"], 1, 2678400, "respawn_seconds")
        if name == "profession_xp":
            _range(
                value["multiplier_basis_points"], 0, 1000000, "multiplier_basis_points"
            )
        if name == "personal_ecology_policy":
            from wakfu_server.ecology_policy import bounds

            bounds(value["plant"])
            bounds(value["monster"])
            _range(value["balance_delta"], 1, 9900, "balance_delta")
            _range(value["imbalance_delta"], -9900, -1, "imbalance_delta")
        if name == "player_allowed_commands":
            if len(value) != len(set(value)) or any(
                not re.fullmatch(r"![a-zA-Z][a-zA-Z0-9_]*", item) for item in value
            ):
                raise ValueError(
                    "Allowed commands must be unique command names without arguments"
                )
        if name == "chat_channel_policy":
            _range(value["maximum_bytes"], 1, 2048, "maximum_bytes")
            _range(value["minimum_interval_ms"], 0, 60000, "minimum_interval_ms")
            _range(value["community"], 0, 255, "community")
            _range(value["language_mask"], 0, 2147483647, "language_mask")
        if name == "monster_initial_population":
            _range(value["members_per_zone"], 1, 8, "members_per_zone")
        if name == "resource_harvest_rewards":
            _range(value["product_quantity"], 1, 32767, "product_quantity")
        if name == "resource_harvest_occupation":
            _range(value["completion_grace_ms"], 0, 60000, "completion_grace_ms")
        if name == "socket_bonus_installation_policy":
            _range(value["request_dedupe_ms"], 0, 60000, "request_dedupe_ms")
            if value["refund_on_decrease"] is not False:
                raise ValueError("Socket bonus refunds are not implemented")
        if name == "planting_level_bonus":
            from wakfu_server.planting_level_policy import validate

            validate(value)
        if name == "weather_simulation":
            from wakfu_server.territory_weather_simulation import validate_policy

            validate_policy(value)
        if name == "weather_local_baseline":
            from wakfu_server.territory_weather import _validated_baseline

            _validated_baseline(
                value["weather"], value["native_byte"], value["native_values"]
            )
        if name == "dungeon_runtime_routes":
            from wakfu_server.dungeon_instances import _load_routes

            try:
                _load_routes(value["routes"])
            except RuntimeError as error:
                raise ValueError(str(error)) from None
        if name == "guild_policy":
            # Enabling unconfigured native capabilities would make existing flows fail.
            _range(value["max_members"], 1, 1000, "max_members")
            _range(value["max_ranks"], 1, 255, "max_ranks")
            if value.get("enabled") and (
                not value.get("catalog") or not value.get("permissions")
            ):
                raise ValueError(
                    "Guild enablement requires a reviewed native catalog and permissions"
                )
            for capability in ("bonuses", "treasury", "progression"):
                if value.get("economy", {}).get(
                    capability + "_enabled"
                ) and not value.get("economy", {}).get("bonus_catalog"):
                    raise ValueError(
                        "Guild economy enablement requires reviewed native capability configuration"
                    )
        if name == "mounts_require_unlock_quest" and value:
            raise ValueError("Mount quest authority is not implemented")
        if name == "rift_catalog":
            from wakfu_server.rift_policy import select_wave

            policy = db.execute(
                "SELECT value FROM settings WHERE name='rift_policy'"
            ).fetchone()["value"]
            for entry in value.values():
                select_wave(entry, policy, "admin-validation", 1)

    def update_setting(self, name, data, operator):
        name = self._setting_name(name)
        if (
            not isinstance(data, dict)
            or set(data) - {"value", "expected_revision", "new_version"}
            or not {"value", "expected_revision"} <= set(data)
        ):
            raise ValueError("Setting value and expected_revision are required")
        if not isinstance(data["expected_revision"], str) or not re.fullmatch(
            r"[a-f0-9]{32}", data["expected_revision"]
        ):
            raise ValueError("Invalid setting revision")
        value = data["value"]
        if name == "server_name":
            from wakfu_server.server_identity import validate_server_name

            validate_server_name(value)
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode()) > 5 * 1024 * 1024:
            raise ValueError("Setting value exceeds 5 MiB")
        changed_name = name
        with self.store.connection() as db:
            # Match the dungeon installer's advisory lock before taking any row locks.
            if name.startswith(("dungeon_runtime_config:", "dungeon_runtime_active:")):
                route_key = name.split(":", 1)[1].rsplit(":v", 1)[0]
                db.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    ("dungeon_runtime_config:" + route_key,),
                )
            row = _editor_row(db, name, lock=True)
            if row is None:
                raise LookupError("Setting not found")
            if row["revision"] != data["expected_revision"]:
                raise SettingsConflict(
                    "Setting changed since it was opened; reload before saving"
                )
            before = row["value"]
            if name in _COMBAT_MULTIPLIERS:
                if "new_version" in data:
                    raise ValueError(
                        "Combat policy versions are allocated automatically"
                    )
                _range(value, 0, MAX_REWARD_MULTIPLIER, "multiplier")
                scaled = Decimal(str(value)) * REWARD_RATE_SCALE
                if scaled != scaled.to_integral_value():
                    raise ValueError("Multiplier supports at most four decimal places")
                policy, column = _COMBAT_MULTIPLIERS[name]
                # The active row lock serializes changes and preserves sibling rates.
                current = dict(
                    db.execute(
                        "SELECT v.* FROM "
                        + policy
                        + "_active a JOIN "
                        + policy
                        + "_versions v USING(version) WHERE a.singleton=true"
                    ).fetchone()
                )
                version = db.execute(
                    "SELECT max(version)+1 AS version FROM " + policy + "_versions"
                ).fetchone()["version"]
                current[column] = int(scaled)
                columns = (
                    ["drop_rate_bp"]
                    if policy == "combat_drop_policy"
                    else ["xp_rate_bp", "kamas_rate_bp", "conquest_rate_bp"]
                )
                db.execute(
                    "INSERT INTO "
                    + policy
                    + "_versions(version,"
                    + ",".join(columns)
                    + ") VALUES ("
                    + ",".join(["%s"] * (len(columns) + 1))
                    + ")",
                    (version, *(current[c] for c in columns)),
                )
                db.execute(
                    "UPDATE " + policy + "_active SET version=%s WHERE singleton=true",
                    (version,),
                )
            elif name.startswith("dungeon_runtime_config:"):
                from wakfu_server.dungeon_runtime_config import (
                    prepare_configuration,
                    install_configuration,
                )

                version = data.get("new_version")
                if (
                    type(version) is not int
                    or not before["version"] < version <= 2147483647
                ):
                    raise ValueError(
                        "A new_version greater than the existing immutable version is required"
                    )
                if (
                    not isinstance(value, dict)
                    or value.get("route", {}).get("key") != route_key
                    or value.get("slug") != before["slug"]
                ):
                    raise ValueError(
                        "Dungeon route and slug identities must remain unchanged"
                    )
                if value["route"] != before["route"]:
                    raise ValueError("Dungeon native route identity is immutable")
                if db.execute(
                    "SELECT 1 FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
                    (route_key, version),
                ).fetchone():
                    raise ValueError(
                        "The new dungeon version already exists; choose an unused version"
                    )
                from wakfu_server.monsters import reference as monster_reference

                for room in value["compiled_plan"]["rooms"]:
                    for monster in room["monsters"]:
                        native = monster_reference(monster["ref_id"])
                        if (
                            monster["native_min_level"],
                            monster["native_max_level"],
                        ) != (native["min_level"], native["max_level"]):
                            raise ValueError(
                                "Dungeon monster native grade bounds cannot be changed"
                            )
                config = prepare_configuration(
                    value["compiled_plan"],
                    value["topology"],
                    value["route"],
                    version=version,
                    provenance="Admin panel: " + operator,
                )
                install_configuration(db, config)
                changed_name = (
                    "dungeon_runtime_config:" + route_key + ":v" + str(version)
                )
                value = config
            elif name.startswith("dungeon_runtime_active:"):
                from wakfu_server.dungeon_runtime_config import (
                    pinned_configuration,
                    install_configuration,
                )

                if (
                    not isinstance(value, dict)
                    or set(value) != {"version", "key"}
                    or type(value["version"]) is not int
                ):
                    raise ValueError("Dungeon selection requires version and key")
                key = (
                    "dungeon_runtime_config:" + route_key + ":v" + str(value["version"])
                )
                if value["key"] != key:
                    raise ValueError(
                        "Dungeon configuration key does not match its route/version"
                    )
                install_configuration(
                    db, pinned_configuration(db, route_key, value["version"])
                )
            else:
                if "new_version" in data:
                    raise ValueError(
                        "new_version is only valid for immutable dungeon configurations"
                    )
                db.execute(
                    "UPDATE settings SET value=%s WHERE name=%s", (Jsonb(value), name)
                )
                self._validate_policy(db, name, before, value)
            self._audit(db, operator, "setting.update", changed_name, before, value)
        result = self.setting(changed_name)
        result["changed_name"] = changed_name
        result["restart_required"] = result["apply_mode"] == "restart"
        return result
