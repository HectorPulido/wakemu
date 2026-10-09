"""Explicit eVI singleton provenance and eXD.q runtime event authority."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
import json
from wakfu_server.paths import DATA_ROOT

_SEAL = object()


@dataclass(frozen=True, init=False)
class NativeCollisionSourceAuthority:
    _seal: object
    _definition_json: str

    @classmethod
    def from_native_catalog(cls):
        definition = protocol_catalog.load(DATA_ROOT / "collision-effect.json")
        if (
            definition.get("reference") != -13
            or definition.get("effect_class") != 55
            or definition.get("native_definition_class") != "eVI"
            or definition.get("parameters") != [1.0, 0.0]
            or definition.get("native_effect_flags") != []
            or definition.get("target_masks") != [None] * 7
            or definition.get("event_suppresses_level_one") is not False
        ):
            raise ValueError("Invalid exported native eVI singleton")
        result = object.__new__(cls)
        object.__setattr__(result, "_seal", _SEAL)
        object.__setattr__(
            result, "_definition_json", json.dumps(definition, sort_keys=True)
        )
        return result

    def definition(self, effect, invocation):
        if getattr(self, "_seal", None) is not _SEAL:
            raise ValueError("Unverified native synthetic source authority")
        definition = json.loads(self._definition_json)
        if (
            effect != definition
            or invocation.reference != -13
            or invocation.level != 0
            or invocation.base_uid != 0
            or invocation.state_uid is not None
            or invocation.native_trigger_context is not None
            or invocation.native_context_hex is not None
            or invocation.native_retained_container != {"present": False}
            or invocation.native_explicit_target is not True
        ):
            raise ValueError("Native eVI source differs from actual eXD.q construction")
        return definition

    def identifiers(self, effect, invocation):
        self.definition(effect, invocation)
        return dict(
            native_container={"present": False},
            effect_action_id=55,
            effect_flags=(),
            native_definition_present=True,
            native_definition_variant=0,
            zone_trigger_policy={
                "definition_present": True,
                "zone_flag": False,
                "point_area": True,
            },
        )

    def runtime_events(self, effect, invocation):
        self.definition(effect, invocation)
        return (2254,)
