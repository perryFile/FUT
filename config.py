"""Persistente indstillinger for teleskopstyringen."""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
DEFAULT_SETTINGS = {
    # Observatoriets placering (SONG-AU, Mt Kent Observatory, Australien).
    "observer_lat_deg": -27.7977,
    "observer_lon_deg": 151.8554,
    "observer_elev_m": 682.0,
}


def load_settings():
    if not CONFIG_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)

    settings = dict(DEFAULT_SETTINGS)
    settings.update(data)
    return settings


def save_settings(settings):
    CONFIG_PATH.write_text(
        json.dumps(settings, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
