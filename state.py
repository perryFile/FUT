"""
Delt tilstand mellem teleskop-loopet og webserveren.
Brug get_state() for et trådsikkert snapshot, og update_state(**kwargs)
for at opdatere felter.
"""
from threading import Lock, Event
from time import time

_lock = Lock()
_manual_target = None

_state = {
    "current_alt": 0.0,
    "current_az": 0.0,
    "api_ra": None,
    "api_dec": None,
    "api_alt": None,
    "api_az": None,
    "api_connected": True,
    "target_alt": None,
    "target_az": None,
    "target_source": "api",
    "manual_target_pending": False,
    "last_motor_az_deg": None,
    "last_motor_alt_deg": None,
    "last_motor_total_deg": None,
    "last_motor_source": None,
    "last_update": None,        # epoch seconds
    "last_move": None,          # epoch seconds for sidste faktiske bevægelse
    "moving": False,
    "status": "starting",       # starting | idle | moving | error | restarting
    "last_error": None,
}

# Sættes af webserveren for at bede teleskop-loopet om at genstarte.
restart_event = Event()

# Vækker teleskop-loopet når websiden sender en kommando.
command_event = Event()


def get_state():
    with _lock:
        snap = dict(_state)
    snap["restart_pending"] = restart_event.is_set()
    return snap


def update_state(**kwargs):
    with _lock:
        _state.update(kwargs)
        _state["last_update"] = time()


def mark_error(msg):
    update_state(status="error", last_error=str(msg))


def mark_moved(az_deg, alt_deg, total_deg, source):
    update_state(last_move=time(),
                 last_motor_az_deg=float(az_deg),
                 last_motor_alt_deg=float(alt_deg),
                 last_motor_total_deg=float(total_deg),
                 last_motor_source=source)


def request_restart():
    restart_event.set()
    command_event.set()


def request_manual_target(alt, az):
    global _manual_target
    manual_alt = float(alt)
    manual_az = float(az)

    if not 0 <= manual_alt <= 90:
        raise ValueError("Alt skal være mellem 0 og 90 grader.")
    if not 0 <= manual_az < 360:
        raise ValueError("Az skal være mellem 0 og 360 grader.")

    with _lock:
        _manual_target = (manual_alt, manual_az)
        _state.update({
            "target_alt": manual_alt,
            "target_az": manual_az,
            "target_source": "manual",
            "manual_target_pending": True,
            "status": "manual_pending",
            "last_error": None,
            "last_update": time(),
        })
    command_event.set()


def set_api_connected(connected):
    """Slå API-positioner til eller fra."""
    connected = bool(connected)
    with _lock:
        _state.update({
            "api_connected": connected,
            "last_error": None,
            "last_update": time(),
        })
    command_event.set()


def pop_manual_target():
    global _manual_target
    with _lock:
        target = _manual_target
        _manual_target = None
        if target is not None:
            _state["manual_target_pending"] = False
    return target
