"""Boolean encounter admission guard over verified original document sources.

This adapter retains existing short-circuit/optional-policy guards. Source
validation failures propagate; it never aliases or rewrites a frozen revision.
Live before/after-operation revision comparisons do not use this adapter.
"""
from wakfu_server.native_catalog_compatibility import require_source_revision


def source_revision_matches(pinned, required_paths):
    require_source_revision(pinned, required_paths)
    return True
