"""Bounded per-transaction cache for rows in sealed published JSON maps."""
from collections import OrderedDict


class PublishedJsonRowCache:
    """Cache decoded rows only for exact immutable native JSON publications.

    Other mappings retain their ordinary per-access behavior. The cached JSON
    rows are private decoded values owned by this transaction object.
    """

    MAX_ROWS_PER_COLLECTION = 128

    def __init__(self):
        self._catalog = None
        self._collections = {}
        self._rows = {}

    @staticmethod
    def _published_native_json(collection):
        from .combat_published_catalogs import (
            PublishedStaticMapping,
            static_catalog_descriptor,
        )

        return (
            type(collection) is PublishedStaticMapping
            and static_catalog_descriptor(collection) is not None
            and collection.representation == "native_json"
        )

    def _reset(self, catalog):
        self._catalog = catalog
        self._collections.clear()
        self._rows.clear()

    def row(self, catalog, collection_name, key):
        """Return ``(row, cacheable)`` while preserving custom-map semantics."""
        if self._catalog is not catalog:
            self._reset(catalog)
        key = str(key)

        if type(catalog) is not dict:
            return catalog[collection_name][key], False
        collection = catalog[collection_name]
        if not self._published_native_json(collection):
            return collection[key], False

        current = self._collections.get(collection_name)
        if current is not collection:
            self._collections[collection_name] = collection
            self._rows[collection_name] = OrderedDict()
        rows = self._rows[collection_name]
        cached = rows.get(key)
        if cached is not None or key in rows:
            rows.move_to_end(key)
            return cached, True

        value = collection[key]
        rows[key] = value
        if len(rows) > self.MAX_ROWS_PER_COLLECTION:
            rows.popitem(last=False)
        return value, True

    def catalog_with_published_row(self, catalog, collection_name, key):
        """Reuse one cached row, preserving sibling maps and fallback order.

        Non-native catalogs are returned untouched without an extra key read.
        Callers can defer this method until the original lookup point.
        """
        if self._catalog is not catalog:
            self._reset(catalog)
        if type(catalog) is not dict:
            return catalog
        collection = catalog.get(collection_name)
        if not self._published_native_json(collection):
            return catalog
        key = str(key)
        # StateLedger historically performs a mapping .get() at this point and
        # raises its own unknown-state ValueError for missing native rows. Do
        # not turn that into an earlier key lookup failure here.
        if key not in collection:
            return catalog
        row, _ = self.row(catalog, collection_name, key)
        result = dict(catalog)
        result[collection_name] = {str(key): row}
        return result
