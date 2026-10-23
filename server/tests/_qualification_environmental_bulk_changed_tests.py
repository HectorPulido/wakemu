import importlib
import build_environmental_resource_profiles, test_environmental_resource_profile_compiler, test_declared_treasure_rewards

for module in (
    build_environmental_resource_profiles,
    test_environmental_resource_profile_compiler,
    test_declared_treasure_rewards,
):
    importlib.reload(module)
