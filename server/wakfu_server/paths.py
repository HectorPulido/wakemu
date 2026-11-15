"""Shared locations for server data and project runtime files."""

from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SERVER_ROOT.parent if SERVER_ROOT.name == "server" else SERVER_ROOT
DATABASE_ROOT = PROJECT_ROOT / "database"
DATA_ROOT = DATABASE_ROOT / "protocol"
