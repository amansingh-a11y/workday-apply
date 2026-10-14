from __future__ import annotations

import json
import os
from pathlib import Path

from workday_apply.models import ProfileStore

CONFIG_DIR = Path(os.environ.get("WORKDAY_APPLY_HOME", Path.home() / ".config" / "workday-apply"))
PROFILE_FILE = CONFIG_DIR / "profile.json"
BROWSER_DIR = CONFIG_DIR / "browser-profile"


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_store() -> ProfileStore:
    ensure_config_dir()
    if not PROFILE_FILE.exists():
        return ProfileStore()
    data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    return ProfileStore.model_validate(data)


def save_store(store: ProfileStore) -> None:
    ensure_config_dir()
    store.profile.touch()
    PROFILE_FILE.write_text(
        json.dumps(store.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
