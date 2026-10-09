#!/usr/bin/env python3
"""Create an independent client profile; share immutable assets only."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from wakfu_server.profiles import profile_root

root = Path(__file__).resolve().parents[2]
source = root / "client"
runtime = profile_root()
target = runtime / "client"
if not (source / "config.properties").is_file() or not (source / "classpath").is_file():
    raise SystemExit(
        "Place your own compatible Wakfu installation in client/ (config.properties and classpath required)."
    )
target.mkdir(parents=True, exist_ok=True)
preferences = runtime / "preferences/preferences"
preferences.mkdir(parents=True, exist_ok=True)
user_preferences = preferences / "userPreferences.properties"
if not user_preferences.exists():
    user_preferences.write_text(
        "version=24\nresolution=1500x950x32x120x0x50x33xDisplay 1xfalse\nmusicMute=true\nambianceSoundsMute=true\nuiSoundsMute=true\n"
    )
for item in source.iterdir():
    if item.name in {
        "config.properties",
        "sentry.properties",
        "log4j.properties",
        "tools",
    }:
        continue
    link = target / item.name
    if not link.exists():
        link.symlink_to(item, target_is_directory=item.is_dir())
config = (source / "config.properties").read_text()
config = re.sub(r"https?://[^/\s]+", "http://127.0.0.1:18080", config)
config = re.sub(
    r"^dispatchAddresses=.*$", "dispatchAddresses=127.0.0.1:15558", config, flags=re.M
)
config = re.sub(
    r"^interChatUrl=.*$", "interChatUrl=127.0.0.1:16337", config, flags=re.M
)
config = re.sub(r"^bugReport.enable=.*$", "bugReport.enable=false", config, flags=re.M)
assert not re.search(r"https?://(?!127\.0\.0\.1)", config)
(target / "config.properties").write_text(config)
(target / "sentry.properties").write_text("dsn=\n")
logging = (source / "log4j.properties").read_text()
logging = logging.replace("INFO, stdout, mainLog, Sentry", "INFO, stdout, mainLog")
(target / "log4j.properties").write_text(logging)
print(
    "Local client profile prepared: dispatcher 127.0.0.1:15558; isolated preferences/cache."
)
