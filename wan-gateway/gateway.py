"""Emulador de enlace WAN: rutea con NAT hacia la 'internet' simulada y expone una
API de control para degradarlo (tc/netem), derribarlo y restaurarlo en vivo.

Es el instrumento de prueba de la demo: la degradación se aplica en la interfaz que
mira al orquestador, en ambos sentidos del camino de ida (egreso) — suficiente para
que el monitor y el tráfico real la perciban.
"""
import ipaddress
import os
import re
import subprocess

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

WAN_ID = os.environ.get("WAN_ID", "wan?")
app = FastAPI(title=f"WAN gateway {WAN_ID}")

estado = {"mode": "normal", "latency_ms": 0.0, "loss_pct": 0.0}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    # Siempre lista de argumentos, nunca shell=True (ver informe: inyección de comandos)
    return subprocess.run(cmd, capture_output=True, text=True)


def ifaces() -> dict:
    """Detecta interfaces por subred (el nombre ethN no es determinístico en Docker).
    'wan' = la que mira al orquestador (172.16.1/2.x); 'inet' = la de internet (172.16.10.x)."""
    out = run(["ip", "-o", "-4", "addr", "show"]).stdout
    res = {}
    for line in out.splitlines():
        m = re.search(r"^\d+:\s+(\S+)\s+inet\s+([\d.]+)/", line)
        if not m or m.group(1) == "lo":
            continue
        ip = ipaddress.ip_address(m.group(2))
        if ip in ipaddress.ip_network("172.16.10.0/24"):
            res["inet"] = m.group(1)
        else:
            res["wan"] = m.group(1)
    return res


def setup():
    i = ifaces()
    # NAT hacia la internet simulada
    run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", i["inet"], "-j", "MASQUERADE"])
    # qdisc raíz limpia por si el contenedor se reinició con netem colgado
    for dev in i.values():
        run(["tc", "qdisc", "del", "dev", dev, "root"])


class Degrade(BaseModel):
    latency_ms: float = Field(ge=0, le=10000)
    loss_pct: float = Field(ge=0, le=100)


@app.post("/degrade")
def degrade(d: Degrade):
    i = ifaces()
    for dev in i.values():   # ambos sentidos del camino: ida y vuelta ven la degradación
        run(["tc", "qdisc", "del", "dev", dev, "root"])
        run(["tc", "qdisc", "add", "dev", dev, "root", "netem",
             "delay", f"{d.latency_ms}ms", f"{d.latency_ms * 0.1}ms",
             "loss", f"{d.loss_pct}%"])
    estado.update(mode="degraded", latency_ms=d.latency_ms, loss_pct=d.loss_pct)
    return estado


@app.post("/down")
def down():
    """Caída total: se DROPea el tráfico ruteado en lugar de bajar la interfaz.
    Bajar el link con 'ip link set down' borra las rutas y complica el /restore;
    el DROP produce el mismo efecto observable (timeouts de las sondas y del tráfico)."""
    if estado["mode"] != "down":
        run(["iptables", "-I", "FORWARD", "1", "-j", "DROP"])
    estado.update(mode="down")
    return estado


@app.post("/restore")
def restore():
    run(["iptables", "-D", "FORWARD", "-j", "DROP"])
    for dev in ifaces().values():
        run(["tc", "qdisc", "del", "dev", dev, "root"])
    estado.update(mode="normal", latency_ms=0.0, loss_pct=0.0)
    return estado


@app.get("/status")
def status():
    return {"wan_id": WAN_ID, **estado}


if __name__ == "__main__":
    setup()
    uvicorn.run(app, host="0.0.0.0", port=9001, log_level="warning")
