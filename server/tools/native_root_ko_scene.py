"""Suggest a real KO ally only when every actual casting root requires one."""


def root_required_ko_ally_scene(root_effects):
    from monster_pending_scenarios import native_ko_ally_recipe

    roots = list(root_effects)
    if not roots or any(not isinstance(root, dict) for root in roots):
        return None
    if all(
        native_ko_ally_recipe(root.get("criteria")) == "knocked_out_ally"
        for root in roots
    ):
        return "knocked_out_ally"
    return None
