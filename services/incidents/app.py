"""Lab-only polling service with a read-only incident API. Run one Uvicorn worker."""
import asyncio
from contextlib import asynccontextmanager
import logging
import os
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from services.incidents.controller import Controller
from services.incidents.rules import MAX_GAP, RULE_VERSION
from services.incidents.telemetry import Collector

logger = logging.getLogger("safeheal.detector")


def create_app(database=".local/incidents.sqlite3", collector=None, poll=True):
    source = collector if collector is not None else Collector()

    @asynccontextmanager
    async def lifespan(app):
        controller = Controller(database)
        app.state.controller = controller
        app.state.last_poll = None
        app.state.telemetry_ok = False
        app.state.poll_error = None
        stop = asyncio.Event()

        async def run():
            while not stop.is_set():
                try:
                    snapshot = await asyncio.to_thread(source.collect)
                    await asyncio.to_thread(controller.ingest, snapshot)
                    app.state.last_poll = time.time()
                    app.state.telemetry_ok = all(not e.problems for e in snapshot.services.values())
                    app.state.poll_error = None
                except Exception as exc:
                    app.state.poll_error = type(exc).__name__
                    logger.error("detector_poll_failed type=%s", type(exc).__name__)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5.)
                except TimeoutError:
                    pass

        task = asyncio.create_task(run()) if poll else None
        try:
            yield
        finally:
            stop.set()
            if task:
                await task  # Collector has three bounded two-second reads; finish before closing DB.
            controller.close()

    app = FastAPI(title="SafeHeal deterministic incident detector", lifespan=lifespan)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "rule_version": RULE_VERSION}

    @app.get("/readyz")
    def ready():
        last = app.state.last_poll
        healthy = last is not None and time.time() - last <= MAX_GAP and app.state.telemetry_ok and app.state.poll_error is None
        return JSONResponse({"status": "ready" if healthy else "insufficient_telemetry",
                             "last_poll_at": last, "poll_error": app.state.poll_error}, status_code=200 if healthy else 503)

    @app.get("/incidents")
    def incidents(limit: int = Query(default=100, ge=1, le=100), active_only: bool = False):
        return {"items": app.state.controller.list_incidents(limit, active_only), "limit": limit}

    @app.get("/incidents/{incident_id}")
    def detail(incident_id: str):
        item = app.state.controller.detail(incident_id)
        if item is None:
            raise HTTPException(404, "Incident not found")
        return item

    @app.get("/evidence/{evidence_id}")
    def evidence(evidence_id: int):
        item = app.state.controller.evidence(evidence_id)
        if item is None:
            raise HTTPException(404, "Evidence not found")
        return item

    return app


def from_env():
    return create_app(os.getenv("INCIDENT_DB", ".local/incidents.sqlite3"),
                      Collector(os.getenv("PROMETHEUS_URL", "http://127.0.0.1:19090")))
