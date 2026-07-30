"""API REST + WebSocket (RF7 backend, RF8 consulta de eventos/decisiones)."""
import asyncio
import json
import logging
import os
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from . import store

log = logging.getLogger("api")


def build_app(cfg: dict, monitors: dict, engine, predictor) -> FastAPI:
    app = FastAPI(title="Multi-WAN Orchestrator", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg["api"]["cors_origins"],
        allow_methods=["GET"],           # la API es de solo lectura: no exponemos escritura
        allow_headers=["*"],
    )
    # métricas Prometheus montadas en la misma app (un solo puerto expuesto)
    app.mount("/metrics", make_asgi_app())

    def state() -> dict:
        return {
            "wans": [m.snapshot() for m in monitors.values()],
            "flows": engine.flows_snapshot(),
            "prediction": predictor.snapshot(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/wans")
    def wans():
        return state()["wans"]

    @app.get("/api/flows")
    def flows():
        return engine.flows_snapshot()

    @app.get("/api/events")
    def events(limit: int = 100):
        return store.recent_events(min(limit, 500))

    @app.get("/api/decisions")
    def decisions(limit: int = 100):
        return store.recent_decisions(min(limit, 500))

    @app.get("/api/policies")
    def policies():
        return cfg["policies"]

    # NUEVO (RF8): expone el log estructurado (orchestrator.jsonl) para la vista
    # "Logs" del dashboard. Lee el tail del archivo, filtra por nivel y traduce
    # {ts, level, logger, msg} -> {time, level, module, msg} (formato del frontend).
    @app.get("/api/logs")
    def logs(level: str | None = None, limit: int = 100):
        path = os.path.join(os.environ.get("LOG_PATH", "/logs"), "orchestrator.jsonl")
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()[-2000:]   # tail acotado: no cargar archivos enormes
        except OSError:
            return []
        out = []
        for ln in lines:
            try:
                d = json.loads(ln)
            except (json.JSONDecodeError, ValueError):
                continue
            if level and d.get("level", "").upper() != level.upper():
                continue
            out.append({
                "time": datetime.fromtimestamp(d.get("ts", 0)).isoformat(timespec="milliseconds"),
                "level": d.get("level", "INFO"),
                "module": d.get("logger", "?"),
                "msg": d.get("msg", ""),
            })
        return out[-min(limit, 500):]

    # NOTA de seguridad (informe, sección superficie de ataque): NO se implementa
    # PUT /api/policies. Editar políticas por HTTP sin autenticación convertiría al
    # orquestador en un vector de control de ruteo no autorizado + CSRF. En esta
    # versión las políticas se cambian editando config.yaml y reiniciando (docker
    # compose restart orchestrator). La edición autenticada queda como trabajo futuro.

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        try:
            while True:
                await sock.send_json(state())
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            pass
        except Exception:
            log.debug("ws cerrado")

    return app