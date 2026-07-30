"""Punto de entrada del orquestador: provisiona PBR, levanta monitores, engine,
predictor y la API en un solo proceso asyncio."""
import asyncio
import json
import logging
import os
import sys
import time

import uvicorn

from .api import build_app
from .config import load_config
from .engine import Engine
from .monitor import WanMonitor
from .predictor import Predictor
from .routing import setup_routing
from . import store


class JsonFormatter(logging.Formatter):
    """Logs estructurados (RF8): una línea JSON por evento, parseable y filtrable."""
    def format(self, record):
        return json.dumps({
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }, ensure_ascii=False)


def setup_logging():
    handlers = [logging.StreamHandler(sys.stdout)]
    log_dir = os.environ.get("LOG_PATH")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(os.path.join(log_dir, "orchestrator.jsonl")))
    for h in handlers:
        h.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=handlers)


async def amain():
    setup_logging()
    log = logging.getLogger("main")

    cfg = load_config()
    store.init_db()
    setup_routing(cfg)                       # provisiona tablas, reglas y NAT (idempotente)
    store.add_event("info", None, "orquestador iniciado; PBR provisionado")

    monitors = {w["id"]: WanMonitor(w, cfg) for w in cfg["wans"]}
    engine = Engine(cfg, monitors)
    predictor = Predictor(cfg, monitors, engine)
    app = build_app(cfg, monitors, engine, predictor)

    server = uvicorn.Server(uvicorn.Config(
        app, host=cfg["api"]["host"], port=cfg["api"]["port"], log_level="warning"))

    tasks = [asyncio.create_task(m.poll_loop()) for m in monitors.values()]
    tasks += [asyncio.create_task(engine.loop()),
              asyncio.create_task(predictor.loop()),
              asyncio.create_task(server.serve())]
    log.info("sistema en marcha: %d WANs, API en :%d", len(monitors), cfg["api"]["port"])
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(amain())
