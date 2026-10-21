"""Three independently deployed services sharing transport and validation code."""
from contextlib import asynccontextmanager, nullcontext
import os
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from services.observability import Metrics, ObservabilityMiddleware, EXCLUDED
from services.tracing import make_tracer, propagator
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel, Field, ValidationError



class Purchase(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, ge=1, le=100)


class Charge(BaseModel):
    order_id: str = Field(min_length=1, max_length=100)
    amount_cents: int = Field(strict=True, gt=0, le=1_000_000)


class Receipt(BaseModel):
    order_id: str
    payment_id: str
    status: str
    amount_cents: int = Field(gt=0)


class Order(BaseModel):
    order_id: str
    item_id: str
    quantity: int = Field(gt=0)
    amount_cents: int = Field(gt=0)
    payment_id: str
    status: str


def create_app(role: str, downstream_url: str | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    if role not in {"gateway", "order", "payment"}:
        raise ValueError("Unknown service role")
    if role != "payment" and not downstream_url:
        raise ValueError("A downstream URL is required")

    provider, tracer = make_tracer(role)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(timeout=3.0 if role == "gateway" else 2.0,
                                     transport=transport, trust_env=False) as client:
            app.state.http = client
            try:
                yield
            finally:
                provider.shutdown()

    app = FastAPI(title=f"SafeHeal {role}", lifespan=lifespan)

    metrics = Metrics()
    app.state.metrics = metrics
    app.add_middleware(ObservabilityMiddleware, role=role, metrics=metrics, tracer=tracer)

    @app.get("/metrics", include_in_schema=False)
    def metric_endpoint():
        return Response(content=generate_latest(metrics.registry),
                        headers={"Content-Type": CONTENT_TYPE_LATEST})

    async def downstream(method, path, request, payload=None):
        span_context = tracer.start_as_current_span(
            f"{method} {path}", kind=SpanKind.CLIENT,
            attributes={"request_id": request.state.request_id, "http.request.method": method},
            record_exception=False, set_status_on_exception=False
        ) if request.url.path not in EXCLUDED else nullcontext(None)
        with span_context as span:
            headers = {"x-request-id": request.state.request_id}
            if span:
                propagator.inject(headers)
            try:
                response = await app.state.http.request(
                    method, downstream_url.rstrip("/") + path, json=payload, headers=headers)
                if span:
                    span.set_attribute("http.response.status_code", response.status_code)
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                if span:
                    span.set_status(Status(StatusCode.ERROR))
                raise HTTPException(504, "Dependency timed out") from exc
            except (httpx.HTTPError, ValueError) as exc:
                if span:
                    span.set_status(Status(StatusCode.ERROR))
                raise HTTPException(503, "Dependency unavailable or invalid response") from exc

    @app.get("/healthz")
    def health():
        # Liveness never depends on another service: avoid restart cascades.
        return {"status": "ok", "service": role}

    @app.get("/readyz")
    async def ready(request: Request):
        if downstream_url:
            evidence = await downstream("GET", "/readyz", request)
            if not isinstance(evidence, dict) or evidence.get("status") != "ready":
                raise HTTPException(503, "Dependency not ready")
        return {"status": "ready", "service": role}

    if role == "payment":
        @app.post("/payments", response_model=Receipt, status_code=201)
        def payment(charge: Charge):
            # Synthetic receipt only: no money movement or external gateway.
            return Receipt(order_id=charge.order_id, payment_id=str(uuid4()),
                           status="simulated_paid", amount_cents=charge.amount_cents)

    elif role == "order":
        @app.post("/orders", response_model=Order, status_code=201)
        async def order(purchase: Purchase, request: Request):
            order_id = str(uuid4())
            amount = purchase.quantity * 1000  # Fixed synthetic catalogue: $10/item.
            data = await downstream("POST", "/payments", request,
                                    {"order_id": order_id, "amount_cents": amount})
            try:
                receipt = Receipt.model_validate(data)
                if (receipt.order_id != order_id or receipt.amount_cents != amount
                        or receipt.status != "simulated_paid"):
                    raise ValueError("Receipt mismatch")
            except (ValidationError, ValueError) as exc:
                raise HTTPException(503, "Invalid payment receipt") from exc
            return Order(order_id=order_id, item_id=purchase.item_id,
                         quantity=purchase.quantity, amount_cents=amount,
                         payment_id=receipt.payment_id, status="confirmed")

    else:
        @app.post("/orders", response_model=Order, status_code=201)
        async def gateway(purchase: Purchase, request: Request):
            data = await downstream("POST", "/orders", request, purchase.model_dump())
            try:
                result = Order.model_validate(data)
                if (result.item_id != purchase.item_id or result.quantity != purchase.quantity
                        or result.amount_cents != purchase.quantity*1000 or result.status != "confirmed"):
                    raise ValueError("Order mismatch")
                return result
            except (ValidationError, ValueError) as exc:
                raise HTTPException(503, "Invalid order response") from exc
    return app


def from_env():
    role = os.environ.get("SERVICE_ROLE", "payment")
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return create_app(role, os.environ.get("DOWNSTREAM_URL"))
