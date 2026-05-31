import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "wallpaper-dinamicos"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "last_video": "",
    "muted": True,
    "brightness": 100,
    "contrast": 100,
    "saturation": 100,
    "blur": 0,
    "autostart": False,
    "volume": 50,
    "playlist": [],
    "playlist_index": 0,
    "auto_advance": False,
    "auto_advance_seconds": 30,
    "playback_mode": "fill",
    "window_geometry": None,
    "frame_fps": 30,
    "show_icons": False,
    "start_minimized": True,
    "pause_on_fullscreen": True,
    "pause_on_lock": True,
}


def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(saved)
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
