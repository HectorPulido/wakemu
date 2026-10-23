"""Reviewed local event bindings; never inferred from translated text at runtime."""


SETTING = "achievement_qualified_rules"


def load(db=None):
    """Read authoritative PostgreSQL policy; no filesystem/default fallback."""
    if db is None:
        from wakfu_server.storage.native_catalog import _database

        with _database().connection() as connection:
            return load(connection)
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        raise ValueError("Missing database achievement rules")
    return validate(row["value"])


def validate(document):
    if type(document) is not dict:
        raise ValueError("Invalid database achievement rules")
    if (
        document.get("schema_version") != 1
        or document.get("policy") != "reviewed_local_native_identity_v1"
    ):
        raise ValueError("Unsupported achievement rule policy")
    definitions = {}
    objective_ids = set()
    variables = {}
    for row in document["variable_bindings"]:
        variable, breed = row["variable_id"], row["breed_id"]
        if (
            any(type(v) is not int or v <= 0 for v in (variable, breed))
            or breed in variables
        ):
            raise ValueError("Invalid achievement breed binding")
        variables[breed] = variable
    for rule in document["definitions"]:
        chest_rule = rule.get("event_policy") == "authenticated_native_chest_open_v1"
        identity = rule["definition_id"]
        if type(identity) is not int or identity <= 0 or identity in definitions:
            raise ValueError("Invalid achievement identity")
        if rule.get("authority") != "proposed_explicit_local_policy_not_activated":
            raise ValueError("Missing reviewed local mapping provenance")
        import re

        if (
            (
                type(rule.get("mission_dependency")) is not bool
                or rule["mission_dependency"]
                and not chest_rule
            )
            or rule.get("native_repeatable") is not False
            or rule.get("native_period") != 0
        ):
            raise ValueError("Unqualified mission or recurring achievement")
        for expression in rule.get("source_criteria", {}).values():
            allowed = r"IsAchievementComplete\([1-9][0-9]*\)"
            if chest_rule:
                allowed = (
                    r"(?:GetRealLevel\(\) >= [1-9][0-9]* and )?"
                    r"IsAchievementComplete\([1-9][0-9]*\)"
                )
            if expression and not re.fullmatch(allowed, expression):
                raise ValueError("Unqualified achievement activation criterion")
        if not rule["objectives"]:
            raise ValueError("Achievement requires qualified objectives")
        for objective in rule["objectives"]:
            oid = objective["objective_id"]
            if type(oid) is not int or oid <= 0 or oid in objective_ids:
                raise ValueError("Invalid achievement objective identity")
            objective_ids.add(oid)
            # Variable objectives retain their reviewed breed as provenance;
            # only a breed objective without a variable is a direct kill.
            selectors = (
                int("variable_id" in objective)
                + int("dungeon_id" in objective)
                + int("breed_id" in objective and "variable_id" not in objective)
                + int("chest_binding_id" in objective)
            )
            if selectors != 1 or (
                "variable_id" in objective and "required_kills" in objective
            ):
                raise ValueError("Achievement objective requires one event selector")
            if "chest_binding_id" in objective:
                if (
                    not chest_rule
                    or type(objective["chest_binding_id"]) is not int
                    or objective["chest_binding_id"] <= 0
                ):
                    raise ValueError("Unqualified chest achievement binding")
            elif chest_rule:
                raise ValueError(
                    "Chest policy cannot authorize unrelated event selectors"
                )
            elif "variable_id" in objective:
                if "breed_id" in objective and (
                    type(objective["breed_id"]) is not int
                    or variables.get(objective["breed_id"]) != objective["variable_id"]
                ):
                    raise ValueError("Achievement variable breed provenance mismatch")
                if (
                    objective["variable_id"] not in variables.values()
                    or objective["operator"] not in ("==", ">=", ">")
                    or type(objective["threshold"]) is not int
                    or objective["threshold"] <= 0
                ):
                    raise ValueError("Unqualified achievement variable expression")
            elif "breed_id" in objective:
                if (
                    type(objective["breed_id"]) is not int
                    or objective["breed_id"] <= 0
                    or objective.get("required_kills") != 1
                    or type(objective.get("required_kills")) is not int
                ):
                    raise ValueError("Unqualified achievement direct kill event")
            elif (
                type(objective.get("dungeon_id")) is not int
                or objective["dungeon_id"] <= 0
            ):
                raise ValueError("Unqualified achievement dungeon event")
        from .rewards import validate

        for reward in rule["rewards"]:
            validate(reward)
        definitions[identity] = rule
    if any(
        parent not in definitions
        for rule in definitions.values()
        for parent in rule["prerequisites"]
    ):
        raise ValueError("Unknown or mission-dependent achievement prerequisite")
    return {
        "definitions": definitions,
        "breed_variables": variables,
        "policy": document["policy"],
    }
