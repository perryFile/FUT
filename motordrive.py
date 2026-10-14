"""
Motor-driver til FUT-teleskopet.

Selve steppingen kører i en kompileret C++ process (stepper_driver)
som bruger lgpio + clock_nanosleep() for µs-præcis puls-timing.
Denne Python-klasse beregner steps, retning og delay-parametre
og kalder C++-binæren via subprocess.
"""

import subprocess
import time
from pathlib import Path

# Sti til den kompilerede stepper-driver.
_DRIVER_BIN = Path(__file__).with_name("stepper_driver")

# Målfrekvens for steppulser (halvperiode = delay pr. HIGH/LOW).
# 5 kHz giver roligere, mere præcis drift end 15 kHz, og C++
# kan overholde timingen uden jitter.
_TARGET_FREQ_HZ = 5_000
_HALF_PERIOD_US = 1e6 / (2 * _TARGET_FREQ_HZ)       # 100 µs -> 5 kHz


class futDrive():
    def __init__(self):
        # Microstepping
        self.STEPS_PER_REV = 200 * 16                 # 200 x 16 mikrostep
        self.M1_GEAR_RATIO = 19.5 #19.5 originally
        self.M2_GEAR_RATIO = 13.5 #13.00 originally
        self.M1_DEG_PER_STEP = 360 / (self.STEPS_PER_REV * self.M1_GEAR_RATIO)
        self.M2_DEG_PER_STEP = 360 / (self.STEPS_PER_REV * self.M2_GEAR_RATIO)

        # Bevægelsesparametre (µs - sendes til C++-driveren).
        # min_delay = fuld fart, max_delay = start/slut af rampe.
        self.min_delay_us = _HALF_PERIOD_US            # 100 µs -> 5 kHz
        self.max_delay_us = _HALF_PERIOD_US * 3        # 300 µs -> ~1.7 kHz
        self.accel_ratio  = 0.25

        if not _DRIVER_BIN.exists():
            raise FileNotFoundError(
                f"Stepper-driver ikke fundet: {_DRIVER_BIN}\n"
                f"Kompiler med:  g++ -O2 -Wall -o stepper_driver "
                f"stepper_driver.cpp -llgpio"
            )

    # -- Hjælpemetoder --

    def angle_to_steps(self, angle, motor):
        """Konverter en *absolut* vinkel til det nærmeste heltal af mikrostep."""
        if motor == 1:
            return round(angle / self.M1_DEG_PER_STEP)
        if motor == 2:
            return round(angle / self.M2_DEG_PER_STEP)
        raise ValueError("motor must be 1 or 2")

    def steps_to_angle(self, steps, motor):
        """Konverter mikrostep tilbage til grader."""
        if motor == 1:
            return steps * self.M1_DEG_PER_STEP
        if motor == 2:
            return steps * self.M2_DEG_PER_STEP
        raise ValueError("motor must be 1 or 2")

    @staticmethod
    def _direction_flag(degree):
        """Returner 1 (HIGH) eller 0 (LOW) til DIR-pin."""
        return 0 if degree < 0 else 1

    def shut_drivers_down(self):
        """Kald C++-driveren med 0 steps - den åbner GPIO, sætter
        ENABLE HIGH og lukker igen."""
        try:
            subprocess.run(
                [str(_DRIVER_BIN),
                 "0", "0", "1", "1",
                 str(self.min_delay_us),
                 str(self.max_delay_us),
                 str(self.accel_ratio)],
                timeout=10, check=False,
                capture_output=True, text=True,
            )
        except Exception as e:
            print(f"shut_drivers_down fejl: {e}")
        print("Motorer slukket.")

    # -- Hovedbevægelse --

    def move_two_motors(self, angle1, angle2, stop_event=None,
                        steps1=None, steps2=None):
        """Bevæger begge stepper-motorer via C++-driveren.

        Hvis *steps1*/*steps2* angives bruges de direkte (fortegnet
        delta-steps).  Ellers beregnes steps fra vinklerne som før.
        """
        if steps1 is None:
            steps1 = self.angle_to_steps(abs(angle1), motor=1)
        else:
            steps1 = abs(steps1)
        if steps2 is None:
            steps2 = self.angle_to_steps(abs(angle2), motor=2)
        else:
            steps2 = abs(steps2)
        total = max(steps1, steps2)

        if total == 0:
            print("Ingen steps nødvendige - springer over.")
            return True

        dir1 = self._direction_flag(angle1)
        dir2 = 1 - self._direction_flag(angle2)   # motor 2 inverteret

        freq = 1e6 / (2 * self.min_delay_us)
        print(f"Synkron bevægelse: total={total} "
              f"(M1: {steps1}, M2: {steps2}), "
              f"C++ driver, {freq:.0f} Hz")

        cmd = [
            str(_DRIVER_BIN),
            str(steps1), str(steps2),
            str(dir1), str(dir2),
            str(self.min_delay_us),
            str(self.max_delay_us),
            str(self.accel_ratio),
        ]

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )

            # Tjek stop_event mens C++ kører.
            while proc.poll() is None:
                if stop_event is not None and stop_event.is_set():
                    print("Bevægelse afbrudt af genstart - "
                          "dræber stepper-process.")
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    return False
                time.sleep(0.1)

            stdout = proc.stdout.read()
            stderr = proc.stderr.read()
            if stderr:
                print(f"[stepper_driver] {stderr.strip()}")

            if proc.returncode != 0:
                raise RuntimeError(
                    f"stepper_driver afsluttede med kode "
                    f"{proc.returncode}: {stderr.strip()}")

            if stdout:
                print(f"[stepper_driver] {stdout.strip()}")
            return True

        except FileNotFoundError:
            raise FileNotFoundError(
                f"Stepper-driver binary ikke fundet: {_DRIVER_BIN}")


if __name__ == "__main__":
    fut_drive = futDrive()
    fut_drive.move_two_motors(90, -40)
