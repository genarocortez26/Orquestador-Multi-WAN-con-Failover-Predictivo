"""Capa de red: policy-based routing, marcado de conexiones y escaneo de flujos.

Diseño: el plano de datos lo maneja el kernel (ip rule + tablas + CONNMARK);
este módulo solo configura reglas y actualiza marcas. Ningún paquete pasa por Python.
"""
import ipaddress
import re
import subprocess
import logging

log = logging.getLogger("routing")

# --- MALA PRÁCTICA (ejemplo, NO usar) -----------------------------------------
# subprocess.run(f"conntrack -U --orig-src {src} --mark {mark}", shell=True)
# shell=True con datos que vienen de la red (IPs/puertos parseados de conntrack)
# habilita inyección de comandos si algo malicioso logra colarse en esos campos.
# Este módulo SIEMPRE invoca con lista de argumentos (sin intérprete de shell).
# -------------------------------------------------------------------------------


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """Ejecuta un comando sin shell. check=False porque muchas reglas son idempotentes
    (agregar una regla que ya existe devuelve error y está bien ignorarlo)."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} -> {r.stderr.strip()}")
    return r


def iface_for_subnet(subnet_ip: str) -> str:
    """Devuelve la interfaz cuya IP pertenece a la misma /24 que subnet_ip.
    En Docker el nombre (eth0/eth1/...) depende del orden de conexión de las redes,
    que NO es determinístico: por eso se resuelve en runtime y no por config."""
    red = ipaddress.ip_network(f"{subnet_ip}/24", strict=False)
    out = run(["ip", "-o", "-4", "addr", "show"]).stdout
    for line in out.splitlines():
        m = re.search(r"^\d+:\s+(\S+)\s+inet\s+([\d.]+)/", line)
        if m and ipaddress.ip_address(m.group(2)) in red:
            return m.group(1)
    raise RuntimeError(f"No hay interfaz en la subred de {subnet_ip}")


def setup_routing(cfg: dict):
    """Provisiona tablas, reglas y marcado. Idempotente (se puede correr al reinicio)."""
    lan_iface = iface_for_subnet(cfg["orchestrator"]["lan_ip"])

    for wan in cfg["wans"]:
        iface = iface_for_subnet(wan["gateway"])
        wan["_iface"] = iface  # cacheado para el resto del proceso
        table, mark, gw = str(wan["routing_table"]), str(wan["fwmark"]), wan["gateway"]

        run(["ip", "route", "replace", "default", "via", gw, "dev", iface, "table", table])
        run(["ip", "rule", "del", "fwmark", mark, "table", table])          # limpia si existía
        run(["ip", "rule", "add", "fwmark", mark, "table", table, "priority", str(100 + wan["fwmark"])])
        # NAT de salida por cada WAN: el gateway solo ve la IP del orquestador
        run(["iptables", "-t", "nat", "-C", "POSTROUTING", "-o", iface, "-j", "MASQUERADE"]) \
            .returncode == 0 or run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", iface, "-j", "MASQUERADE"])

    # Restaurar la marca de la conexión en cada paquete que entra por la LAN
    if run(["iptables", "-t", "mangle", "-C", "PREROUTING", "-i", lan_iface,
            "-j", "CONNMARK", "--restore-mark"]).returncode != 0:
        run(["iptables", "-t", "mangle", "-A", "PREROUTING", "-i", lan_iface,
             "-j", "CONNMARK", "--restore-mark"])

    # Ruta por defecto de la tabla main = WAN primaria (para el primer paquete de un
    # flujo aún sin marca; el motor de decisión lo marca en el siguiente ciclo)
    w0 = cfg["wans"][0]
    run(["ip", "route", "replace", "default", "via", w0["gateway"], "dev", w0["_iface"]])
    log.info("PBR provisionado. LAN=%s, WANs=%s",
             lan_iface, {w["id"]: w["_iface"] for w in cfg["wans"]})


# ---------------- Flujos (conntrack) ----------------

_CT_RE = re.compile(
    r"^(?P<proto>tcp|udp)\s+\d+\s+\d+\s+(?:\S+\s+)?"
    r"src=(?P<src>[\d.]+)\s+dst=(?P<dst>[\d.]+)\s+sport=(?P<sport>\d+)\s+dport=(?P<dport>\d+)"
    r".*?mark=(?P<mark>\d+)"
)


def list_flows(lan_prefix: str) -> list[dict]:
    """Flujos activos originados en la LAN, con su marca actual."""
    out = run(["conntrack", "-L", "-f", "ipv4"]).stdout
    flows = []
    for line in out.splitlines():
        m = _CT_RE.match(line.strip())
        if not m:
            continue
        d = m.groupdict()
        if not d["src"].startswith(lan_prefix):
            continue
        d["sport"], d["dport"], d["mark"] = int(d["sport"]), int(d["dport"]), int(d["mark"])
        d["key"] = f'{d["proto"]}:{d["src"]}:{d["sport"]}->{d["dst"]}:{d["dport"]}'
        flows.append(d)
    return flows


def set_flow_mark(flow: dict, mark: int) -> bool:
    """Marca la conexión en conntrack; el kernel enruta los próximos paquetes por la
    tabla asociada a esa marca (via CONNMARK --restore-mark)."""
    r = run(["conntrack", "-U", "-p", flow["proto"],
             "--orig-src", flow["src"], "--orig-dst", flow["dst"],
             "--sport", str(flow["sport"]), "--dport", str(flow["dport"]),
             "--mark", str(mark)])
    return r.returncode == 0
