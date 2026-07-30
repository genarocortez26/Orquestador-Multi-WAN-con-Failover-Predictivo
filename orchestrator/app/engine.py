"""Gestor de flujos y failover (RF3, RF4): asigna flujos nuevos, migra ante degradación
o caída, y aplica la histéresis de recuperación a través de monitor.is_eligible()."""
import asyncio
import logging
import time

from prometheus_client import Counter, Gauge

from . import store
from .decision import classify, choose_wan
from .routing import list_flows, set_flow_mark

log = logging.getLogger("engine")

C_FAILOVER = Counter("failover_total", "Failovers ejecutados", ["wan_id", "reason"])
G_FLOWS = Gauge("active_flows", "Flujos activos", ["wan_id", "traffic_class"])


class Engine:
    def __init__(self, cfg: dict, monitors: dict):
        self.cfg = cfg
        self.monitors = monitors                      # wan_id -> WanMonitor
        self.mark_to_wan = {w["fwmark"]: w["id"] for w in cfg["wans"]}
        self.wan_to_mark = {w["id"]: w["fwmark"] for w in cfg["wans"]}
        self.flows: dict[str, dict] = {}              # key -> {flow, class, wan_id}
        self.last_status = {wid: "up" for wid in monitors}
        self.lan_prefix = ".".join(cfg["orchestrator"]["lan_ip"].split(".")[:3]) + "."
        self.predicted_alert: dict[str, bool] = {wid: False for wid in monitors}

    # ---------- ciclo principal ----------

    async def loop(self):
        interval = self.cfg["orchestrator"]["flow_poll_interval_seconds"]
        while True:
            t0 = time.time()
            try:
                self._scan_and_assign()
                self._react_to_status_changes()
            except Exception:
                log.exception("ciclo del engine")
            await asyncio.sleep(max(0.0, interval - (time.time() - t0)))

    # ---------- asignación de flujos nuevos (RF3) ----------

    def _scan_and_assign(self):
        vivos = list_flows(self.lan_prefix)
        vistos = set()
        for f in vivos:
            vistos.add(f["key"])
            if f["key"] in self.flows:
                continue
            tclass = classify(f, self.cfg["traffic_classification"])
            wan_id, reason = choose_wan(tclass, self.monitors, self.cfg)
            if wan_id is None:
                continue
            if set_flow_mark(f, self.wan_to_mark[wan_id]):
                self.flows[f["key"]] = {"flow": f, "class": tclass, "wan_id": wan_id}
                store.add_decision(f["key"], tclass, wan_id, reason)
                log.info("flujo %s [%s] -> %s (%s)", f["key"], tclass, wan_id, reason)

        # flujos que conntrack ya no reporta: expiraron
        for key in list(self.flows):
            if key not in vistos:
                del self.flows[key]
        self._export_flow_gauges()

    # ---------- failover reactivo (RF4) ----------

    def _react_to_status_changes(self):
        for wid, mon in self.monitors.items():
            prev, cur = self.last_status[wid], mon.status
            if prev == cur:
                continue
            self.last_status[wid] = cur
            if cur == "down":
                store.add_event("failover", wid, f"{wid} caída total: migrando todos los flujos")
                n = self.migrate_flows(wid, only_migratable=False, reason="wan_down")
                C_FAILOVER.labels(wid, "down").inc()
                log.warning("%s DOWN -> %d flujos migrados", wid, n)
            elif cur == "degraded":
                store.add_event("degraded", wid, f"{wid} degradada: migrando clases críticas")
                n = self.migrate_flows(wid, only_migratable=True, reason="degraded")
                C_FAILOVER.labels(wid, "degraded").inc()
                log.warning("%s DEGRADED -> %d flujos críticos migrados", wid, n)
            elif cur == "up" and prev in ("down", "degraded"):
                store.add_event("recovery", wid,
                                f"{wid} recuperada (histéresis "
                                f"{self.cfg['thresholds']['recovery_hysteresis_seconds']}s antes de recibir tráfico)")
                log.info("%s RECOVERED", wid)

    def migrate_flows(self, from_wan: str, only_migratable: bool, reason: str) -> int:
        """Reasigna los flujos de una WAN. only_migratable=True respeta la política
        migrate_on_degradation de cada clase (degradación); False migra todo (caída)."""
        moved = 0
        for key, info in self.flows.items():
            if info["wan_id"] != from_wan:
                continue
            policy = self.cfg["_policies_by_class"][info["class"]]
            if only_migratable and not policy.get("migrate_on_degradation", False):
                continue
            new_wan, why = choose_wan(info["class"], self.monitors, self.cfg)
            if new_wan is None or new_wan == from_wan:
                continue
            if set_flow_mark(info["flow"], self.wan_to_mark[new_wan]):
                info["wan_id"] = new_wan
                store.add_decision(key, info["class"], new_wan, f"{reason}:{why}")
                moved += 1
        self._export_flow_gauges()
        return moved

    # ---------- migración preventiva (invocada por el predictor, RF5) ----------

    def preventive_migration(self, from_wan: str):
        if self.predicted_alert.get(from_wan):
            return  # ya migrado por esta alerta; evitar repetir en cada ciclo
        self.predicted_alert[from_wan] = True
        store.add_event("predicted", from_wan,
                        f"degradación anticipada en {from_wan}: migrando VoIP preventivamente")
        moved = 0
        for key, info in self.flows.items():
            if info["wan_id"] == from_wan and info["class"] == "voip":
                new_wan, why = choose_wan("voip", self.monitors, self.cfg)
                if new_wan and new_wan != from_wan and set_flow_mark(info["flow"], self.wan_to_mark[new_wan]):
                    info["wan_id"] = new_wan
                    store.add_decision(key, "voip", new_wan, f"predictive:{why}")
                    moved += 1
        log.warning("PREDICCIÓN %s -> %d flujos VoIP migrados preventivamente", from_wan, moved)

    def clear_prediction(self, wan_id: str):
        self.predicted_alert[wan_id] = False

    # ---------- estado para API/WS ----------

    def _export_flow_gauges(self):
        counts: dict[tuple, int] = {}
        for info in self.flows.values():
            counts[(info["wan_id"], info["class"])] = counts.get((info["wan_id"], info["class"]), 0) + 1
        for w in self.cfg["wans"]:
            for c in ("voip", "web", "bulk", "other"):
                G_FLOWS.labels(w["id"], c).set(counts.get((w["id"], c), 0))

    def flows_snapshot(self) -> list[dict]:
        return [{"flow": k, "class": v["class"], "wan_id": v["wan_id"]} for k, v in self.flows.items()]
