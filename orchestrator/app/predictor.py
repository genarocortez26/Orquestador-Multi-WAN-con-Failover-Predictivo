"""Failover predictivo (RF5): Isolation Forest sobre ventanas de métricas.

El modelo se entrena OFFLINE con train_model.py y acá solo se hace inferencia.
Si no hay modelo en /models, el componente se desactiva con un log claro y el
sistema sigue funcionando con failover reactivo (el ML es un diferenciador, no
una dependencia crítica).
"""
import asyncio
import logging
import os
from collections import deque

import numpy as np
from prometheus_client import Gauge

log = logging.getLogger("predictor")

G_ANOM = Gauge("wan_anomaly_score", "Score de anomalía del predictor (mayor = peor)", ["wan_id"])


def _features(window: list[dict]) -> np.ndarray:
    """Media, desvío y PENDIENTE de latencia/jitter/pérdida sobre la ventana.
    Las pendientes son lo que da capacidad anticipatoria: una rampa de degradación
    tiene pendiente positiva antes de cruzar los umbrales reactivos."""
    lat = np.array([m["latency_ms"] for m in window])
    jit = np.array([m["jitter_ms"] for m in window])
    loss = np.array([m["loss_pct"] for m in window])
    x = np.arange(len(window))

    def slope(y):
        return float(np.polyfit(x, y, 1)[0]) if len(y) > 1 else 0.0

    return np.array([[lat.mean(), lat.std(), slope(lat),
                      jit.mean(), jit.std(), slope(jit),
                      loss.mean(), loss.std(), slope(loss)]])


class Predictor:
    def __init__(self, cfg: dict, monitors: dict, engine):
        self.cfg = cfg["ml"]
        self.monitors = monitors
        self.engine = engine
        self.model = None
        self.scaler = None
        self.windows = {wid: deque(maxlen=self.cfg["feature_window"]) for wid in monitors}
        self.consecutive = {wid: 0 for wid in monitors}
        self._load()

    def _load(self):
        if not self.cfg.get("enabled", False):
            log.info("ML deshabilitado por config")
            return
        try:
            import joblib
            self.model = joblib.load(self.cfg["model_path"])
            self.scaler = joblib.load(self.cfg["scaler_path"])
            log.info("modelo cargado de %s", self.cfg["model_path"])
        except FileNotFoundError:
            log.warning("no hay modelo en %s: predictor desactivado. "
                        "Entrenar con: docker compose exec orchestrator python train_model.py",
                        self.cfg["model_path"])
        except Exception:
            log.exception("error cargando modelo: predictor desactivado")
            self.model = None

    async def loop(self):
        if self.model is None:
            return
        while True:
            for wid, mon in self.monitors.items():
                self.windows[wid].append(mon.metrics())
                if len(self.windows[wid]) < self.cfg["feature_window"]:
                    continue
                x = self.scaler.transform(_features(list(self.windows[wid])))
                # decision_function: positivo = normal, negativo = anómalo.
                # Lo invertimos para que "mayor = más anómalo" (más intuitivo en el dashboard).
                score = float(-self.model.decision_function(x)[0])
                G_ANOM.labels(wid).set(round(score, 4))

                if score > self.cfg["anomaly_threshold"] and mon.status == "up":
                    self.consecutive[wid] += 1
                    if self.consecutive[wid] >= self.cfg["consecutive_alerts"]:
                        self.engine.preventive_migration(wid)
                else:
                    self.consecutive[wid] = 0
                    if mon.status == "up":
                        self.engine.clear_prediction(wid)
            await asyncio.sleep(1)

    def snapshot(self) -> dict:
        return {
            "enabled": self.model is not None,
            "alerts": {w: bool(v) for w, v in self.engine.predicted_alert.items()},
        }


# --- REENTRENAMIENTO ONLINE (DESCARTADO, dejar documentado) -----------------------
# async def retrain_loop(self):
#     while True:
#         await asyncio.sleep(self.cfg["retrain_interval_minutes"] * 60)
#         nuevo = entrenar_con_datos_recientes(...)
#         self.model = nuevo   # <- swap en caliente
# Problemas: (1) en una demo de 15 min nunca llega a ejecutarse; (2) el swap en
# caliente durante un failover deja al sistema decidiendo con dos modelos distintos
# en la misma ventana; (3) entrenar dentro del proceso del orquestador compite por
# CPU con el plano de control justo cuando más se lo necesita. En un producto real
# esto se resuelve con un pipeline de entrenamiento separado y despliegue versionado
# del modelo. Para el TP: entrenamiento offline + carga al inicio. Trabajo futuro.
# -----------------------------------------------------------------------------------
