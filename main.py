# Importerer funktionen, der henter teleskopets ønskede position
# (Rektascension og Deklination)
from futData import get_position

# Importerer klassen til styring af motorerne
from motordrive import futDrive

from math import hypot
from threading import Thread
from time import sleep
import atexit
import signal
import sys

import state
from web import app
from hostname import advertise_hostname


# Tid mellem positions-tjek (sekunder).
LOOP_INTERVAL_S = 10.0

# Minimum tilladt altitude (grader).  Negative værdier = under horisonten.
MIN_ALTITUDE_DEG = 0.0

# API-positioner mindre end denne samlede ændring udløser ikke en bevægelse.
API_MOVE_THRESHOLD_DEG = 2.0

# Absolut azimuth-grænser.  Teleskopet starter ved 0° og må dreje
# ±180° (360° totalt) – ellers ødelægges kablerne.
AZ_MIN_DEG = -180.0
AZ_MAX_DEG =  180.0


def compute_safe_delta_az(current_az, target_az):
    """
    Beregn den rotation i grader som bringer teleskopet fra *current_az*
    til *target_az* (target er 0-360° logisk fra API/manual) uden at den
    resulterende fysiske position går uden for [AZ_MIN_DEG, AZ_MAX_DEG].

    Returnerer (delta_az, long_way) hvor *long_way* er True hvis den
    korte vej ville bryde kabelgrænsen og den lange vej blev valgt.

    Kaster ValueError hvis ingen retning er sikker.
    """
    # Normaliser target til -180..+180 (samme rum som fysisk position).
    target_norm = (target_az + 180) % 360 - 180

    # To mulige deltas: CW (positiv) og CCW (negativ).
    delta_short = (target_norm - current_az + 540) % 360 - 180   # ±180
    delta_long = delta_short - 360 if delta_short > 0 else delta_short + 360

    def _safe(delta):
        new_pos = current_az + delta
        return AZ_MIN_DEG <= new_pos <= AZ_MAX_DEG

    short_safe = _safe(delta_short)
    long_safe = _safe(delta_long)

    if short_safe:
        return delta_short, False
    if long_safe:
        return delta_long, True

    # Ingen retning holder sig inden for grænsen – bør ikke ske.
    raise ValueError(
        f"Kan ikke nå Az {target_norm:.2f}° fra {current_az:.2f}° "
        f"uden at overskride kabelgrænsen "
        f"[{AZ_MIN_DEG}°, {AZ_MAX_DEG}°]."
    )


def target_offset_deg(current_alt, current_az, target_alt, target_az):
    """Returner samlet Alt/Az-afstand med korrekt azimuth-wraparound."""
    az_offset = (target_az - current_az + 180) % 360 - 180
    return hypot(target_alt - current_alt, az_offset)


def wait_for_next_check():
    """Vent, men vågn med det samme hvis websiden sender en kommando."""
    state.command_event.wait(LOOP_INTERVAL_S)
    state.command_event.clear()


def telescope_loop():
    """Hovedloopet: hent ønsket position og bevæg motorerne ved behov.

    Position spores i *heltal af mikrostep* for at undgå kumulativ
    afrundingsfejl.  Grader-repræsentationen udledes fra step-tællerne
    og bruges kun til display, kabelgrænse-tjek og API-sammenligning.
    """
    fut_drive = futDrive()

    # Autoritativ position: heltal af mikrostep (motor 1 = az, motor 2 = alt).
    cur_az_steps = 0
    cur_alt_steps = 0

    def _sync_deg():
        """Udled grader fra step-tællere og opdater shared state."""
        az_deg = fut_drive.steps_to_angle(cur_az_steps, motor=1)
        alt_deg = fut_drive.steps_to_angle(cur_alt_steps, motor=2)
        state.update_state(current_alt=alt_deg, current_az=az_deg)
        return alt_deg, az_deg

    cur_alt_deg, cur_az_deg = _sync_deg()
    state.update_state(status="idle")

    while True:
        # Håndter genstart anmodet fra websiden.
        if state.restart_event.is_set():
            print("Genstart anmodet – nulstiller position og motorer.")
            try:
                fut_drive.shut_drivers_down()
            except Exception as e:
                print(f"Fejl ved nedlukning af drivere: {e}")
            cur_az_steps = 0
            cur_alt_steps = 0
            fut_drive = futDrive()
            cur_alt_deg, cur_az_deg = _sync_deg()
            state.update_state(status="idle", last_error=None)
            state.restart_event.clear()

        manual_target = state.pop_manual_target()
        api_connected = state.get_state()["api_connected"]
        target_source = "manual" if manual_target is not None else "api"

        if manual_target is not None:
            # Manuelt input fra websiden er allerede i Alt/Az.
            target_alt, target_az = manual_target
            pos = (None, None, target_alt, target_az)
        elif api_connected:
            # Henter den ønskede position. Kan returnere None ved fejl.
            try:
                pos = get_position()
            except Exception as e:
                state.mark_error(f"get_position kastede: {e}")
                wait_for_next_check()
                continue

            if pos is not None:
                api_ra, api_dec, api_alt, api_az = pos
                state.update_state(api_ra=api_ra, api_dec=api_dec,
                                   api_alt=api_alt, api_az=api_az)
        else:
            state.update_state(status="idle", moving=False)
            wait_for_next_check()
            continue

        if pos is None:
            state.mark_error("Kunne ikke hente position fra API.")
            wait_for_next_check()
            continue

        _ra, _dec, alt_degree, az_degree = pos

        # Sikkerhedstjek: afvis mål under horisonten.
        if alt_degree < MIN_ALTITUDE_DEG:
            msg = (f"Mål afvist: altitude {alt_degree:.2f}° er under "
                   f"minimumsgrænsen ({MIN_ALTITUDE_DEG}°).")
            print(msg)
            state.mark_error(msg)
            wait_for_next_check()
            continue

        if target_source == "api":
            # Sammenlign med teleskopets faktiske position. Når en lille
            # ændring springes over, står positionen stille, så efterfølgende
            # små API-ændringer automatisk akkumuleres til tærsklen nås.
            change = target_offset_deg(
                cur_alt_deg, cur_az_deg, alt_degree, az_degree)
            if change < API_MOVE_THRESHOLD_DEG:
                state.update_state(
                    status="idle",
                    moving=False,
                    target_alt=alt_degree,
                    target_az=az_degree,
                    target_source=target_source,
                )
                wait_for_next_check()
                continue

        state.update_state(target_alt=alt_degree,
                           target_az=az_degree,
                           target_source=target_source)

        # ── Beregn nødvendig azimuth-rotation (kabelgrænse) ─────
        try:
            delta_az_deg, long_way = compute_safe_delta_az(
                cur_az_deg, az_degree)
        except ValueError as e:
            state.mark_error(str(e))
            wait_for_next_check()
            continue

        if long_way:
            msg = (f"Kabelbeskyttelse: drejer den lange vej "
                   f"({delta_az_deg:+.2f}°) for at undgå kabelgrænsen.")
            print(msg)
            state.update_state(last_error=msg)

        # ── Absolut mål i mikrostep ─────────────────────────────
        # Beregn den ønskede *absolutte* step-position for hvert
        # mål.  Afrunding sker kun her – og fordi positionen
        # spores i steps, akkumuleres ingen fejl over tid.
        target_az_deg = cur_az_deg + delta_az_deg
        target_az_steps = fut_drive.angle_to_steps(target_az_deg, motor=1)
        target_alt_steps = fut_drive.angle_to_steps(alt_degree, motor=2)

        delta_az_steps = target_az_steps - cur_az_steps
        delta_alt_steps = target_alt_steps - cur_alt_steps

        # Spring over hvis intet step-forskel (< ½ mikrostep).
        if delta_az_steps == 0 and delta_alt_steps == 0:
            print("Mål er inden for ½ mikrostep – ingen bevægelse.")
            state.update_state(status="idle")
            wait_for_next_check()
            continue

        delta_az_moved = fut_drive.steps_to_angle(delta_az_steps, motor=1)
        delta_alt_moved = fut_drive.steps_to_angle(delta_alt_steps, motor=2)
        distance = hypot(delta_az_moved, delta_alt_moved)

        print(f"Bevæger til Alt-step={target_alt_steps}, "
              f"Az-step={target_az_steps} "
              f"(Δaz={delta_az_steps}, Δalt={delta_alt_steps})")

        state.update_state(status="moving",
                           target_alt=alt_degree,
                           target_az=target_az_deg,
                           moving=True)
        try:
            # Motorerne er monteret spejlvendt → invertér fortegn.
            completed = fut_drive.move_two_motors(
                -delta_az_moved, -delta_alt_moved,
                stop_event=state.restart_event,
                steps1=delta_az_steps,
                steps2=delta_alt_steps,
            )
            if not completed:
                # Bevægelsen blev afbrudt – positionen er ukendt.
                # Vi opdaterer IKKE step-tællerne; genstart nulstiller.
                state.update_state(status="restarting", moving=False)
                continue

            # Bevægelsen fuldført – opdater step-tællerne.
            cur_az_steps = target_az_steps
            cur_alt_steps = target_alt_steps
            cur_alt_deg, cur_az_deg = _sync_deg()
            state.mark_moved(delta_az_moved, delta_alt_moved,
                             distance, target_source)
            state.update_state(status="idle", moving=False, last_error=None)
        except Exception as e:
            state.update_state(moving=False)
            state.mark_error(f"Bevægelsesfejl: {e}")

        wait_for_next_check()


# ── Graceful shutdown ────────────────────────────────────────────────
_cleanup_done = False


def _cleanup():
    """Sluk motorer via C++-driveren ved programafslutning."""
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    print("Lukker ned – slukker motorer.")
    try:
        drive = futDrive()
        drive.shut_drivers_down()
    except Exception as e:
        print(f"Cleanup fejl: {e}")


def _signal_handler(signum, _frame):
    """Håndter SIGINT/SIGTERM for graceful shutdown."""
    print(f"\nModtog signal {signum} – lukker ned.")
    _cleanup()
    sys.exit(0)


if __name__ == "__main__":
    # Registrer cleanup ved afslutning.
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Start teleskop-loopet i en baggrundstråd.
    Thread(target=telescope_loop, daemon=True).start()

    # Annoncer 'fut.local' på netværket via mDNS, så websiden kan
    # tilgås på http://fut.local:8080/ uden at kende IP-adressen.
    advertise_hostname("fut", port=8080)

    # Kør webserveren i hovedtråden. Bind til alle interfaces
    # så websiden kan tilgås fra netværket.
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
