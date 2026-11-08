"""Known native readers between retained-GC schema proof and serialization."""


# Actual readers used by snapshot conversion and the intervening complete-view
# preflight (_retained_population, NativeRetainedEffectView, state_managers).
_MAPPING_READERS = tuple(
    (name, getattr(dict, name))
    for name in (
        "items",
        "get",
        "values",
        "keys",
        "__getitem__",
        "__iter__",
        "__len__",
        "__contains__",
        "__eq__",
    )
)


def _plain_mapping_reads(value):
    kind = type(value)
    if kind is dict:
        return True
    if (
        not issubclass(kind, dict)
        or kind.__getattribute__ is not dict.__getattribute__
        or any(getattr(kind, name) is not method for name, method in _MAPPING_READERS)
    ):
        return False
    try:
        fields = vars(value)
    except TypeError:  # Native slotted dictionary rows cannot shadow readers.
        return True
    return not any(name in fields for name, _ in _MAPPING_READERS)


# These native serializers invoke explicit validation methods. A customized
# method can mutate unrelated deferred rows, so it disables the whole adapter.
from . import combat_static_catalogs as _catalogs

_IMMUTABLE_CATALOG = _catalogs.ImmutableCatalog
_CATALOG_READERS = tuple(
    getattr(_IMMUTABLE_CATALOG, name)
    for name in (
        "__new__",
        "__init__",
        "_cached_views",
        *(name for name, _ in _MAPPING_READERS),
    )
)
_CATALOG_FREEZE = _catalogs._freeze
from .combat_state_ledger import StateLedger

_LEDGER_ENTRIES = StateLedger.entries
_NO_DESCRIPTOR = object()
_LEDGER_FIELDS = tuple(
    vars(StateLedger).get(name, _NO_DESCRIPTOR) for name in ("actor_id", "_entries")
)
from .combat_character_copy_book import CopyBookAction
from wakfu_server.characters.owned_social_context import OwnedSocialContext

_COPY_VALIDATE = CopyBookAction.validate
_SOCIAL_METHODS = tuple(
    getattr(OwnedSocialContext, name)
    for name in ("to_record", "validate", "_source_fields")
)


def serialization_reads_plain(value):
    kind = type(value)
    if kind is _IMMUTABLE_CATALOG:
        # Equipment pins use this exact native read-only view. Its source is
        # admitted separately; serialization stays eager, including weak-cache
        # population. Custom readers retain the complete legacy projection.
        return (
            _catalogs.ImmutableCatalog is kind
            and _catalogs._freeze is _CATALOG_FREEZE
            and kind.__getattribute__ is dict.__getattribute__
            and all(
                getattr(kind, name) is method
                for name, method in zip(
                    (
                        "__new__",
                        "__init__",
                        "_cached_views",
                        *(name for name, _ in _MAPPING_READERS),
                    ),
                    _CATALOG_READERS,
                )
            )
        )
    if issubclass(kind, dict):
        return _plain_mapping_reads(value)
    for base in (list, tuple, set, frozenset):
        if issubclass(kind, base):
            return kind.__iter__ is base.__iter__ and kind.__len__ is base.__len__
    if kind is StateLedger:
        return (
            kind.__getattribute__ is object.__getattribute__
            and kind.entries is _LEDGER_ENTRIES
            and all(
                vars(kind).get(name, _NO_DESCRIPTOR) is original
                for name, original in zip(("actor_id", "_entries"), _LEDGER_FIELDS)
            )
        )
    if kind is CopyBookAction:
        if kind.validate is not _COPY_VALIDATE or "validate" in vars(value):
            return False
    elif kind is OwnedSocialContext:
        if any(
            getattr(kind, name) is not method or name in vars(value)
            for name, method in zip(
                ("to_record", "validate", "_source_fields"), _SOCIAL_METHODS
            )
        ):
            return False
    # Dataclass serialization reads declared fields via getattr. Native scalar
    # defaults are harmless; introduced properties/descriptors are callbacks.
    fields = getattr(kind, "__dataclass_fields__", None)
    if type(fields) is dict:
        return kind.__getattribute__ is object.__getattribute__ and all(
            not hasattr(vars(kind).get(name), "__get__") for name in fields
        )
    return True  # Unknown types still fail the unchanged canonical admission.
