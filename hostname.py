"""
Annoncer en mDNS / Zeroconf hostname så websiden kan tilgås på
fx http://fut.local:8080/ uden at man behøver kende IP-adressen.

Foretrukken metode: Avahi (typisk allerede installeret på Raspberry Pi OS).
Hvis Avahi ikke er aktivt, kan man i stedet installere `zeroconf`:
    pip install zeroconf
"""
import socket


def _local_ip():
    """Find IP-adressen på det aktive netværksinterface."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Behøver ikke faktisk forbindelse – bare en route-lookup.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def advertise_hostname(name="fut", port=8080):
    """
    Forsøg at registrere `<name>.local` via Zeroconf.
    Stille no-op hvis biblioteket ikke er installeret –
    Avahi (på Pi'en) annoncerer allerede maskinens egen hostname,
    så hvis Pi'en hedder 'fut' i /etc/hostname virker fut.local
    uden videre.
    """
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        print(f"[hostname] zeroconf ikke installeret – stoler på Avahi. "
              f"Sørg for at Pi'ens hostname er '{name}' "
              f"(http://{name}.local:{port}/).")
        return None

    ip = _local_ip()
    info = ServiceInfo(
        "_http._tcp.local.",
        f"{name}._http._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties={"path": "/"},
        server=f"{name}.local.",
    )
    zc = Zeroconf()
    try:
        zc.register_service(info)
        print(f"[hostname] Annoncerer http://{name}.local:{port}/ "
              f"(IP {ip}).")
    except Exception as e:
        print(f"[hostname] Kunne ikke registrere mDNS-tjeneste: {e}")
        zc.close()
        return None
    return zc
