/*
 * stepper_driver.cpp – Præcis dual-stepper motor driver til FUT.
 *
 * Bruger lgpio (Pi 5 native) og clock_nanosleep() for µs-præcision.
 *
 * Kompilér:  g++ -O2 -Wall -o stepper_driver stepper_driver.cpp -llgpio
 *
 * Brug:
 *   ./stepper_driver <steps1> <steps2> <dir1> <dir2>
 *                    <min_delay_us> <max_delay_us> <accel_ratio>
 *
 * Exit: 0 = OK,  1 = fejl (stderr)
 */
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <lgpio.h>

// GPIO-pin definitioner (BCM-numre, gpiochip4 på Pi 5)
static const int CHIP       = 4;
static const int M1_DIR     = 2;
static const int M1_STEP    = 3;
static const int M1_ENABLE  = 5;
static const int M2_DIR     = 17;
static const int M2_STEP    = 27;
static const int M2_ENABLE  = 6;

static int h = -1;   // gpiochip handle

static void advance(struct timespec &ts, long ns) {
    ts.tv_nsec += ns;
    while (ts.tv_nsec >= 1000000000L) {
        ts.tv_sec  += 1;
        ts.tv_nsec -= 1000000000L;
    }
    clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, nullptr);
}

static bool gpio_init() {
    h = lgGpiochipOpen(CHIP);
    if (h < 0) {
        fprintf(stderr, "Kan ikke åbne gpiochip%d: %s\n",
                CHIP, lguErrorText(h));
        return false;
    }
    int pins[] = {M1_DIR, M1_STEP, M1_ENABLE,
                  M2_DIR, M2_STEP, M2_ENABLE};
    for (int p : pins) {
        int r = lgGpioClaimOutput(h, 0, p, 0);
        if (r < 0) {
            fprintf(stderr, "GPIO %d fejl: %s\n", p, lguErrorText(r));
            lgGpiochipClose(h); return false;
        }
    }
    lgGpioWrite(h, M1_ENABLE, 1);
    lgGpioWrite(h, M2_ENABLE, 1);
    return true;
}

static void gpio_cleanup() {
    if (h < 0) return;
    lgGpioWrite(h, M1_ENABLE, 1);
    lgGpioWrite(h, M2_ENABLE, 1);
    int pins[] = {M1_DIR, M1_STEP, M1_ENABLE,
                  M2_DIR, M2_STEP, M2_ENABLE};
    for (int p : pins) lgGpioFree(h, p);
    lgGpiochipClose(h);
    h = -1;
}

int main(int argc, char *argv[]) {
    if (argc != 8) {
        fprintf(stderr,
            "Brug: %s <steps1> <steps2> <dir1> <dir2> "
            "<min_delay_us> <max_delay_us> <accel_ratio>\n", argv[0]);
        return 1;
    }

    int    steps1     = atoi(argv[1]);
    int    steps2     = atoi(argv[2]);
    int    dir1       = atoi(argv[3]);
    int    dir2       = atoi(argv[4]);
    double min_us     = atof(argv[5]);
    double max_us     = atof(argv[6]);
    double accel_r    = atof(argv[7]);
    int    total      = (steps1 > steps2) ? steps1 : steps2;

    if (steps1 < 0 || steps2 < 0) {
        fprintf(stderr, "steps skal være >= 0\n"); return 1;
    }
    if (total == 0) { printf("DONE steps=0\n"); return 0; }

    long min_ns = (long)(min_us * 1000.0);
    long max_ns = (long)(max_us * 1000.0);

    int accel = (int)(total * accel_r);
    int decel = accel;
    int flat  = total - accel - decel;
    if (flat < 0) { accel = total / 2; decel = total - accel; flat = 0; }

    if (!gpio_init()) return 1;

    // Aktiver drivere
    lgGpioWrite(h, M1_ENABLE, 0);
    lgGpioWrite(h, M2_ENABLE, 0);

    // 2 s stabilisering
    struct timespec tw;
    clock_gettime(CLOCK_MONOTONIC, &tw);
    advance(tw, 2000000000L);

    // Sæt retning
    lgGpioWrite(h, M1_DIR, dir1);
    lgGpioWrite(h, M2_DIR, dir2);

    fprintf(stderr, "C++ stepper: total=%d (M1=%d M2=%d) "
            "delay=%.1f–%.1f µs accel=%.0f%%\n",
            total, steps1, steps2, min_us, max_us, accel_r * 100);

    int err1 = 0, err2 = 0;
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);

    for (int s = 0; s < total; s++) {
        // Trapezoidal delay
        long dns;
        if (accel > 0 && s < accel) {
            double f = (double)s / accel;
            dns = max_ns - (long)(f * (max_ns - min_ns));
        } else if (s < accel + flat) {
            dns = min_ns;
        } else if (decel > 0) {
            double f = (double)(s - accel - flat) / decel;
            dns = min_ns + (long)(f * (max_ns - min_ns));
        } else {
            dns = min_ns;
        }

        // Bresenham
        bool m1 = false, m2 = false;
        err1 += steps1;  err2 += steps2;
        if (err1 >= total) { err1 -= total; m1 = true; }
        if (err2 >= total) { err2 -= total; m2 = true; }

        // Puls HIGH
        if (m1) lgGpioWrite(h, M1_STEP, 1);
        if (m2) lgGpioWrite(h, M2_STEP, 1);
        advance(ts, dns);

        // Puls LOW
        if (m1) lgGpioWrite(h, M1_STEP, 0);
        if (m2) lgGpioWrite(h, M2_STEP, 0);
        advance(ts, dns);
    }

    // 2 s ventetid efter bevægelse
    clock_gettime(CLOCK_MONOTONIC, &tw);
    advance(tw, 2000000000L);

    gpio_cleanup();
    printf("DONE steps=%d\n", total);
    return 0;
}

