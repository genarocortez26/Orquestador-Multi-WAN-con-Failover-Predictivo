"""Generador de tráfico de la PyME: mantiene vivo tráfico de las tres clases contra
el servidor externo para que la demo tenga flujos que clasificar y migrar.

  - VoIP : UDP a puerto 10000 (rango RTP de la config), paquetes chicos cada 20 ms
  - Web  : GET HTTP a puerto 8000 cada ~2 s  (8000 está en web_ports_tcp de la config)
  - Bulk : conexión TCP a puerto 9000 enviando datos sostenidos

Solo usa la biblioteca estándar (sin dependencias).
"""
import os
import socket
import threading
import time
import urllib.request

GW = os.environ["GATEWAY_IP"]
HTTP_URL = os.environ["EXTERNAL_HTTP"]
VOIP_HOST = os.environ["EXTERNAL_VOIP_HOST"]
BULK_HOST = os.environ["EXTERNAL_BULK_HOST"]
BULK_PORT = int(os.environ["EXTERNAL_BULK_PORT"])


def set_default_route():
    """Apunta la default route al orquestador. Docker deja la .254 (su gateway de red)
    como default; sin este paso el tráfico esquivaría al orquestador y no habría demo."""
    os.system(f"ip route replace default via {GW}")  # valor de env controlado por compose


def voip_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"\x80" * 160          # tamaño típico de un paquete RTP G.711 de 20 ms
    while True:
        try:
            s.sendto(payload, (VOIP_HOST, 10000))
        except OSError:
            pass
        time.sleep(0.02)


def web_loop():
    while True:
        try:
            urllib.request.urlopen(HTTP_URL, timeout=3).read()
        except Exception:
            pass
        time.sleep(2)


def bulk_loop():
    chunk = b"x" * 65536
    while True:
        try:
            with socket.create_connection((BULK_HOST, BULK_PORT), timeout=3) as s:
                while True:
                    s.sendall(chunk)
                    time.sleep(0.05)         # ~10 Mbps sostenidos, no satura el bridge
        except OSError:
            time.sleep(2)                    # el servidor no está o el enlace cayó: reintentar


if __name__ == "__main__":
    set_default_route()
    for fn in (voip_loop, web_loop, bulk_loop):
        threading.Thread(target=fn, daemon=True).start()
    print("generador de tráfico activo (voip/web/bulk)")
    while True:
        time.sleep(60)
