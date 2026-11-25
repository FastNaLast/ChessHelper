"""Пути проекта и настройки (settings.json)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
REPERTOIRE_DIR = DATA / "repertoire"
REPORTS = PROJECT / "reports"
ENGINE_DIR = PROJECT / "engine"
ENGINE_EXE = ENGINE_DIR / "stockfish.exe"
SETTINGS_FILE = PROJECT / "settings.json"

DEFAULTS = {
    "engine_path": str(ENGINE_EXE),
    "threads": 2,
    "hash_mb": 256,
    "depth": 16,
    "multipv": 3,
    "report_depth": 12,
    "opacity": 0.97,
    "always_on_top": True,
    "window": {"x": None, "y": None, "w": 470, "h": 720},
    "capture": {"x": 0, "y": 0, "w": 640, "h": 640},
    "camera": {"url": "http://192.168.0.100:8080/video", "corners": []},
    "phone": {"port": 8000},
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load() -> dict:
    if SETTINGS_FILE.exists():
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
    else:
        raw = {}
    cfg = _merge(DEFAULTS, raw)
    for folder in (DATA, REPERTOIRE_DIR, REPORTS, ENGINE_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    return cfg


def save(cfg: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
