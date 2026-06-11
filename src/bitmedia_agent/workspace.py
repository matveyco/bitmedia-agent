"""Workspace resolution — the single source of path truth.

A workspace is the directory holding config/, data/, credentials/ and .env for one
operated account. Set BITMEDIA_WORKSPACE, or run from the workspace directory.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_env_loaded_for: str | None = None


def root() -> Path:
    return Path(os.environ.get("BITMEDIA_WORKSPACE", ".")).resolve()


def load_env() -> None:
    global _env_loaded_for
    ws = str(root())
    if _env_loaded_for != ws:
        load_dotenv(root() / ".env")
        _env_loaded_for = ws


def limits_path() -> Path:
    return root() / "config" / "limits.yaml"


def campaign_path() -> Path:
    return root() / "config" / "campaign.yaml"


def ledger_path() -> Path:
    return root() / "data" / "ledger.jsonl"


def reports_dir() -> Path:
    return root() / "data" / "reports"


def waitlist_path() -> Path:
    return root() / "data" / "waitlist.jsonl"


def credentials_dir() -> Path:
    return root() / "credentials"
