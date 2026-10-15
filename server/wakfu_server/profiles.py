from .paths import PROJECT_ROOT
import os
from pathlib import Path
import re

ROOT = PROJECT_ROOT


def profile_root(name=None):
    name = name or os.environ.get("WAKFU_LOCAL_PROFILE", "main")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise ValueError("Invalid local profile name")
    return (
        ROOT / ".local-state/wakemu/world"
        if name == "main"
        else ROOT / ".local-state/wakemu/instances" / name
    )
