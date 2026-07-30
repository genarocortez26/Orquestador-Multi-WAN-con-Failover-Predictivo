"""Monitoreo de calidad por WAN (RF1): RTT, jitter, pérdida y estado, con ventanas móviles.

Throughput: se mide de forma PASIVA leyendo los contadores de bytes de la interfaz
(/sys/class/net/<if>/statistics). La medición ACTIVA con iperf3 se descartó: inyecta
tráfico que contamina las propias métricas de latencia/pérdida en el momento de medir.
"""
import asyncio
import re
import statistics
import time
import logging
from collections import deque

from prometheus_client import Gauge

from .routing import run

log = logging.getLogger("monitor")

G_LAT = Gauge("wan_latency_ms", "RTT promedio (ventana móvil)", ["wan_id"])
G_JIT = Gauge("wan_jitter_ms", "Jitter (desvío estándar del RTT)", ["wan_id"])
G_LOSS = Gauge("wan_loss_pct", "Pérdida de paquetes % (ventana móvil)", ["wan_id"])
G_UP = Gauge("wan_status", "1=up 0=down", ["wan_id"])
G_THR = Gauge("wan_throughput_bps", "Throughput de salida (pasivo)", ["wan_id"])

_PING_RE = re.compile(r"time=([\d.]+)\s*ms")


class WanMonitor:
    """Estado vivo de una WAN. El resto del sistema lee .snapshot()."""

    def __init__(self, wan: dict, cfg: dict):
        self.wan = wan
        self.cfg = cfg
        t = cfg["orchestrator"]
        self.rtts = deque(maxlen=t["poll_window_latency"])
        self.loss_win = deque(maxlen=t["poll_window_loss"])   # 1 = perdido, 0 = ok
        self.consecutive_timeouts = 0
        self.status = "up"            # up | degraded | down
        self.healthy_since: float | None = time.time()
        self.up_seconds = 0.0
        self.total_seconds = 0.0
        self._last_bytes: int | None = None
        self._last_bytes_ts: float | None = None
        self.throughput_bps = 0.0

    # --------- muestreo ---------

    async def _ping_once(self, target: str) -> float | None:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", "-m", str(self.wan["fwmark"]), target,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await proc.communicate()
        m = _PING_RE.search(out.decode())
        return float(m.group(1)) if m else None

    def _read_tx_bytes(self) -> int:
        try:
            with open(f"/sys/class/net/{self.wan['_iface']}/statistics/tx_bytes") as f:
                return int(f.read())
        except OSError:
            return 0

    async def poll_loop(self):
        interval = self.cfg["orchestrator"]["poll_interval_seconds"]
        target = self.wan["monitor_targets"][0]
        while True:
            t0 = time.time()
            rtt = await self._ping_once(target)
            if rtt is None:
                self.loss_win.append(1)
                self.consecutive_timeouts += 1
            else:
                self.loss_win.append(0)
                self.consecutive_timeouts = 0
                self.rtts.append(rtt)

            # throughput pasivo por delta de contadores
            b, now = self._read_tx_bytes(), time.time()
            if self._last_bytes is not None and now > self._last_bytes_ts:
                self.throughput_bps = max(0.0, (b - self._last_bytes) * 8 / (now - self._last_bytes_ts))
            self._last_bytes, self._last_bytes_ts = b, now

            self._update_status()
            self._export()

            self.total_seconds += interval
            if self.status != "down":
                self.up_seconds += interval

            await asyncio.sleep(max(0.0, interval - (time.time() - t0)))

    # --------- estado ---------

    def metrics(self) -> dict:
        lat = statistics.fmean(self.rtts) if self.rtts else 9999.0
        jit = statistics.pstdev(self.rtts) if len(self.rtts) > 1 else 0.0
        loss = 100.0 * sum(self.loss_win) / len(self.loss_win) if self.loss_win else 0.0
        return {"latency_ms": lat, "jitter_ms": jit, "loss_pct": loss,
                "throughput_bps": self.throughput_bps}

    def _update_status(self):
        th = self.cfg["thresholds"]
        m = self.metrics()
        if (self.consecutive_timeouts >= th["hard_down_consecutive_timeouts"]
                or m["loss_pct"] >= th["hard_down_loss_pct"]):
            new = "down"
        elif (m["latency_ms"] >= th["degraded_latency_ms"]
                or m["loss_pct"] >= th["degraded_loss_pct"]
                or m["jitter_ms"] >= th["degraded_jitter_ms"]):
            new = "degraded"
        else:
            new = "up"

        if new == "up":
            if self.healthy_since is None:
                self.healthy_since = time.time()
        else:
            self.healthy_since = None
        self.status = new

    def is_eligible(self) -> bool:
        """Apto para recibir tráfico: sano y con la histéresis de recuperación cumplida."""
        if self.status != "up" or self.healthy_since is None:
            return False
        return (time.time() - self.healthy_since) >= self.cfg["thresholds"]["recovery_hysteresis_seconds"]

    def snapshot(self) -> dict:
        m = self.metrics()
        return {"id": self.wan["id"], "name": self.wan["name"], "status": self.status,
                "eligible": self.is_eligible(),
                "uptime_pct": 100.0 * self.up_seconds / self.total_seconds if self.total_seconds else 100.0,
                **m}

    def _export(self):
        m = self.metrics()
        wid = self.wan["id"]
        G_LAT.labels(wid).set(m["latency_ms"])
        G_JIT.labels(wid).set(m["jitter_ms"])
        G_LOSS.labels(wid).set(m["loss_pct"])
        G_THR.labels(wid).set(m["throughput_bps"])
        G_UP.labels(wid).set(0 if self.status == "down" else 1)


# --- MEDICIÓN ACTIVA DE ANCHO DE BANDA (DESCARTADA, no reactivar sin leer esto) ---
# async def medir_bw_iperf(self):
#     """Corre iperf3 -c contra el servidor externo cada N minutos."""
#     ...
# Problema: el tráfico de iperf3 satura el enlace bajo prueba, elevando latencia y
# pérdida de NUESTRAS propias sondas → el monitor ve una degradación que él mismo
# causó y puede disparar un failover espurio. En un producto real esto se resuelve
# midiendo en horarios valle o con técnicas de packet-pair; para este TP el
# throughput pasivo cumple RF1 sin ese efecto observador.
# -----------------------------------------------------------------------------------
