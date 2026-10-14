import requests
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u

from config import load_settings

API_URL   = "https://fut.phys.au.dk/observe/api/telescope_status.php"
API_TOKEN = "observe-api-Aipaiye2"


def _observer_location():
    s = load_settings()
    return EarthLocation(
        lat=s["observer_lat_deg"] * u.deg,
        lon=s["observer_lon_deg"] * u.deg,
        height=s["observer_elev_m"] * u.m,
    )


def radec_to_altaz(ra_deg, dec_deg, when=None):
    """
    Konverterer RA/Dec (i grader, ICRS) til Alt/Az (i grader)
    for observatoriets placering på det givne tidspunkt.
    """
    location = _observer_location()
    obstime = Time(when) if when is not None else Time.now()
    target = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    altaz = target.transform_to(AltAz(obstime=obstime, location=location))
    return float(altaz.alt.deg), float(altaz.az.deg)

def ra_to_degrees(ra):
    """
    Konverter RA i timer til grader.
    RA kan komme som:
    - int/float (timer, fx 5.5 = 5h30m)
    - string "hh:mm:ss"
    """
    if isinstance(ra, (int, float)):
        return float(ra) * 15  # 1 time = 15 grader
    elif isinstance(ra, str):
        h, m, s = [float(x) for x in ra.split(":")]
        return (h + m/60 + s/3600) * 15
    else:
        raise ValueError(f"Ugyldigt RA-format: {ra}")

def dec_to_degrees(dec):
    """
    Konverter Dec i grader.
    Dec kan komme som:
    - int/float (grader)
    - string "±dd:mm:ss"
    """
    if isinstance(dec, (int, float)):
        return float(dec)
    elif isinstance(dec, str):
        parts = dec.split(":")
        deg = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        # Tjek strengen for negativt fortegn i stedet for deg < 0,
        # fordi float("-0") == -0.0 og (-0.0 < 0) er False i Python.
        sign = -1 if dec.lstrip().startswith("-") else 1
        return deg + sign * (minutes/60 + seconds/3600)
    else:
        raise ValueError(f"Ugyldigt Dec-format: {dec}")

def get_position():
    """
    Hent den ønskede teleskopposition fra API'et og konverter til
    (ra_deg, dec_deg, alt_deg, az_deg).

    Kaster exception ved fejl i stedet for at returnere None,
    så kalderen kan vise den faktiske fejlbesked i dashboardet.
    """
    # HTTP-headers til API-kaldet
    headers = {
        'X-API-Token': API_TOKEN,
        'User-Agent': 'TelescopeTest/1.0'
    }

    # Sender en GET-forespørgsel til API'et
    # timeout=10 forhindrer programmet i at hænge ved langsomt svar
    resp = requests.get(API_URL, headers=headers, timeout=10)

    # Kaster en exception hvis HTTP-status ikke er 200 (OK)
    resp.raise_for_status()

    # Parser svaret fra JSON til Python-dictionary
    data = resp.json()

    # Henter målpositionen for RA og DEC fra API-responsen
    target_ra  = data.get("current_ra")
    target_dec = data.get("current_dec")

    # Kontrollerer at både RA og DEC findes i svaret
    if target_ra is None or target_dec is None:
        raise ValueError("Target RA eller Dec findes ikke i API-responsen.")

    # Konverterer RA og DEC til grader
    ra_deg  = ra_to_degrees(target_ra)
    dec_deg = dec_to_degrees(target_dec)

    # Konverterer videre til Alt/Az for observatoriet (her og nu).
    alt_deg, az_deg = radec_to_altaz(ra_deg, dec_deg)

    # Udskriver de beregnede værdier til debug/overvågning
    print(f"Current RA  : {ra_deg:.6f}°")
    print(f"Current Dec : {dec_deg:.6f}°")
    print(f"Current Alt : {alt_deg:.6f}°")
    print(f"Current Az  : {az_deg:.6f}°")

    # Returnerer både equatorial- og horisontale koordinater i grader.
    return ra_deg, dec_deg, alt_deg, az_deg
